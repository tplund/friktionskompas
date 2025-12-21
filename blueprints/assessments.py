"""
Assessment Blueprint - CRUD operations for assessments.

Routes:
- /admin/scheduled-assessments - Overview of scheduled assessments
- /admin/assessment/<assessment_id>/cancel - Cancel a scheduled assessment
- /admin/assessment/<assessment_id>/reschedule - Reschedule an assessment
- /admin/assessment/new - Create new assessment (organization or individual)
- /admin/assessment/<assessment_id> - View assessment results
- /admin/assessment/<assessment_id>/delete - Delete an assessment
- /admin/assessment/<assessment_id>/detailed - Detailed analysis with layering
- /admin/assessment/<assessment_id>/pdf - Export assessment to PDF
- /admin/rename-assessments - Rename assessments (dev tool)
- /admin/recreate-assessments - Recreate missing assessments from responses
- /admin/seed-assessments - Seed assessments from JSON
- /admin/assessment-types - Manage assessment types (superadmin)
- /admin/seed-assessment-types - Seed assessment types
- /admin/assessment-type/<type_id>/toggle - Toggle assessment type active status
- /admin/customer/<customer_id>/assessments - View customer assessment config
- /admin/customer/<customer_id>/assessments (POST) - Update customer assessment types
- /admin/customer/<customer_id>/assessments/preset/<preset_id> - Apply preset to customer
- /admin/tasks/<task_id>/new-assessment - Create situation assessment
- /admin/situation-assessments/<assessment_id> - View situation assessment results
"""

from flask import Blueprint, render_template, redirect, url_for, session, request, flash, Response, jsonify
from datetime import datetime
from io import BytesIO

from auth_helpers import login_required, admin_required, superadmin_required, get_current_user
from db_hierarchical import (
    get_db,
    create_assessment,
    create_individual_assessment,
    generate_tokens_for_assessment,
    get_unit_contacts,
    get_assessment_overview,
    get_unit_stats,
    get_unit_path,
    create_situation_assessment,
    generate_situation_tokens,
    get_situation_results,
    get_task,
    get_toplevel_units
)
from db_multitenant import (
    get_customer_filter,
    get_available_assessments,
    get_customer,
    get_all_assessment_types,
    get_all_presets,
    get_customer_assessment_config,
    set_customer_assessment_types,
    seed_assessment_types
)
from analysis import (
    get_detailed_breakdown,
    check_anonymity_threshold,
    calculate_substitution_db,
    get_free_text_comments,
    get_kkc_recommendations,
    get_start_here_recommendation,
    get_alerts_and_findings
)
from mailjet_integration import send_assessment_batch
from scheduler import (
    get_scheduled_assessments,
    cancel_scheduled_assessment,
    reschedule_assessment
)
from translations import get_user_language
from audit import log_action, AuditAction

assessments_bp = Blueprint('assessments', __name__)


def get_individual_scores(target_unit_id, assessment_id):
    """
    Hent individuelle respondent-scores for radar chart visualization

    Returns:
        {
            'employees': [
                {'MENING': 3.5, 'TRYGHED': 4.2, 'KAN': 3.8, 'BESVÆR': 2.1},
                {'MENING': 2.8, 'TRYGHED': 3.1, 'KAN': 4.5, 'BESVÆR': 3.2},
                ...
            ],
            'leader': {'MENING': 4.1, 'TRYGHED': 4.5, 'KAN': 4.3, 'BESVÆR': 1.8}
        }
    """
    with get_db() as conn:
        # Get subtree of units
        subtree_cte = f"""
        WITH RECURSIVE subtree AS (
            SELECT id FROM organizational_units WHERE id = ?
            UNION ALL
            SELECT ou.id FROM organizational_units ou
            JOIN subtree ON ou.parent_id = subtree.id
        )
        """

        # Get all individual employee scores
        # Use respondent_name if available, otherwise use minute-based session grouping
        # (assuming all responses from same respondent come within same minute)
        employee_query = f"""
        {subtree_cte}
        SELECT
            COALESCE(r.respondent_name, strftime('%Y-%m-%d %H:%M', r.created_at)) as resp_key,
            q.field,
            AVG(CASE
                WHEN q.reverse_scored = 1 THEN 6 - r.score
                ELSE r.score
            END) as avg_score
        FROM responses r
        JOIN questions q ON r.question_id = q.id
        JOIN subtree ON r.unit_id = subtree.id
        WHERE r.assessment_id = ?
          AND r.respondent_type = 'employee'
          AND q.field IN ('MENING', 'TRYGHED', 'KAN', 'BESVÆR')
        GROUP BY resp_key, q.field
        """

        employee_rows = conn.execute(employee_query, [target_unit_id, assessment_id]).fetchall()

        # Group by resp_key
        employees = {}
        for row in employee_rows:
            resp_key = row['resp_key']
            if resp_key not in employees:
                employees[resp_key] = {}
            employees[resp_key][row['field']] = row['avg_score']

        # Convert to list of complete respondents (all 4 fields)
        employee_list = []
        for resp_key, scores in employees.items():
            if len(scores) == 4:  # Only include if all 4 fields answered
                employee_list.append(scores)

        # Get leader's self-assessment
        leader_query = f"""
        {subtree_cte}
        SELECT
            q.field,
            AVG(CASE
                WHEN q.reverse_scored = 1 THEN 6 - r.score
                ELSE r.score
            END) as avg_score
        FROM responses r
        JOIN questions q ON r.question_id = q.id
        JOIN subtree ON r.unit_id = subtree.id
        WHERE r.assessment_id = ?
          AND r.respondent_type = 'leader_self'
          AND q.field IN ('MENING', 'TRYGHED', 'KAN', 'BESVÆR')
        GROUP BY q.field
        """

        leader_rows = conn.execute(leader_query, [target_unit_id, assessment_id]).fetchall()

        leader = {}
        for row in leader_rows:
            leader[row['field']] = row['avg_score']

        return {
            'employees': employee_list,
            'leader': leader if len(leader) == 4 else None
        }


@assessments_bp.route('/admin/scheduled-assessments')
@login_required
def scheduled_assessments():
    """Oversigt over planlagte målinger"""
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))

    with get_db() as conn:
        # Hent scheduled assessments
        if user['role'] in ('admin', 'superadmin'):
            assessments = conn.execute("""
                SELECT c.*, ou.name as target_name, ou.full_path
                FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE c.status = 'scheduled'
                ORDER BY c.scheduled_at ASC
            """).fetchall()
        else:
            assessments = conn.execute("""
                SELECT c.*, ou.name as target_name, ou.full_path
                FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE c.status = 'scheduled' AND ou.customer_id = ?
                ORDER BY c.scheduled_at ASC
            """, [user['customer_id']]).fetchall()

    return render_template('admin/scheduled_assessments.html',
                         assessments=[dict(c) for c in assessments])


@assessments_bp.route('/admin/assessment/<assessment_id>/cancel', methods=['POST'])
@login_required
def cancel_assessment(assessment_id):
    """Annuller en planlagt måling"""
    user = get_current_user()

    # Verificer at brugeren har adgang til kampagnen
    with get_db() as conn:
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        assessment = conn.execute(f"""
            SELECT c.* FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ? AND c.status = 'scheduled' AND ({where_clause})
        """, [assessment_id] + params).fetchone()

        if not assessment:
            flash('Måling ikke fundet eller kan ikke annulleres', 'error')
            return redirect(url_for('assessments.scheduled_assessments'))

    # Annuller kampagnen
    success = cancel_scheduled_assessment(assessment_id)
    if success:
        flash('Planlagt måling annulleret', 'success')
    else:
        flash('Kunne ikke annullere målingen', 'error')

    return redirect(url_for('assessments.scheduled_assessments'))


@assessments_bp.route('/admin/assessment/<assessment_id>/reschedule', methods=['POST'])
@login_required
def reschedule_assessment_route(assessment_id):
    """Ændr tidspunkt for en planlagt måling"""
    user = get_current_user()

    # Verificer at brugeren har adgang til kampagnen
    with get_db() as conn:
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        assessment = conn.execute(f"""
            SELECT c.* FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ? AND c.status = 'scheduled' AND ({where_clause})
        """, [assessment_id] + params).fetchone()

        if not assessment:
            flash('Måling ikke fundet eller kan ikke ændres', 'error')
            return redirect(url_for('assessments.scheduled_assessments'))

    # Hent nyt tidspunkt fra form
    new_date = request.form.get('new_date', '').strip()
    new_time = request.form.get('new_time', '08:00').strip()

    if not new_date:
        flash('Vælg en ny dato', 'error')
        return redirect(url_for('assessments.scheduled_assessments'))

    new_scheduled_at = datetime.fromisoformat(f"{new_date}T{new_time}:00")

    success = reschedule_assessment(assessment_id, new_scheduled_at)
    if success:
        flash(f'Måling flyttet til {new_date} kl. {new_time}', 'success')
    else:
        flash('Kunne ikke ændre tidspunkt', 'error')

    return redirect(url_for('assessments.scheduled_assessments'))


@assessments_bp.route('/admin/assessment/new', methods=['GET', 'POST'])
@login_required
def new_assessment():
    """Opret og send ny kampagne (eller planlæg til senere)"""
    user = get_current_user()

    if request.method == 'POST':
        name = request.form['name']
        period = request.form['period']
        sent_from = request.form.get('sent_from', 'admin')
        sender_name = request.form.get('sender_name', 'HR')
        assessment_type_id = request.form.get('assessment_type_id', 'gruppe_friktion')
        target_type = request.form.get('target_type', 'organization')

        # Tjek om det er en scheduled assessment
        scheduled_date = request.form.get('scheduled_date', '').strip()
        scheduled_time = request.form.get('scheduled_time', '').strip()

        scheduled_at = None
        if scheduled_date:
            # Kombiner dato og tid (default til 08:00 hvis ikke angivet)
            if not scheduled_time:
                scheduled_time = '08:00'
            scheduled_at = f"{scheduled_date}T{scheduled_time}:00"

        if target_type == 'individual':
            # ===== INDIVIDUEL MÅLING =====
            target_email = request.form.get('target_email', '').strip()
            target_name = request.form.get('target_name', '').strip()

            if not target_email:
                flash('Email er påkrævet for individuel måling', 'error')
                return redirect(url_for('assessments.new_assessment'))

            # Opret assessment uden target_unit (individuel)
            assessment_id = create_individual_assessment(
                name=name,
                period=period,
                target_email=target_email,
                target_name=target_name,
                sent_from=sent_from,
                sender_name=sender_name,
                assessment_type_id=assessment_type_id,
                scheduled_at=scheduled_at
            )

            if scheduled_at:
                flash(f'Individuel måling planlagt til {scheduled_date} kl. {scheduled_time}', 'success')
                return redirect(url_for('assessments.scheduled_assessments'))
            else:
                flash(f'Individuel måling sendt til {target_email}!', 'success')
                return redirect(url_for('assessments.view_assessment', assessment_id=assessment_id))

        else:
            # ===== ORGANISATIONS MÅLING (original logik) =====
            target_unit_id = request.form.get('target_unit_id')
            if not target_unit_id:
                flash('Vælg en organisation', 'error')
                return redirect(url_for('assessments.new_assessment'))

            # Opret kampagne
            assessment_id = create_assessment(
                target_unit_id=target_unit_id,
                name=name,
                period=period,
                sent_from=sent_from,
                scheduled_at=scheduled_at,
                sender_name=sender_name,
                assessment_type_id=assessment_type_id
            )

            if scheduled_at:
                # Scheduled assessment - send ikke nu
                flash(f'Måling planlagt til {scheduled_date} kl. {scheduled_time}', 'success')
                return redirect(url_for('assessments.scheduled_assessments'))
            else:
                # Send nu
                tokens_by_unit = generate_tokens_for_assessment(assessment_id)

                total_sent = 0
                for unit_id, tokens in tokens_by_unit.items():
                    contacts = get_unit_contacts(unit_id)
                    if not contacts:
                        continue

                    results = send_assessment_batch(contacts, tokens, name, sender_name)
                    total_sent += results['emails_sent'] + results['sms_sent']

                flash(f'Måling sendt! {sum(len(t) for t in tokens_by_unit.values())} tokens genereret, {total_sent} sendt.', 'success')
                return redirect(url_for('assessments.view_assessment', assessment_id=assessment_id))

    # GET: Vis form - kun units fra samme customer
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
    with get_db() as conn:
        # Alle units til dropdown (filtreret efter customer)
        units = conn.execute(f"""
            SELECT ou.id, ou.name, ou.full_path, ou.level, ou.employee_count
            FROM organizational_units ou
            WHERE {where_clause}
            ORDER BY ou.full_path
        """, params).fetchall()

    # Hent tilgængelige målingstyper for denne kunde
    lang = get_user_language()
    assessment_types = get_available_assessments(
        customer_id=user.get('customer_id'),
        lang=lang
    )

    return render_template('admin/new_assessment.html',
                         units=[dict(u) for u in units],
                         assessment_types=assessment_types)


@assessments_bp.route('/admin/assessment/<assessment_id>')
@login_required
def view_assessment(assessment_id):
    """Se kampagne resultater"""
    user = get_current_user()

    with get_db() as conn:
        # Hent assessment med customer filter
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        assessment = conn.execute(f"""
            SELECT c.* FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ? AND ({where_clause})
        """, [assessment_id] + params).fetchone()

        if not assessment:
            flash("Måling ikke fundet eller ingen adgang", 'error')
            return redirect(url_for('admin_core.admin_home'))

    # Target unit info
    target_unit_id = assessment['target_unit_id']
    breadcrumbs = get_unit_path(target_unit_id)

    # Overview af alle leaf units
    overview = get_assessment_overview(assessment_id)

    # Aggregeret stats for target unit (inkl. children)
    aggregate_stats = get_unit_stats(
        unit_id=target_unit_id,
        assessment_id=assessment_id,
        include_children=True
    )

    # Total tokens sendt/brugt
    with get_db() as conn:
        token_stats = conn.execute("""
            SELECT
                COUNT(*) as tokens_sent,
                SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as tokens_used
            FROM tokens
            WHERE assessment_id = ?
        """, (assessment_id,)).fetchone()

    return render_template('admin/view_assessment.html',
        assessment=dict(assessment),
        target_breadcrumbs=breadcrumbs,
        overview=overview,
        aggregate_stats=aggregate_stats,
        token_stats=dict(token_stats))


@assessments_bp.route('/admin/assessment/<assessment_id>/delete', methods=['POST'])
@login_required
def delete_assessment(assessment_id):
    """Slet en kampagne og alle tilhørende data"""
    user = get_current_user()

    with get_db() as conn:
        # Hent assessment med customer filter for at verificere adgang
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        assessment = conn.execute(f"""
            SELECT c.*, ou.name as unit_name FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ? AND ({where_clause})
        """, [assessment_id] + params).fetchone()

        if not assessment:
            flash("Måling ikke fundet eller ingen adgang", 'error')
            return redirect(url_for('admin_core.assessments_overview'))

        assessment_name = assessment['name']

        # Slet kampagnen (CASCADE sletter responses og tokens automatisk)
        conn.execute("DELETE FROM assessments WHERE id = ?", [assessment_id])
        conn.commit()

        # Audit log assessment deletion
        log_action(
            AuditAction.ASSESSMENT_DELETED,
            entity_type="assessment",
            entity_id=assessment_id,
            details=f"Deleted assessment: {assessment_name}"
        )

        flash(f'Målingen "{assessment_name}" blev slettet', 'success')

    return redirect(url_for('admin_core.assessments_overview'))


@assessments_bp.route('/admin/assessment/<assessment_id>/detailed')
@login_required
def assessment_detailed_analysis(assessment_id):
    """Detaljeret analyse med lagdeling og respondent-sammenligning"""
    import traceback
    user = get_current_user()

    try:
        with get_db() as conn:
            # Hent assessment - admin/superadmin ser alt
            if user['role'] in ('admin', 'superadmin'):
                assessment = conn.execute("""
                    SELECT c.*, ou.customer_id FROM assessments c
                    JOIN organizational_units ou ON c.target_unit_id = ou.id
                    WHERE c.id = ?
                """, [assessment_id]).fetchone()
            else:
                assessment = conn.execute("""
                    SELECT c.*, ou.customer_id FROM assessments c
                    JOIN organizational_units ou ON c.target_unit_id = ou.id
                    WHERE c.id = ? AND ou.customer_id = ?
                """, [assessment_id, user['customer_id']]).fetchone()

            if not assessment:
                flash("Måling ikke fundet eller ingen adgang", 'error')
                return redirect(url_for('admin_core.admin_home'))

        target_unit_id = assessment['target_unit_id']
        assessment_customer_id = assessment['customer_id']

        # Check anonymity
        anonymity = check_anonymity_threshold(assessment_id, target_unit_id)

        if not anonymity.get('can_show_results'):
            flash(f"Ikke nok svar endnu. {anonymity.get('response_count', 0)} af {anonymity.get('min_required', 5)} modtaget.", 'warning')
            return redirect(url_for('assessments.view_assessment', assessment_id=assessment_id))

        # Get detailed breakdown
        breakdown = get_detailed_breakdown(target_unit_id, assessment_id, include_children=True)

        # Calculate substitution (tid-bias)
        substitution = calculate_substitution_db(target_unit_id, assessment_id, 'employee')

        # Add has_substitution flag and count for template
        substitution['has_substitution'] = substitution.get('flagged', False) and substitution.get('flagged_count', 0) > 0
        substitution['count'] = substitution.get('flagged_count', 0)

        # Get free text comments
        free_text_comments = get_free_text_comments(target_unit_id, assessment_id, include_children=True)

        # Get KKC recommendations
        employee_stats = breakdown.get('employee', {})
        comparison = breakdown.get('comparison', {})
        kkc_recommendations = get_kkc_recommendations(employee_stats, comparison)
        start_here = get_start_here_recommendation(kkc_recommendations)

        # Get alerts and findings
        alerts = get_alerts_and_findings(breakdown, comparison, substitution)

        # Get individual scores for radar chart
        individual_scores = get_individual_scores(target_unit_id, assessment_id)

        # Breadcrumbs
        breadcrumbs = get_unit_path(target_unit_id)

        # Get last response date
        with get_db() as conn:
            last_response = conn.execute("""
                SELECT MAX(created_at) as last_date
                FROM responses
                WHERE assessment_id = ? AND created_at IS NOT NULL
            """, [assessment_id]).fetchone()

            last_response_date = None
            if last_response and last_response['last_date']:
                dt = datetime.fromisoformat(last_response['last_date'])
                last_response_date = dt.strftime('%d-%m-%Y')

        return render_template('admin/assessment_detailed.html',
            assessment=dict(assessment),
            target_breadcrumbs=breadcrumbs,
            breakdown=breakdown,
            anonymity=anonymity,
            substitution=substitution,
            free_text_comments=free_text_comments,
            kkc_recommendations=kkc_recommendations,
            start_here=start_here,
            alerts=alerts,
            last_response_date=last_response_date,
            current_customer_id=assessment_customer_id,
            individual_scores=individual_scores
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"<h1>Fejl i assessment_detailed_analysis</h1><pre>{error_details}</pre>", 500


@assessments_bp.route('/admin/assessment/<assessment_id>/pdf')
@login_required
def assessment_pdf_export(assessment_id):
    """Eksporter måling til PDF"""
    user = get_current_user()

    try:
        with get_db() as conn:
            # Hent assessment - admin/superadmin ser alt
            if user['role'] in ('admin', 'superadmin'):
                assessment = conn.execute("""
                    SELECT c.*, ou.customer_id FROM assessments c
                    JOIN organizational_units ou ON c.target_unit_id = ou.id
                    WHERE c.id = ?
                """, [assessment_id]).fetchone()
            else:
                assessment = conn.execute("""
                    SELECT c.*, ou.customer_id FROM assessments c
                    JOIN organizational_units ou ON c.target_unit_id = ou.id
                    WHERE c.id = ? AND ou.customer_id = ?
                """, [assessment_id, user['customer_id']]).fetchone()

            if not assessment:
                flash("Måling ikke fundet eller ingen adgang", 'error')
                return redirect(url_for('admin_core.admin_home'))

        target_unit_id = assessment['target_unit_id']

        # Check anonymity
        anonymity = check_anonymity_threshold(assessment_id, target_unit_id)
        if not anonymity.get('can_show_results'):
            flash("Ikke nok svar til at generere PDF", 'warning')
            return redirect(url_for('assessments.view_assessment', assessment_id=assessment_id))

        # Get all data
        breakdown = get_detailed_breakdown(target_unit_id, assessment_id, include_children=True)
        substitution = calculate_substitution_db(target_unit_id, assessment_id, 'employee')
        free_text_comments = get_free_text_comments(target_unit_id, assessment_id, include_children=True)

        employee_stats = breakdown.get('employee', {})
        comparison = breakdown.get('comparison', {})
        kkc_recommendations = get_kkc_recommendations(employee_stats, comparison)
        start_here = get_start_here_recommendation(kkc_recommendations)

        alerts = get_alerts_and_findings(breakdown, comparison, substitution)

        # Token stats
        with get_db() as conn:
            token_stats = conn.execute("""
                SELECT
                    COUNT(*) as tokens_sent,
                    SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as tokens_used
                FROM tokens
                WHERE assessment_id = ?
            """, (assessment_id,)).fetchone()

        # Calculate overall score
        emp = breakdown.get('employee', {})
        if emp:
            fields = ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']
            scores = [emp.get(f, {}).get('avg_score', 3) for f in fields]
            avg_score = sum(scores) / len(scores)
            overall_score = (avg_score - 1) / 4 * 100
        else:
            overall_score = 0

        response_rate = (token_stats['tokens_used'] / token_stats['tokens_sent'] * 100) if token_stats['tokens_sent'] > 0 else 0

        # Render HTML template
        html = render_template('admin/assessment_pdf.html',
            assessment=dict(assessment),
            breakdown=breakdown,
            alerts=alerts,
            start_here=start_here,
            free_text_comments=free_text_comments,
            token_stats=dict(token_stats),
            overall_score=overall_score,
            response_rate=response_rate,
            generated_date=datetime.now().strftime('%d-%m-%Y %H:%M')
        )

        # Generate PDF
        try:
            from xhtml2pdf import pisa

            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)

            if pisa_status.err:
                flash("Fejl ved PDF generering", 'error')
                return redirect(url_for('assessments.view_assessment', assessment_id=assessment_id))

            pdf_buffer.seek(0)

            # Create filename
            safe_name = assessment['name'].replace(' ', '_').replace('/', '-')
            filename = f"Friktionsmaaling_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

            return Response(
                pdf_buffer.getvalue(),
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'}
            )
        except ImportError:
            flash("PDF bibliotek ikke installeret. Kontakt administrator.", 'error')
            return redirect(url_for('assessments.view_assessment', assessment_id=assessment_id))

    except Exception as e:
        import traceback
        print(f"PDF export error: {traceback.format_exc()}")
        flash(f"Fejl ved PDF eksport: {str(e)}", 'error')
        return redirect(url_for('assessments.view_assessment', assessment_id=assessment_id))


@assessments_bp.route('/admin/rename-assessments', methods=['POST'])
@admin_required
def rename_assessments():
    """Omdøb målinger fra 'Unit - Q# YYYY' til 'Q# YYYY - Unit' format"""
    import re

    # Kvartal til dato mapping
    quarter_dates = {
        'Q1': '2025-01-15',
        'Q2': '2025-04-15',
        'Q3': '2025-07-15',
        'Q4': '2025-10-15'
    }

    count = 0
    with get_db() as conn:
        assessments = conn.execute("""
            SELECT id, name, created_at
            FROM assessments
            WHERE name LIKE '% - Q_ 2025'
        """).fetchall()

        for a in assessments:
            match = re.match(r'^(.+) - (Q\d) (\d{4})$', a['name'])
            if match:
                unit_name = match.group(1)
                quarter = match.group(2)
                year = match.group(3)
                new_name = f"{quarter} {year} - {unit_name}"
                new_date = quarter_dates.get(quarter, a['created_at'])

                conn.execute("""
                    UPDATE assessments
                    SET name = ?, created_at = ?
                    WHERE id = ?
                """, (new_name, new_date, a['id']))
                count += 1

    flash(f'Omdøbt {count} målinger til nyt format', 'success')
    return redirect(url_for('dev_tools.dev_tools'))


@assessments_bp.route('/admin/recreate-assessments', methods=['POST'])
def recreate_assessments():
    """Genskab manglende assessments baseret på eksisterende responses"""

    with get_db() as conn:
        # Find alle unikke assessment_id'er fra responses der IKKE findes i assessments
        orphan_assessment_ids = conn.execute("""
            SELECT DISTINCT r.assessment_id
            FROM responses r
            LEFT JOIN assessments a ON r.assessment_id = a.id
            WHERE a.id IS NULL
        """).fetchall()

        if not orphan_assessment_ids:
            flash('Ingen manglende assessments fundet - alle responses har tilknyttede assessments', 'info')
            return redirect(url_for('dev_tools.db_status'))

        created = 0
        errors = []

        for row in orphan_assessment_ids:
            assessment_id = row['assessment_id']

            # Find unit_id fra responses for denne assessment
            unit_info = conn.execute("""
                SELECT DISTINCT r.unit_id, ou.name as unit_name, ou.id as unit_exists
                FROM responses r
                LEFT JOIN organizational_units ou ON r.unit_id = ou.id
                WHERE r.assessment_id = ?
                LIMIT 1
            """, [assessment_id]).fetchone()

            if not unit_info or not unit_info['unit_exists']:
                errors.append(f"Assessment {assessment_id}: Unit ikke fundet")
                continue

            unit_id = unit_info['unit_id']
            unit_name = unit_info['unit_name'] or 'Ukendt'

            # Find dato fra responses
            date_info = conn.execute("""
                SELECT MIN(created_at) as first_response
                FROM responses WHERE assessment_id = ?
            """, [assessment_id]).fetchone()

            created_at = date_info['first_response'] if date_info else datetime.now().isoformat()

            # Tjek om der er leader responses
            leader_count = conn.execute("""
                SELECT COUNT(*) as cnt FROM responses
                WHERE assessment_id = ? AND respondent_type IN ('leader_assess', 'leader_self')
            """, [assessment_id]).fetchone()['cnt']

            include_leader = 1 if leader_count > 0 else 0

            # Opret assessment med genskabt data
            assessment_name = f"Genskabt: {unit_name}"
            try:
                conn.execute("""
                    INSERT INTO assessments (id, target_unit_id, name, period, created_at,
                                           include_leader_assessment, include_leader_self, status)
                    VALUES (?, ?, ?, 'Genskabt', ?, ?, ?, 'sent')
                """, [assessment_id, unit_id, assessment_name, created_at, include_leader, include_leader])
                created += 1
            except Exception as e:
                errors.append(f"Assessment {assessment_id}: {str(e)}")

        conn.commit()

    if created > 0:
        flash(f'Genskabt {created} assessments!', 'success')
    if errors:
        flash(f'Fejl: {len(errors)} assessments kunne ikke genskabes. Se logs.', 'warning')
        for err in errors[:5]:  # Vis max 5 fejl
            flash(err, 'error')

    return redirect(url_for('dev_tools.db_status'))


@assessments_bp.route('/admin/seed-assessments', methods=['POST'])
def seed_assessments():
    """Seed assessments og responses fra JSON filer"""
    import json
    import os

    base_path = os.path.dirname(os.path.dirname(__file__))
    assessments_path = os.path.join(base_path, 'seed_assessments.json')
    responses_path = os.path.join(base_path, 'seed_responses.json')

    if not os.path.exists(assessments_path):
        flash('seed_assessments.json ikke fundet!', 'error')
        return redirect(url_for('dev_tools.db_status'))

    with open(assessments_path, 'r', encoding='utf-8') as f:
        assessments = json.load(f)

    inserted_assessments = 0
    skipped_assessments = 0
    errors = []

    with get_db() as conn:
        # Seed assessments
        for a in assessments:
            existing = conn.execute("SELECT id FROM assessments WHERE id = ?", [a['id']]).fetchone()
            if existing:
                skipped_assessments += 1
                continue

            unit_exists = conn.execute("SELECT id FROM organizational_units WHERE id = ?",
                                       [a['target_unit_id']]).fetchone()
            if not unit_exists:
                errors.append(f"{a['id']}: Unit {a['target_unit_id']} findes ikke")
                continue

            try:
                conn.execute("""
                    INSERT INTO assessments (id, target_unit_id, name, period, sent_from, sent_at,
                                           created_at, mode, include_leader_assessment, include_leader_self,
                                           min_responses, scheduled_at, status, sender_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [a['id'], a['target_unit_id'], a['name'], a['period'], a.get('sent_from', 'admin'),
                      a.get('sent_at'), a.get('created_at'), a.get('mode', 'anonymous'),
                      a.get('include_leader_assessment', 0), a.get('include_leader_self', 0),
                      a.get('min_responses', 5), a.get('scheduled_at'), a.get('status', 'sent'),
                      a.get('sender_name', 'HR')])
                inserted_assessments += 1
            except Exception as e:
                errors.append(f"{a['id']}: {str(e)}")

        conn.commit()

        # Seed responses hvis filen findes
        inserted_responses = 0
        skipped_responses = 0
        if os.path.exists(responses_path):
            with open(responses_path, 'r', encoding='utf-8') as f:
                responses = json.load(f)

            # Hent eksisterende response IDs for hurtig lookup
            existing_ids = set(r[0] for r in conn.execute("SELECT id FROM responses").fetchall())

            for r in responses:
                if r.get('id') in existing_ids:
                    skipped_responses += 1
                    continue

                # Tjek at assessment eksisterer
                assessment_exists = conn.execute("SELECT id FROM assessments WHERE id = ?",
                                                 [r['assessment_id']]).fetchone()
                if not assessment_exists:
                    continue

                try:
                    conn.execute("""
                        INSERT INTO responses (id, assessment_id, unit_id, question_id, score,
                                             respondent_type, created_at, free_text)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, [r.get('id'), r['assessment_id'], r['unit_id'], r['question_id'],
                          r['score'], r.get('respondent_type', 'employee'),
                          r.get('created_at'), r.get('free_text')])
                    inserted_responses += 1
                except Exception as e:
                    errors.append(f"Response {r.get('id')}: {str(e)}")

            conn.commit()

            flash(f'Seedet {inserted_assessments} assessments og {inserted_responses} responses!', 'success')
            if skipped_assessments > 0 or skipped_responses > 0:
                flash(f'Skippet {skipped_assessments} assessments og {skipped_responses} responses (findes allerede)', 'info')
        else:
            flash(f'Seedet {inserted_assessments} assessments! (Responses fil ikke fundet)', 'success')

    if errors:
        flash(f'{len(errors)} fejl under seeding. Se logs.', 'warning')

    return redirect(url_for('dev_tools.db_status'))


@assessments_bp.route('/admin/assessment-types')
@superadmin_required
def assessment_types():
    """Administrer målingstyper - kun superadmin"""
    types = get_all_assessment_types(get_user_language())
    presets = get_all_presets()

    # Hent spørgsmål for hver type
    questions_by_type = {}
    with get_db() as conn:
        # Mapping fra assessment_type_id til profil_questions question_type
        type_mapping = {
            'screening': 'screening',
            'kapacitet': 'capacity',
            'baandbredde': 'bandwidth',
            'profil_fuld': None,  # Alle profil spørgsmål
            'profil_situation': None,
        }

        # Hent profil-spørgsmål for individuelle typer
        for at_id, q_type in type_mapping.items():
            if q_type:
                questions = conn.execute("""
                    SELECT id, field, layer, text_da, question_type, sequence
                    FROM profil_questions
                    WHERE question_type = ?
                    ORDER BY sequence
                """, (q_type,)).fetchall()
            elif at_id in ('profil_fuld', 'profil_situation'):
                questions = conn.execute("""
                    SELECT id, field, layer, text_da, question_type, sequence
                    FROM profil_questions
                    WHERE question_type IN ('sensitivity', 'capacity', 'bandwidth')
                    ORDER BY sequence
                """).fetchall()
            else:
                questions = []

            questions_by_type[at_id] = [dict(q) for q in questions]

        # Hent gruppe-spørgsmål (for gruppe_friktion og gruppe_leder)
        gruppe_questions = conn.execute("""
            SELECT id, field, text_da, reverse_scored, sequence
            FROM questions
            WHERE is_default = 1
            ORDER BY field, sequence
        """).fetchall()
        questions_by_type['gruppe_friktion'] = [dict(q) for q in gruppe_questions]
        questions_by_type['gruppe_leder'] = [dict(q) for q in gruppe_questions]

    return render_template('admin/assessment_types.html',
                         assessment_types=types,
                         presets=presets,
                         questions_by_type=questions_by_type)


@assessments_bp.route('/admin/seed-assessment-types', methods=['GET', 'POST'])
def seed_assessment_types_route():
    """Seed/re-seed assessment types - no auth for initial setup"""
    seed_assessment_types()
    if request.method == 'GET':
        return jsonify({'status': 'ok', 'message': 'Assessment types og presets seedet!'})
    flash('Målingstyper og presets seedet!', 'success')
    return redirect(url_for('assessments.assessment_types'))


@assessments_bp.route('/admin/assessment-type/<type_id>/toggle', methods=['POST'])
@superadmin_required
def toggle_assessment_type(type_id):
    """Aktiver/deaktiver en målingstype"""
    with get_db() as conn:
        # Hent nuværende status
        current = conn.execute(
            "SELECT is_active FROM assessment_types WHERE id = ?", (type_id,)
        ).fetchone()

        if current:
            new_status = 0 if current['is_active'] else 1
            conn.execute(
                "UPDATE assessment_types SET is_active = ? WHERE id = ?",
                (new_status, type_id)
            )
            status_text = 'aktiveret' if new_status else 'deaktiveret'
            flash(f'Målingstype {status_text}!', 'success')

    return redirect(url_for('assessments.assessment_types'))


@assessments_bp.route('/admin/customer/<customer_id>/assessments')
@admin_required
def customer_assessments(customer_id):
    """Konfigurer målingstyper for en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('customers.manage_customers'))

    config = get_customer_assessment_config(customer_id)
    presets = get_all_presets()

    return render_template('admin/customer_assessments.html',
                         customer=customer,
                         config=config,
                         presets=presets)


@assessments_bp.route('/admin/customer/<customer_id>/assessments', methods=['POST'])
@admin_required
def update_customer_assessments(customer_id):
    """Opdater målingstyper for en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('customers.manage_customers'))

    # Hent valgte typer fra form
    enabled_types = request.form.getlist('assessment_types')

    if enabled_types:
        set_customer_assessment_types(customer_id, enabled_types)
        flash('Målingstyper opdateret for kunde!', 'success')
    else:
        # Hvis ingen valgt, slet custom config (brug default preset)
        with get_db() as conn:
            conn.execute(
                "DELETE FROM customer_assessment_types WHERE customer_id = ?",
                (customer_id,)
            )
        flash('Kunde bruger nu standard preset!', 'success')

    return redirect(url_for('assessments.customer_assessments', customer_id=customer_id))


@assessments_bp.route('/admin/customer/<customer_id>/assessments/preset/<int:preset_id>', methods=['POST'])
@admin_required
def apply_preset_to_customer(customer_id, preset_id):
    """Anvend et preset til en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('customers.manage_customers'))

    with get_db() as conn:
        # Hent typer fra preset
        preset_types = conn.execute('''
            SELECT assessment_type_id FROM preset_assessment_types
            WHERE preset_id = ?
        ''', (preset_id,)).fetchall()

        type_ids = [t['assessment_type_id'] for t in preset_types]

    if type_ids:
        set_customer_assessment_types(customer_id, type_ids)
        flash('Preset anvendt på kunde!', 'success')

    return redirect(url_for('assessments.customer_assessments', customer_id=customer_id))


# ========================================
# SITUATIONSMÅLING ROUTES
# ========================================

@assessments_bp.route('/admin/tasks/<task_id>/new-assessment', methods=['GET', 'POST'])
@admin_required
def admin_situation_assessment_new(task_id):
    """Opret ny situationsmåling for en opgave"""
    task = get_task(task_id)
    if not task:
        flash('Opgave ikke fundet', 'error')
        return redirect(url_for('admin_tasks'))

    if len(task['actions']) < 2:
        flash('Tilføj mindst 2 handlinger før du kan starte en måling', 'error')
        return redirect(url_for('admin_task_detail', task_id=task_id))

    if request.method == 'POST':
        name = request.form.get('name', '').strip() or f"Måling af {task['name']}"
        period = request.form.get('period', '').strip()
        unit_id = request.form.get('unit_id') or task.get('unit_id')
        sent_from = request.form.get('sent_from', '').strip()
        sender_name = request.form.get('sender_name', '').strip()

        if not unit_id:
            flash('Vælg en organisation at sende til', 'error')
            return redirect(url_for('assessments.admin_situation_assessment_new', task_id=task_id))

        # Opret assessment
        assessment_id = create_situation_assessment(
            task_id=task_id,
            name=name,
            period=period,
            unit_id=unit_id,
            sent_from=sent_from,
            sender_name=sender_name
        )

        # Hent kontakter fra unit
        contacts = get_unit_contacts(unit_id)
        if not contacts:
            flash('Ingen kontakter fundet i den valgte organisation. Tilføj kontakter først.', 'error')
            return redirect(url_for('assessments.admin_situation_assessment_new', task_id=task_id))

        # Generer tokens
        recipients = [{'email': c['email'], 'name': c.get('name')} for c in contacts if c.get('email')]
        tokens = generate_situation_tokens(assessment_id, recipients)

        # Send emails hvis ønsket
        send_emails = request.form.get('send_emails') == 'on'
        if send_emails and tokens:
            from mailjet_integration import send_situation_assessment_batch
            try:
                result = send_situation_assessment_batch(
                    recipients=recipients,
                    tokens=tokens,
                    task_name=task['name'],
                    sender_name=sender_name or 'Friktionskompasset',
                    sent_from=sent_from
                )
                flash(f'Måling oprettet og {result.get("emails_sent", 0)} invitationer sendt!', 'success')
            except Exception as e:
                flash(f'Måling oprettet, men der opstod en fejl ved afsendelse: {str(e)}', 'warning')
        else:
            flash(f'Måling oprettet med {len(tokens)} tokens. Emails ikke sendt.', 'success')

        return redirect(url_for('assessments.admin_situation_assessment_view', assessment_id=assessment_id))

    # GET - vis formular
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
    customer_id = params[0] if params else None
    units = get_toplevel_units(customer_id)

    return render_template('admin/situation_assessment_new.html',
                           task=task,
                           units=units,
                           active_page='tasks')


@assessments_bp.route('/admin/situation-assessments/<assessment_id>')
@admin_required
def admin_situation_assessment_view(assessment_id):
    """Vis resultater for situationsmåling"""
    results = get_situation_results(assessment_id)
    if not results:
        flash('Måling ikke fundet', 'error')
        return redirect(url_for('admin_tasks'))

    return render_template('admin/situation_assessment.html',
                           results=results,
                           active_page='tasks')

"""
Admin Core Blueprint - Dashboard and main overview pages.

Routes:
- /admin - Main dashboard (admin_home) with KPIs, trend, and unit scores
- /admin/units - Organizational tree view
- /admin/noegletal - KPI dashboard
- /admin/trend - Trend analysis over time
- /admin/assessments-overview - Overview of all assessments
- /admin/analyser - Analysis overview with drill-down
- /admin/dashboard - Hierarchical organization dashboard (org_dashboard)
- /admin/dashboard/<customer_id> - Customer-level dashboard
- /admin/dashboard/<customer_id>/<unit_id> - Unit drill-down dashboard
- /admin/audit-log - Audit log viewer
- /admin/gdpr - GDPR dashboard
- /admin/gdpr/delete-customer/<customer_id> - Delete customer data (GDPR)
"""

from flask import Blueprint, render_template, redirect, url_for, session, request, flash

from auth_helpers import login_required, admin_required, get_current_user
from db_hierarchical import get_db
from db_multitenant import get_customer_filter
from analysis import get_trend_data
from audit import log_action, AuditAction, get_audit_logs, get_audit_log_count, get_action_summary

admin_core_bp = Blueprint('admin_core', __name__)


# ========================================
# GDPR SUB-PROCESSORS CONSTANT
# ========================================

SUB_PROCESSORS = [
    {
        'name': 'Render',
        'purpose': 'Hosting og serverdrift',
        'data_types': 'Alle applikationsdata',
        'location': 'EU (Frankfurt)',
        'url': 'https://render.com/privacy'
    },
    {
        'name': 'Mailjet',
        'purpose': 'Email-udsendelse',
        'data_types': 'Email-adresser, navne',
        'location': 'EU',
        'url': 'https://www.mailjet.com/gdpr/'
    },
    {
        'name': 'Cloudflare',
        'purpose': 'DNS, CDN, DDoS-beskyttelse',
        'data_types': 'IP-adresser, HTTP headers',
        'location': 'Global (EU-compliant)',
        'url': 'https://www.cloudflare.com/gdpr/introduction/'
    },
    {
        'name': 'GitHub',
        'purpose': 'Kildekode hosting',
        'data_types': 'Ingen persondata (kun kode)',
        'location': 'USA (EU-US DPF)',
        'url': 'https://docs.github.com/en/site-policy/privacy-policies'
    }
]


@admin_core_bp.route('/admin')
@login_required
def admin_home():
    """Dashboard v2 - kombineret oversigt med KPIs, trend, og analyser"""
    user = get_current_user()

    # User rolle skal bruge user_home, ikke admin
    if user.get('role') == 'user':
        return redirect(url_for('user_home'))

    customer_filter = session.get('customer_filter') or user.get('customer_id')
    unit_id = request.args.get('unit_id')  # For trend filter

    with get_db() as conn:
        # Base filter for queries
        if customer_filter:
            customer_where = "WHERE ou.customer_id = ?"
            customer_params = [customer_filter]
            cid = customer_filter
        elif user['role'] not in ('admin', 'superadmin'):
            customer_where = "WHERE ou.customer_id = ?"
            customer_params = [user['customer_id']]
            cid = user['customer_id']
        else:
            customer_where = ""
            customer_params = []
            cid = None

        # === KPI Stats ===
        if cid:
            total_customers = 1
            total_units = conn.execute(
                "SELECT COUNT(*) as cnt FROM organizational_units WHERE customer_id = ?",
                [cid]
            ).fetchone()['cnt']
            total_assessments = conn.execute("""
                SELECT COUNT(*) as cnt FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [cid]).fetchone()['cnt']
            total_responses = conn.execute("""
                SELECT COUNT(*) as cnt FROM responses r
                JOIN assessments c ON r.assessment_id = c.id
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [cid]).fetchone()['cnt']
        else:
            total_customers = conn.execute("SELECT COUNT(*) as cnt FROM customers").fetchone()['cnt']
            total_units = conn.execute("SELECT COUNT(*) as cnt FROM organizational_units").fetchone()['cnt']
            total_assessments = conn.execute("SELECT COUNT(*) as cnt FROM assessments").fetchone()['cnt']
            total_responses = conn.execute("SELECT COUNT(*) as cnt FROM responses").fetchone()['cnt']

        # === Field Scores (aggregeret) ===
        field_scores_query = """
            SELECT
                q.field,
                AVG(CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END) as avg_score,
                COUNT(*) as response_count
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            JOIN assessments c ON r.assessment_id = c.id
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            {where}
            GROUP BY q.field
            ORDER BY avg_score ASC
        """.format(where=customer_where)
        field_scores = conn.execute(field_scores_query, customer_params).fetchall()

        # === Seneste målinger ===
        recent_assessments_query = """
            SELECT
                c.id,
                c.name,
                c.period,
                c.created_at,
                ou.name as unit_name,
                COUNT(DISTINCT r.id) as response_count
            FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            LEFT JOIN responses r ON r.assessment_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT 5
        """.format(where=customer_where)
        recent_assessments = conn.execute(recent_assessments_query, customer_params).fetchall()

        # === Units for dropdown ===
        if cid:
            units = conn.execute("""
                SELECT id, name, full_path, level
                FROM organizational_units
                WHERE customer_id = ?
                ORDER BY full_path
            """, [cid]).fetchall()
        else:
            units = conn.execute("""
                SELECT id, name, full_path, level
                FROM organizational_units
                ORDER BY full_path
            """).fetchall()

        # === Unit scores - hierarkisk med aggregerede scores ===
        # Hent alle units med deres aggregerede scores (inkl. børn)
        unit_scores_query = """
            SELECT
                ou.id,
                ou.name,
                ou.full_path,
                ou.level,
                ou.parent_id,

                -- Tæl antal målinger for denne enhed OG børn
                (SELECT COUNT(*) FROM assessments a
                 JOIN organizational_units ou2 ON a.target_unit_id = ou2.id
                 WHERE ou2.full_path LIKE ou.full_path || '%') as assessment_count,

                -- Total responses for denne enhed OG børn
                COUNT(DISTINCT r.id) as total_responses,

                AVG(CASE
                    WHEN q.field = 'MENING' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END
                END) as employee_mening,

                AVG(CASE
                    WHEN q.field = 'TRYGHED' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END
                END) as employee_tryghed,

                AVG(CASE
                    WHEN q.field = 'KAN' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END
                END) as employee_kan,

                AVG(CASE
                    WHEN q.field = 'BESVÆR' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END
                END) as employee_besvaer

            FROM organizational_units ou
            -- Join med alle børne-units for at aggregere
            LEFT JOIN organizational_units children ON children.full_path LIKE ou.full_path || '%'
            LEFT JOIN assessments c ON c.target_unit_id = children.id
            LEFT JOIN responses r ON c.id = r.assessment_id AND r.respondent_type = 'employee'
            LEFT JOIN questions q ON r.question_id = q.id
            {where}
            GROUP BY ou.id
            HAVING total_responses > 0
            ORDER BY ou.full_path
        """.format(where=customer_where)
        unit_scores_raw = conn.execute(unit_scores_query, customer_params).fetchall()

        # Enrich and build hierarchy
        unit_scores = []
        unit_by_id = {}
        for unit in unit_scores_raw:
            unit_dict = dict(unit)
            unit_dict['children'] = []
            unit_dict['has_children'] = False
            unit_by_id[unit['id']] = unit_dict
            unit_scores.append(unit_dict)

        # Mark units that have children with data
        for unit in unit_scores:
            if unit['parent_id'] and unit['parent_id'] in unit_by_id:
                unit_by_id[unit['parent_id']]['has_children'] = True

        # === Alerts ===
        alerts = []
        for unit in unit_scores:
            # Only show alerts for leaf units (not aggregated)
            if unit.get('has_children'):
                continue
            # Low scores
            for field, label in [('employee_tryghed', 'TRYGHED'), ('employee_besvaer', 'BESVÆR'),
                                 ('employee_mening', 'MENING'), ('employee_kan', 'KAN')]:
                if unit.get(field) and unit[field] < 2.5:
                    alerts.append({
                        'icon': '⚠️',
                        'text': f"{unit['name']}: {label} kritisk lav ({unit[field]:.2f})",
                        'unit_id': unit['id']
                    })

    # Get trend data
    if cid:
        trend_data = get_trend_data(unit_id=unit_id, customer_id=cid)
    else:
        trend_data = get_trend_data(unit_id=unit_id)

    return render_template('admin/dashboard_v2.html',
                         # KPIs
                         total_customers=total_customers,
                         total_units=total_units,
                         total_assessments=total_assessments,
                         total_responses=total_responses,
                         show_customer_stats=(user['role'] in ('admin', 'superadmin') and not customer_filter),
                         # Field scores
                         field_scores=[dict(f) for f in field_scores],
                         # Recent
                         recent_assessments=[dict(c) for c in recent_assessments],
                         # Trend
                         trend_data=trend_data,
                         units=[dict(u) for u in units],
                         selected_unit=unit_id,
                         # Unit drill-down
                         unit_scores=unit_scores,
                         # Alerts
                         alerts=alerts[:10])


@admin_core_bp.route('/admin/units')
@login_required
def admin_units():
    """Organisationstræ - vis og rediger organisationsstrukturen"""
    user = get_current_user()

    # Check for customer filter (admin filtering by customer)
    customer_filter = session.get('customer_filter') or user.get('customer_id')

    with get_db() as conn:
        # Hent units baseret på customer filter
        if customer_filter:
            # Filter på specific customer
            all_units = conn.execute("""
                SELECT
                    ou.*,
                    COUNT(DISTINCT children.id) as child_count,
                    COUNT(DISTINCT leaf.id) as leaf_count,
                    COALESCE(SUM(leaf.employee_count), ou.employee_count) as total_employees
                FROM organizational_units ou
                LEFT JOIN organizational_units children ON children.parent_id = ou.id
                LEFT JOIN (
                    SELECT ou2.id, ou2.full_path, ou2.employee_count FROM organizational_units ou2
                    LEFT JOIN organizational_units c ON ou2.id = c.parent_id
                    WHERE c.id IS NULL
                ) leaf ON leaf.full_path LIKE ou.full_path || '%'
                WHERE ou.customer_id = ?
                GROUP BY ou.id
                ORDER BY ou.full_path
            """, [customer_filter]).fetchall()

            assessment_count = conn.execute("""
                SELECT COUNT(DISTINCT c.id) as cnt
                FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [customer_filter]).fetchone()['cnt']
        else:
            # Admin ser alt (ingen filter)
            all_units = conn.execute("""
                SELECT
                    ou.*,
                    COUNT(DISTINCT children.id) as child_count,
                    COUNT(DISTINCT leaf.id) as leaf_count,
                    COALESCE(SUM(leaf.employee_count), ou.employee_count) as total_employees
                FROM organizational_units ou
                LEFT JOIN organizational_units children ON children.parent_id = ou.id
                LEFT JOIN (
                    SELECT ou2.id, ou2.full_path, ou2.employee_count FROM organizational_units ou2
                    LEFT JOIN organizational_units c ON ou2.id = c.parent_id
                    WHERE c.id IS NULL
                ) leaf ON leaf.full_path LIKE ou.full_path || '%'
                GROUP BY ou.id
                ORDER BY ou.full_path
            """).fetchall()

            assessment_count = conn.execute("SELECT COUNT(*) as cnt FROM assessments").fetchone()['cnt']

        # Hent customer info - altid
        customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
        customers_dict = {c['id']: c['name'] for c in customers}

    return render_template('admin/home.html',
                         units=[dict(u) for u in all_units],
                         assessment_count=assessment_count,
                         show_all_customers=(user['role'] in ('admin', 'superadmin')),
                         customers_dict=customers_dict,
                         current_filter=session.get('customer_filter'),
                         current_filter_name=session.get('customer_filter_name'))


@admin_core_bp.route('/admin/noegletal')
@login_required
def admin_noegletal():
    """Dashboard med nøgletal - samlet overblik over systemet"""
    user = get_current_user()
    customer_filter = session.get('customer_filter') or user.get('customer_id')

    with get_db() as conn:
        # Base filter for queries
        if customer_filter:
            customer_where = "WHERE ou.customer_id = ?"
            customer_params = [customer_filter]
        elif user['role'] not in ('admin', 'superadmin'):
            customer_where = "WHERE ou.customer_id = ?"
            customer_params = [user['customer_id']]
        else:
            customer_where = ""
            customer_params = []

        # Totale stats
        if customer_filter or user['role'] not in ('admin', 'superadmin'):
            cid = customer_filter or user['customer_id']
            total_customers = 1
            total_units = conn.execute(
                "SELECT COUNT(*) as cnt FROM organizational_units WHERE customer_id = ?",
                [cid]
            ).fetchone()['cnt']
            total_assessments = conn.execute("""
                SELECT COUNT(*) as cnt FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [cid]).fetchone()['cnt']
            total_responses = conn.execute("""
                SELECT COUNT(*) as cnt FROM responses r
                JOIN assessments c ON r.assessment_id = c.id
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [cid]).fetchone()['cnt']
        else:
            total_customers = conn.execute("SELECT COUNT(*) as cnt FROM customers").fetchone()['cnt']
            total_units = conn.execute("SELECT COUNT(*) as cnt FROM organizational_units").fetchone()['cnt']
            total_assessments = conn.execute("SELECT COUNT(*) as cnt FROM assessments").fetchone()['cnt']
            total_responses = conn.execute("SELECT COUNT(*) as cnt FROM responses").fetchone()['cnt']

        # Gennemsnitlige scores per felt
        field_scores_query = """
            SELECT
                q.field,
                AVG(CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END) as avg_score,
                COUNT(*) as response_count
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            JOIN assessments c ON r.assessment_id = c.id
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            {where}
            GROUP BY q.field
            ORDER BY avg_score ASC
        """.format(where=customer_where)
        field_scores = conn.execute(field_scores_query, customer_params).fetchall()

        # Seneste kampagner
        recent_assessments_query = """
            SELECT
                c.id,
                c.name,
                c.period,
                c.created_at,
                ou.name as unit_name,
                cust.name as customer_name,
                COUNT(DISTINCT r.id) as response_count,
                (SELECT COUNT(*) FROM tokens t WHERE t.assessment_id = c.id) as token_count
            FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            JOIN customers cust ON ou.customer_id = cust.id
            LEFT JOIN responses r ON r.assessment_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT 5
        """.format(where=customer_where)
        recent_assessments = conn.execute(recent_assessments_query, customer_params).fetchall()

        # Per-kunde stats (kun for admin/superadmin uden filter)
        customer_stats = []
        if user['role'] in ('admin', 'superadmin') and not customer_filter:
            customer_stats = conn.execute("""
                SELECT
                    cust.id,
                    cust.name,
                    COUNT(DISTINCT ou.id) as unit_count,
                    COUNT(DISTINCT c.id) as assessment_count,
                    COUNT(DISTINCT r.id) as response_count
                FROM customers cust
                LEFT JOIN organizational_units ou ON ou.customer_id = cust.id
                LEFT JOIN assessments c ON c.target_unit_id = ou.id
                LEFT JOIN responses r ON r.assessment_id = c.id
                GROUP BY cust.id
                ORDER BY response_count DESC
            """).fetchall()

        # Svarprocent beregning
        response_rate_data = conn.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN t.is_used = 1 THEN t.token END) as used_tokens,
                COUNT(DISTINCT t.token) as total_tokens
            FROM tokens t
            JOIN assessments c ON t.assessment_id = c.id
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            {where}
        """.format(where=customer_where), customer_params).fetchone()

        if response_rate_data['total_tokens'] > 0:
            avg_response_rate = (response_rate_data['used_tokens'] / response_rate_data['total_tokens']) * 100
        else:
            avg_response_rate = 0

    return render_template('admin/noegletal.html',
                         total_customers=total_customers,
                         total_units=total_units,
                         total_assessments=total_assessments,
                         total_responses=total_responses,
                         avg_response_rate=avg_response_rate,
                         field_scores=[dict(f) for f in field_scores],
                         recent_assessments=[dict(c) for c in recent_assessments],
                         customer_stats=[dict(c) for c in customer_stats],
                         show_customer_stats=(user['role'] in ('admin', 'superadmin') and not customer_filter))


@admin_core_bp.route('/admin/trend')
@login_required
def admin_trend():
    """Trend analyse - sammenlign friktionsscores over tid"""
    user = get_current_user()
    customer_filter = session.get('customer_filter') or user.get('customer_id')

    # Get unit_id from query param (optional)
    unit_id = request.args.get('unit_id')

    # Get trend data
    if customer_filter or user['role'] not in ('admin', 'superadmin'):
        cid = customer_filter or user['customer_id']
        trend_data = get_trend_data(unit_id=unit_id, customer_id=cid)
    else:
        trend_data = get_trend_data(unit_id=unit_id)

    # Get available units for filter dropdown
    with get_db() as conn:
        if customer_filter or user['role'] not in ('admin', 'superadmin'):
            cid = customer_filter or user['customer_id']
            units = conn.execute("""
                SELECT id, name, full_path, level
                FROM organizational_units
                WHERE customer_id = ?
                ORDER BY full_path
            """, [cid]).fetchall()
        else:
            units = conn.execute("""
                SELECT id, name, full_path, level
                FROM organizational_units
                ORDER BY full_path
            """).fetchall()

    return render_template('admin/trend.html',
                         trend_data=trend_data,
                         units=[dict(u) for u in units],
                         selected_unit=unit_id)


@admin_core_bp.route('/admin/assessments-overview')
@login_required
def assessments_overview():
    """Oversigt over alle analyser/kampagner"""
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))

    with get_db() as conn:
        # Hent alle assessments med stats
        if user['role'] in ('admin', 'superadmin'):
            assessments = conn.execute("""
                SELECT
                    c.*,
                    ou.name as target_name,
                    COALESCE(COUNT(DISTINCT t.token), 0) as tokens_sent,
                    COALESCE(COUNT(DISTINCT CASE WHEN t.is_used = 1 THEN t.token END), 0) as tokens_used,
                    COUNT(DISTINCT r.respondent_name) as unique_respondents,
                    COUNT(DISTINCT r.id) as total_responses,
                    AVG(CASE
                        WHEN q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END
                    END) as avg_besvaer
                FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                LEFT JOIN tokens t ON c.id = t.assessment_id
                LEFT JOIN responses r ON c.id = r.assessment_id
                LEFT JOIN questions q ON r.question_id = q.id
                GROUP BY c.id
                ORDER BY c.created_at DESC
            """).fetchall()
        else:
            # Manager ser kun kampagner for sine units
            assessments = conn.execute("""
                SELECT
                    c.*,
                    ou.name as target_name,
                    COALESCE(COUNT(DISTINCT t.token), 0) as tokens_sent,
                    COALESCE(COUNT(DISTINCT CASE WHEN t.is_used = 1 THEN t.token END), 0) as tokens_used,
                    COUNT(DISTINCT r.respondent_name) as unique_respondents,
                    COUNT(DISTINCT r.id) as total_responses,
                    AVG(CASE
                        WHEN q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END
                    END) as avg_besvaer
                FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                LEFT JOIN tokens t ON c.id = t.assessment_id
                LEFT JOIN responses r ON c.id = r.assessment_id
                LEFT JOIN questions q ON r.question_id = q.id
                WHERE ou.customer_id = ?
                GROUP BY c.id
                ORDER BY c.created_at DESC
            """, [user['customer_id']]).fetchall()

    return render_template('admin/assessments_overview.html',
                         assessments=[dict(c) for c in assessments])


@admin_core_bp.route('/admin/analyser')
@login_required
def analyser():
    """Analyser: Aggregeret friktionsdata på tværs af organisationen.

    Modes:
    1. Default (no unit_id): Show units with aggregated scores across ALL assessments
    2. With unit_id: Show individual assessments for that unit
    """
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))

    # Get filter parameters
    unit_id = request.args.get('unit_id')  # Filter by unit (and children)
    # Default sort: by date DESC when viewing assessments (unit_id set), by name ASC otherwise
    default_sort = 'date' if unit_id else 'name'
    default_order = 'desc' if unit_id else 'asc'
    sort_by = request.args.get('sort', default_sort)
    sort_order = request.args.get('order', default_order)

    with get_db() as conn:
        enriched_units = []
        selected_unit_name = None
        show_assessments = False  # Whether we're showing individual assessments
        trend_data = None  # Trend data for units with multiple assessments

        if unit_id:
            # Get unit info
            unit_row = conn.execute("SELECT id, name, parent_id FROM organizational_units WHERE id = ?", [unit_id]).fetchone()
            if unit_row:
                selected_unit_name = unit_row['name']

            # Check if this unit has direct assessments
            has_direct_assessments = conn.execute("""
                SELECT COUNT(*) FROM assessments WHERE target_unit_id = ?
            """, [unit_id]).fetchone()[0] > 0

            if has_direct_assessments:
                # MODE 2a: Show individual assessments for this unit (leaf node)
                show_assessments = True

                # Get trend data if there are multiple group assessments
                trend_data = None
                assessment_count = conn.execute("""
                    SELECT COUNT(*) FROM assessments
                    WHERE target_unit_id = ? AND assessment_type_id = 'gruppe_friktion'
                """, [unit_id]).fetchone()[0]

                if assessment_count >= 2:
                    # Calculate trend from oldest to newest assessment (only gruppe_friktion)
                    trend_query = """
                        SELECT
                            a.id,
                            a.name,
                            a.period,
                            a.created_at,
                            AVG(CASE WHEN r.respondent_type = 'employee' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as overall,
                            AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as mening,
                            AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as tryghed,
                            AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as kan,
                            AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as besvaer
                        FROM assessments a
                        JOIN responses r ON a.id = r.assessment_id
                        JOIN questions q ON r.question_id = q.id
                        WHERE a.target_unit_id = ? AND a.assessment_type_id = 'gruppe_friktion'
                        GROUP BY a.id
                        ORDER BY a.created_at ASC
                    """
                    trend_rows = conn.execute(trend_query, [unit_id]).fetchall()

                    if len(trend_rows) >= 2:
                        first = dict(trend_rows[0])
                        last = dict(trend_rows[-1])

                        # Calculate changes
                        def calc_change(field):
                            f_val = first.get(field)
                            l_val = last.get(field)
                            if f_val and l_val:
                                return round(l_val - f_val, 2)
                            return None

                        # Build assessments list for chart
                        assessments_for_chart = []
                        for row in trend_rows:
                            r = dict(row)
                            assessments_for_chart.append({
                                'name': r['name'],
                                'period': r.get('period') or '',
                                'date': r['created_at'][:10] if r['created_at'] else '',
                                'scores': {
                                    'TRYGHED': round(r['tryghed'] or 0, 2),
                                    'MENING': round(r['mening'] or 0, 2),
                                    'KAN': round(r['kan'] or 0, 2),
                                    'BESVÆR': round(r['besvaer'] or 0, 2),
                                }
                            })

                        trend_data = {
                            'first_name': first['name'],
                            'last_name': last['name'],
                            'assessment_count': len(trend_rows),
                            'overall_change': calc_change('overall'),
                            'mening_change': calc_change('mening'),
                            'tryghed_change': calc_change('tryghed'),
                            'kan_change': calc_change('kan'),
                            'besvaer_change': calc_change('besvaer'),
                            'first_overall': round(first.get('overall') or 0, 2),
                            'last_overall': round(last.get('overall') or 0, 2),
                            'assessments': assessments_for_chart,
                            'fields': ['TRYGHED', 'MENING', 'KAN', 'BESVÆR'],
                        }

                query = """
                    SELECT
                        ou.id,
                        ou.name,
                        ou.full_path,
                        ou.level,
                        c.id as assessment_id,
                        c.name as assessment_name,
                        c.period,
                        c.created_at,
                        COUNT(DISTINCT r.id) as total_responses,
                        CAST(SUM(CASE WHEN r.respondent_type = 'employee' THEN 1 ELSE 0 END) AS REAL) / 24 as unique_respondents,

                        AVG(CASE WHEN r.respondent_type = 'employee' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_overall,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_mening,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_tryghed,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_kan,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_besvaer,

                        AVG(CASE WHEN r.respondent_type = 'leader_assess' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_overall,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_mening,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_tryghed,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_kan,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_besvaer

                    FROM organizational_units ou
                    JOIN assessments c ON c.target_unit_id = ou.id
                    JOIN responses r ON c.id = r.assessment_id
                    JOIN questions q ON r.question_id = q.id
                    WHERE ou.id = ?
                """
                query_params = [unit_id]

                if where_clause != "1=1":
                    query += f" AND {where_clause}"
                    query_params.extend(params)

                query += """
                    GROUP BY ou.id, c.id
                    HAVING total_responses > 0
                """

                assessment_sort_columns = {
                    'name': 'c.name',
                    'date': 'c.created_at',
                    'responses': 'unique_respondents',
                    'employee_overall': 'employee_overall',
                    'mening': 'employee_mening',
                    'tryghed': 'employee_tryghed',
                    'kan': 'employee_kan',
                    'besvaer': 'employee_besvaer',
                }
                sort_col = assessment_sort_columns.get(sort_by, 'c.created_at')
                order = 'DESC' if sort_order == 'desc' else 'ASC'
                if sort_by == 'date' and sort_order == 'asc':
                    order = 'ASC'
                elif sort_by == 'date':
                    order = 'DESC'
                query += f" ORDER BY {sort_col} {order}"

                units = conn.execute(query, query_params).fetchall()

            else:
                # MODE 2b: Show children with aggregated scores (parent node)
                # Use recursive CTE to get all descendants' data aggregated per direct child
                show_assessments = False

                query = """
                    WITH RECURSIVE descendants AS (
                        -- Direct children of the selected unit
                        SELECT id, id as root_child_id, name as root_child_name
                        FROM organizational_units
                        WHERE parent_id = ?

                        UNION ALL

                        -- All descendants, keeping track of which direct child they belong to
                        SELECT ou.id, d.root_child_id, d.root_child_name
                        FROM organizational_units ou
                        JOIN descendants d ON ou.parent_id = d.id
                    )
                    SELECT
                        child.id,
                        child.name,
                        child.full_path,
                        child.level,
                        COUNT(DISTINCT c.id) as assessment_count,
                        COUNT(DISTINCT r.id) as total_responses,
                        CAST(SUM(CASE WHEN r.respondent_type = 'employee' THEN 1 ELSE 0 END) AS REAL) / 24 as unique_respondents,

                        AVG(CASE WHEN r.respondent_type = 'employee' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_overall,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_mening,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_tryghed,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_kan,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_besvaer,

                        AVG(CASE WHEN r.respondent_type = 'leader_assess' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_overall,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_mening,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_tryghed,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_kan,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_besvaer

                    FROM organizational_units child
                    JOIN descendants d ON d.root_child_id = child.id
                    JOIN assessments c ON c.target_unit_id = d.id
                    JOIN responses r ON c.id = r.assessment_id
                    JOIN questions q ON r.question_id = q.id
                    WHERE child.parent_id = ?
                """
                query_params = [unit_id, unit_id]

                if where_clause != "1=1":
                    # Replace 'ou.' with 'child.' since we alias organizational_units as 'child'
                    adjusted_where = where_clause.replace('ou.', 'child.')
                    query += f" AND {adjusted_where}"
                    query_params.extend(params)

                query += """
                    GROUP BY child.id
                    HAVING total_responses > 0
                    ORDER BY child.name
                """

                units = conn.execute(query, query_params).fetchall()

        else:
            # MODE 1: Show units with aggregated scores (no individual assessments)
            query = """
                SELECT
                    ou.id,
                    ou.name,
                    ou.full_path,
                    ou.level,
                    COUNT(DISTINCT c.id) as assessment_count,
                    COUNT(DISTINCT r.id) as total_responses,
                    -- Calculate respondents: employee responses / 24 questions per respondent
                    CAST(SUM(CASE WHEN r.respondent_type = 'employee' THEN 1 ELSE 0 END) AS REAL) / 24 as unique_respondents,

                    -- Employee scores (aggregated across ALL assessments)
                    AVG(CASE WHEN r.respondent_type = 'employee' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_overall,
                    AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_mening,
                    AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_tryghed,
                    AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_kan,
                    AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as employee_besvaer,

                    -- Leader assessment scores
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_overall,
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'MENING' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_mening,
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'TRYGHED' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_tryghed,
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'KAN' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_kan,
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'BESVÆR' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as leader_besvaer

                FROM organizational_units ou
                JOIN assessments c ON c.target_unit_id = ou.id
                JOIN responses r ON c.id = r.assessment_id
                JOIN questions q ON r.question_id = q.id
            """

            query_params = []
            if where_clause != "1=1":
                query += f" WHERE {where_clause}"
                query_params.extend(params)

            # Group by UNIT only (not assessment) to get aggregated scores
            query += """
                GROUP BY ou.id, ou.name, ou.full_path, ou.level
                HAVING total_responses > 0
            """

            # Add sorting
            sort_columns = {
                'name': 'ou.name',
                'responses': 'total_responses',
                'employee_overall': 'employee_overall',
                'mening': 'employee_mening',
                'tryghed': 'employee_tryghed',
                'kan': 'employee_kan',
                'besvaer': 'employee_besvaer',
                'gap': 'ABS(employee_overall - leader_overall)'
            }

            sort_col = sort_columns.get(sort_by, 'ou.name')
            order = 'DESC' if sort_order == 'desc' else 'ASC'
            query += f" ORDER BY {sort_col} {order}"

            units = conn.execute(query, query_params).fetchall()

        # Enrich units with indicators
        for unit in units:
            unit_dict = dict(unit)

            # For aggregated view, we can't calculate per-assessment indicators
            # Set defaults
            unit_dict['has_substitution'] = False
            unit_dict['has_leader_gap'] = False
            unit_dict['has_leader_blocked'] = False

            # Calculate leader gap if we have both scores
            if unit_dict.get('employee_overall') and unit_dict.get('leader_overall'):
                max_gap = 0
                for field in ['tryghed', 'mening', 'kan', 'besvaer']:
                    emp_score = unit_dict.get(f'employee_{field}')
                    leader_score = unit_dict.get(f'leader_{field}')
                    if emp_score and leader_score:
                        gap = abs(emp_score - leader_score)
                        if gap > max_gap:
                            max_gap = gap
                unit_dict['has_leader_gap'] = max_gap > 1.0

            enriched_units.append(unit_dict)

    return render_template('admin/analyser.html',
                         units=enriched_units,
                         current_unit_id=unit_id,
                         selected_unit_name=selected_unit_name,
                         show_assessments=show_assessments,
                         sort_by=sort_by,
                         sort_order=sort_order,
                         trend_data=trend_data)


@admin_core_bp.route('/admin/dashboard')
@admin_core_bp.route('/admin/dashboard/<customer_id>')
@admin_core_bp.route('/admin/dashboard/<customer_id>/<unit_id>')
@login_required
def org_dashboard(customer_id=None, unit_id=None):
    """
    Hierarkisk organisations-dashboard med drill-down.

    Niveauer:
    1. /admin/dashboard - Oversigt over alle kunder (kun admin)
    2. /admin/dashboard/<customer_id> - Oversigt over kundens forvaltninger
    3. /admin/dashboard/<customer_id>/<unit_id> - Drill-down i unit hierarki
    """
    user = get_current_user()

    # Hvis ikke admin/superadmin, tving til egen kunde
    if user['role'] not in ('admin', 'superadmin'):
        customer_id = user['customer_id']
    # For admin/superadmin: brug customer_filter fra session hvis sat
    elif not customer_id and session.get('customer_filter'):
        customer_id = session.get('customer_filter')

    with get_db() as conn:
        # Niveau 1: Vis alle kunder (kun admin/superadmin uden customer_id)
        if not customer_id and user['role'] in ('admin', 'superadmin'):
            customers = conn.execute("""
                SELECT
                    c.id,
                    c.name,
                    COUNT(DISTINCT ou.id) as unit_count,
                    COUNT(DISTINCT camp.id) as assessment_count,
                    COUNT(DISTINCT r.id) as response_count,
                    AVG(CASE
                        WHEN r.respondent_type = 'employee' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END
                    END) as avg_score
                FROM customers c
                LEFT JOIN organizational_units ou ON ou.customer_id = c.id
                LEFT JOIN assessments camp ON camp.target_unit_id = ou.id
                LEFT JOIN responses r ON r.assessment_id = camp.id
                LEFT JOIN questions q ON r.question_id = q.id
                GROUP BY c.id
                ORDER BY c.name
            """).fetchall()

            return render_template('admin/org_dashboard.html',
                                 level='customers',
                                 items=[dict(c) for c in customers],
                                 breadcrumb=[{'name': 'Alle Organisationer', 'url': None}])

        # Hent kundeinfo
        customer = conn.execute("SELECT * FROM customers WHERE id = ?", [customer_id]).fetchone()
        if not customer:
            flash('Kunde ikke fundet', 'error')
            return redirect(url_for('admin_core.org_dashboard'))

        # Niveau 2 & 3: Vis units under kunde eller parent unit
        if unit_id:
            # Drill-down: vis børn af denne unit
            parent_unit = conn.execute("SELECT * FROM organizational_units WHERE id = ?", [unit_id]).fetchone()
            if not parent_unit:
                flash('Enhed ikke fundet', 'error')
                return redirect(url_for('admin_core.org_dashboard', customer_id=customer_id))

            parent_id_filter = unit_id
            current_level = parent_unit['level'] + 1

            # Byg breadcrumb
            breadcrumb = [{'name': 'Alle Organisationer', 'url': url_for('admin_core.org_dashboard')}]
            breadcrumb.append({'name': customer['name'], 'url': url_for('admin_core.org_dashboard', customer_id=customer_id)})

            # Tilføj parent units til breadcrumb
            path_units = []
            current = parent_unit
            while current:
                path_units.insert(0, current)
                if current['parent_id']:
                    current = conn.execute("SELECT * FROM organizational_units WHERE id = ?", [current['parent_id']]).fetchone()
                else:
                    current = None

            for pu in path_units[:-1]:  # Alle undtagen sidste (den er current)
                breadcrumb.append({'name': pu['name'], 'url': url_for('admin_core.org_dashboard', customer_id=customer_id, unit_id=pu['id'])})
            breadcrumb.append({'name': parent_unit['name'], 'url': None})

        else:
            # Top-level: vis root units for denne kunde
            parent_id_filter = None
            current_level = 0
            breadcrumb = [
                {'name': 'Alle Organisationer', 'url': url_for('admin_core.org_dashboard')},
                {'name': customer['name'], 'url': None}
            ]
            parent_unit = None

        # Hent units på dette niveau med aggregerede scores
        if parent_id_filter:
            # Hent child units med rekursiv aggregering fra underenheder
            child_units = conn.execute("""
                SELECT id, name, level, leader_name,
                       (SELECT COUNT(*) FROM organizational_units WHERE parent_id = ou.id) as child_count,
                       (SELECT camp.id FROM assessments camp WHERE camp.target_unit_id = ou.id LIMIT 1) as direct_assessment_id
                FROM organizational_units ou
                WHERE ou.parent_id = ?
                ORDER BY ou.name
            """, [parent_id_filter]).fetchall()

            # Beregn aggregerede scores for hver unit inkl. alle underenheder
            units = []
            for child in child_units:
                # Rekursiv query der aggregerer fra hele subtræet
                agg = conn.execute("""
                    WITH RECURSIVE subtree AS (
                        SELECT id FROM organizational_units WHERE id = ?
                        UNION ALL
                        SELECT ou.id FROM organizational_units ou
                        JOIN subtree st ON ou.parent_id = st.id
                    )
                    SELECT
                        COUNT(DISTINCT camp.id) as assessment_count,
                        COUNT(DISTINCT r.id) as response_count,
                        AVG(CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END) as avg_score,
                        AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as score_mening,
                        AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as score_tryghed,
                        AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as score_kan,
                        AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as score_besvaer
                    FROM subtree st
                    LEFT JOIN assessments camp ON camp.target_unit_id = st.id
                    LEFT JOIN responses r ON r.assessment_id = camp.id AND r.respondent_type = 'employee'
                    LEFT JOIN questions q ON r.question_id = q.id
                """, [child['id']]).fetchone()

                units.append({
                    'id': child['id'],
                    'name': child['name'],
                    'level': child['level'],
                    'leader_name': child['leader_name'],
                    'child_count': child['child_count'],
                    'direct_assessment_id': child['direct_assessment_id'],
                    'assessment_count': agg['assessment_count'] or 0,
                    'response_count': agg['response_count'] or 0,
                    'avg_score': agg['avg_score'],
                    'score_mening': agg['score_mening'],
                    'score_tryghed': agg['score_tryghed'],
                    'score_kan': agg['score_kan'],
                    'score_besvaer': agg['score_besvaer']
                })

            # Hent friktionsprofiler for denne unit (hvis leaf node) - with fallback
            try:
                profiler = conn.execute("""
                    SELECT ps.id, ps.person_name, ps.created_at, ps.is_complete
                    FROM profil_sessions ps
                    WHERE ps.unit_id = ? AND ps.is_complete = 1
                    ORDER BY ps.created_at DESC
                """, [unit_id]).fetchall()
            except Exception:
                profiler = []

            # Add profil_count to units
            for u in units:
                try:
                    count = conn.execute("""
                        SELECT COUNT(*) FROM profil_sessions ps
                        WHERE ps.unit_id = ? AND ps.is_complete = 1
                    """, [u['id']]).fetchone()[0]
                    u['profil_count'] = count
                except Exception:
                    u['profil_count'] = 0
        else:
            # Root units for kunde - med rekursiv aggregering fra underenheder
            # Først hent root units
            root_units = conn.execute("""
                SELECT id, name, level, leader_name,
                       (SELECT COUNT(*) FROM organizational_units WHERE parent_id = ou.id) as child_count,
                       (SELECT camp.id FROM assessments camp WHERE camp.target_unit_id = ou.id LIMIT 1) as direct_assessment_id
                FROM organizational_units ou
                WHERE ou.customer_id = ? AND ou.parent_id IS NULL
                ORDER BY ou.name
            """, [customer_id]).fetchall()

            # Beregn aggregerede scores for hver root unit inkl. alle underenheder
            units = []
            for root in root_units:
                # Rekursiv query der aggregerer fra hele subtræet
                agg = conn.execute("""
                    WITH RECURSIVE subtree AS (
                        SELECT id FROM organizational_units WHERE id = ?
                        UNION ALL
                        SELECT ou.id FROM organizational_units ou
                        JOIN subtree st ON ou.parent_id = st.id
                    )
                    SELECT
                        COUNT(DISTINCT camp.id) as assessment_count,
                        COUNT(DISTINCT r.id) as response_count,
                        AVG(CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END) as avg_score,
                        AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as score_mening,
                        AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as score_tryghed,
                        AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as score_kan,
                        AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as score_besvaer
                    FROM subtree st
                    LEFT JOIN assessments camp ON camp.target_unit_id = st.id
                    LEFT JOIN responses r ON r.assessment_id = camp.id AND r.respondent_type = 'employee'
                    LEFT JOIN questions q ON r.question_id = q.id
                """, [root['id']]).fetchone()

                units.append({
                    'id': root['id'],
                    'name': root['name'],
                    'level': root['level'],
                    'leader_name': root['leader_name'],
                    'child_count': root['child_count'],
                    'direct_assessment_id': root['direct_assessment_id'],
                    'assessment_count': agg['assessment_count'] or 0,
                    'response_count': agg['response_count'] or 0,
                    'avg_score': agg['avg_score'],
                    'score_mening': agg['score_mening'],
                    'score_tryghed': agg['score_tryghed'],
                    'score_kan': agg['score_kan'],
                    'score_besvaer': agg['score_besvaer']
                })

            # Add profil_count to units (units er allerede dicts)
            for u in units:
                try:
                    count = conn.execute("""
                        SELECT COUNT(*) FROM profil_sessions ps
                        WHERE ps.unit_id = ? AND ps.is_complete = 1
                    """, [u['id']]).fetchone()[0]
                    u['profil_count'] = count
                except Exception:
                    u['profil_count'] = 0

            profiler = []  # Ingen profiler på root niveau

        # Beregn samlet score for dette niveau
        if parent_unit:
            # Aggregér for parent unit
            agg_scores = conn.execute("""
                WITH RECURSIVE subtree AS (
                    SELECT id FROM organizational_units WHERE id = ?
                    UNION ALL
                    SELECT ou.id FROM organizational_units ou
                    JOIN subtree st ON ou.parent_id = st.id
                )
                SELECT
                    AVG(CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END) as avg_score,
                    AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as mening,
                    AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as tryghed,
                    AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as kan,
                    AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as besvaer,
                    COUNT(DISTINCT r.id) as response_count
                FROM responses r
                JOIN assessments camp ON r.assessment_id = camp.id
                JOIN questions q ON r.question_id = q.id
                JOIN subtree st ON camp.target_unit_id = st.id
                WHERE r.respondent_type = 'employee'
            """, [unit_id]).fetchone()
        else:
            # Aggregér for hele kunden
            agg_scores = conn.execute("""
                SELECT
                    AVG(CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END) as avg_score,
                    AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as mening,
                    AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as tryghed,
                    AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as kan,
                    AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 8 - r.score ELSE r.score END END) as besvaer,
                    COUNT(DISTINCT r.id) as response_count
                FROM responses r
                JOIN assessments camp ON r.assessment_id = camp.id
                JOIN questions q ON r.question_id = q.id
                JOIN organizational_units ou ON camp.target_unit_id = ou.id
                WHERE ou.customer_id = ? AND r.respondent_type = 'employee'
            """, [customer_id]).fetchone()

        return render_template('admin/org_dashboard.html',
                             level='units',
                             items=units,  # Already list of dicts
                             customer=dict(customer),
                             parent_unit=dict(parent_unit) if parent_unit else None,
                             agg_scores=dict(agg_scores) if agg_scores else None,
                             breadcrumb=breadcrumb,
                             customer_id=customer_id,
                             profiler=[dict(p) for p in profiler] if profiler else [])


# ========================================
# AUDIT LOG
# ========================================

@admin_core_bp.route('/admin/audit-log')
@admin_required
def audit_log_page():
    """Audit log oversigt - kun admin"""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    filters = {
        'action': request.args.get('action', ''),
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', '')
    }

    # Get logs with filters
    logs = get_audit_logs(
        limit=per_page,
        offset=(page - 1) * per_page,
        action=filters['action'] or None,
        start_date=filters['start_date'] or None,
        end_date=filters['end_date'] or None
    )

    # Get total count for pagination
    total = get_audit_log_count(
        action=filters['action'] or None,
        start_date=filters['start_date'] or None,
        end_date=filters['end_date'] or None
    )
    total_pages = (total + per_page - 1) // per_page

    # Get summary for last 30 days
    summary = get_action_summary(days=30)

    return render_template('admin/audit_log.html',
                          logs=logs,
                          page=page,
                          total_pages=total_pages,
                          filters=filters,
                          summary=summary)


# ========================================
# GDPR / DPO DASHBOARD
# ========================================

@admin_core_bp.route('/admin/gdpr')
@admin_required
def admin_gdpr():
    """GDPR/DPO Dashboard - overblik over data og compliance"""
    # Kun superadmin kan se fuld GDPR oversigt
    user = get_current_user()
    is_superadmin = user['role'] == 'superadmin'

    with get_db() as conn:
        # Data statistik
        stats = {}

        if is_superadmin:
            # Fuld statistik for superadmin
            stats['customers'] = conn.execute('SELECT COUNT(*) FROM customers').fetchone()[0]
            stats['users'] = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            stats['units'] = conn.execute('SELECT COUNT(*) FROM organizational_units').fetchone()[0]
            stats['assessments'] = conn.execute('SELECT COUNT(*) FROM assessments').fetchone()[0]
            stats['responses'] = conn.execute('SELECT COUNT(*) FROM responses').fetchone()[0]
            stats['tokens'] = conn.execute('SELECT COUNT(*) FROM tokens').fetchone()[0]
            stats['situation_assessments'] = conn.execute('SELECT COUNT(*) FROM situation_assessments').fetchone()[0]
            stats['situation_responses'] = conn.execute('SELECT COUNT(*) FROM situation_responses').fetchone()[0]

            # Ældste og nyeste data
            oldest = conn.execute('SELECT MIN(created_at) FROM responses').fetchone()[0]
            newest = conn.execute('SELECT MAX(created_at) FROM responses').fetchone()[0]
            stats['oldest_data'] = oldest[:10] if oldest else 'Ingen data'
            stats['newest_data'] = newest[:10] if newest else 'Ingen data'

            # Kunder med data
            customers_with_data = conn.execute('''
                SELECT c.id, c.name,
                       (SELECT COUNT(*) FROM users WHERE customer_id = c.id) as user_count,
                       (SELECT COUNT(*) FROM organizational_units WHERE customer_id = c.id) as unit_count,
                       (SELECT COUNT(*) FROM assessments a
                        JOIN organizational_units ou ON a.target_unit_id = ou.id
                        WHERE ou.customer_id = c.id) as assessment_count
                FROM customers c
                ORDER BY c.name
            ''').fetchall()
            stats['customers_detail'] = [dict(c) for c in customers_with_data]
        else:
            # Begrænset statistik for admin/manager
            customer_id = user['customer_id']
            stats['units'] = conn.execute(
                'SELECT COUNT(*) FROM organizational_units WHERE customer_id = ?',
                (customer_id,)
            ).fetchone()[0]
            stats['users'] = conn.execute(
                'SELECT COUNT(*) FROM users WHERE customer_id = ?',
                (customer_id,)
            ).fetchone()[0]

    return render_template('admin/gdpr.html',
                           stats=stats,
                           sub_processors=SUB_PROCESSORS,
                           is_superadmin=is_superadmin,
                           active_page='gdpr')


@admin_core_bp.route('/admin/gdpr/delete-customer/<customer_id>', methods=['POST'])
@admin_required
def admin_gdpr_delete_customer(customer_id):
    """Slet al data for en kunde (GDPR sletning)"""
    user = get_current_user()
    if user['role'] != 'superadmin':
        flash('Kun superadmin kan slette kundedata', 'error')
        return redirect(url_for('admin_core.admin_gdpr'))

    with get_db() as conn:
        # Hent kundenavn til bekræftelse
        customer = conn.execute('SELECT name FROM customers WHERE id = ?', (customer_id,)).fetchone()
        if not customer:
            flash('Kunde ikke fundet', 'error')
            return redirect(url_for('admin_core.admin_gdpr'))

        customer_name = customer['name']

        # CASCADE DELETE vil slette alt relateret data
        conn.execute('DELETE FROM customers WHERE id = ?', (customer_id,))

        # Log sletningen
        log_action(
            AuditAction.GDPR_DELETE,
            entity_type='customer',
            entity_id=customer_id,
            details=f'Slettet kunde: {customer_name} ({customer_id})'
        )

    flash(f'Al data for "{customer_name}" er slettet permanent', 'success')
    return redirect(url_for('admin_core.admin_gdpr'))

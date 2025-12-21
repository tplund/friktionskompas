"""
Unit management blueprint - organizational unit CRUD operations and hierarchy management.

Routes:
- /admin/unit/<unit_id> (GET) - View single unit with details, children, and assessments
- /admin/unit/new (GET, POST) - Create new organizational unit
- /admin/unit/<unit_id>/contacts/upload (POST) - Upload contacts for a unit from CSV
- /admin/unit/<unit_id>/sick_leave (POST) - Update sick leave percentage for a unit
- /admin/unit/<unit_id>/delete (POST) - Delete unit and all children (cascade)
- /admin/unit/<unit_id>/dashboard (GET) - Unit dashboard with aggregated assessment data
- /admin/units/bulk-delete (POST) - Delete multiple units at once (admin only)
- /api/units/<unit_id>/move (POST) - Move unit to new parent (admin only)
- /admin/bulk-upload (GET, POST) - Bulk upload units from CSV with hierarchical structure
- /admin/bulk-upload/confirm (POST) - Confirm and execute bulk upload
- /admin/csv-template (GET) - Download CSV template for bulk upload
- /admin/generate-test-csv (GET) - Generate test CSV with sample organizational data
"""

from flask import Blueprint, render_template, redirect, url_for, session, \
    request, flash, Response, jsonify
import csv
import io
import json
import base64

from auth_helpers import login_required, admin_required, get_current_user
from db_hierarchical import (
    get_db, create_unit, get_unit_children, get_unit_path, get_leaf_units,
    add_contacts_bulk, get_assessment_overview, move_unit
)
from db_multitenant import get_customer_filter
from csv_upload_hierarchical import (
    validate_csv_format, bulk_upload_from_csv, generate_csv_template
)
from audit import log_action, AuditAction

units_bp = Blueprint('units', __name__)


# =============================================================================
# UNIT VIEW AND CRUD
# =============================================================================

@units_bp.route('/admin/unit/<unit_id>')
@login_required
def view_unit(unit_id):
    """Vis unit med children og kampagner"""
    user = get_current_user()

    with get_db() as conn:
        # Hent unit med customer filter
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        unit = conn.execute(
            f"SELECT * FROM organizational_units ou WHERE ou.id = ? AND ({where_clause})",
            [unit_id] + params
        ).fetchone()

        if not unit:
            flash("Unit ikke fundet eller ingen adgang", 'error')
            return redirect(url_for('admin_core.admin_home'))

        # Hent kontakter
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE unit_id = ?",
            (unit_id,)
        ).fetchall()

    # Breadcrumbs
    breadcrumbs = get_unit_path(unit_id)

    # Direct children
    children = get_unit_children(unit_id, recursive=False)

    # Leaf units under dette (for assessments)
    leaf_units = get_leaf_units(unit_id)

    # Kampagner rettet mod denne unit
    with get_db() as conn:
        assessments = conn.execute("""
            SELECT c.*,
                   COUNT(DISTINCT t.token) as tokens_sent,
                   SUM(CASE WHEN t.is_used = 1 THEN 1 ELSE 0 END) as tokens_used
            FROM assessments c
            LEFT JOIN tokens t ON c.id = t.assessment_id
            WHERE c.target_unit_id = ?
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, (unit_id,)).fetchall()

    return render_template('admin/view_unit.html',
        unit=dict(unit),
        breadcrumbs=breadcrumbs,
        children=children,
        leaf_units=leaf_units,
        assessments=[dict(c) for c in assessments],
        contacts=[dict(c) for c in contacts])


@units_bp.route('/admin/unit/new', methods=['GET', 'POST'])
@login_required
def new_unit():
    """Opret ny organisation"""
    user = get_current_user()

    if request.method == 'POST':
        # Opret med parent selector
        name = request.form['name']
        parent_id = request.form.get('parent_id') or None
        leader_name = request.form.get('leader_name')
        leader_email = request.form.get('leader_email')
        employee_count = int(request.form.get('employee_count', 0))
        sick_leave_percent = float(request.form.get('sick_leave_percent', 0))

        unit_id = create_unit(
            name=name,
            parent_id=parent_id,
            leader_name=leader_name,
            leader_email=leader_email,
            employee_count=employee_count,
            sick_leave_percent=sick_leave_percent,
            customer_id=user['customer_id']
        )

        flash(f"Organisation '{name}' oprettet!", 'success')
        return redirect(url_for('units.view_unit', unit_id=unit_id))

    # GET: Vis form - kun vis units fra samme customer
    # Check if parent_id is provided in query parameter
    default_parent_id = request.args.get('parent')

    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
    with get_db() as conn:
        # Alle units til parent dropdown (filtreret efter customer)
        all_units = conn.execute(f"""
            SELECT ou.id, ou.name, ou.full_path, ou.level
            FROM organizational_units ou
            WHERE {where_clause}
            ORDER BY ou.full_path
        """, params).fetchall()

    return render_template('admin/new_unit.html',
                         all_units=[dict(u) for u in all_units],
                         default_parent_id=default_parent_id)


@units_bp.route('/admin/unit/<unit_id>/contacts/upload', methods=['POST'])
@login_required
def upload_contacts(unit_id):
    """Upload kontakter fra CSV"""
    if 'file' not in request.files:
        flash('Ingen fil uploaded', 'error')
        return redirect(url_for('units.view_unit', unit_id=unit_id))

    file = request.files['file']
    if file.filename == '':
        flash('Ingen fil valgt', 'error')
        return redirect(url_for('units.view_unit', unit_id=unit_id))

    # Læs CSV
    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    csv_reader = csv.DictReader(stream)

    contacts = []
    for row in csv_reader:
        email = row.get('email', '').strip() or None
        phone = row.get('phone', '').strip() or None
        if email or phone:
            contacts.append({'email': email, 'phone': phone})

    # Gem i database
    add_contacts_bulk(unit_id, contacts)

    flash(f'{len(contacts)} kontakter uploaded!', 'success')
    return redirect(url_for('units.view_unit', unit_id=unit_id))


@units_bp.route('/admin/unit/<unit_id>/sick_leave', methods=['POST'])
@login_required
def update_unit_sick_leave(unit_id):
    """Opdater sygefravær for unit"""
    sick_leave = float(request.form['sick_leave_percent'])

    with get_db() as conn:
        conn.execute(
            "UPDATE organizational_units SET sick_leave_percent = ? WHERE id = ?",
            (sick_leave, unit_id)
        )

    flash(f'Sygefravær opdateret til {sick_leave}%', 'success')
    return redirect(url_for('units.view_unit', unit_id=unit_id))


@units_bp.route('/admin/unit/<unit_id>/delete', methods=['POST'])
@login_required
def delete_unit(unit_id):
    """Slet organisation og alle dens children"""
    user = get_current_user()

    with get_db() as conn:
        # Check access rights
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        unit = conn.execute(
            f"SELECT * FROM organizational_units ou WHERE ou.id = ? AND ({where_clause})",
            [unit_id] + params
        ).fetchone()

        if not unit:
            flash('Organisation ikke fundet eller ingen adgang', 'error')
            return redirect(url_for('admin_core.admin_home'))

        unit_name = unit['name']

        # SQLite cascade delete vil slette alle children automatisk
        # pga. ON DELETE CASCADE i foreign key constraints
        conn.execute("DELETE FROM organizational_units WHERE id = ?", (unit_id,))

        # Audit log unit deletion
        log_action(
            AuditAction.UNIT_DELETED,
            entity_type="unit",
            entity_id=unit_id,
            details=f"Deleted unit: {unit_name}"
        )

    flash(f'Organisation "{unit_name}" og alle underorganisationer er slettet', 'success')
    return redirect(url_for('admin_core.admin_home'))


@units_bp.route('/admin/unit/<unit_id>/dashboard')
@login_required
def unit_dashboard(unit_id):
    """Unit dashboard med aggregeret data"""
    user = get_current_user()

    with get_db() as conn:
        # Hent unit med customer filter
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        unit = conn.execute(
            f"SELECT * FROM organizational_units ou WHERE ou.id = ? AND ({where_clause})",
            [unit_id] + params
        ).fetchone()

        if not unit:
            flash("Unit ikke fundet eller ingen adgang", 'error')
            return redirect(url_for('admin_core.admin_home'))

        # Find seneste kampagne for denne unit
        latest_assessment = conn.execute("""
            SELECT * FROM assessments
            WHERE target_unit_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (unit_id,)).fetchone()

    if not latest_assessment:
        flash('Ingen målinger endnu', 'error')
        return redirect(url_for('units.view_unit', unit_id=unit_id))

    # Breadcrumbs
    breadcrumbs = get_unit_path(unit_id)

    # Overview af leaf units
    overview = get_assessment_overview(latest_assessment['id'])

    return render_template('admin/unit_dashboard.html',
                         unit=dict(unit),
                         breadcrumbs=breadcrumbs,
                         assessment=dict(latest_assessment),
                         units=overview)


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@units_bp.route('/admin/units/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_units():
    """Slet flere organisationer på én gang"""
    user = get_current_user()

    if user['role'] not in ('admin', 'superadmin'):
        flash('Kun administratorer kan bulk-slette', 'error')
        return redirect(url_for('admin_core.admin_home'))

    unit_ids_json = request.form.get('unit_ids', '[]')
    try:
        unit_ids = json.loads(unit_ids_json)
    except (json.JSONDecodeError, ValueError):
        flash('Ugyldige unit IDs', 'error')
        return redirect(url_for('admin_core.admin_home'))

    if not unit_ids:
        flash('Ingen organisationer valgt', 'warning')
        return redirect(url_for('admin_core.admin_home'))

    deleted_count = 0
    with get_db() as conn:
        for unit_id in unit_ids:
            # Tjek om unit eksisterer (og ikke allerede slettet som child af en anden)
            unit = conn.execute(
                "SELECT id, name FROM organizational_units WHERE id = ?",
                (unit_id,)
            ).fetchone()

            if unit:
                # Slet unit (cascade sletter children)
                conn.execute("DELETE FROM organizational_units WHERE id = ?", (unit_id,))
                deleted_count += 1

    flash(f'{deleted_count} organisation(er) slettet', 'success')
    return redirect(url_for('admin_core.admin_home'))


@units_bp.route('/api/units/<unit_id>/move', methods=['POST'])
@login_required
def api_move_unit(unit_id):
    """API: Flyt organisation til ny parent"""
    user = get_current_user()
    if user['role'] not in ('admin', 'superadmin'):
        return jsonify({'success': False, 'error': 'Kun administratorer kan flytte organisationer'}), 403

    data = request.get_json()
    new_parent_id = data.get('new_parent_id')  # None for toplevel

    # Konverter tom streng til None
    if new_parent_id == '' or new_parent_id == 'null':
        new_parent_id = None

    try:
        move_unit(unit_id, new_parent_id)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Fejl ved flytning: {str(e)}'}), 500


# =============================================================================
# BULK UPLOAD FROM CSV
# =============================================================================

@units_bp.route('/admin/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload():
    """Bulk upload af units fra CSV med hierarkisk struktur - Step 1: Preview"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Ingen fil uploaded', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('Ingen fil valgt', 'error')
            return redirect(request.url)

        # Læs fil
        content = file.stream.read().decode('UTF-8')

        # Valider først
        validation = validate_csv_format(content)
        if not validation['valid']:
            for error in validation['errors']:
                flash(error, 'error')
            return redirect(request.url)

        # Parse hele filen for at få bedre preview
        if content.startswith('\ufeff'):
            content_clean = content[1:]
        else:
            content_clean = content

        stream = io.StringIO(content_clean)
        csv_reader = csv.DictReader(stream, delimiter=';')

        all_rows = []
        org_paths = set()
        for row_num, row in enumerate(csv_reader, start=2):
            org_path = row.get('Organisation', '').strip()
            if org_path:
                org_paths.add(org_path)
                firstname = row.get('FirstName', '').strip()
                lastname = row.get('Lastname', '').strip()
                all_rows.append({
                    'row': row_num,
                    'path': org_path,
                    'levels': len(org_path.split('//')),
                    'name': f"{firstname} {lastname}".strip() or '-',
                    'email': row.get('Email', '').strip() or '-',
                })

        # Byg hierarki preview
        hierarchy = {}
        for path in sorted(org_paths):
            parts = path.split('//')
            for i, part in enumerate(parts):
                key = '//'.join(parts[:i+1])
                if key not in hierarchy:
                    hierarchy[key] = {'name': part, 'indent': i, 'count': 0}

        # Tæl personer per organisation
        for row in all_rows:
            if row['path'] in hierarchy:
                hierarchy[row['path']]['count'] += 1

        hierarchy_preview = list(hierarchy.values())
        for i, item in enumerate(hierarchy_preview):
            item['last'] = (i == len(hierarchy_preview) - 1)

        # Encode CSV data til hidden field
        csv_data_encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')

        # Max dybde
        max_depth = max((r['levels'] for r in all_rows), default=0)

        return render_template('admin/bulk_upload.html',
            preview=all_rows[:20],  # Vis max 20 rækker i preview
            total_rows=len(all_rows),
            unique_orgs=len(org_paths),
            max_depth=max_depth,
            hierarchy_preview=hierarchy_preview[:30],  # Max 30 hierarki items
            warnings=validation['warnings'],
            csv_data_encoded=csv_data_encoded
        )

    # GET: Vis upload form
    return render_template('admin/bulk_upload.html')


@units_bp.route('/admin/bulk-upload/confirm', methods=['POST'])
@login_required
def bulk_upload_confirm():
    """Bulk upload af units fra CSV - Step 2: Bekræft og importer"""
    user = get_current_user()

    csv_data_encoded = request.form.get('csv_data', '')
    if not csv_data_encoded:
        flash('Ingen data at importere', 'error')
        return redirect(url_for('units.bulk_upload'))

    try:
        content = base64.b64decode(csv_data_encoded).decode('utf-8')
    except Exception as e:
        flash(f'Fejl ved dekodning af data: {str(e)}', 'error')
        return redirect(url_for('units.bulk_upload'))

    # Upload med customer_id
    stats = bulk_upload_from_csv(content, customer_id=user['customer_id'])

    if stats['errors']:
        for error in stats['errors']:
            flash(error, 'warning')

    flash(f"{stats['units_created']} organisationer oprettet! {stats['contacts_created']} kontakter tilføjet.", 'success')
    return redirect(url_for('admin_core.admin_home'))


@units_bp.route('/admin/csv-template')
@login_required
def download_csv_template():
    """Download CSV skabelon"""
    template = generate_csv_template()
    return Response(
        template,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=friktionskompas_skabelon.csv'}
    )


@units_bp.route('/admin/generate-test-csv')
@login_required
def generate_test_csv():
    """Generer test CSV med realistic organisationer - Excel-kompatibelt format"""
    output = io.StringIO()
    # UTF-8 BOM for Excel compatibility
    output.write('\ufeff')

    # Brug semikolon som delimiter (Excel standard i Danmark)
    writer = csv.writer(output, delimiter=';')

    # Header
    writer.writerow(['FirstName', 'Lastname', 'Email', 'phone', 'Organisation'])

    # Test data - realistic dansk kommune struktur med multiple medarbejdere per afdeling
    test_data = [
        # Odder Kommune - Ældrepleje
        ['Mette', 'Hansen', 'mette.hansen@odder.dk', '+4512345001', 'Odder Kommune//Ældrepleje//Hjemmeplejen Nord'],
        ['Jens', 'Nielsen', 'jens.nielsen@odder.dk', '+4512345002', 'Odder Kommune//Ældrepleje//Hjemmeplejen Nord'],
        ['Anne', 'Larsen', 'anne.larsen@odder.dk', '+4512345003', 'Odder Kommune//Ældrepleje//Hjemmeplejen Nord'],

        ['Peter', 'Sørensen', 'peter.soerensen@odder.dk', '+4512345004', 'Odder Kommune//Ældrepleje//Hjemmeplejen Syd'],
        ['Lise', 'Andersen', 'lise.andersen@odder.dk', '+4512345005', 'Odder Kommune//Ældrepleje//Hjemmeplejen Syd'],

        ['Thomas', 'Berg', 'thomas.berg@odder.dk', '', 'Odder Kommune//Ældrepleje//Natholdet'],
        ['Susanne', 'Møller', 'susanne.moeller@odder.dk', '+4512345006', 'Odder Kommune//Ældrepleje//Natholdet'],

        # Odder Kommune - Børn og Unge
        ['Maria', 'Petersen', 'maria.petersen@odder.dk', '+4512345007', 'Odder Kommune//Børn og Unge//Dagpleje Øst'],
        ['Lars', 'Thomsen', 'lars.thomsen@odder.dk', '', 'Odder Kommune//Børn og Unge//Dagpleje Øst'],

        ['Sofie', 'Jensen', 'sofie.jensen@odder.dk', '+4512345008', 'Odder Kommune//Børn og Unge//Børnehaven Solglimt'],
        ['Michael', 'Larsen', 'michael.larsen@odder.dk', '+4512345009', 'Odder Kommune//Børn og Unge//Børnehaven Solglimt'],

        # TechCorp - IT virksomhed
        ['Anders', 'Kristensen', 'anders@techcorp.dk', '+4512345010', 'TechCorp//IT Afdeling//Development'],
        ['Katrine', 'Nielsen', 'katrine@techcorp.dk', '', 'TechCorp//IT Afdeling//Development'],
        ['Henrik', 'Poulsen', 'henrik@techcorp.dk', '+4512345011', 'TechCorp//IT Afdeling//Development'],

        ['Erik', 'Hansen', 'erik@techcorp.dk', '+4512345012', 'TechCorp//IT Afdeling//Support'],
        ['Louise', 'Berg', 'louise@techcorp.dk', '', 'TechCorp//IT Afdeling//Support'],

        ['Jan', 'Christensen', 'jan@techcorp.dk', '+4512345013', 'TechCorp//IT Afdeling//DevOps'],

        # TechCorp - HR
        ['Pia', 'Andersen', 'pia@techcorp.dk', '+4512345014', 'TechCorp//HR//Rekruttering'],
        ['Ole', 'Hansen', 'ole@techcorp.dk', '', 'TechCorp//HR//Rekruttering'],

        ['Hanne', 'Nielsen', 'hanne@techcorp.dk', '+4512345015', 'TechCorp//HR//Løn og Personale'],

        # TechCorp - Sales
        ['Bent', 'Jensen', 'bent@techcorp.dk', '+4512345016', 'TechCorp//Sales//Nordics'],
        ['Kirsten', 'Madsen', 'kirsten@techcorp.dk', '', 'TechCorp//Sales//Nordics'],

        ['Niels', 'Olsen', 'niels@techcorp.dk', '+4512345017', 'TechCorp//Sales//DACH'],

        # Hospital
        ['Dr. Anna', 'Schmidt', 'anna.schmidt@auh.dk', '+4512345018', 'Aarhus Universitetshospital//Medicin//Kardiologi'],
        ['Dr. Peter', 'Mogensen', 'peter.mogensen@auh.dk', '', 'Aarhus Universitetshospital//Medicin//Kardiologi'],

        ['Dr. Marie', 'Frederiksen', 'marie.frederiksen@auh.dk', '+4512345019', 'Aarhus Universitetshospital//Medicin//Endokrinologi'],

        ['Dr. Jørgen', 'Rasmussen', 'joergen.rasmussen@auh.dk', '+4512345020', 'Aarhus Universitetshospital//Kirurgi//Ortopædkirurgi'],
        ['Sygpl. Karen', 'Sørensen', 'karen.soerensen@auh.dk', '', 'Aarhus Universitetshospital//Kirurgi//Ortopædkirurgi'],
    ]

    # Skriv data
    for row in test_data:
        writer.writerow(row)

    # Return CSV
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment;filename=friktionskompas_test_data.csv'}
    )

"""
Export and backup blueprint - database backups, bulk exports, restore operations.

Routes:
- /admin/backup (GET) - Backup/restore page
- /admin/backup/download (GET) - Download full database backup as JSON
- /admin/backup/restore (POST) - Restore database from uploaded JSON backup
- /admin/bulk-export (GET) - Bulk data export page with options
- /admin/bulk-export/download (POST) - Download bulk export with specified options
- /admin/upload-database (GET, POST) - Upload a database file directly
- /admin/restore-db-from-backup (GET, POST) - Restore database from git-pushed db_backup.b64 file
- /admin/cleanup-empty (GET) - Delete all and import clean local database
"""

from flask import Blueprint, render_template, redirect, url_for, session, \
    request, flash, Response, jsonify
import csv
import io
import os
import json
from datetime import datetime

from extensions import csrf
from auth_helpers import (
    login_required, admin_required, api_or_admin_required,
    get_current_user, check_admin_api_key, is_api_request
)
from db_hierarchical import get_db
from db_multitenant import get_customer_filter
from friction_engine import score_to_percent
from audit import log_action, AuditAction

export_bp = Blueprint('export', __name__)


# =============================================================================
# BULK EXPORT
# =============================================================================

@export_bp.route('/admin/bulk-export')
@admin_required
def bulk_export_page():
    """Bulk data export page with options for anonymization and format."""
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))

    with get_db() as conn:
        # Get customers for dropdown (superadmin only)
        customers = []
        if user['role'] == 'superadmin':
            customers = conn.execute("""
                SELECT id, name FROM customers ORDER BY name
            """).fetchall()

        # Get assessments
        if user['role'] == 'superadmin':
            assessments = conn.execute("""
                SELECT a.id, a.name, a.period, c.name as customer_name
                FROM assessments a
                JOIN organizational_units ou ON a.target_unit_id = ou.id
                JOIN customers c ON ou.customer_id = c.id
                ORDER BY a.created_at DESC
                LIMIT 100
            """).fetchall()
        else:
            assessments = conn.execute(f"""
                SELECT a.id, a.name, a.period
                FROM assessments a
                JOIN organizational_units ou ON a.target_unit_id = ou.id
                WHERE {where_clause}
                ORDER BY a.created_at DESC
                LIMIT 100
            """, params).fetchall()

        # Get stats
        if user['role'] == 'superadmin':
            stats = {
                'assessments': conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
                'responses': conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0],
                'units': conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0],
            }
        else:
            stats = {
                'assessments': conn.execute(f"""
                    SELECT COUNT(*) FROM assessments a
                    JOIN organizational_units ou ON a.target_unit_id = ou.id
                    WHERE {where_clause}
                """, params).fetchone()[0],
                'responses': conn.execute(f"""
                    SELECT COUNT(*) FROM responses r
                    JOIN assessments a ON r.assessment_id = a.id
                    JOIN organizational_units ou ON a.target_unit_id = ou.id
                    WHERE {where_clause}
                """, params).fetchone()[0],
                'units': conn.execute(f"""
                    SELECT COUNT(*) FROM organizational_units WHERE {where_clause}
                """, params).fetchone()[0],
            }

    return render_template('admin/bulk_export.html',
        customers=customers,
        assessments=assessments,
        stats=stats,
        selected_customer_id=request.args.get('customer_id'),
        current_user=user
    )


@export_bp.route('/admin/bulk-export/download', methods=['POST'])
@admin_required
def bulk_export_download():
    """Download bulk export with specified options."""
    import hashlib
    import uuid

    user = get_current_user()

    # Parse options
    customer_id = request.form.get('customer_id') or None
    assessment_id = request.form.get('assessment_id') or None
    export_format = request.form.get('format', 'json')
    anonymization = request.form.get('anonymization', 'pseudonymized')

    include_responses = request.form.get('include_responses') == '1'
    include_scores = request.form.get('include_scores') == '1'
    include_questions = request.form.get('include_questions') == '1'
    include_units = request.form.get('include_units') == '1'

    # Security: non-superadmin can only export own customer data
    if user['role'] != 'superadmin':
        customer_id = user['customer_id']

    # Helper for anonymization
    def anonymize_email(email, level):
        if level == 'none':
            return email
        elif level == 'pseudonymized':
            # Consistent hash-based UUID
            hash_bytes = hashlib.sha256(email.encode()).digest()[:16]
            return str(uuid.UUID(bytes=hash_bytes))
        else:  # full
            return None

    def anonymize_unit_name(name, unit_id, level):
        if level == 'full':
            return f"unit_{unit_id}"
        return name

    with get_db() as conn:
        export_data = {
            'export_date': datetime.now().isoformat(),
            'export_version': '1.0',
            'anonymization_level': anonymization,
            'filters': {
                'customer_id': customer_id,
                'assessment_id': assessment_id
            }
        }

        # Build WHERE clause based on filters
        where_conditions = []
        params = []

        if customer_id:
            where_conditions.append("ou.customer_id = ?")
            params.append(customer_id)
        elif user['role'] != 'superadmin':
            where_conditions.append("ou.customer_id = ?")
            params.append(user['customer_id'])

        if assessment_id:
            where_conditions.append("a.id = ?")
            params.append(assessment_id)

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        # Export responses
        if include_responses:
            responses = conn.execute(f"""
                SELECT
                    r.id as response_id,
                    r.question_id,
                    r.score,
                    r.created_at as response_date,
                    r.respondent_name,
                    r.respondent_type,
                    a.id as assessment_id,
                    a.name as assessment_name,
                    a.period,
                    ou.id as unit_id,
                    ou.name as unit_name,
                    ou.full_path
                FROM responses r
                JOIN assessments a ON r.assessment_id = a.id
                JOIN organizational_units ou ON r.unit_id = ou.id
                WHERE {where_clause}
                ORDER BY r.created_at
            """, params).fetchall()

            export_data['responses'] = [
                {
                    'response_id': r['response_id'],
                    'question_id': r['question_id'],
                    'score': r['score'],
                    'response_date': r['response_date'],
                    'respondent_id': anonymize_email(r['respondent_name'] or '', anonymization) if r['respondent_name'] else None,
                    'is_leader': r['respondent_type'] == 'leader',
                    'assessment_id': r['assessment_id'],
                    'assessment_name': r['assessment_name'] if anonymization != 'full' else None,
                    'period': r['period'],
                    'unit_id': r['unit_id'],
                    'unit_name': anonymize_unit_name(r['unit_name'], r['unit_id'], anonymization),
                }
                for r in responses
            ]

        # Export aggregated scores
        if include_scores:
            # Get scores per assessment/unit
            scores_query = f"""
                SELECT
                    a.id as assessment_id,
                    a.name as assessment_name,
                    a.period,
                    ou.id as unit_id,
                    ou.name as unit_name,
                    q.field,
                    AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                    COUNT(DISTINCT r.respondent_name) as response_count
                FROM responses r
                JOIN assessments a ON r.assessment_id = a.id
                JOIN organizational_units ou ON r.unit_id = ou.id
                JOIN questions q ON r.question_id = q.id
                WHERE {where_clause}
                GROUP BY a.id, ou.id, q.field
            """
            scores = conn.execute(scores_query, params).fetchall()

            export_data['aggregated_scores'] = [
                {
                    'assessment_id': s['assessment_id'],
                    'assessment_name': s['assessment_name'] if anonymization != 'full' else None,
                    'period': s['period'],
                    'unit_id': s['unit_id'],
                    'unit_name': anonymize_unit_name(s['unit_name'], s['unit_id'], anonymization),
                    'field': s['field'],
                    'score': round(s['avg_score'], 2) if s['avg_score'] else None,
                    'percent': round(score_to_percent(s['avg_score']), 1) if s['avg_score'] else None,
                    'response_count': s['response_count']
                }
                for s in scores
            ]

        # Export questions metadata
        if include_questions:
            questions = conn.execute("""
                SELECT id, sequence, field, text_da, text_en, reverse_scored, is_default
                FROM questions
                WHERE is_default = 1
                ORDER BY sequence
            """).fetchall()

            export_data['questions'] = [
                {
                    'id': q['id'],
                    'sequence': q['sequence'],
                    'field': q['field'],
                    'text_da': q['text_da'],
                    'text_en': q['text_en'],
                    'reverse_scored': bool(q['reverse_scored'])
                }
                for q in questions
            ]

        # Export organizational units
        if include_units:
            units_query = f"""
                SELECT ou.id, ou.name, ou.full_path, ou.parent_id, ou.level, c.name as customer_name
                FROM organizational_units ou
                JOIN customers c ON ou.customer_id = c.id
                WHERE {where_clause.replace('a.id = ?', '1=1').replace('t.assessment_id = ?', '1=1')}
            """
            # Remove assessment filter for units
            units_params = [p for p in params if p != assessment_id]
            units = conn.execute(units_query, units_params if units_params else []).fetchall()

            export_data['units'] = [
                {
                    'id': u['id'],
                    'name': anonymize_unit_name(u['name'], u['id'], anonymization),
                    'path': u['full_path'] if anonymization != 'full' else None,
                    'parent_id': u['parent_id'],
                    'level': u['level'],
                    'customer': u['customer_name'] if anonymization == 'none' else None
                }
                for u in units
            ]

    # Audit log
    log_action(
        AuditAction.DATA_EXPORTED,
        entity_type="bulk_export",
        details=f"Bulk export: format={export_format}, anonymization={anonymization}, "
                f"customer={customer_id}, assessment={assessment_id}"
    )

    # Return in requested format
    if export_format == 'csv':
        # Flatten to CSV - primarily responses data
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')

        if include_responses and 'responses' in export_data:
            # Header
            writer.writerow([
                'response_id', 'question_id', 'score', 'response_date',
                'respondent_id', 'is_leader', 'assessment_id', 'assessment_name',
                'period', 'unit_id', 'unit_name'
            ])
            # Data
            for r in export_data['responses']:
                writer.writerow([
                    r['response_id'], r['question_id'], r['score'], r['response_date'],
                    r['respondent_id'], r['is_leader'], r['assessment_id'], r['assessment_name'],
                    r['period'], r['unit_id'], r['unit_name']
                ])

        csv_content = output.getvalue()
        filename = f"friktionskompas_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return Response(
            '\ufeff' + csv_content,  # BOM for Excel
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    else:
        # JSON format
        json_str = json.dumps(export_data, ensure_ascii=False, indent=2, default=str)
        filename = f"friktionskompas_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        return Response(
            json_str,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )


# =============================================================================
# BACKUP & RESTORE
# =============================================================================

@export_bp.route('/admin/backup')
@admin_required
def backup_page():
    """Backup/restore side"""
    with get_db() as conn:
        stats = {
            'customers': conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            'users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'units': conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0],
            'assessments': conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
            'responses': conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0],
            'contacts': conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
            'tokens': conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0],
        }
    return render_template('admin/backup.html', stats=stats)


@export_bp.route('/admin/backup/download')
@admin_required
def backup_download():
    """Download fuld database backup som JSON"""
    backup_data = {
        'backup_date': datetime.now().isoformat(),
        'version': '1.0',
        'tables': {}
    }

    with get_db() as conn:
        # Export alle relevante tabeller
        tables_to_export = [
            'customers',
            'users',
            'organizational_units',
            'contacts',
            'assessments',
            'tokens',
            'responses',
            'questions',
            'email_logs',
            'translations'
        ]

        for table in tables_to_export:
            try:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                backup_data['tables'][table] = [dict(row) for row in rows]
            except Exception as e:
                backup_data['tables'][table] = {'error': str(e)}

    # Audit log backup creation
    log_action(
        AuditAction.BACKUP_CREATED,
        entity_type="database",
        details=f"Full database backup downloaded"
    )

    # Returner som downloadbar JSON fil
    json_str = json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
    filename = f"friktionskompas_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    return Response(
        json_str,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@export_bp.route('/admin/backup/restore', methods=['POST'])
@admin_required
def backup_restore():
    """Restore database fra uploadet JSON backup"""
    if 'backup_file' not in request.files:
        flash('Ingen fil uploadet', 'error')
        return redirect(url_for('export.backup_page'))

    file = request.files['backup_file']
    if file.filename == '':
        flash('Ingen fil valgt', 'error')
        return redirect(url_for('export.backup_page'))

    try:
        backup_data = json.load(file)
    except json.JSONDecodeError:
        flash('Ugyldig JSON fil', 'error')
        return redirect(url_for('export.backup_page'))

    if 'tables' not in backup_data:
        flash('Ugyldig backup fil format', 'error')
        return redirect(url_for('export.backup_page'))

    # Valider at det er en rigtig backup
    if 'version' not in backup_data:
        flash('Backup fil mangler versionsnummer', 'error')
        return redirect(url_for('export.backup_page'))

    restore_mode = request.form.get('restore_mode', 'merge')
    stats = {'inserted': 0, 'skipped': 0, 'errors': 0}

    with get_db() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")

        if restore_mode == 'replace':
            # Slet eksisterende data først (i omvendt rækkefølge pga. foreign keys)
            delete_order = ['responses', 'tokens', 'email_logs', 'contacts', 'assessments',
                           'organizational_units', 'users', 'customers']
            for table in delete_order:
                try:
                    conn.execute(f"DELETE FROM {table}")
                except Exception:
                    pass  # Table may not exist - continue with others

        # Restore tabeller i rigtig rækkefølge (parents før children)
        restore_order = ['customers', 'users', 'organizational_units', 'contacts',
                        'assessments', 'tokens', 'responses', 'questions', 'translations']

        # SQL injection protection: Validér kolonne-navne (tilføjet i go-live audit 2025-12-18)
        import re
        SAFE_COLUMN_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

        def validate_column_names(columns):
            """Returnerer True hvis alle kolonne-navne er sikre"""
            return all(SAFE_COLUMN_PATTERN.match(col) for col in columns)

        for table in restore_order:
            if table not in backup_data['tables']:
                continue

            table_data = backup_data['tables'][table]
            if isinstance(table_data, dict) and 'error' in table_data:
                continue

            for row in table_data:
                try:
                    # SQL injection protection: Validér kolonne-navne
                    if not validate_column_names(row.keys()):
                        stats['errors'] += 1
                        continue  # Skip rows with suspicious column names

                    # Check om row allerede eksisterer (baseret på id)
                    if 'id' in row:
                        existing = conn.execute(f"SELECT id FROM {table} WHERE id = ?", (row['id'],)).fetchone()
                        if existing and restore_mode == 'merge':
                            stats['skipped'] += 1
                            continue

                    # Insert row (kolonne-navne er nu valideret)
                    columns = ', '.join(row.keys())
                    placeholders = ', '.join(['?' for _ in row])
                    conn.execute(f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
                               list(row.values()))
                    stats['inserted'] += 1
                except Exception as e:
                    stats['errors'] += 1

        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()

    # Audit log restore
    log_action(
        AuditAction.BACKUP_RESTORED,
        entity_type="database",
        details=f"Database restored from backup (mode: {restore_mode}). {stats['inserted']} inserted, {stats['skipped']} skipped, {stats['errors']} errors"
    )

    flash(f"Restore gennemført: {stats['inserted']} rækker importeret, {stats['skipped']} sprunget over, {stats['errors']} fejl", 'success')
    return redirect(url_for('export.backup_page'))


@export_bp.route('/admin/restore-db-from-backup', methods=['GET', 'POST'])
@csrf.exempt  # API uses X-Admin-API-Key header for auth
@api_or_admin_required
def restore_db_from_backup():
    """Restore database fra git-pushed db_backup.b64 fil.

    Denne endpoint bruges til at synkronisere lokal database til Render:
    1. Lokalt: python -c "import base64; open('db_backup.b64','w').write(base64.b64encode(open('friktionskompas_v3.db','rb').read()).decode())"
    2. git add db_backup.b64 && git commit -m "DB sync" && git push
    3. Vent på deployment
    4. curl -X POST https://friktionskompasset.dk/admin/restore-db-from-backup -H "X-Admin-API-Key: YOUR_KEY"
    """
    import base64
    import shutil
    from db_hierarchical import DB_PATH

    # Find backup fil i repo
    backup_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db_backup.b64')

    if not os.path.exists(backup_path):
        return jsonify({
            'success': False,
            'error': 'db_backup.b64 ikke fundet i repo',
            'hint': 'Kør lokalt: python -c "import base64; open(\'db_backup.b64\',\'w\').write(base64.b64encode(open(\'friktionskompas_v3.db\',\'rb\').read()).decode())"'
        }), 404

    try:
        # Læs base64 og decode
        with open(backup_path, 'r') as f:
            b64_content = f.read()

        db_content = base64.b64decode(b64_content)

        # Backup eksisterende database
        if os.path.exists(DB_PATH):
            backup_existing = DB_PATH + '.before_restore'
            shutil.copy2(DB_PATH, backup_existing)

        # Skriv ny database
        with open(DB_PATH, 'wb') as f:
            f.write(db_content)

        # Verificer
        new_size = os.path.getsize(DB_PATH)

        return jsonify({
            'success': True,
            'message': 'Database restored successfully',
            'db_path': DB_PATH,
            'new_size_bytes': new_size,
            'new_size_mb': round(new_size / (1024 * 1024), 2)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@export_bp.route('/admin/upload-database', methods=['GET', 'POST'])
@login_required
def upload_database():
    """Upload en database fil direkte"""
    if session['user']['role'] not in ('admin', 'superadmin'):
        return "Ikke tilladt", 403

    from db_hierarchical import DB_PATH
    import shutil

    if request.method == 'GET':
        return '''
        <h1>Upload Database</h1>
        <p>Current DB path: ''' + DB_PATH + '''</p>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="dbfile" accept=".db">
            <br><br>
            <input type="submit" value="Upload og erstat database">
        </form>
        <p style="color:red;">ADVARSEL: Dette erstatter HELE databasen!</p>
        '''

    if 'dbfile' not in request.files:
        return 'Ingen fil valgt', 400

    file = request.files['dbfile']
    if file.filename == '':
        return 'Ingen fil valgt', 400

    try:
        # Save uploaded file directly to DB_PATH
        file.save(DB_PATH)
        flash(f'Database uploadet til {DB_PATH}!', 'success')
        return redirect('/admin')
    except Exception as e:
        return f'Fejl: {str(e)}'


@export_bp.route('/admin/cleanup-empty')
@login_required
def cleanup_empty_units():
    """SLET ALT og importer ren lokal database"""
    if session['user']['role'] not in ('admin', 'superadmin'):
        return "Ikke tilladt", 403

    from db_hierarchical import DB_PATH

    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'local_data_export.json')

    # Debug info
    debug = f"DB_PATH: {DB_PATH}, JSON exists: {os.path.exists(json_path)}"

    if not os.path.exists(json_path):
        return f'FEJL: local_data_export.json ikke fundet! Debug: {debug}'

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    try:
        with get_db() as conn:
            # Disable foreign keys during delete/insert, enable after
            conn.execute("PRAGMA foreign_keys=OFF")

            # Tæl før
            before_units = conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0]
            before_responses = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]

            # SLET ALT FØRST
            conn.execute("DELETE FROM responses")
            conn.execute("DELETE FROM tokens")
            conn.execute("DELETE FROM assessments")
            conn.execute("DELETE FROM contacts")
            conn.execute("DELETE FROM organizational_units")

            # Importer units - sorteret efter level så parents kommer først
            units_sorted = sorted(data.get('organizational_units', []), key=lambda x: x.get('level', 0))
            for unit in units_sorted:
                conn.execute('''
                    INSERT INTO organizational_units (id, name, full_path, parent_id, level, leader_name, leader_email, employee_count, sick_leave_percent, customer_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (unit['id'], unit['name'], unit.get('full_path'), unit.get('parent_id'),
                      unit.get('level', 0), unit.get('leader_name'), unit.get('leader_email'),
                      unit.get('employee_count', 0), unit.get('sick_leave_percent', 0), unit.get('customer_id')))

            # Importer assessments
            for camp in data.get('assessments', []):
                conn.execute('''
                    INSERT INTO assessments (id, name, target_unit_id, period, created_at, min_responses, mode)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (camp['id'], camp['name'], camp['target_unit_id'], camp.get('period'),
                      camp.get('created_at'), camp.get('min_responses', 5), camp.get('mode', 'anonymous')))

            # Importer responses
            for resp in data.get('responses', []):
                conn.execute('''
                    INSERT INTO responses (assessment_id, unit_id, question_id, score, respondent_type, respondent_name, comment, category_comment, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (resp['assessment_id'], resp['unit_id'], resp['question_id'],
                      resp['score'], resp.get('respondent_type'), resp.get('respondent_name'),
                      resp.get('comment'), resp.get('category_comment'), resp.get('created_at')))

            # Nu commit - alt eller intet
            conn.commit()

            units = conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0]
            assessments = conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]
            responses = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]

            # Vis toplevel names
            toplevel = conn.execute("SELECT name FROM organizational_units WHERE parent_id IS NULL").fetchall()
            names = [t[0] for t in toplevel]

        flash(f'Database erstattet! Før: {before_units} units/{before_responses} responses, Nu: {units} units, {assessments} målinger, {responses} responses. Toplevel: {names}', 'success')
    except Exception as e:
        import traceback
        return f'FEJL: {str(e)}.<br><br>Traceback:<pre>{traceback.format_exc()}</pre><br>Debug: {debug}'

    return redirect('/admin')

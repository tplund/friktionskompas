"""
Dev Tools Blueprint - Development and seed routes for admin use.

Routes:
- /admin/seed-translations - Seed translations to database
- /admin/seed-domains - Seed standard domains to database
- /admin/seed-herning - Seed Herning test data
- /admin/seed-testdata - Run seed script to generate test data
- /admin/seed-testdata (GET) - Seed test data page
- /admin/seed-assessments - Seed assessments from JSON files
- /admin/seed-assessment-types - Seed/re-seed assessment types
- /admin/delete-all-data - Delete ALL data (admin only)
- /admin/generate-test-data - Generate test data
- /admin/generate-test-csv - Generate test CSV file
- /admin/dev-tools - Dev tools main page
- /admin/clear-cache - Clear entire cache
- /admin/vary-testdata - Add realistic variation to test data
- /admin/rename-assessments - Rename assessments to new format
- /admin/fix-missing-leader-data - Add missing leader responses
- /admin/db-status - Full database status (public debug)
- /admin/export-db-backup - Export database as base64
- /admin/recreate-assessments - Recreate missing assessments from responses
- /admin/fix-default-preset - Fix default preset to Enterprise Full
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, Response, session
import csv
import io
import os
import json
import secrets
import random
from datetime import datetime

from auth_helpers import login_required, admin_required, superadmin_required, api_or_admin_required, get_current_user
from db_hierarchical import get_db, create_assessment, get_questions, get_all_leaf_units_under, DB_PATH
from db_multitenant import get_customer_filter, seed_assessment_types
from csv_upload_hierarchical import bulk_upload_from_csv
from translations import seed_translations, clear_translation_cache
from cache import get_cache_stats, invalidate_all
from extensions import csrf

dev_tools_bp = Blueprint('dev_tools', __name__)


def dev_tools_enabled():
    """Check if dev tools are enabled via environment variable or debug mode"""
    from flask import current_app
    return (os.environ.get('ENABLE_DEV_TOOLS', 'false').lower() == 'true' or
            current_app.debug)


def is_api_request():
    """Check if request is from API (has API key header)"""
    return 'X-Admin-API-Key' in request.headers



@dev_tools_bp.route('/admin/seed-translations', methods=['GET', 'POST'])
@api_or_admin_required
def admin_seed_translations():
    """Seed translations til database. Supports both browser and API access.

    API Usage:
        curl -X POST https://friktionskompasset.dk/admin/seed-translations \
             -H "X-Admin-API-Key: YOUR_KEY"
    """
    seed_translations()
    clear_translation_cache()

    # Return JSON for API requests
    if is_api_request():
        return jsonify({
            'success': True,
            'message': 'Translations seeded successfully'
        })

    # Check if request came from db-status (no flash, just redirect)
    referrer = request.referrer or ''
    if 'db-status' in referrer:
        return redirect('/admin/db-status')
    flash('Oversættelser er seedet til databasen', 'success')
    return redirect(request.referrer or url_for('admin_core.admin_home'))


@dev_tools_bp.route('/admin/seed-domains', methods=['GET', 'POST'])
@api_or_admin_required
def admin_seed_domains():
    """Seed standard domæner til database. Supports both browser and API access.

    API Usage:
        curl https://friktionskompasset.dk/admin/seed-domains \
             -H "X-Admin-API-Key: YOUR_KEY"
    """
    # Domæne konfigurationer
    # Generiske domæner: Alle login-metoder (MS, Google, Email)
    # Enterprise domæner: Kun Microsoft (f.eks. herning)
    domains_config = [
        {
            'domain': 'friktionskompasset.dk',
            'default_language': 'da',
            'auth_providers': {
                'email_password': True,
                'microsoft': {'enabled': True},
                'google': {'enabled': True},
                'apple': {'enabled': False},
                'facebook': {'enabled': False}
            }
        },
        {
            'domain': 'frictioncompass.com',
            'default_language': 'en',
            'auth_providers': {
                'email_password': True,
                'microsoft': {'enabled': True},
                'google': {'enabled': True},
                'apple': {'enabled': False},
                'facebook': {'enabled': False}
            }
        },
        {
            'domain': 'herning.friktionskompasset.dk',
            'default_language': 'da',
            'auth_providers': {
                'email_password': True,
                'microsoft': {'enabled': True},
                'google': {'enabled': False},
                'apple': {'enabled': False},
                'facebook': {'enabled': False}
            }
        }
    ]

    created = 0
    updated = 0

    with get_db() as conn:
        for config in domains_config:
            # Check if domain exists
            existing = conn.execute('SELECT id FROM domains WHERE domain = ?',
                                   (config['domain'],)).fetchone()

            if existing:
                # Update existing
                conn.execute('''
                    UPDATE domains
                    SET default_language = ?, auth_providers = ?, is_active = 1
                    WHERE domain = ?
                ''', (config['default_language'],
                      json.dumps(config['auth_providers']),
                      config['domain']))
                updated += 1
            else:
                # Create new
                domain_id = 'dom-' + secrets.token_urlsafe(8)
                conn.execute('''
                    INSERT INTO domains (id, domain, default_language, auth_providers, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (domain_id, config['domain'], config['default_language'],
                      json.dumps(config['auth_providers'])))
                created += 1

        conn.commit()

    # Return JSON for API requests
    if is_api_request():
        return jsonify({
            'success': True,
            'created': created,
            'updated': updated,
            'domains': [d['domain'] for d in domains_config]
        })

    flash(f'Domæner seedet: {created} oprettet, {updated} opdateret', 'success')
    return redirect(request.referrer or url_for('customers.manage_domains'))


@dev_tools_bp.route('/admin/delete-all-data', methods=['POST'])
@admin_required
def delete_all_data():
    """Slet ALLE data - kun for admin"""
    confirm = request.form.get('confirm')
    if confirm != 'SLET ALT':
        flash('Du skal skrive "SLET ALT" for at bekræfte', 'error')
        return redirect(url_for('admin_core.admin_home'))

    with get_db() as conn:
        # Slet i rigtig rækkefølge pga foreign keys
        conn.execute("DELETE FROM responses")
        conn.execute("DELETE FROM tokens")
        conn.execute("DELETE FROM assessments")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM organizational_units")
        conn.execute("DELETE FROM questions WHERE is_default = 0")  # Behold default spørgsmål

    flash('Alle data er slettet!', 'success')
    return redirect(url_for('admin_core.admin_home'))


@dev_tools_bp.route('/admin/generate-test-data', methods=['POST'])
@admin_required
def generate_test_data():
    """Generer testdata - organisationer, kontakter, kampagner og svar"""
    if not dev_tools_enabled():
        flash('Dev tools er deaktiveret i produktion', 'error')
        return redirect(url_for('admin_core.admin_home'))
    user = get_current_user()

    # Test CSV data
    test_csv = """\ufeffFirstName;Lastname;Email;phone;Organisation
Mette;Hansen;mette.hansen@odder.dk;+4512345001;Odder Kommune//Ældrepleje//Hjemmeplejen Nord
Jens;Nielsen;jens.nielsen@odder.dk;+4512345002;Odder Kommune//Ældrepleje//Hjemmeplejen Nord
Anne;Larsen;anne.larsen@odder.dk;+4512345003;Odder Kommune//Ældrepleje//Hjemmeplejen Nord
Peter;Sørensen;peter.soerensen@odder.dk;+4512345004;Odder Kommune//Ældrepleje//Hjemmeplejen Syd
Lise;Andersen;lise.andersen@odder.dk;+4512345005;Odder Kommune//Ældrepleje//Hjemmeplejen Syd
Thomas;Berg;thomas.berg@odder.dk;;Odder Kommune//Ældrepleje//Natholdet
Susanne;Møller;susanne.moeller@odder.dk;+4512345006;Odder Kommune//Ældrepleje//Natholdet
Maria;Petersen;maria.petersen@odder.dk;+4512345007;Odder Kommune//Børn og Unge//Dagpleje Øst
Lars;Thomsen;lars.thomsen@odder.dk;;Odder Kommune//Børn og Unge//Dagpleje Øst
Sofie;Jensen;sofie.jensen@odder.dk;+4512345008;Odder Kommune//Børn og Unge//Børnehaven Solglimt
Michael;Larsen;michael.larsen@odder.dk;+4512345009;Odder Kommune//Børn og Unge//Børnehaven Solglimt
Anders;Kristensen;anders@techcorp.dk;+4512345010;TechCorp//IT Afdeling//Development
Katrine;Nielsen;katrine@techcorp.dk;;TechCorp//IT Afdeling//Development
Henrik;Poulsen;henrik@techcorp.dk;+4512345011;TechCorp//IT Afdeling//Development
Erik;Hansen;erik@techcorp.dk;+4512345012;TechCorp//IT Afdeling//Support
Louise;Berg;louise@techcorp.dk;;TechCorp//IT Afdeling//Support
Jan;Christensen;jan@techcorp.dk;+4512345013;TechCorp//IT Afdeling//DevOps
Pia;Andersen;pia@techcorp.dk;+4512345014;TechCorp//HR//Rekruttering
Ole;Hansen;ole@techcorp.dk;;TechCorp//HR//Rekruttering
Hanne;Nielsen;hanne@techcorp.dk;+4512345015;TechCorp//HR//Løn og Personale
Bent;Jensen;bent@techcorp.dk;+4512345016;TechCorp//Sales//Nordics
Kirsten;Madsen;kirsten@techcorp.dk;;TechCorp//Sales//Nordics
Niels;Olsen;niels@techcorp.dk;+4512345017;TechCorp//Sales//DACH"""

    # Upload test data
    stats = bulk_upload_from_csv(test_csv, customer_id=user['customer_id'])

    # Find top-level organisationer
    with get_db() as conn:
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        top_units = conn.execute(f"""
            SELECT id, name, full_path
            FROM organizational_units
            WHERE parent_id IS NULL {where_clause}
        """, params).fetchall()

        # Hent alle spørgsmål
        questions = get_questions()

        assessments_created = 0
        responses_created = 0

        # Opret kampagner for hver top-level organisation
        for unit in top_units:
            # Opret 2 kampagner per organisation (Q1 og Q2 2024)
            for quarter, period in [("Q1", "2024 Q1"), ("Q2", "2024 Q2")]:
                assessment_id = create_assessment(
                    name=f"{unit['name']} - {quarter} 2024",
                    target_unit_id=unit['id'],
                    period=period,
                    customer_id=user['customer_id']
                )
                assessments_created += 1

                # Hent alle leaf units under denne organisation
                leaf_units = get_all_leaf_units_under(unit['id'])

                # Generer svar for hver leaf unit
                for leaf in leaf_units:
                    # 5-8 medarbejdere per unit
                    num_respondents = random.randint(5, 8)
                    for _ in range(num_respondents):
                        for q in questions:
                            score = random.randint(1, 5)
                            conn.execute("""
                                INSERT INTO responses (assessment_id, unit_id, question_id, score, respondent_type)
                                VALUES (?, ?, ?, ?, 'employee')
                            """, (assessment_id, leaf['id'], q['id'], score))
                            responses_created += 1

        conn.commit()

    flash(f'Testdata genereret! {assessments_created} målinger, {responses_created} svar', 'success')
    return redirect(url_for('admin_core.admin_home'))


@dev_tools_bp.route('/admin/generate-test-csv')
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

        ['Triage Leder', 'Christiansen', 'triage@auh.dk', '+4512345021', 'Aarhus Universitetshospital//Akutmodtagelsen//Triage'],
    ]

    for row in test_data:
        writer.writerow(row)

    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment;filename=test_organisationer.csv'}
    )


@dev_tools_bp.route('/admin/seed-herning', methods=['GET', 'POST'])
def seed_herning_direct():
    """Direkte endpoint til at seede Herning testdata (ingen auth for initial setup)"""
    try:
        import seed_herning_testdata
        seed_herning_testdata.main()
        return jsonify({'success': True, 'message': 'Herning testdata genereret!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@dev_tools_bp.route('/admin/seed-testdata', methods=['POST'])
@login_required
def seed_testdata():
    """Kør seed script for at generere testdata"""
    if session['user']['role'] not in ('admin', 'superadmin'):
        flash('Kun administratorer kan køre seed', 'error')
        return redirect('/admin')

    action = request.form.get('action', 'seed')

    if action == 'import_local':
        # Importer lokal kommune-data
        try:
            from import_local_data import import_local_data
            result = import_local_data()
            if result.get('success'):
                flash(f"Importeret: {result['units_imported']} units, {result['assessments_imported']} målinger, {result['responses_imported']} responses", 'success')
            else:
                flash(f"Fejl: {result.get('error', 'Ukendt fejl')}", 'error')
        except Exception as e:
            flash(f'Fejl ved import: {str(e)}', 'error')

    elif action == 'seed_herning':
        # Generer Herning testdata (kanonisk test-kunde)
        try:
            import seed_herning_testdata
            seed_herning_testdata.main()
            flash('Herning testdata genereret! (Borgere, trend-data, B2C)', 'success')
        except Exception as e:
            flash(f'Fejl ved Herning seed: {str(e)}', 'error')

    else:
        # Kør standard seed
        try:
            import seed_testdata
            seed_testdata.main()
            flash('Testdata genereret!', 'success')
        except Exception as e:
            flash(f'Fejl ved seed: {str(e)}', 'error')

    return redirect('/admin/seed-testdata')


@dev_tools_bp.route('/admin/seed-testdata')
@login_required
def seed_testdata_page():
    """Vis seed-side"""
    if session['user']['role'] not in ('admin', 'superadmin'):
        flash('Kun administratorer har adgang', 'error')
        return redirect('/admin')

    # Tjek nuværende data
    with get_db() as conn:
        stats = {
            'customers': conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            'users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'units': conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0],
            'assessments': conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
            'responses': conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0],
        }

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Seed Testdata</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
            .stats {{ background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .stats p {{ margin: 5px 0; }}
            .btn {{ background: #3b82f6; color: white; padding: 12px 24px; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; }}
            .btn:hover {{ background: #2563eb; }}
            .warning {{ background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>Seed Testdata</h1>
        <p>Dette vil generere testdata til systemet.</p>

        <div class="stats">
            <h3>Nuværende data:</h3>
            <p>Kunder: {stats['customers']}</p>
            <p>Brugere: {stats['users']}</p>
            <p>Organisationer: {stats['units']}</p>
            <p>Målinger: {stats['assessments']}</p>
            <p>Responses: {stats['responses']}</p>
        </div>

        <div class="warning">
            <strong>Bemærk:</strong> Seed tilføjer demo-data. Import erstatter demo-data med rigtige kommune-data.
        </div>

        <h3>Vælg handling:</h3>

        <form method="POST" style="margin-bottom: 15px;">
            <input type="hidden" name="action" value="seed_herning">
            <button type="submit" class="btn" style="background: #10b981;">Seed Herning Testdata (anbefalet)</button>
            <p style="font-size: 0.9em; color: #666; margin-top: 5px;">Genererer komplet testdata for Herning Kommune: Borgere (B2C), trend-data (Q1-Q4), medarbejdere + ledere</p>
        </form>

        <form method="POST" style="margin-bottom: 15px;">
            <input type="hidden" name="action" value="import_local">
            <button type="submit" class="btn" style="background: #6366f1;">Importer Kommune-data</button>
            <p style="font-size: 0.9em; color: #666; margin-top: 5px;">Importerer fra lokal database (kun hvis tilgængelig)</p>
        </form>

        <form method="POST">
            <input type="hidden" name="action" value="seed">
            <button type="submit" class="btn">Kør Seed Script (demo-data)</button>
            <p style="font-size: 0.9em; color: #666; margin-top: 5px;">Genererer tomme demo-virksomheder</p>
        </form>

        <p style="margin-top: 20px;"><a href="/admin">← Tilbage til admin</a></p>
    </body>
    </html>
    '''


@dev_tools_bp.route('/admin/dev-tools')
@admin_required
def dev_tools():
    """Dev tools samlet side - kun admin"""
    with get_db() as conn:
        stats = {
            'customers': conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            'users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'units': conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0],
            'assessments': conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
            'responses': conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0],
            'tokens': conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0],
            'translations': conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0],
        }

    # Get cache stats
    cache_stats = get_cache_stats()

    return render_template('admin/dev_tools.html', stats=stats, cache_stats=cache_stats)


@dev_tools_bp.route('/admin/clear-cache', methods=['POST'])
@admin_required
def clear_cache():
    """Ryd hele cachen - kun admin"""
    count = invalidate_all()
    flash(f'Cache ryddet! ({count} entries fjernet)', 'success')
    return redirect(url_for('dev_tools.dev_tools'))


@dev_tools_bp.route('/admin/rename-assessments', methods=['POST'])
@admin_required
def rename_assessments():
    """Omdøb målinger fra 'Unit - Q# YYYY' til 'Q# YYYY - Unit' format"""
    if not dev_tools_enabled():
        flash('Dev tools er deaktiveret i produktion', 'error')
        return redirect(url_for('admin_core.admin_home'))
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


@dev_tools_bp.route('/admin/vary-testdata', methods=['POST'])
@admin_required
def vary_testdata():
    """Tilføj realistisk variation til testdata - forskellige organisationer får forskellige profiler"""
    if not dev_tools_enabled():
        flash('Dev tools er deaktiveret i produktion', 'error')
        return redirect(url_for('admin_core.admin_home'))
    # Profiler for forskellige organisationstyper - 7-POINT SKALA
    # Hvert felt har: (target_mean, std_dev, extreme_chance)
    # extreme_chance = sandsynlighed for at producere 1 eller 7 i stedet
    PROFILES = {
        'Birk Skole': {
            'MENING': (5.5, 1.0, 0.08), 'TRYGHED': (5.2, 1.1, 0.06),
            'KAN': (3.5, 1.2, 0.10), 'BESVÆR': (4.5, 1.0, 0.05)
        },
        'Gødstrup Skole': {
            'MENING': (3.0, 1.2, 0.12), 'TRYGHED': (3.8, 1.1, 0.08),
            'KAN': (4.0, 1.0, 0.05), 'BESVÆR': (2.8, 1.3, 0.15)
        },
        'Hammerum Skole': {
            'MENING': (6.0, 0.9, 0.10), 'TRYGHED': (6.3, 0.8, 0.12),
            'KAN': (5.2, 1.0, 0.08), 'BESVÆR': (5.7, 0.9, 0.10)
        },
        'Snejbjerg Skole': {
            'MENING': (4.5, 1.1, 0.06), 'TRYGHED': (3.0, 1.2, 0.10),
            'KAN': (4.8, 1.0, 0.06), 'BESVÆR': (4.5, 1.1, 0.05)
        },
        'Aktivitetscentret Midt': {
            'MENING': (5.2, 1.1, 0.08), 'TRYGHED': (4.5, 1.2, 0.07),
            'KAN': (2.5, 1.3, 0.15), 'BESVÆR': (2.2, 1.2, 0.18)
        },
        'Bofællesskabet Åparken': {
            'MENING': (6.3, 0.8, 0.15), 'TRYGHED': (5.5, 1.0, 0.10),
            'KAN': (4.5, 1.1, 0.06), 'BESVÆR': (3.8, 1.2, 0.08)
        },
        'Støttecentret Vestergade': {
            'MENING': (3.5, 1.2, 0.10), 'TRYGHED': (5.2, 1.0, 0.06),
            'KAN': (6.0, 0.9, 0.12), 'BESVÆR': (5.2, 1.0, 0.08)
        },
    }
    DEFAULT = {'MENING': (4.0, 1.2, 0.08), 'TRYGHED': (4.0, 1.2, 0.08), 'KAN': (4.0, 1.2, 0.08), 'BESVÆR': (4.0, 1.2, 0.08)}

    def get_score(profile, field):
        mean, std, extreme_chance = profile.get(field, DEFAULT[field])
        # Chance for ekstreme scores (1 eller 7)
        if random.random() < extreme_chance:
            return 7 if mean > 4.0 else 1
        # Normal distribution med bredere spredning
        score = random.gauss(mean, std)
        return max(1, min(7, round(score)))

    random.seed(42)
    count = 0

    with get_db() as conn:
        # Opdater employee responses
        # VIGTIGT: For reverse_scored spørgsmål skal vi invertere scoren!
        # Profilen angiver den ØNSKEDE justerede score (efter reverse).
        # Så hvis vi vil have adjusted=4.5 for et reverse_scored spørgsmål,
        # skal raw score være 6-4.5=1.5 → afrundet til 2
        responses = conn.execute("""
            SELECT r.id, ou.name as unit_name, q.field, q.reverse_scored
            FROM responses r
            JOIN organizational_units ou ON r.unit_id = ou.id
            JOIN questions q ON r.question_id = q.id
            WHERE r.respondent_type = 'employee'
        """).fetchall()

        for r in responses:
            profile = next((PROFILES[k] for k in PROFILES if k in r['unit_name']), DEFAULT)
            target_score = get_score(profile, r['field'])
            # For reverse_scored spørgsmål: invert scoren (7-point: 8 - score)
            if r['reverse_scored'] == 1:
                new_score = 8 - target_score
            else:
                new_score = target_score
            conn.execute("UPDATE responses SET score = ? WHERE id = ?", (new_score, r['id']))
            count += 1

        # Opdater leader_assess (lidt højere scores - leder-bias)
        leader_responses = conn.execute("""
            SELECT r.id, ou.name as unit_name, q.field, q.reverse_scored
            FROM responses r
            JOIN organizational_units ou ON r.unit_id = ou.id
            JOIN questions q ON r.question_id = q.id
            WHERE r.respondent_type = 'leader_assess'
        """).fetchall()

        for r in leader_responses:
            profile = next((PROFILES[k] for k in PROFILES if k in r['unit_name']), DEFAULT)
            mean, std, extreme_chance = profile.get(r['field'], DEFAULT[r['field']])
            # Ledere vurderer typisk 0.5 point højere (positiv bias) på 7-point skala
            leader_profile = {r['field']: (min(7, mean + 0.5), std * 0.9, extreme_chance * 0.8)}
            target_score = get_score(leader_profile, r['field'])
            # For reverse_scored spørgsmål: invert scoren (7-point: 8 - score)
            if r['reverse_scored'] == 1:
                new_score = 8 - target_score
            else:
                new_score = target_score
            conn.execute("UPDATE responses SET score = ? WHERE id = ?", (new_score, r['id']))
            count += 1

        # Opdater leader_self (varierer mere) - 7-point skala
        leader_self = conn.execute("""
            SELECT r.id FROM responses r WHERE r.respondent_type = 'leader_self'
        """).fetchall()

        for r in leader_self:
            new_score = random.choice([3, 4, 4, 5, 5, 5, 6, 6])
            conn.execute("UPDATE responses SET score = ? WHERE id = ?", (new_score, r['id']))
            count += 1

    # Ryd cache så nye værdier vises
    invalidate_all()

    flash(f'Opdateret {count} responses med realistisk variation og ryddet cache', 'success')
    return redirect(url_for('dev_tools.dev_tools'))


@dev_tools_bp.route('/admin/fix-missing-leader-data', methods=['POST'])
@admin_required
def fix_missing_leader_data():
    """Tilføj manglende leader_assess og leader_self data til gruppe_friktion assessments"""
    if not dev_tools_enabled():
        flash('Dev tools er deaktiveret i produktion', 'error')
        return redirect(url_for('admin_core.admin_home'))
    random.seed(42)
    added_count = 0

    with get_db() as conn:
        # Find alle gruppe_friktion assessments
        assessments = conn.execute("""
            SELECT a.id, a.name, a.target_unit_id, ou.name as unit_name
            FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE a.assessment_type_id = 'gruppe_friktion'
              AND a.name NOT LIKE 'B2C%'
        """).fetchall()

        # Hent alle spørgsmål
        questions = conn.execute("""
            SELECT id, field, reverse_scored FROM questions WHERE is_default = 1
        """).fetchall()

        for assessment in assessments:
            # Tjek om der allerede er leader_assess data
            has_leader_assess = conn.execute("""
                SELECT COUNT(*) FROM responses
                WHERE assessment_id = ? AND respondent_type = 'leader_assess'
            """, (assessment['id'],)).fetchone()[0] > 0

            has_leader_self = conn.execute("""
                SELECT COUNT(*) FROM responses
                WHERE assessment_id = ? AND respondent_type = 'leader_self'
            """, (assessment['id'],)).fetchone()[0] > 0

            if has_leader_assess and has_leader_self:
                continue  # Allerede OK

            # Hent employee responses for at finde unit_id
            sample_response = conn.execute("""
                SELECT unit_id FROM responses
                WHERE assessment_id = ? AND respondent_type = 'employee'
                LIMIT 1
            """, (assessment['id'],)).fetchone()

            if not sample_response:
                continue

            unit_id = sample_response['unit_id']

            # Generer leader_assess data (lidt højere end employee)
            if not has_leader_assess:
                respondent_name = f"Leder vurdering - {assessment['unit_name']}"
                for q in questions:
                    # Ledere vurderer typisk lidt højere (bias)
                    base_score = random.choice([3, 3, 4, 4, 4, 5])
                    if q['reverse_scored'] == 1:
                        score = 6 - base_score
                    else:
                        score = base_score

                    conn.execute("""
                        INSERT INTO responses (assessment_id, question_id, unit_id,
                                              respondent_type, respondent_name, score)
                        VALUES (?, ?, ?, 'leader_assess', ?, ?)
                    """, (assessment['id'], q['id'], unit_id, respondent_name, score))
                    added_count += 1

            # Generer leader_self data (varierer mere)
            if not has_leader_self:
                respondent_name = f"Leder selv - {assessment['unit_name']}"
                for q in questions:
                    # Ledere vurderer sig selv mere varieret
                    base_score = random.choice([2, 3, 3, 4, 4, 4, 5])
                    if q['reverse_scored'] == 1:
                        score = 6 - base_score
                    else:
                        score = base_score

                    conn.execute("""
                        INSERT INTO responses (assessment_id, question_id, unit_id,
                                              respondent_type, respondent_name, score)
                        VALUES (?, ?, ?, 'leader_self', ?, ?)
                    """, (assessment['id'], q['id'], unit_id, respondent_name, score))
                    added_count += 1

            # Opdater assessment til at inkludere leder-vurdering
            conn.execute("""
                UPDATE assessments
                SET include_leader_assessment = 1, include_leader_self = 1
                WHERE id = ?
            """, (assessment['id'],))

    # Ryd cache
    invalidate_all()

    flash(f'Tilføjet {added_count} manglende leder-responses og opdateret assessments', 'success')
    return redirect(url_for('dev_tools.dev_tools'))


@dev_tools_bp.route('/admin/export-db-backup')
@csrf.exempt
@api_or_admin_required
def export_db_backup():
    """Export database as base64 for reverse sync (production -> local).

    Usage:
    curl -s "https://friktionskompasset.dk/admin/export-db-backup" \
        -H "X-Admin-API-Key: YOUR_KEY" > db_from_render.b64

    Then locally:
    python -c "import base64; open('friktionskompas_v3.db','wb').write(base64.b64decode(open('db_from_render.b64').read()))"
    """
    import base64

    # Use the actual DB path from environment or default
    db_path = os.environ.get('DB_PATH', DB_PATH)

    if not os.path.exists(db_path):
        return jsonify({'success': False, 'error': f'Database not found at {db_path}'}), 404

    with open(db_path, 'rb') as f:
        db_bytes = f.read()

    db_b64 = base64.b64encode(db_bytes).decode('utf-8')

    # Return as plain text for easy download
    return db_b64, 200, {'Content-Type': 'text/plain'}


@dev_tools_bp.route('/admin/db-status')
def db_status():
    """Fuld database status - offentlig debug"""
    info = {
        'db_path': DB_PATH,
        'db_exists': os.path.exists(DB_PATH),
        'db_size': os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    }

    with get_db() as conn:
        # Alle units
        all_units = conn.execute("SELECT id, name, parent_id, full_path FROM organizational_units ORDER BY full_path").fetchall()

        # Alle customers
        customers = conn.execute("SELECT id, name FROM customers").fetchall()

        # Assessments
        assessments = conn.execute("SELECT id, name, target_unit_id FROM assessments").fetchall()

        # Response count and respondent_name check
        resp_count = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        resp_with_name = conn.execute("SELECT COUNT(*) FROM responses WHERE respondent_name IS NOT NULL AND respondent_name != ''").fetchone()[0]
        resp_sample = conn.execute("SELECT respondent_name, respondent_type FROM responses LIMIT 5").fetchall()

        # Questions check
        try:
            questions_count = conn.execute("SELECT COUNT(*) FROM questions WHERE is_default = 1").fetchone()[0]
            questions_total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        except Exception:
            questions_count = 0
            questions_total = 0

        # Translations check
        try:
            translations_count = conn.execute("SELECT COUNT(DISTINCT key) FROM translations").fetchone()[0]
            # Pivot the translations table to show da and en columns
            translations_sample = conn.execute("""
                SELECT
                    t1.key,
                    t1.value as da,
                    COALESCE(t2.value, '-') as en
                FROM translations t1
                LEFT JOIN translations t2 ON t1.key = t2.key AND t2.language = 'en'
                WHERE t1.language = 'da'
                LIMIT 5
            """).fetchall()
        except Exception as e:
            translations_count = 0
            translations_sample = []
            translations_error = str(e)

    html = f"""
    <html><head><style>
        body {{ font-family: monospace; padding: 20px; }}
        table {{ border-collapse: collapse; margin: 10px 0; }}
        td, th {{ border: 1px solid #ccc; padding: 5px 10px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        h2 {{ margin-top: 20px; }}
    </style></head><body>
    <h1>Database Status</h1>
    <p><b>Path:</b> {info['db_path']}</p>
    <p><b>Exists:</b> {info['db_exists']}</p>
    <p><b>Size:</b> {info['db_size']} bytes</p>

    <h2>Customers ({len(customers)})</h2>
    <table><tr><th>ID</th><th>Name</th></tr>
    {''.join(f"<tr><td>{c['id']}</td><td>{c['name']}</td></tr>" for c in customers)}
    </table>

    <h2>Units ({len(all_units)})</h2>
    <table><tr><th>ID</th><th>Name</th><th>Parent</th><th>Path</th></tr>
    {''.join(f"<tr><td>{u['id'][:12]}...</td><td>{u['name']}</td><td>{(u['parent_id'] or '-')[:12]}</td><td>{u['full_path']}</td></tr>" for u in all_units)}
    </table>

    <h2>Assessments ({len(assessments)})</h2>
    <table><tr><th>ID</th><th>Name</th><th>Target</th></tr>
    {''.join(f"<tr><td>{c['id']}</td><td>{c['name']}</td><td>{c['target_unit_id'][:12]}...</td></tr>" for c in assessments)}
    </table>

    <p><b>Responses:</b> {resp_count}</p>
    <p><b>Responses with respondent_name:</b> {resp_with_name}</p>
    <p><b>Sample responses:</b></p>
    <ul>{''.join(f"<li>{r['respondent_name']} ({r['respondent_type']})</li>" for r in resp_sample)}</ul>

    <h2>Questions</h2>
    <p><b>Total questions:</b> {questions_total}</p>
    <p><b>Default questions (is_default=1):</b> {questions_count}</p>
    <p style="color: {'green' if questions_count >= 20 else 'red'};">
        {'OK - Nok spørgsmål' if questions_count >= 20 else 'FEJL - Mangler spørgsmål! Upload database igen.'}
    </p>

    <h2>Translations</h2>
    <p><b>Total translations:</b> {translations_count}</p>
    <p style="color: {'green' if translations_count >= 100 else 'red'};">
        {'OK - Oversættelser loaded' if translations_count >= 100 else 'FEJL - Mangler oversættelser! Klik Seed Translations.'}
    </p>
    <table><tr><th>Key</th><th>DA</th><th>EN</th></tr>
    {''.join(f"<tr><td>{t['key']}</td><td>{t['da'][:30]}...</td><td>{t['en'][:30] if t['en'] else '-'}...</td></tr>" for t in translations_sample)}
    </table>

    <h2>Actions</h2>
    <form action="/admin/seed-translations" method="POST" style="display: inline;">
        <button type="submit" style="padding: 10px 20px; background: #3b82f6; color: white; border: none; border-radius: 5px; cursor: pointer;">
            Seed Translations (Genindlæs oversættelser)
        </button>
    </form>
    <form action="/admin/recreate-assessments" method="POST" style="display: inline; margin-left: 10px;">
        <button type="submit" style="padding: 10px 20px; background: #10b981; color: white; border: none; border-radius: 5px; cursor: pointer;">
            Genskab Assessments (fra responses)
        </button>
    </form>
    <form action="/admin/seed-assessments" method="POST" style="display: inline; margin-left: 10px;">
        <button type="submit" style="padding: 10px 20px; background: #f59e0b; color: white; border: none; border-radius: 5px; cursor: pointer;">
            Seed Assessments (fra JSON)
        </button>
    </form>
    <br><br>
    <p><a href="/admin/full-reset">FULD RESET - Slet alt og genimporter</a></p>
    <p><a href="/admin/upload-database">Upload database fil</a></p>
    </body></html>
    """
    return html


@dev_tools_bp.route('/admin/recreate-assessments', methods=['POST'])
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


@dev_tools_bp.route('/admin/seed-assessments', methods=['POST'])
def seed_assessments():
    """Seed assessments og responses fra JSON filer"""
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
                    continue  # Skip silently - assessment mangler

                try:
                    conn.execute("""
                        INSERT INTO responses (id, assessment_id, unit_id, question_id, score,
                                             created_at, respondent_type, respondent_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, [r.get('id'), r['assessment_id'], r.get('unit_id'), r['question_id'],
                          r['score'], r.get('created_at'), r.get('respondent_type', 'employee'),
                          r.get('respondent_name')])
                    inserted_responses += 1
                except Exception as e:
                    pass  # Skip errors silently for responses

            conn.commit()
            flash(f'Seedet {inserted_responses} responses, {skipped_responses} sprunget over', 'info')

    flash(f'Seedet {inserted_assessments} assessments, {skipped_assessments} sprunget over', 'success')
    if errors:
        flash(f'{len(errors)} fejl - check at units eksisterer', 'warning')

    return redirect(url_for('dev_tools.db_status'))


@dev_tools_bp.route('/admin/seed-assessment-types', methods=['GET', 'POST'])
def seed_assessment_types_route():
    """Seed/re-seed assessment types - no auth for initial setup"""
    seed_assessment_types()
    if request.method == 'GET':
        return jsonify({'status': 'ok', 'message': 'Assessment types og presets seedet!'})
    flash('Målingstyper og presets seedet!', 'success')
    return redirect(url_for('assessments.assessment_types'))


@dev_tools_bp.route('/admin/fix-default-preset', methods=['GET'])
def fix_default_preset():
    """Fix default preset til Enterprise Full (alle 7 målingstyper)"""
    with get_db() as conn:
        # Sæt alle presets til ikke-default
        conn.execute("UPDATE assessment_presets SET is_default = 0")

        # Sæt Enterprise Full til default
        conn.execute("UPDATE assessment_presets SET is_default = 1 WHERE name = 'Enterprise Full'")

        # Tjek om Enterprise Full preset eksisterer
        preset = conn.execute("SELECT id FROM assessment_presets WHERE name = 'Enterprise Full'").fetchone()

        if not preset:
            # Opret Enterprise Full preset hvis det ikke eksisterer
            conn.execute("""
                INSERT INTO assessment_presets (name, description, is_default)
                VALUES ('Enterprise Full', 'Alle målingstyper aktiveret', 1)
            """)
            preset_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Tilføj alle 7 målingstyper
            all_types = ['screening', 'profil_fuld', 'profil_situation', 'gruppe_friktion',
                        'gruppe_leder', 'kapacitet', 'baandbredde']
            for type_id in all_types:
                conn.execute("""
                    INSERT OR IGNORE INTO preset_assessment_types (preset_id, assessment_type_id)
                    VALUES (?, ?)
                """, (preset_id, type_id))

            types_added = all_types
        else:
            preset_id = preset['id']
            # Tilføj alle manglende typer til Enterprise Full
            all_types = ['screening', 'profil_fuld', 'profil_situation', 'gruppe_friktion',
                        'gruppe_leder', 'kapacitet', 'baandbredde']
            for type_id in all_types:
                conn.execute("""
                    INSERT OR IGNORE INTO preset_assessment_types (preset_id, assessment_type_id)
                    VALUES (?, ?)
                """, (preset_id, type_id))

            # Hent tilføjede typer
            types_in_preset = conn.execute("""
                SELECT assessment_type_id FROM preset_assessment_types WHERE preset_id = ?
            """, (preset_id,)).fetchall()
            types_added = [t['assessment_type_id'] for t in types_in_preset]

    return jsonify({
        'status': 'ok',
        'message': f'Default preset ændret til Enterprise Full ({len(types_added)} målingstyper)',
        'types': types_added
    })

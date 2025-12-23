"""
Flask app for Friktionsprofil
Kan køres standalone eller integreres i admin_app
"""
from flask import Flask, render_template, request, redirect, url_for, flash, session
from db_profil import (
    init_profil_tables,
    create_session,
    get_session,
    complete_session,
    get_questions_by_field,
    save_responses,
    list_sessions,
    generate_test_profiles,
    # Pair session functions
    create_pair_session,
    get_pair_session,
    get_pair_session_by_code,
    get_pair_session_by_profil_session,
    join_pair_session,
    update_pair_status
)
from analysis_profil import (
    get_full_analysis,
    get_color_matrix,
    compare_profiles
)

import os
import secrets as secrets_module

app = Flask(__name__)

# Sikker secret key fra miljøvariabel (fallback til autogeneret i development)
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY and not os.environ.get('FLASK_DEBUG'):
    raise RuntimeError('SECRET_KEY must be set in production')
app.secret_key = SECRET_KEY or secrets_module.token_hex(32)

# Debug mode configuration
app.debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

# Security configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['SESSION_COOKIE_SECURE'] = not app.debug  # True in production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialiser database ved opstart
init_profil_tables()


# ========================================
# SURVEY ROUTES
# ========================================

@app.route('/profil/')
@app.route('/profil/start', methods=['GET'])
def profil_start():
    """Vis startside for ny profil"""
    return render_template('profil/start.html')


@app.route('/profil/start', methods=['POST'])
def profil_create():
    """Opret ny session og redirect til spørgeskema"""
    name = request.form.get('name', '').strip() or None
    email = request.form.get('email', '').strip() or None
    context = request.form.get('context', 'general')

    session_id = create_session(
        person_name=name,
        person_email=email,
        context=context
    )

    return redirect(url_for('profil_survey', session_id=session_id))


@app.route('/profil/<session_id>')
def profil_survey(session_id):
    """Vis spørgeskema"""
    profil_session = get_session(session_id)
    if not profil_session:
        flash('Session ikke fundet', 'error')
        return redirect(url_for('profil_start'))

    if profil_session['is_complete']:
        return redirect(url_for('profil_report', session_id=session_id))

    questions_by_field = get_questions_by_field()

    return render_template(
        'profil/survey.html',
        session_id=session_id,
        session=profil_session,
        questions_by_field=questions_by_field
    )


@app.route('/profil/<session_id>/submit', methods=['POST'])
def profil_submit(session_id):
    """Modtag svar og gem"""
    profil_session = get_session(session_id)
    if not profil_session:
        flash('Session ikke fundet', 'error')
        return redirect(url_for('profil_start'))

    # Parse alle svar
    responses = {}
    for key, value in request.form.items():
        if key.startswith('q_'):
            question_id = int(key.replace('q_', ''))
            score = int(value)
            responses[question_id] = score

    # Gem svar
    save_responses(session_id, responses)

    # Marker som færdig
    complete_session(session_id)

    # Tjek om dette er del af en par-session
    pair = get_pair_session_by_profil_session(session_id)
    if pair:
        # Opdater par-status og redirect til par-side
        update_pair_status(pair['id'])
        return redirect(url_for('pair_status', pair_id=pair['id']))

    return redirect(url_for('profil_report', session_id=session_id))


@app.route('/profil/<session_id>/report')
def profil_report(session_id):
    """Vis rapport"""
    analysis = get_full_analysis(session_id)
    if not analysis:
        flash('Profil ikke fundet', 'error')
        return redirect(url_for('profil_start'))

    # Tjek om session er del af et par
    pair = get_pair_session_by_profil_session(session_id)

    return render_template(
        'profil/report.html',
        session=analysis['session'],
        score_matrix=analysis['score_matrix'],
        color_matrix=analysis['color_matrix'],
        columns=analysis['columns'],
        summary=analysis['summary'],
        interpretations=analysis['interpretations'],
        pair=pair  # Tilføjet for at vise link til par-sammenligning
    )


# ========================================
# PAIR ROUTES (par-måling)
# ========================================

@app.route('/profil/pair/start', methods=['GET'])
def pair_start():
    """Vis startside for par-måling"""
    return render_template('profil/pair_start.html')


@app.route('/profil/pair/start', methods=['POST'])
def pair_create():
    """Opret par-session og redirect til survey"""
    name = request.form.get('name', '').strip() or None
    email = request.form.get('email', '').strip() or None

    result = create_pair_session(
        person_a_name=name,
        person_a_email=email
    )

    # Gem pair_id i session så vi kan finde det efter survey
    session['pair_id'] = result['pair_id']

    return redirect(url_for('profil_survey', session_id=result['session_id']))


@app.route('/profil/pair/join', methods=['GET'])
def pair_join():
    """Vis formular til at joine par-måling"""
    code = request.args.get('code', '')
    return render_template('profil/pair_join.html', prefilled_code=code)


@app.route('/profil/pair/join', methods=['POST'])
def pair_join_submit():
    """Behandl join-request"""
    code = request.form.get('code', '').strip().upper()
    name = request.form.get('name', '').strip() or None
    email = request.form.get('email', '').strip() or None

    if not code:
        flash('Indtast venligst en kode', 'error')
        return redirect(url_for('pair_join'))

    result = join_pair_session(
        pair_code=code,
        person_b_name=name,
        person_b_email=email
    )

    if not result:
        flash('Ugyldig kode eller koden er allerede brugt', 'error')
        return redirect(url_for('pair_join'))

    # Gem pair_id i session
    session['pair_id'] = result['pair_id']

    return redirect(url_for('profil_survey', session_id=result['session_id']))


@app.route('/profil/pair/<pair_id>/status')
def pair_status(pair_id):
    """Vis status for par-måling (venter på partner)"""
    pair = get_pair_session(pair_id)
    if not pair:
        flash('Par-session ikke fundet', 'error')
        return redirect(url_for('profil_start'))

    # Opdater status
    status = update_pair_status(pair_id)
    pair['status'] = status

    if status == 'complete':
        return redirect(url_for('pair_compare', pair_id=pair_id))

    return render_template('profil/pair_waiting.html', pair=pair)


@app.route('/profil/pair/<pair_id>/status/check')
def pair_status_check(pair_id):
    """API endpoint til at tjekke status (for auto-refresh)"""
    from flask import jsonify

    pair = get_pair_session(pair_id)
    if not pair:
        return jsonify({'error': 'Not found'}), 404

    status = update_pair_status(pair_id)

    return jsonify({
        'status': status,
        'redirect': url_for('pair_compare', pair_id=pair_id) if status == 'complete' else None
    })


@app.route('/profil/pair/<pair_id>/compare')
def pair_compare(pair_id):
    """Vis sammenligning af par"""
    pair = get_pair_session(pair_id)
    if not pair:
        flash('Par-session ikke fundet', 'error')
        return redirect(url_for('profil_start'))

    if pair['status'] != 'complete':
        return redirect(url_for('pair_status', pair_id=pair_id))

    # Hent sammenligning via eksisterende compare_profiles funktion
    comparison = compare_profiles(
        pair['person_a_session_id'],
        pair['person_b_session_id']
    )

    if not comparison:
        flash('Kunne ikke generere sammenligning', 'error')
        return redirect(url_for('pair_status', pair_id=pair_id))

    return render_template(
        'profil/pair_compare.html',
        pair=pair,
        comparison=comparison
    )


# ========================================
# ADMIN ROUTES (til integration i admin_app)
# ========================================

@app.route('/profil/admin/')
def profil_admin_list():
    """Liste alle profiler"""
    sessions = list_sessions(include_incomplete=True)
    return render_template('profil/admin_list.html', sessions=sessions)


@app.route('/profil/compare/<session1>/<session2>')
def profil_compare(session1, session2):
    """Sammenlign to profiler"""
    comparison = compare_profiles(session1, session2)
    if not comparison:
        flash('En eller begge profiler ikke fundet', 'error')
        return redirect(url_for('profil_admin_list'))

    return render_template('profil/compare.html', comparison=comparison)


# ========================================
# TEST/DEMO ROUTES
# ========================================

@app.route('/profil/generate-test-data')
def profil_generate_test():
    """Generer testprofiler"""
    sessions = generate_test_profiles()
    return f"""
    <h1>Testprofiler oprettet</h1>
    <ul>
    {''.join(f"<li><a href='/profil/{s['session_id']}/report'>{s['name']}</a> - {s['description']}</li>" for s in sessions)}
    </ul>
    <p><a href="/profil/start">Start ny profil</a></p>
    """


@app.route('/profil/test-profiles')
def profil_test_list():
    """Vis liste over testprofiler"""
    sessions = list_sessions()
    test_sessions = [s for s in sessions if s.get('context') == 'test']

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Testprofiler</title>
        <style>
            body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
            h1 { color: #0f3460; }
            .profile-list { list-style: none; padding: 0; }
            .profile-list li {
                padding: 15px;
                margin: 10px 0;
                background: #f5f5f5;
                border-radius: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            a { color: #0f3460; }
            .btn {
                padding: 8px 16px;
                background: #0f3460;
                color: white;
                text-decoration: none;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <h1>Testprofiler</h1>
    """

    if test_sessions:
        html += "<ul class='profile-list'>"
        for s in test_sessions:
            html += f"""
            <li>
                <span>{s['person_name'] or 'Unavngivet'}</span>
                <a class="btn" href="/profil/{s['id']}/report">Se profil</a>
            </li>
            """
        html += "</ul>"
    else:
        html += """
        <p>Ingen testprofiler fundet.</p>
        <p><a href="/profil/generate-test-data">Generer testdata</a></p>
        """

    html += """
        <hr>
        <p><a href="/profil/start">Start ny profil</a></p>
    </body>
    </html>
    """
    return html


# ========================================
# MAIN
# ========================================

if __name__ == '__main__':
    print("=" * 50)
    print("Friktionsprofil kører på http://localhost:5003")
    print("=" * 50)
    print("\nEndpoints:")
    print("  /profil/start          - Start ny profil")
    print("  /profil/test-profiles  - Se testprofiler")
    print("  /profil/generate-test-data - Generer testdata")
    print()
    # Debug mode controlled by FLASK_DEBUG environment variable
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=5003)

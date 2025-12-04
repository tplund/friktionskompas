"""
Admin interface for Friktionskompasset v3
Hierarkisk organisationsstruktur med units + Multi-tenant
"""
from flask import Flask, render_template, request, redirect, url_for, flash, Response, session, jsonify
import csv
import io
import os
import secrets
from functools import wraps
from db_hierarchical import (
    init_db, create_unit, create_unit_from_path, create_campaign,
    generate_tokens_for_campaign, get_unit_children, get_unit_path,
    get_leaf_units, validate_and_use_token, save_response, get_unit_stats,
    get_campaign_overview, get_questions, get_db, add_contacts_bulk,
    get_unit_contacts
)
from analysis import (
    get_detailed_breakdown, check_anonymity_threshold,
    get_layer_interpretation, calculate_substitution,
    get_free_text_comments, get_kkc_recommendations,
    get_start_here_recommendation
)
from db_multitenant import (
    authenticate_user, create_customer, create_user, list_customers,
    list_users, get_customer_filter, init_multitenant_db, get_customer
)
from csv_upload_hierarchical import (
    validate_csv_format, bulk_upload_from_csv, generate_csv_template
)
from mailjet_integration import (
    send_campaign_batch, get_email_stats, get_email_logs, update_email_status,
    get_template, save_template, list_templates, DEFAULT_TEMPLATES
)
from db_hierarchical import init_db
from db_profil import (
    init_profil_tables, get_all_questions as get_profil_questions,
    get_db as get_profil_db
)

# Initialize databases
init_db()  # Main hierarchical database
init_profil_tables()  # Profil tables
init_multitenant_db()  # Multi-tenant tables

app = Flask(__name__)

# Sikker secret key fra miljøvariabel (fallback til autogeneret i development)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)


@app.context_processor
def inject_customers():
    """Gør kundeliste tilgængelig i alle templates"""
    customers = []
    if 'user' in session and session['user']['role'] == 'admin':
        with get_db() as conn:
            customers = conn.execute("""
                SELECT id, name
                FROM customers
                ORDER BY name
            """).fetchall()

    def get_score_class(score):
        """Return CSS class based on friction score (0-5 scale)"""
        if score is None:
            return 'score-none'
        if score > 3.5:
            return 'score-high'
        elif score >= 2.5:
            return 'score-medium'
        else:
            return 'score-low'

    def get_percent_class(score):
        """Return CSS class based on friction score as percent"""
        if score is None:
            return 'score-none'
        percent = (score / 5) * 100
        if percent > 70:
            return 'score-high'
        elif percent >= 50:
            return 'score-medium'
        else:
            return 'score-low'

    def get_gap_class(employee_score, leader_score):
        """Return CSS class and icon based on gap between employee and leader"""
        if employee_score is None or leader_score is None:
            return 'gap-none', ''
        gap = abs(employee_score - leader_score)
        if gap > 1.0:  # More than 1 point difference on 0-5 scale
            return 'gap-critical', '🚨'
        elif gap > 0.5:
            return 'gap-warning', '⚠️'
        else:
            return 'gap-ok', '✓'

    def to_percent(score):
        """Convert 0-5 score to percent"""
        if score is None:
            return None
        return (score / 5) * 100

    return dict(
        customers=customers,
        get_score_class=get_score_class,
        get_percent_class=get_percent_class,
        get_gap_class=get_gap_class,
        to_percent=to_percent
    )


def login_required(f):
    """Decorator til at kræve login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Du skal være logget ind for at se denne side', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator til at kræve admin rolle"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Du skal være logget ind', 'error')
            return redirect(url_for('login'))
        if session['user']['role'] != 'admin':
            flash('Kun admin har adgang til denne side', 'error')
            return redirect(url_for('analyser'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Hent current user fra session"""
    return session.get('user')


@app.route('/')
def index():
    """Root route - redirect til login eller admin"""
    if 'user' in session:
        return redirect(url_for('analyser'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login side"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = authenticate_user(username, password)

        if user:
            session['user'] = user
            flash(f'Velkommen {user["name"]}!', 'success')
            return redirect(url_for('analyser'))
        else:
            flash('Forkert brugernavn eller password', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    session.pop('user', None)
    flash('Du er nu logget ud', 'success')
    return redirect(url_for('login'))


@app.route('/admin/delete-all-data', methods=['POST'])
@admin_required
def delete_all_data():
    """Slet ALLE data - kun for admin"""
    confirm = request.form.get('confirm')
    if confirm != 'SLET ALT':
        flash('Du skal skrive "SLET ALT" for at bekræfte', 'error')
        return redirect(url_for('admin_home'))

    with get_db() as conn:
        # Slet i rigtig rækkefølge pga foreign keys
        conn.execute("DELETE FROM responses")
        conn.execute("DELETE FROM tokens")
        conn.execute("DELETE FROM campaigns")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM organizational_units")
        conn.execute("DELETE FROM questions WHERE is_default = 0")  # Behold default spørgsmål

    flash('Alle data er slettet!', 'success')
    return redirect(url_for('admin_home'))


@app.route('/admin/generate-test-data', methods=['POST'])
@admin_required
def generate_test_data():
    """Generer testdata - organisationer, kontakter, kampagner og svar"""
    import random
    from db_hierarchical import create_campaign, get_questions, get_all_leaf_units_under

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
        where_clause, params = get_customer_filter(user['role'], user['customer_id'])
        top_units = conn.execute(f"""
            SELECT id, name, full_path
            FROM organizational_units
            WHERE parent_id IS NULL {where_clause}
        """, params).fetchall()

        # Hent alle spørgsmål
        questions = get_questions()

        campaigns_created = 0
        responses_created = 0

        # Opret kampagner for hver top-level organisation
        for unit in top_units:
            # Opret 2 kampagner per organisation (Q1 og Q2 2024)
            for quarter, period in [("Q1", "2024 Q1"), ("Q2", "2024 Q2")]:
                campaign_id = create_campaign(
                    target_unit_id=unit['id'],
                    name=f"{unit['name']} - {period}",
                    period=period,
                    sent_from='admin'
                )
                campaigns_created += 1

                # Find alle leaf units under denne organisation
                leaf_units = get_all_leaf_units_under(unit['id'])

                # Generer svar for hver leaf unit
                for leaf_unit in leaf_units:
                    # Simuler at 70-90% af medarbejdere svarer
                    response_rate = random.uniform(0.7, 0.9)
                    num_responses = max(1, int(leaf_unit['employee_count'] * response_rate))

                    for _ in range(num_responses):
                        # Generer realistiske svar for hvert spørgsmål
                        for question in questions:
                            # Generer score baseret på felt (nogle felter scorer højere end andre)
                            if question['field'] == 'Samarbejde':
                                # Samarbejde scorer generelt godt (3-5)
                                score = random.choices([3, 4, 5], weights=[0.2, 0.4, 0.4])[0]
                            elif question['field'] == 'Engagement':
                                # Engagement er middel (2-5)
                                score = random.choices([2, 3, 4, 5], weights=[0.15, 0.35, 0.35, 0.15])[0]
                            elif question['field'] == 'Innovation':
                                # Innovation lidt lavere (2-4)
                                score = random.choices([2, 3, 4], weights=[0.3, 0.5, 0.2])[0]
                            else:  # Performance
                                # Performance middel-høj (3-5)
                                score = random.choices([3, 4, 5], weights=[0.3, 0.4, 0.3])[0]

                            conn.execute("""
                                INSERT INTO responses (campaign_id, unit_id, question_id, score)
                                VALUES (?, ?, ?, ?)
                            """, (campaign_id, leaf_unit['id'], question['id'], score))
                            responses_created += 1

    flash(f'Testdata genereret! {stats["units_created"]} organisationer, {stats["contacts_created"]} kontakter, {campaigns_created} målinger og {responses_created} svar oprettet.', 'success')
    return redirect(url_for('admin_home'))


@app.route('/admin')
@login_required
def admin_home():
    """Admin forside - vis organisationstræ"""
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

            campaign_count = conn.execute("""
                SELECT COUNT(DISTINCT c.id) as cnt
                FROM campaigns c
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

            campaign_count = conn.execute("SELECT COUNT(*) as cnt FROM campaigns").fetchone()['cnt']

        # Hent customer info - altid
        customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
        customers_dict = {c['id']: c['name'] for c in customers}

    return render_template('admin/home.html',
                         units=[dict(u) for u in all_units],
                         campaign_count=campaign_count,
                         show_all_customers=(user['role'] == 'admin'),
                         customers_dict=customers_dict,
                         current_filter=session.get('customer_filter'),
                         current_filter_name=session.get('customer_filter_name'))


@app.route('/admin/campaigns-overview')
@login_required
def campaigns_overview():
    """Oversigt over alle analyser/kampagner"""
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'])

    with get_db() as conn:
        # Hent alle campaigns med stats
        if user['role'] == 'admin':
            campaigns = conn.execute("""
                SELECT
                    c.*,
                    ou.name as target_name,
                    COALESCE(COUNT(DISTINCT t.token), 0) as tokens_sent,
                    COALESCE(COUNT(DISTINCT CASE WHEN t.is_used = 1 THEN t.token END), 0) as tokens_used,
                    COUNT(DISTINCT r.respondent_name) as unique_respondents,
                    COUNT(DISTINCT r.id) as total_responses,
                    AVG(CASE
                        WHEN q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                    END) as avg_besvaer
                FROM campaigns c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                LEFT JOIN tokens t ON c.id = t.campaign_id
                LEFT JOIN responses r ON c.id = r.campaign_id
                LEFT JOIN questions q ON r.question_id = q.id
                GROUP BY c.id
                ORDER BY c.created_at DESC
            """).fetchall()
        else:
            # Manager ser kun kampagner for sine units
            campaigns = conn.execute("""
                SELECT
                    c.*,
                    ou.name as target_name,
                    COALESCE(COUNT(DISTINCT t.token), 0) as tokens_sent,
                    COALESCE(COUNT(DISTINCT CASE WHEN t.is_used = 1 THEN t.token END), 0) as tokens_used,
                    COUNT(DISTINCT r.respondent_name) as unique_respondents,
                    COUNT(DISTINCT r.id) as total_responses,
                    AVG(CASE
                        WHEN q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                    END) as avg_besvaer
                FROM campaigns c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                LEFT JOIN tokens t ON c.id = t.campaign_id
                LEFT JOIN responses r ON c.id = r.campaign_id
                LEFT JOIN questions q ON r.question_id = q.id
                WHERE ou.customer_id = ?
                GROUP BY c.id
                ORDER BY c.created_at DESC
            """, [user['customer_id']]).fetchall()

    return render_template('admin/campaigns_overview.html',
                         campaigns=[dict(c) for c in campaigns])


@app.route('/admin/analyser')
@login_required
def analyser():
    """Analyser: Aggregeret friktionsdata på tværs af organisationen"""
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'])

    # Get filter parameters
    campaign_id = request.args.get('campaign_id', type=int)
    sort_by = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')

    with get_db() as conn:
        # Get available campaigns for filtering
        if user['role'] == 'admin':
            campaigns = conn.execute("""
                SELECT id, name, period
                FROM campaigns
                ORDER BY created_at DESC
            """).fetchall()
        else:
            campaigns = conn.execute("""
                SELECT DISTINCT c.id, c.name, c.period
                FROM campaigns c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
                ORDER BY c.created_at DESC
            """, [user['customer_id']]).fetchall()

        # Build query for unit friction scores with leader/employee comparison
        query = """
            SELECT
                ou.id,
                ou.name,
                ou.full_path,
                ou.level,
                c.id as campaign_id,
                COUNT(DISTINCT r.id) as total_responses,
                COUNT(DISTINCT r.respondent_name) as unique_respondents,

                -- Employee scores
                AVG(CASE
                    WHEN r.respondent_type = 'employee' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_overall,

                AVG(CASE
                    WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_mening,

                AVG(CASE
                    WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_tryghed,

                AVG(CASE
                    WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_kan,

                AVG(CASE
                    WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_besvaer,

                -- Leader assessment scores
                AVG(CASE
                    WHEN r.respondent_type = 'leader_assess' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as leader_overall,

                AVG(CASE
                    WHEN r.respondent_type = 'leader_assess' AND q.field = 'MENING' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as leader_mening,

                AVG(CASE
                    WHEN r.respondent_type = 'leader_assess' AND q.field = 'TRYGHED' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as leader_tryghed,

                AVG(CASE
                    WHEN r.respondent_type = 'leader_assess' AND q.field = 'KAN' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as leader_kan,

                AVG(CASE
                    WHEN r.respondent_type = 'leader_assess' AND q.field = 'BESVÆR' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as leader_besvaer

            FROM organizational_units ou
            LEFT JOIN campaigns c ON c.target_unit_id = ou.id
            LEFT JOIN responses r ON c.id = r.campaign_id
            LEFT JOIN questions q ON r.question_id = q.id
        """

        # Add filters
        conditions = []
        query_params = []

        if user['role'] != 'admin':
            conditions.append("ou.customer_id = ?")
            query_params.append(user['customer_id'])

        if campaign_id:
            conditions.append("c.id = ?")
            query_params.append(campaign_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            GROUP BY ou.id, ou.name, ou.full_path, ou.level, c.id
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

        # Beregn indikatorer for hver unit
        enriched_units = []
        for unit in units:
            unit_dict = dict(unit)

            # Beregn substitution
            substitution = calculate_substitution(unit['id'], unit['campaign_id'], 'employee')
            unit_dict['has_substitution'] = substitution.get('flagged', False)

            # Beregn leader gap (forskel mellem leder vurdering og medarbejdere)
            max_gap = 0
            if unit['employee_overall'] and unit['leader_overall']:
                for field in ['mening', 'tryghed', 'kan', 'besvaer']:
                    emp_key = f'employee_{field}'
                    leader_key = f'leader_{field}'
                    if unit[emp_key] and unit[leader_key]:
                        gap = abs(unit[emp_key] - unit[leader_key])
                        if gap > max_gap:
                            max_gap = gap
            unit_dict['has_leader_gap'] = max_gap > 1.0

            # Beregn leader blocked (lederens egne friktioner blokerer)
            # Vi behøver leader_self scores - lad os hente dem
            leader_self_scores = conn.execute("""
                SELECT
                    AVG(CASE
                        WHEN r.respondent_type = 'leader_self' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                    END) as leader_self_mening,
                    AVG(CASE
                        WHEN r.respondent_type = 'leader_self' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                    END) as leader_self_tryghed,
                    AVG(CASE
                        WHEN r.respondent_type = 'leader_self' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                    END) as leader_self_kan,
                    AVG(CASE
                        WHEN r.respondent_type = 'leader_self' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                    END) as leader_self_besvaer
                FROM responses r
                JOIN questions q ON r.question_id = q.id
                WHERE r.unit_id = ? AND r.campaign_id = ?
            """, (unit['id'], unit['campaign_id'])).fetchone()

            leader_blocked = False
            if leader_self_scores:
                for field in ['mening', 'tryghed', 'kan', 'besvaer']:
                    emp_score = unit[f'employee_{field}']
                    leader_self_score = leader_self_scores[f'leader_self_{field}']
                    # Hvis BÅDE medarbejdere OG leder selv har høje friktioner (under 70%)
                    if emp_score and leader_self_score and emp_score < 3.5 and leader_self_score < 3.5:
                        leader_blocked = True
                        break
            unit_dict['has_leader_blocked'] = leader_blocked

            enriched_units.append(unit_dict)

    return render_template('admin/analyser.html',
                         units=enriched_units,
                         campaigns=[dict(c) for c in campaigns],
                         current_campaign=campaign_id,
                         sort_by=sort_by,
                         sort_order=sort_order)


@app.route('/admin/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload():
    """Bulk upload af units fra CSV med hierarkisk struktur"""
    user = get_current_user()

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('❌ Ingen fil uploaded', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('❌ Ingen fil valgt', 'error')
            return redirect(request.url)

        # Læs fil
        content = file.stream.read().decode('UTF-8')

        # Valider først
        validation = validate_csv_format(content)
        if not validation['valid']:
            for error in validation['errors']:
                flash(f"❌ {error}", 'error')
            return redirect(request.url)

        # Vis advarsler
        for warning in validation['warnings']:
            flash(f"⚠️ {warning}", 'warning')

        # Upload med customer_id
        stats = bulk_upload_from_csv(content, customer_id=user['customer_id'])

        if stats['errors']:
            for error in stats['errors']:
                flash(f"⚠️ {error}", 'warning')

        flash(f"{stats['units_created']} organisationer oprettet! {stats['contacts_created']} kontakter tilføjet.", 'success')
        return redirect(url_for('admin_home'))

    # GET: Vis upload form
    return render_template('admin/bulk_upload.html')


@app.route('/admin/csv-template')
@login_required
def download_csv_template():
    """Download CSV skabelon"""
    template = generate_csv_template()
    return Response(
        template,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=friktionskompas_skabelon.csv'}
    )


@app.route('/admin/generate-test-csv')
@login_required
def generate_test_csv():
    """Generer test CSV med realistic organisationer - Excel-kompatibelt format"""
    import csv
    import io

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


@app.route('/admin/unit/<unit_id>')
@login_required
def view_unit(unit_id):
    """Vis unit med children og kampagner"""
    user = get_current_user()

    with get_db() as conn:
        # Hent unit med customer filter
        where_clause, params = get_customer_filter(user['role'], user['customer_id'])
        unit = conn.execute(
            f"SELECT * FROM organizational_units ou WHERE ou.id = ? AND ({where_clause})",
            [unit_id] + params
        ).fetchone()

        if not unit:
            flash("Unit ikke fundet eller ingen adgang", 'error')
            return redirect(url_for('admin_home'))

        # Hent kontakter
        contacts = conn.execute(
            "SELECT * FROM contacts WHERE unit_id = ?",
            (unit_id,)
        ).fetchall()

    # Breadcrumbs
    breadcrumbs = get_unit_path(unit_id)

    # Direct children
    children = get_unit_children(unit_id, recursive=False)

    # Leaf units under dette (for campaigns)
    leaf_units = get_leaf_units(unit_id)

    # Kampagner rettet mod denne unit
    with get_db() as conn:
        campaigns = conn.execute("""
            SELECT c.*,
                   COUNT(DISTINCT t.token) as tokens_sent,
                   SUM(CASE WHEN t.is_used = 1 THEN 1 ELSE 0 END) as tokens_used
            FROM campaigns c
            LEFT JOIN tokens t ON c.id = t.campaign_id
            WHERE c.target_unit_id = ?
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, (unit_id,)).fetchall()

    return render_template('admin/view_unit.html',
        unit=dict(unit),
        breadcrumbs=breadcrumbs,
        children=children,
        leaf_units=leaf_units,
        campaigns=[dict(c) for c in campaigns],
        contacts=[dict(c) for c in contacts])


@app.route('/admin/unit/new', methods=['GET', 'POST'])
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
        return redirect(url_for('view_unit', unit_id=unit_id))

    # GET: Vis form - kun vis units fra samme customer
    # Check if parent_id is provided in query parameter
    default_parent_id = request.args.get('parent')

    where_clause, params = get_customer_filter(user['role'], user['customer_id'])
    with get_db() as conn:
        # Alle units til parent dropdown (filtreret efter customer)
        all_units = conn.execute(f"""
            SELECT id, name, full_path, level
            FROM organizational_units
            WHERE {where_clause}
            ORDER BY full_path
        """, params).fetchall()

    return render_template('admin/new_unit.html',
                         all_units=[dict(u) for u in all_units],
                         default_parent_id=default_parent_id)


@app.route('/admin/unit/<unit_id>/contacts/upload', methods=['POST'])
@login_required
def upload_contacts(unit_id):
    """Upload kontakter fra CSV"""
    if 'file' not in request.files:
        flash('❌ Ingen fil uploaded', 'error')
        return redirect(url_for('view_unit', unit_id=unit_id))

    file = request.files['file']
    if file.filename == '':
        flash('❌ Ingen fil valgt', 'error')
        return redirect(url_for('view_unit', unit_id=unit_id))

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

    flash(f'✅ {len(contacts)} kontakter uploaded!', 'success')
    return redirect(url_for('view_unit', unit_id=unit_id))


@app.route('/admin/unit/<unit_id>/sick_leave', methods=['POST'])
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
    return redirect(url_for('view_unit', unit_id=unit_id))


@app.route('/admin/unit/<unit_id>/delete', methods=['POST'])
@login_required
def delete_unit(unit_id):
    """Slet organisation og alle dens children"""
    user = get_current_user()

    with get_db() as conn:
        # Check access rights
        where_clause, params = get_customer_filter(user['role'], user['customer_id'])
        unit = conn.execute(
            f"SELECT * FROM organizational_units ou WHERE ou.id = ? AND ({where_clause})",
            [unit_id] + params
        ).fetchone()

        if not unit:
            flash('Organisation ikke fundet eller ingen adgang', 'error')
            return redirect(url_for('admin_home'))

        unit_name = unit['name']

        # SQLite cascade delete vil slette alle children automatisk
        # pga. ON DELETE CASCADE i foreign key constraints
        conn.execute("DELETE FROM organizational_units WHERE id = ?", (unit_id,))

    flash(f'Organisation "{unit_name}" og alle underorganisationer er slettet', 'success')
    return redirect(url_for('admin_home'))


@app.route('/admin/units/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_units():
    """Slet flere organisationer på én gang"""
    user = get_current_user()

    if user['role'] != 'admin':
        flash('Kun administratorer kan bulk-slette', 'error')
        return redirect(url_for('admin_home'))

    import json
    unit_ids_json = request.form.get('unit_ids', '[]')
    try:
        unit_ids = json.loads(unit_ids_json)
    except:
        flash('Ugyldige unit IDs', 'error')
        return redirect(url_for('admin_home'))

    if not unit_ids:
        flash('Ingen organisationer valgt', 'warning')
        return redirect(url_for('admin_home'))

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
    return redirect(url_for('admin_home'))


@app.route('/admin/campaign/new', methods=['GET', 'POST'])
@login_required
def new_campaign():
    """Opret og send ny kampagne"""
    user = get_current_user()

    if request.method == 'POST':
        target_unit_id = request.form['target_unit_id']
        name = request.form['name']
        period = request.form['period']
        sent_from = request.form.get('sent_from', 'admin')
        sender_name = request.form.get('sender_name', 'HR')

        # Opret kampagne
        campaign_id = create_campaign(
            target_unit_id=target_unit_id,
            name=name,
            period=period,
            sent_from=sent_from
        )

        # Generer tokens for alle leaf units
        tokens_by_unit = generate_tokens_for_campaign(campaign_id)

        # Send til hver unit
        total_sent = 0
        for unit_id, tokens in tokens_by_unit.items():
            contacts = get_unit_contacts(unit_id)
            if not contacts:
                continue

            # Match tokens med kontakter
            results = send_campaign_batch(contacts, tokens, name, sender_name)
            total_sent += results['emails_sent'] + results['sms_sent']

        flash(f'✅ Måling sendt! {sum(len(t) for t in tokens_by_unit.values())} tokens genereret, {total_sent} sendt.', 'success')
        return redirect(url_for('view_campaign', campaign_id=campaign_id))

    # GET: Vis form - kun units fra samme customer
    where_clause, params = get_customer_filter(user['role'], user['customer_id'])
    with get_db() as conn:
        # Alle units til dropdown (filtreret efter customer)
        units = conn.execute(f"""
            SELECT ou.id, ou.name, ou.full_path, ou.level, ou.employee_count
            FROM organizational_units ou
            WHERE {where_clause}
            ORDER BY ou.full_path
        """, params).fetchall()

    return render_template('admin/new_campaign.html',
                         units=[dict(u) for u in units])


@app.route('/admin/campaign/<campaign_id>')
@login_required
def view_campaign(campaign_id):
    """Se kampagne resultater"""
    user = get_current_user()

    with get_db() as conn:
        # Hent campaign med customer filter
        where_clause, params = get_customer_filter(user['role'], user['customer_id'])
        campaign = conn.execute(f"""
            SELECT c.* FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ? AND ({where_clause})
        """, [campaign_id] + params).fetchone()

        if not campaign:
            flash("Måling ikke fundet eller ingen adgang", 'error')
            return redirect(url_for('admin_home'))

    # Target unit info
    target_unit_id = campaign['target_unit_id']
    breadcrumbs = get_unit_path(target_unit_id)

    # Overview af alle leaf units
    overview = get_campaign_overview(campaign_id)

    # Aggregeret stats for target unit (inkl. children)
    aggregate_stats = get_unit_stats(
        unit_id=target_unit_id,
        campaign_id=campaign_id,
        include_children=True
    )

    # Total tokens sendt/brugt
    with get_db() as conn:
        token_stats = conn.execute("""
            SELECT
                COUNT(*) as tokens_sent,
                SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as tokens_used
            FROM tokens
            WHERE campaign_id = ?
        """, (campaign_id,)).fetchone()

    return render_template('admin/view_campaign.html',
        campaign=dict(campaign),
        target_breadcrumbs=breadcrumbs,
        overview=overview,
        aggregate_stats=aggregate_stats,
        token_stats=dict(token_stats))


@app.route('/admin/customers')
@admin_required
def manage_customers():
    """Customer management - kun admin"""
    customers = list_customers()
    users = list_users()  # Alle users
    return render_template('admin/customers.html',
                         customers=customers,
                         users=users)


@app.route('/admin/customer/new', methods=['POST'])
@admin_required
def create_new_customer():
    """Opret ny customer - kun admin"""
    name = request.form['name']
    contact_email = request.form.get('contact_email')

    customer_id = create_customer(name, contact_email)

    flash(f'Customer "{name}" oprettet!', 'success')
    return redirect(url_for('manage_customers'))


@app.route('/admin/user/new', methods=['POST'])
@admin_required
def create_new_user():
    """Opret ny bruger - kun admin"""
    username = request.form['username']
    password = request.form['password']
    name = request.form['name']
    email = request.form.get('email')
    role = request.form['role']
    customer_id = request.form.get('customer_id') or None

    try:
        user_id = create_user(username, password, name, email, role, customer_id)
        flash(f'Bruger "{username}" oprettet!', 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('manage_customers'))


@app.route('/admin/impersonate/<customer_id>')
@admin_required
def impersonate_customer(customer_id):
    """Filter data to specific customer while staying in admin view"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('manage_customers'))

    # Store filter in session - but keep admin role!
    session['customer_filter'] = customer_id
    session['customer_filter_name'] = customer['name']

    flash(f'Viser kun data for: {customer["name"]}', 'success')
    return redirect(url_for('admin_home'))


@app.route('/admin/stop-impersonate')
@login_required
def stop_impersonate():
    """Clear customer filter - show all data"""
    session.pop('customer_filter', None)
    session.pop('customer_filter_name', None)
    # Also clear old impersonating data if present
    if 'original_user' in session:
        session['user'] = session.pop('original_user')
    session.pop('impersonating', None)
    flash('Viser alle kunder', 'success')

    return redirect(url_for('admin_home'))


@app.route('/admin/view/<view_mode>')
@admin_required
def switch_view_mode(view_mode):
    """Switch mellem user/manager/admin visning"""
    if view_mode not in ['user', 'manager', 'admin']:
        flash('Ugyldig visning', 'error')
        return redirect(url_for('admin_home'))

    session['view_mode'] = view_mode

    # Redirect baseret på view mode
    if view_mode == 'user':
        # Brugervisning - vis spørgeskema (vi skal have en token først)
        return redirect(url_for('user_view_survey'))
    elif view_mode == 'manager':
        # Managervisning - vis dashboard
        return redirect(url_for('manager_dashboard'))
    else:
        # Adminvisning - normal admin home
        return redirect(url_for('admin_home'))


@app.route('/admin/user-view/survey')
@login_required
def user_view_survey():
    """Brugervisning - vis links til preview"""
    # Brug preview mode i stedet for tokens
    base_url = "http://localhost:5002/preview?type="

    employee_url = base_url + "employee"
    leader_assess_url = base_url + "leader_assess"
    leader_self_url = base_url + "leader_self"

    return render_template('admin/user_view.html',
                         employee_url=employee_url,
                         leader_assess_url=leader_assess_url,
                         leader_self_url=leader_self_url)


@app.route('/admin/manager-view/dashboard')
@login_required
def manager_dashboard():
    """Managervisning - vis aggregeret dashboard"""
    user = get_current_user()

    # Hent alle top-level units (for admin) eller kun customer units (for manager)
    where_clause, params = get_customer_filter(user['role'], user['customer_id'])

    with get_db() as conn:
        # Hent organisationer
        units = conn.execute(f"""
            SELECT
                ou.*,
                COUNT(DISTINCT children.id) as child_count
            FROM organizational_units ou
            LEFT JOIN organizational_units children ON children.parent_id = ou.id
            WHERE ou.parent_id IS NULL AND ({where_clause})
            GROUP BY ou.id
            ORDER BY ou.name
        """, params).fetchall()

        # Hent kampagner
        campaigns = conn.execute(f"""
            SELECT c.*, ou.name as unit_name
            FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE {where_clause}
            ORDER BY c.created_at DESC
            LIMIT 10
        """, params).fetchall()

    return render_template('manager_dashboard.html',
                         units=[dict(u) for u in units],
                         campaigns=[dict(c) for c in campaigns])


@app.route('/admin/unit/<unit_id>/dashboard')
@login_required
def unit_dashboard(unit_id):
    """Unit dashboard med aggregeret data"""
    user = get_current_user()

    with get_db() as conn:
        # Hent unit med customer filter
        where_clause, params = get_customer_filter(user['role'], user['customer_id'])
        unit = conn.execute(
            f"SELECT * FROM organizational_units ou WHERE ou.id = ? AND ({where_clause})",
            [unit_id] + params
        ).fetchone()

        if not unit:
            flash("Unit ikke fundet eller ingen adgang", 'error')
            return redirect(url_for('admin_home'))

        # Find seneste kampagne for denne unit
        latest_campaign = conn.execute("""
            SELECT * FROM campaigns
            WHERE target_unit_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (unit_id,)).fetchone()

    if not latest_campaign:
        flash('❌ Ingen målinger endnu', 'error')
        return redirect(url_for('view_unit', unit_id=unit_id))

    # Breadcrumbs
    breadcrumbs = get_unit_path(unit_id)

    # Overview af leaf units
    overview = get_campaign_overview(latest_campaign['id'])

    return render_template('admin/unit_dashboard.html',
                         unit=dict(unit),
                         breadcrumbs=breadcrumbs,
                         campaign=dict(latest_campaign),
                         units=overview)


def get_individual_scores(target_unit_id, campaign_id):
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
        # Use respondent_name as identifier (or a hash of unit+created_at if anonymous)
        employee_query = f"""
        {subtree_cte}
        SELECT
            COALESCE(r.respondent_name, CAST(r.id AS TEXT)) as resp_key,
            q.field,
            AVG(CASE
                WHEN q.reverse_scored = 1 THEN 6 - r.score
                ELSE r.score
            END) as avg_score
        FROM responses r
        JOIN questions q ON r.question_id = q.id
        JOIN subtree ON r.unit_id = subtree.id
        WHERE r.campaign_id = ?
          AND r.respondent_type = 'employee'
          AND q.field IN ('MENING', 'TRYGHED', 'KAN', 'BESVÆR')
        GROUP BY resp_key, q.field
        """

        employee_rows = conn.execute(employee_query, [target_unit_id, campaign_id]).fetchall()

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
        WHERE r.campaign_id = ?
          AND r.respondent_type = 'leader_self'
          AND q.field IN ('MENING', 'TRYGHED', 'KAN', 'BESVÆR')
        GROUP BY q.field
        """

        leader_rows = conn.execute(leader_query, [target_unit_id, campaign_id]).fetchall()

        leader = {}
        for row in leader_rows:
            leader[row['field']] = row['avg_score']

        return {
            'employees': employee_list,
            'leader': leader if len(leader) == 4 else None
        }


@app.route('/admin/campaign/<campaign_id>/detailed')
@login_required
def campaign_detailed_analysis(campaign_id):
    """Detaljeret analyse med lagdeling og respondent-sammenligning"""
    import traceback
    user = get_current_user()

    try:
        with get_db() as conn:
            # Hent campaign - admin ser alt
            if user['role'] == 'admin':
                campaign = conn.execute("""
                    SELECT c.*, ou.customer_id FROM campaigns c
                    JOIN organizational_units ou ON c.target_unit_id = ou.id
                    WHERE c.id = ?
                """, [campaign_id]).fetchone()
            else:
                campaign = conn.execute("""
                    SELECT c.*, ou.customer_id FROM campaigns c
                    JOIN organizational_units ou ON c.target_unit_id = ou.id
                    WHERE c.id = ? AND ou.customer_id = ?
                """, [campaign_id, user['customer_id']]).fetchone()

            if not campaign:
                flash("Måling ikke fundet eller ingen adgang", 'error')
                return redirect(url_for('admin_home'))

        target_unit_id = campaign['target_unit_id']
        campaign_customer_id = campaign['customer_id']

        # Check anonymity
        anonymity = check_anonymity_threshold(campaign_id, target_unit_id)

        if not anonymity.get('can_show_results'):
            flash(f"Ikke nok svar endnu. {anonymity.get('response_count', 0)} af {anonymity.get('min_required', 5)} modtaget.", 'warning')
            return redirect(url_for('view_campaign', campaign_id=campaign_id))

        # Get detailed breakdown
        breakdown = get_detailed_breakdown(target_unit_id, campaign_id, include_children=True)

        # Calculate substitution (tid-bias)
        substitution = calculate_substitution(target_unit_id, campaign_id, 'employee')

        # Add has_substitution flag and count for template
        substitution['has_substitution'] = substitution.get('flagged', False) and substitution.get('flagged_count', 0) > 0
        substitution['count'] = substitution.get('flagged_count', 0)

        # Get free text comments
        free_text_comments = get_free_text_comments(target_unit_id, campaign_id, include_children=True)

        # Get KKC recommendations
        employee_stats = breakdown.get('employee', {})
        comparison = breakdown.get('comparison', {})
        kkc_recommendations = get_kkc_recommendations(employee_stats, comparison)
        start_here = get_start_here_recommendation(kkc_recommendations)

        # Get alerts and findings
        from analysis import get_alerts_and_findings
        alerts = get_alerts_and_findings(breakdown, comparison, substitution)

        # Get individual scores for radar chart
        individual_scores = get_individual_scores(target_unit_id, campaign_id)

        # Breadcrumbs
        breadcrumbs = get_unit_path(target_unit_id)

        # Get last response date
        with get_db() as conn:
            last_response = conn.execute("""
                SELECT MAX(created_at) as last_date
                FROM responses
                WHERE campaign_id = ? AND created_at IS NOT NULL
            """, [campaign_id]).fetchone()

            last_response_date = None
            if last_response and last_response['last_date']:
                from datetime import datetime
                dt = datetime.fromisoformat(last_response['last_date'])
                last_response_date = dt.strftime('%d-%m-%Y')

        return render_template('admin/campaign_detailed.html',
            campaign=dict(campaign),
            target_breadcrumbs=breadcrumbs,
            breakdown=breakdown,
            anonymity=anonymity,
            substitution=substitution,
            free_text_comments=free_text_comments,
            kkc_recommendations=kkc_recommendations,
            start_here=start_here,
            alerts=alerts,
            last_response_date=last_response_date,
            current_customer_id=campaign_customer_id,
            individual_scores=individual_scores
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"<h1>Fejl i campaign_detailed_analysis</h1><pre>{error_details}</pre>", 500


# ========================================
# FRIKTIONSPROFIL ROUTES
# ========================================

from db_profil import (
    init_profil_tables,
    create_session as create_profil_session,
    get_session as get_profil_session,
    complete_session as complete_profil_session,
    get_questions_by_field as get_profil_questions_by_field,
    save_responses as save_profil_responses,
    list_sessions as list_profil_sessions,
    generate_test_profiles
)
from analysis_profil import (
    get_full_analysis as get_profil_analysis,
    compare_profiles as compare_profil_profiles
)

# Initialize profil tables
init_profil_tables()


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

    # Hent customer_id fra session hvis bruger er logget ind
    customer_id = None
    if 'user' in session:
        customer_id = session['user'].get('customer_id')

    session_id = create_profil_session(
        person_name=name,
        person_email=email,
        context=context,
        customer_id=customer_id
    )

    return redirect(url_for('profil_survey', session_id=session_id))


@app.route('/profil/<session_id>')
def profil_survey(session_id):
    """Vis spørgeskema"""
    profil_session = get_profil_session(session_id)
    if not profil_session:
        flash('Session ikke fundet', 'error')
        return redirect(url_for('profil_start'))

    if profil_session['is_complete']:
        return redirect(url_for('profil_report', session_id=session_id))

    questions_by_field = get_profil_questions_by_field()

    return render_template(
        'profil/survey.html',
        session_id=session_id,
        session=profil_session,
        questions_by_field=questions_by_field
    )


@app.route('/profil/<session_id>/submit', methods=['POST'])
def profil_submit(session_id):
    """Modtag svar og gem"""
    profil_session = get_profil_session(session_id)
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
    save_profil_responses(session_id, responses)

    # Marker som færdig
    complete_profil_session(session_id)

    return redirect(url_for('profil_report', session_id=session_id))


@app.route('/profil/<session_id>/report')
def profil_report(session_id):
    """Vis rapport"""
    analysis = get_profil_analysis(session_id)
    if not analysis:
        flash('Profil ikke fundet', 'error')
        return redirect(url_for('profil_start'))

    # Tilføj screening-resultater
    from screening_profil import screen_profil
    screening = screen_profil(session_id)

    return render_template(
        'profil/report.html',
        session=analysis['session'],
        score_matrix=analysis['score_matrix'],
        color_matrix=analysis['color_matrix'],
        columns=analysis['columns'],
        summary=analysis['summary'],
        interpretations=analysis['interpretations'],
        screening=screening
    )


@app.route('/admin/profiler')
@login_required
def profil_admin_list():
    """Liste alle profiler"""
    user = session['user']

    # Filter på customer hvis ikke admin
    customer_id = None
    if user['role'] != 'admin':
        customer_id = user.get('customer_id')

    sessions = list_profil_sessions(customer_id=customer_id, include_incomplete=True)
    return render_template('profil/admin_list.html', sessions=sessions)


@app.route('/profil/compare/<session1>/<session2>')
def profil_compare(session1, session2):
    """Sammenlign to profiler"""
    comparison = compare_profil_profiles(session1, session2)
    if not comparison:
        flash('En eller begge profiler ikke fundet', 'error')
        return redirect(url_for('profil_admin_list'))

    return render_template('profil/compare.html', comparison=comparison)


@app.route('/profil/generate-test-data')
def profil_generate_test():
    """Generer testprofiler"""
    sessions = generate_test_profiles()
    flash(f'Oprettet {len(sessions)} testprofiler', 'success')
    return redirect(url_for('profil_admin_list'))


@app.route('/admin/profil/invite', methods=['GET', 'POST'])
@login_required
def profil_invite():
    """Send profil-invitation via email"""
    if request.method == 'GET':
        return render_template('profil/invite.html')

    # POST - send invitation
    email = request.form.get('email', '').strip()
    name = request.form.get('name', '').strip() or None
    context = request.form.get('context', 'general')

    if not email:
        flash('Email er påkrævet', 'error')
        return redirect(url_for('profil_invite'))

    # Hent customer_id fra session
    customer_id = None
    if 'user' in session:
        customer_id = session['user'].get('customer_id')

    # Opret session
    session_id = create_profil_session(
        person_name=name,
        person_email=email,
        context=context,
        customer_id=customer_id
    )

    # Send invitation
    from mailjet_integration import send_profil_invitation
    sender_name = session['user'].get('name', 'HR')

    success = send_profil_invitation(
        to_email=email,
        session_id=session_id,
        person_name=name,
        context=context,
        sender_name=sender_name
    )

    if success:
        flash(f'Invitation sendt til {email}', 'success')
    else:
        flash(f'Kunne ikke sende email til {email} - profil oprettet manuelt', 'warning')

    return redirect(url_for('profil_admin_list'))


@app.route('/admin/profil/delete', methods=['POST'])
@login_required
def profil_delete():
    """Slet en eller flere profiler"""
    from db_profil import delete_sessions

    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({'success': False, 'error': 'Ingen profiler angivet'}), 400

    ids = data['ids']
    if not isinstance(ids, list) or len(ids) == 0:
        return jsonify({'success': False, 'error': 'Ingen profiler angivet'}), 400

    deleted = delete_sessions(ids)

    return jsonify({
        'success': True,
        'deleted': deleted
    })


# ========================================
# DOMAIN VERIFICATION
# ========================================

@app.route('/881785f5a46238616dba5c7ba38aa2c6.txt')
def mailjet_verification():
    """Mailjet domain verification file"""
    return '', 200, {'Content-Type': 'text/plain'}


# ========================================
# EMAIL TRACKING & WEBHOOK
# ========================================

@app.route('/admin/email-stats')
@login_required
def email_stats():
    """Vis email statistik og logs"""
    campaign_id = request.args.get('campaign_id')
    stats = get_email_stats(campaign_id)
    logs = get_email_logs(campaign_id, limit=100)
    return render_template('admin/email_stats.html', stats=stats, logs=logs, campaign_id=campaign_id)


@app.route('/api/email-stats')
@login_required
def api_email_stats():
    """API endpoint for email stats"""
    campaign_id = request.args.get('campaign_id')
    stats = get_email_stats(campaign_id)
    return jsonify(stats)


@app.route('/webhook/mailjet', methods=['POST'])
def mailjet_webhook():
    """Webhook endpoint for Mailjet events (delivery, open, click, bounce)"""
    events = request.get_json()
    if not events:
        return jsonify({'status': 'no data'}), 400

    for event in events:
        event_type = event.get('event')
        message_id = str(event.get('MessageID', ''))

        if event_type == 'sent':
            update_email_status(message_id, 'delivered', 'delivered_at')
        elif event_type == 'open':
            update_email_status(message_id, 'opened', 'opened_at')
        elif event_type == 'click':
            update_email_status(message_id, 'clicked', 'clicked_at')
        elif event_type in ('bounce', 'blocked', 'spam'):
            update_email_status(message_id, 'bounced', 'bounced_at')

    return jsonify({'status': 'ok'})


# ========================================
# EMAIL TEMPLATES
# ========================================

@app.route('/admin/email-templates')
@login_required
def email_templates():
    """Email template editor"""
    user = get_current_user()
    with get_db() as conn:
        if user['role'] == 'admin':
            customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
        else:
            customers = conn.execute(
                "SELECT id, name FROM customers WHERE id = ?",
                [user['customer_id']]
            ).fetchall()

    selected_customer = request.args.get('customer_id', type=int)
    return render_template('admin/email_templates.html',
                         customers=customers,
                         selected_customer=selected_customer,
                         default_templates=DEFAULT_TEMPLATES)


@app.route('/api/email-templates')
@login_required
def api_list_templates():
    """API: List templates for a customer"""
    customer_id = request.args.get('customer_id', type=int)
    templates = list_templates(customer_id)
    return jsonify(templates)


@app.route('/api/email-templates', methods=['POST'])
@login_required
def api_save_template():
    """API: Save a template"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data'}), 400

    customer_id = data.get('customer_id')
    template_type = data.get('template_type')
    subject = data.get('subject')
    html_content = data.get('html_content')
    text_content = data.get('text_content')

    if not all([customer_id, template_type, subject, html_content]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    success = save_template(customer_id, template_type, subject, html_content, text_content)
    return jsonify({'success': success})


# ==========================================
# PROFIL-SPØRGSMÅL ADMIN
# ==========================================

@app.route('/admin/profil-questions')
@login_required
def profil_questions_admin():
    """Admin interface for profil-spørgsmål"""
    if session['user']['role'] != 'admin':
        flash('Kun administratorer har adgang til denne side', 'error')
        return redirect('/admin')

    questions = get_profil_questions()
    import json
    questions_json = json.dumps(questions)

    # Get intro texts from settings
    intro_texts = get_profil_intro_texts()

    return render_template('admin/profil_questions.html',
                         questions=questions,
                         questions_json=questions_json,
                         intro_texts=intro_texts)


def get_profil_intro_texts():
    """Hent intro/outro tekster fra database"""
    try:
        with get_profil_db() as conn:
            # Tjek om settings tabel findes
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profil_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            rows = conn.execute("SELECT key, value FROM profil_settings WHERE key LIKE '%intro' OR key LIKE '%outro'").fetchall()
            return {row['key']: row['value'] for row in rows}
    except:
        return {}


def save_profil_intro_texts(texts: dict):
    """Gem intro/outro tekster"""
    try:
        with get_profil_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profil_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            for key, value in texts.items():
                conn.execute("""
                    INSERT OR REPLACE INTO profil_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (key, value))
        return True
    except Exception as e:
        print(f"Error saving intro texts: {e}")
        return False


@app.route('/api/profil-questions', methods=['POST'])
@login_required
def api_create_profil_question():
    """API: Opret nyt profil-spørgsmål"""
    if session['user']['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Ikke autoriseret'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Ingen data'}), 400

    required = ['field', 'layer', 'text_da', 'sequence', 'question_type']
    if not all(data.get(f) for f in required):
        return jsonify({'success': False, 'error': 'Manglende felter'}), 400

    try:
        with get_profil_db() as conn:
            conn.execute("""
                INSERT INTO profil_questions
                (field, layer, text_da, state_text_da, question_type, reverse_scored, sequence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                data['field'],
                data['layer'],
                data['text_da'],
                data.get('state_text_da', ''),
                data['question_type'],
                data.get('reverse_scored', 0),
                data['sequence']
            ))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/profil-questions/<int:question_id>', methods=['PUT'])
@login_required
def api_update_profil_question(question_id):
    """API: Opdater profil-spørgsmål"""
    if session['user']['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Ikke autoriseret'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Ingen data'}), 400

    try:
        with get_profil_db() as conn:
            conn.execute("""
                UPDATE profil_questions SET
                    field = ?,
                    layer = ?,
                    text_da = ?,
                    state_text_da = ?,
                    question_type = ?,
                    reverse_scored = ?,
                    sequence = ?
                WHERE id = ?
            """, (
                data['field'],
                data['layer'],
                data['text_da'],
                data.get('state_text_da', ''),
                data['question_type'],
                data.get('reverse_scored', 0),
                data['sequence'],
                question_id
            ))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/profil-questions/<int:question_id>', methods=['DELETE'])
@login_required
def api_delete_profil_question(question_id):
    """API: Slet profil-spørgsmål"""
    if session['user']['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Ikke autoriseret'}), 403

    try:
        with get_profil_db() as conn:
            conn.execute("DELETE FROM profil_questions WHERE id = ?", (question_id,))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/profil-intro-texts', methods=['POST'])
@login_required
def api_save_profil_intro_texts():
    """API: Gem intro/outro tekster"""
    if session['user']['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Ikke autoriseret'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Ingen data'}), 400

    success = save_profil_intro_texts(data)
    return jsonify({'success': success})


@app.route('/admin/seed-testdata', methods=['POST'])
@login_required
def seed_testdata():
    """Kør seed script for at generere testdata"""
    if session['user']['role'] != 'admin':
        flash('Kun administratorer kan køre seed', 'error')
        return redirect('/admin')

    action = request.form.get('action', 'seed')

    if action == 'import_local':
        # Importer lokal kommune-data
        try:
            from import_local_data import import_local_data
            result = import_local_data()
            if result.get('success'):
                flash(f"Importeret: {result['units_imported']} units, {result['campaigns_imported']} kampagner, {result['responses_imported']} responses", 'success')
            else:
                flash(f"Fejl: {result.get('error', 'Ukendt fejl')}", 'error')
        except Exception as e:
            flash(f'Fejl ved import: {str(e)}', 'error')

    else:
        # Kør standard seed
        try:
            import seed_testdata
            seed_testdata.main()
            flash('Testdata genereret!', 'success')
        except Exception as e:
            flash(f'Fejl ved seed: {str(e)}', 'error')

    return redirect('/admin/seed-testdata')


@app.route('/admin/seed-testdata')
@login_required
def seed_testdata_page():
    """Vis seed-side"""
    if session['user']['role'] != 'admin':
        flash('Kun administratorer har adgang', 'error')
        return redirect('/admin')

    # Tjek nuværende data
    with get_db() as conn:
        stats = {
            'customers': conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            'users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'units': conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0],
            'campaigns': conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
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
            <p>Kampagner: {stats['campaigns']}</p>
            <p>Responses: {stats['responses']}</p>
        </div>

        <div class="warning">
            <strong>Bemærk:</strong> Seed tilføjer demo-data. Import erstatter demo-data med rigtige kommune-data.
        </div>

        <h3>Vælg handling:</h3>

        <form method="POST" style="margin-bottom: 15px;">
            <input type="hidden" name="action" value="import_local">
            <button type="submit" class="btn" style="background: #10b981;">Importer Kommune-data (anbefalet)</button>
            <p style="font-size: 0.9em; color: #666; margin-top: 5px;">Importerer 25 units, 11 kampagner og 2376 responses fra lokal database</p>
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


@app.route('/admin/db-status')
def db_status():
    """Fuld database status - offentlig debug"""
    from db_hierarchical import DB_PATH
    import os

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

        # Campaigns
        campaigns = conn.execute("SELECT id, name, target_unit_id FROM campaigns").fetchall()

        # Response count and respondent_name check
        resp_count = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        resp_with_name = conn.execute("SELECT COUNT(*) FROM responses WHERE respondent_name IS NOT NULL AND respondent_name != ''").fetchone()[0]
        resp_sample = conn.execute("SELECT respondent_name, respondent_type FROM responses LIMIT 5").fetchall()

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

    <h2>Campaigns ({len(campaigns)})</h2>
    <table><tr><th>ID</th><th>Name</th><th>Target</th></tr>
    {''.join(f"<tr><td>{c['id']}</td><td>{c['name']}</td><td>{c['target_unit_id'][:12]}...</td></tr>" for c in campaigns)}
    </table>

    <p><b>Responses:</b> {resp_count}</p>
    <p><b>Responses with respondent_name:</b> {resp_with_name}</p>
    <p><b>Sample responses:</b></p>
    <ul>{''.join(f"<li>{r['respondent_name']} ({r['respondent_type']})</li>" for r in resp_sample)}</ul>

    <h2>Actions</h2>
    <p><a href="/admin/full-reset">FULD RESET - Slet alt og genimporter</a></p>
    </body></html>
    """
    return html


@app.route('/admin/full-reset')
def full_reset():
    """Komplet database reset - slet ALLE tabeller og genimporter"""
    import json
    import os
    import traceback
    from db_hierarchical import DB_PATH

    json_path = os.path.join(os.path.dirname(__file__), 'local_data_export.json')
    if not os.path.exists(json_path):
        return f'FEJL: local_data_export.json ikke fundet. Path: {json_path}'

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return f'FEJL ved læsning af JSON: {str(e)}'

    results = []

    try:
        with get_db() as conn:
            # Tæl før
            before_units = conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0]
            before_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            results.append(f"Før: {before_units} units, {before_customers} customers")

            # SLET ALT - ignorer fejl hvis tabeller ikke eksisterer
            for table in ['responses', 'campaigns', 'organizational_units', 'customers', 'users']:
                try:
                    conn.execute(f"DELETE FROM {table}")
                except Exception as e:
                    results.append(f"Kunne ikke slette {table}: {e}")
            conn.commit()
            results.append("Slettet data fra tabeller")

            # Opret standard customers
            try:
                conn.execute("INSERT INTO customers (id, name) VALUES ('cust-herning', 'Herning Kommune')")
                conn.execute("INSERT INTO customers (id, name) VALUES ('cust-odder', 'Odder Kommune')")
                results.append("Oprettet customers: Herning Kommune, Odder Kommune")
            except Exception as e:
                results.append(f"Fejl ved customers: {e}")

            # Opret admin user
            try:
                conn.execute("""
                    INSERT INTO users (id, username, email, password_hash, role, customer_id, name)
                    VALUES ('admin-1', 'admin', 'admin@example.com', 'admin123', 'admin', NULL, 'Administrator')
                """)
                results.append("Oprettet admin bruger (admin/admin123)")
            except Exception as e:
                results.append(f"Fejl ved admin user: {e}")

            # Importer units med customer_id
            unit_count = 0
            for unit in data.get('organizational_units', []):
                try:
                    conn.execute('''
                        INSERT INTO organizational_units (id, name, full_path, parent_id, level, leader_name, leader_email, employee_count, sick_leave_percent, customer_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (unit['id'], unit['name'], unit.get('full_path'), unit.get('parent_id'),
                          unit.get('level', 0), unit.get('leader_name'), unit.get('leader_email'),
                          unit.get('employee_count', 0), unit.get('sick_leave_percent', 0),
                          'cust-herning'))
                    unit_count += 1
                except Exception as e:
                    results.append(f"Fejl unit {unit.get('name')}: {e}")
            results.append(f"Importeret {unit_count} units")

            # Importer campaigns
            camp_count = 0
            for camp in data.get('campaigns', []):
                try:
                    conn.execute('''
                        INSERT INTO campaigns (id, name, target_unit_id, period, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (camp['id'], camp['name'], camp['target_unit_id'], camp.get('period'), camp.get('created_at')))
                    camp_count += 1
                except Exception as e:
                    results.append(f"Fejl campaign {camp.get('name')}: {e}")
            results.append(f"Importeret {camp_count} campaigns")

            # Importer responses
            resp_count = 0
            for resp in data.get('responses', []):
                try:
                    conn.execute('''
                        INSERT INTO responses (campaign_id, unit_id, question_id, score, respondent_type, respondent_name, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (resp['campaign_id'], resp['unit_id'], resp['question_id'],
                          resp['score'], resp.get('respondent_type'), resp.get('respondent_name'), resp.get('created_at')))
                    resp_count += 1
                except Exception as e:
                    if resp_count == 0:  # Kun vis første fejl
                        results.append(f"Fejl response: {e}")
            results.append(f"Importeret {resp_count} responses")

            conn.commit()

            # Verificer
            after_units = conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0]
            after_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            toplevel = conn.execute("SELECT name FROM organizational_units WHERE parent_id IS NULL").fetchall()
            results.append(f"Efter: {after_units} units, {after_customers} customers")
            results.append(f"Toplevel: {[t['name'] for t in toplevel]}")

    except Exception as e:
        return f"<h1>FEJL</h1><pre>{traceback.format_exc()}</pre>"

    return f"""
    <h1>Database Reset Udført</h1>
    <ul>{''.join(f'<li>{r}</li>' for r in results)}</ul>
    <p><a href="/admin/db-status">Se database status</a></p>
    <p><a href="/admin">Gå til admin</a></p>
    """


@app.route('/admin/cleanup-empty')
@login_required
def cleanup_empty_units():
    """SLET ALT og importer ren lokal database"""
    if session['user']['role'] != 'admin':
        return "Ikke tilladt", 403

    import json
    import os
    from db_hierarchical import DB_PATH

    json_path = os.path.join(os.path.dirname(__file__), 'local_data_export.json')

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
            conn.execute("DELETE FROM campaigns")
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

            # Importer campaigns
            for camp in data.get('campaigns', []):
                conn.execute('''
                    INSERT INTO campaigns (id, name, target_unit_id, period, created_at, min_responses, mode)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (camp['id'], camp['name'], camp['target_unit_id'], camp.get('period'),
                      camp.get('created_at'), camp.get('min_responses', 5), camp.get('mode', 'anonymous')))

            # Importer responses
            for resp in data.get('responses', []):
                conn.execute('''
                    INSERT INTO responses (campaign_id, unit_id, question_id, score, respondent_type, respondent_name, comment, category_comment, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (resp['campaign_id'], resp['unit_id'], resp['question_id'],
                      resp['score'], resp.get('respondent_type'), resp.get('respondent_name'),
                      resp.get('comment'), resp.get('category_comment'), resp.get('created_at')))

            # Nu commit - alt eller intet
            conn.commit()

            units = conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0]
            campaigns = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
            responses = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]

            # Vis toplevel names
            toplevel = conn.execute("SELECT name FROM organizational_units WHERE parent_id IS NULL").fetchall()
            names = [t[0] for t in toplevel]

        flash(f'Database erstattet! Før: {before_units} units/{before_responses} responses, Nu: {units} units, {campaigns} kampagner, {responses} responses. Toplevel: {names}', 'success')
    except Exception as e:
        import traceback
        return f'FEJL: {str(e)}.<br><br>Traceback:<pre>{traceback.format_exc()}</pre><br>Debug: {debug}'

    return redirect('/admin')


if __name__ == '__main__':
    app.run(debug=True, port=5001)

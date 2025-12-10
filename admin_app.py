"""
Admin interface for Friktionskompasset v3
Hierarkisk organisationsstruktur med units + Multi-tenant
"""
from flask import Flask, render_template, request, redirect, url_for, flash, Response, session, jsonify, send_from_directory
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
    get_start_here_recommendation, get_trend_data
)
from db_multitenant import (
    authenticate_user, create_customer, create_user, list_customers,
    list_users, get_customer_filter, init_multitenant_db, get_customer, update_customer,
    get_domain_config, list_domains, create_domain, update_domain, delete_domain,
    generate_email_code, verify_email_code, find_user_by_email, create_b2c_user,
    get_or_create_b2c_customer, authenticate_by_email_code, reset_password_with_code
)
from csv_upload_hierarchical import (
    validate_csv_format, bulk_upload_from_csv, generate_csv_template
)
from mailjet_integration import (
    send_campaign_batch, get_email_stats, get_email_logs, update_email_status,
    get_template, save_template, list_templates, DEFAULT_TEMPLATES,
    check_and_notify_campaign_completed, send_login_code
)
from db_hierarchical import init_db
from db_profil import (
    init_profil_tables, get_all_questions as get_profil_questions,
    get_db as get_profil_db
)
from translations import t, get_user_language, set_language, SUPPORTED_LANGUAGES, seed_translations, clear_translation_cache
from scheduler import start_scheduler, get_scheduled_campaigns, cancel_scheduled_campaign, reschedule_campaign
from oauth import (
    init_oauth, oauth, get_enabled_providers, get_provider_info,
    handle_oauth_callback, get_auth_providers_for_domain, save_auth_providers,
    DEFAULT_AUTH_PROVIDERS
)
from cache import get_cache_stats, invalidate_all, invalidate_campaign_cache, Pagination

# Copy seed database to persistent disk on first deploy (if not exists)
def copy_seed_database():
    """Copy bundled database to persistent disk if empty/missing."""
    import shutil
    persistent_path = '/var/data/friktionskompas_v3.db'
    seed_path = os.path.join(os.path.dirname(__file__), 'seed_database.db')

    if os.path.exists('/var/data') and os.path.exists(seed_path):
        # Force copy if FORCE_SEED_DB env var is set (one-time migration)
        # Or if persistent db is empty/missing
        force_copy = os.environ.get('FORCE_SEED_DB', '').lower() in ('1', 'true', 'yes')
        should_copy = (
            not os.path.exists(persistent_path) or
            os.path.getsize(persistent_path) < 10000 or
            force_copy
        )
        if should_copy:
            print(f"[STARTUP] Copying seed database to {persistent_path} (force={force_copy})")
            shutil.copy2(seed_path, persistent_path)
            print(f"[STARTUP] Seed database copied successfully ({os.path.getsize(persistent_path)} bytes)")

copy_seed_database()

# Initialize databases
init_db()  # Main hierarchical database
init_profil_tables()  # Profil tables
init_multitenant_db()  # Multi-tenant tables

# Start scheduler for planned campaigns
start_scheduler()

# Seed translations and clear cache on startup
seed_translations()  # Ensures translations exist in database
clear_translation_cache()  # Clear any stale cached values

app = Flask(__name__)

# Sikker secret key fra miljøvariabel (fallback til autogeneret i development)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Initialize OAuth
init_oauth(app)

# Register Friktionsprofil Blueprint
from friktionsprofil_routes import friktionsprofil
app.register_blueprint(friktionsprofil)

from flask import g

# Domain middleware - detect domain and load config
@app.before_request
def detect_domain():
    """Detect domain and load domain-specific config"""
    host = request.host.split(':')[0].lower()  # Remove port if present

    # Try to get domain config from database
    domain_config = get_domain_config(host)

    if domain_config:
        g.domain_config = domain_config
        # Auto-set language based on domain if not already set by user
        if 'language' not in session:
            session['language'] = domain_config.get('default_language', 'da')
        # Auto-set customer filter based on domain if user is admin and no filter set
        if domain_config.get('customer_id') and 'user' in session:
            if session['user']['role'] == 'admin' and 'customer_filter' not in session:
                session['customer_filter'] = domain_config['customer_id']
    else:
        g.domain_config = None


@app.context_processor
def inject_domain_config():
    """Make domain config available in all templates"""
    return {
        'domain_config': getattr(g, 'domain_config', None)
    }


# Context processor for translations - gør t() tilgængelig i alle templates
@app.context_processor
def inject_translation_helpers():
    """Injicer translation helpers i alle templates"""
    return {
        't': t,
        'get_user_language': get_user_language,
        'supported_languages': SUPPORTED_LANGUAGES
    }


@app.context_processor
def inject_customers():
    """Gør kundeliste tilgængelig i alle templates"""
    customers = []
    if 'user' in session and session['user']['role'] in ('admin', 'superadmin'):
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
    """Decorator til at kræve admin eller superadmin rolle"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Du skal være logget ind', 'error')
            return redirect(url_for('login'))
        if session['user']['role'] not in ('admin', 'superadmin'):
            flash('Kun admin har adgang til denne side', 'error')
            return redirect(url_for('analyser'))
        return f(*args, **kwargs)
    return decorated_function


def superadmin_required(f):
    """Decorator til at kræve superadmin rolle"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Du skal være logget ind', 'error')
            return redirect(url_for('login'))
        if session['user']['role'] != 'superadmin':
            flash('Kun system administrator har adgang til denne side', 'error')
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


@app.route('/verifyforzoho.html')
def zoho_verify():
    """Zoho domain verification"""
    return send_from_directory('.', 'verifyforzoho.html')


@app.route('/zoho-domain-verification.html')
def zoho_domain_verify():
    """Zoho domain verification (alternative file)"""
    return send_from_directory('.', 'zoho-domain-verification.html')


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

    # Get enabled OAuth providers for this domain
    domain = request.host.split(':')[0].lower()
    enabled_providers = get_enabled_providers(domain)
    providers_info = {p: get_provider_info(p) for p in enabled_providers if p != 'email_password'}
    show_email_password = 'email_password' in enabled_providers

    return render_template('login.html',
                           oauth_providers=providers_info,
                           show_email_password=show_email_password)


# ========================================
# OAUTH ROUTES
# ========================================

@app.route('/auth/<provider>')
def oauth_login(provider):
    """Start OAuth flow for a provider"""
    if provider not in ['microsoft', 'google', 'apple', 'facebook']:
        flash('Ukendt login-metode', 'error')
        return redirect(url_for('login'))

    # Check if provider is enabled for this domain
    domain = request.host.split(':')[0].lower()
    enabled = get_enabled_providers(domain)

    if provider not in enabled:
        flash(f'{provider.title()} login er ikke aktiveret', 'error')
        return redirect(url_for('login'))

    # Get the OAuth client
    client = oauth.create_client(provider)
    if not client:
        flash(f'{provider.title()} er ikke konfigureret', 'error')
        return redirect(url_for('login'))

    # Generate redirect URI
    redirect_uri = url_for('oauth_callback', provider=provider, _external=True)

    return client.authorize_redirect(redirect_uri)


@app.route('/auth/<provider>/callback')
def oauth_callback(provider):
    """Handle OAuth callback"""
    if provider not in ['microsoft', 'google', 'apple', 'facebook']:
        flash('Ukendt login-metode', 'error')
        return redirect(url_for('login'))

    try:
        client = oauth.create_client(provider)
        if not client:
            flash(f'{provider.title()} er ikke konfigureret', 'error')
            return redirect(url_for('login'))

        # Get token
        token = client.authorize_access_token()

        # Get user info
        if provider == 'microsoft':
            # Microsoft returns userinfo in the token response
            userinfo = token.get('userinfo')
            if not userinfo:
                # Fetch from userinfo endpoint
                resp = client.get('https://graph.microsoft.com/oidc/userinfo')
                userinfo = resp.json()
        elif provider == 'google':
            userinfo = token.get('userinfo')
            if not userinfo:
                resp = client.get('https://openidconnect.googleapis.com/v1/userinfo')
                userinfo = resp.json()
        else:
            userinfo = token.get('userinfo', {})

        # Handle the callback
        user = handle_oauth_callback(provider, token, userinfo)

        if user:
            session['user'] = user
            flash(f'Velkommen {user["name"]}!', 'success')
            return redirect(url_for('analyser'))
        else:
            flash('Kunne ikke logge ind - kontakt administrator', 'error')
            return redirect(url_for('login'))

    except Exception as e:
        print(f"[OAuth] Callback error for {provider}: {e}")
        flash(f'Fejl ved login med {provider.title()}', 'error')
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    """Logout"""
    session.pop('user', None)
    flash('Du er nu logget ud', 'success')
    return redirect(url_for('login'))


# ========================================
# PASSWORDLESS LOGIN & REGISTRATION ROUTES
# ========================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registreringsside for B2C brugere"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()

        if not email or '@' not in email:
            flash('Indtast venligst en gyldig email', 'error')
            return render_template('register.html')

        if not name:
            flash('Indtast venligst dit navn', 'error')
            return render_template('register.html')

        # Tjek om email allerede eksisterer
        existing_user = find_user_by_email(email)
        if existing_user:
            flash('Denne email er allerede registreret. Prøv at logge ind.', 'error')
            return redirect(url_for('login'))

        # Gem i session til verificering
        session['pending_registration'] = {'email': email, 'name': name}

        # Generer og send kode
        code = generate_email_code(email, 'register')
        if send_login_code(email, code, 'register', get_user_language()):
            flash('Vi har sendt en kode til din email', 'success')
            return redirect(url_for('verify_registration'))
        else:
            flash('Kunne ikke sende email. Prøv igen.', 'error')

    return render_template('register.html')


@app.route('/register/verify', methods=['GET', 'POST'])
def verify_registration():
    """Verificer registrering med email-kode"""
    pending = session.get('pending_registration')
    if not pending:
        return redirect(url_for('register'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()

        if verify_email_code(pending['email'], code, 'register'):
            # Opret B2C bruger
            b2c_customer_id = get_or_create_b2c_customer()
            try:
                user_id = create_b2c_user(
                    email=pending['email'],
                    name=pending['name'],
                    customer_id=b2c_customer_id
                )

                # Log brugeren ind
                user = find_user_by_email(pending['email'])
                if user:
                    session['user'] = {
                        'id': user['id'],
                        'username': user['username'],
                        'name': user['name'],
                        'email': user['email'],
                        'role': user['role'],
                        'customer_id': user['customer_id'],
                        'customer_name': user.get('customer_name')
                    }
                    session.pop('pending_registration', None)
                    flash(f'Velkommen {user["name"]}! Din konto er oprettet.', 'success')
                    return redirect(url_for('user_home'))

            except Exception as e:
                print(f"[Register] Error creating user: {e}")
                flash('Der opstod en fejl. Prøv igen.', 'error')
        else:
            flash('Forkert eller udløbet kode. Prøv igen.', 'error')

    return render_template('verify_code.html',
                          email=pending['email'],
                          action='register',
                          title='Verificer din email')


@app.route('/login/email', methods=['GET', 'POST'])
def email_login():
    """Passwordless login med email-kode"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or '@' not in email:
            flash('Indtast venligst en gyldig email', 'error')
            return render_template('email_login.html')

        # Tjek om bruger eksisterer
        user = find_user_by_email(email)
        if not user:
            # Giv ikke info om at bruger ikke findes (sikkerhed)
            flash('Hvis emailen er registreret, sender vi en kode', 'success')
            return redirect(url_for('verify_email_login', email=email))

        # Generer og send kode
        code = generate_email_code(email, 'login')
        session['pending_email_login'] = email

        if send_login_code(email, code, 'login', get_user_language()):
            flash('Vi har sendt en kode til din email', 'success')
        else:
            flash('Hvis emailen er registreret, sender vi en kode', 'success')

        return redirect(url_for('verify_email_login'))

    return render_template('email_login.html')


@app.route('/login/email/verify', methods=['GET', 'POST'])
def verify_email_login():
    """Verificer email login-kode"""
    email = session.get('pending_email_login')
    if not email:
        return redirect(url_for('email_login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()

        user = authenticate_by_email_code(email, code)
        if user:
            session['user'] = user
            session.pop('pending_email_login', None)
            flash(f'Velkommen {user["name"]}!', 'success')

            # Redirect baseret på rolle
            if user['role'] == 'user':
                return redirect(url_for('user_home'))
            else:
                return redirect(url_for('analyser'))
        else:
            flash('Forkert eller udløbet kode. Prøv igen.', 'error')

    return render_template('verify_code.html',
                          email=email,
                          action='login',
                          title='Indtast din loginkode')


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Glemt password - send reset kode"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or '@' not in email:
            flash('Indtast venligst en gyldig email', 'error')
            return render_template('forgot_password.html')

        # Tjek om bruger eksisterer (men giv ikke info til brugeren)
        user = find_user_by_email(email)
        if user:
            code = generate_email_code(email, 'reset')
            send_login_code(email, code, 'reset', get_user_language())

        session['pending_password_reset'] = email
        flash('Hvis emailen er registreret, sender vi en kode til nulstilling', 'success')
        return redirect(url_for('reset_password'))

    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Nulstil password med kode"""
    email = session.get('pending_password_reset')
    if not email:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not code:
            flash('Indtast koden fra din email', 'error')
        elif len(new_password) < 8:
            flash('Password skal være mindst 8 tegn', 'error')
        elif new_password != confirm_password:
            flash('Passwords matcher ikke', 'error')
        else:
            if reset_password_with_code(email, code, new_password):
                session.pop('pending_password_reset', None)
                flash('Dit password er nulstillet. Log ind med dit nye password.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Forkert eller udløbet kode. Prøv igen.', 'error')

    return render_template('reset_password.html', email=email)


@app.route('/resend-code', methods=['POST'])
def resend_code():
    """Gensend verifikationskode"""
    code_type = request.form.get('type', 'login')
    email = None

    if code_type == 'login':
        email = session.get('pending_email_login')
    elif code_type == 'register':
        pending = session.get('pending_registration')
        email = pending.get('email') if pending else None
    elif code_type == 'reset':
        email = session.get('pending_password_reset')

    if email:
        code = generate_email_code(email, code_type)
        if send_login_code(email, code, code_type, get_user_language()):
            flash('Ny kode sendt!', 'success')
        else:
            flash('Kunne ikke sende kode. Prøv igen.', 'error')
    else:
        flash('Ingen email at sende til', 'error')

    return redirect(request.referrer or url_for('login'))


@app.route('/user')
@login_required
def user_home():
    """Hjemmeside for B2C brugere"""
    user = session.get('user')
    if user['role'] != 'user':
        return redirect(url_for('analyser'))

    return render_template('user_home.html')


@app.route('/help')
def help_page():
    """Brugerrettet hjælpeside"""
    return render_template('help.html')


@app.route('/set-language/<lang>')
def set_user_language(lang):
    """Skift brugerens sprog"""
    set_language(lang)
    # Redirect tilbage til forrige side eller forsiden
    return redirect(request.referrer or url_for('index'))


@app.route('/admin/seed-translations', methods=['POST'])
def admin_seed_translations():
    """Seed translations til database (public for db-status access)"""
    seed_translations()
    clear_translation_cache()
    # Check if request came from db-status (no flash, just redirect)
    referrer = request.referrer or ''
    if 'db-status' in referrer:
        return redirect('/admin/db-status')
    flash('Oversættelser er seedet til databasen', 'success')
    return redirect(request.referrer or url_for('admin_home'))


@app.route('/admin/seed-domains', methods=['POST'])
def admin_seed_domains():
    """Seed standard domæner til database"""
    import json
    import secrets

    # Domæne konfigurationer
    domains_config = [
        {
            'domain': 'friktionskompasset.dk',
            'default_language': 'da',
            'auth_providers': {
                'email_password': True,
                'microsoft': {'enabled': True},
                'google': {'enabled': True},
                'apple': {'enabled': True},
                'facebook': {'enabled': True}
            }
        },
        {
            'domain': 'frictioncompass.com',
            'default_language': 'en',
            'auth_providers': {
                'email_password': True,
                'microsoft': {'enabled': False},
                'google': {'enabled': True},
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

    flash(f'Domæner seedet: {created} oprettet, {updated} opdateret', 'success')
    return redirect(request.referrer or url_for('admin_domains'))


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


@app.route('/admin/noegletal')
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
        elif user['role'] != 'admin':
            customer_where = "WHERE ou.customer_id = ?"
            customer_params = [user['customer_id']]
        else:
            customer_where = ""
            customer_params = []

        # Totale stats
        if customer_filter or user['role'] != 'admin':
            cid = customer_filter or user['customer_id']
            total_customers = 1
            total_units = conn.execute(
                "SELECT COUNT(*) as cnt FROM organizational_units WHERE customer_id = ?",
                [cid]
            ).fetchone()['cnt']
            total_campaigns = conn.execute("""
                SELECT COUNT(*) as cnt FROM campaigns c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [cid]).fetchone()['cnt']
            total_responses = conn.execute("""
                SELECT COUNT(*) as cnt FROM responses r
                JOIN campaigns c ON r.campaign_id = c.id
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [cid]).fetchone()['cnt']
        else:
            total_customers = conn.execute("SELECT COUNT(*) as cnt FROM customers").fetchone()['cnt']
            total_units = conn.execute("SELECT COUNT(*) as cnt FROM organizational_units").fetchone()['cnt']
            total_campaigns = conn.execute("SELECT COUNT(*) as cnt FROM campaigns").fetchone()['cnt']
            total_responses = conn.execute("SELECT COUNT(*) as cnt FROM responses").fetchone()['cnt']

        # Gennemsnitlige scores per felt
        field_scores_query = """
            SELECT
                q.field,
                AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                COUNT(*) as response_count
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            JOIN campaigns c ON r.campaign_id = c.id
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            {where}
            GROUP BY q.field
            ORDER BY avg_score ASC
        """.format(where=customer_where)
        field_scores = conn.execute(field_scores_query, customer_params).fetchall()

        # Seneste kampagner
        recent_campaigns_query = """
            SELECT
                c.id,
                c.name,
                c.period,
                c.created_at,
                ou.name as unit_name,
                cust.name as customer_name,
                COUNT(DISTINCT r.id) as response_count,
                (SELECT COUNT(*) FROM tokens t WHERE t.campaign_id = c.id) as token_count
            FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            JOIN customers cust ON ou.customer_id = cust.id
            LEFT JOIN responses r ON r.campaign_id = c.id
            {where}
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT 5
        """.format(where=customer_where)
        recent_campaigns = conn.execute(recent_campaigns_query, customer_params).fetchall()

        # Per-kunde stats (kun for admin uden filter)
        customer_stats = []
        if user['role'] == 'admin' and not customer_filter:
            customer_stats = conn.execute("""
                SELECT
                    cust.id,
                    cust.name,
                    COUNT(DISTINCT ou.id) as unit_count,
                    COUNT(DISTINCT c.id) as campaign_count,
                    COUNT(DISTINCT r.id) as response_count
                FROM customers cust
                LEFT JOIN organizational_units ou ON ou.customer_id = cust.id
                LEFT JOIN campaigns c ON c.target_unit_id = ou.id
                LEFT JOIN responses r ON r.campaign_id = c.id
                GROUP BY cust.id
                ORDER BY response_count DESC
            """).fetchall()

        # Svarprocent beregning
        response_rate_data = conn.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN t.is_used = 1 THEN t.token END) as used_tokens,
                COUNT(DISTINCT t.token) as total_tokens
            FROM tokens t
            JOIN campaigns c ON t.campaign_id = c.id
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
                         total_campaigns=total_campaigns,
                         total_responses=total_responses,
                         avg_response_rate=avg_response_rate,
                         field_scores=[dict(f) for f in field_scores],
                         recent_campaigns=[dict(c) for c in recent_campaigns],
                         customer_stats=[dict(c) for c in customer_stats],
                         show_customer_stats=(user['role'] == 'admin' and not customer_filter))


@app.route('/admin/trend')
@login_required
def admin_trend():
    """Trend analyse - sammenlign friktionsscores over tid"""
    user = get_current_user()
    customer_filter = session.get('customer_filter') or user.get('customer_id')

    # Get unit_id from query param (optional)
    unit_id = request.args.get('unit_id')

    # Get trend data
    if customer_filter or user['role'] != 'admin':
        cid = customer_filter or user['customer_id']
        trend_data = get_trend_data(unit_id=unit_id, customer_id=cid)
    else:
        trend_data = get_trend_data(unit_id=unit_id)

    # Get available units for filter dropdown
    with get_db() as conn:
        if customer_filter or user['role'] != 'admin':
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


@app.route('/admin/scheduled-campaigns')
@login_required
def scheduled_campaigns():
    """Oversigt over planlagte målinger"""
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'])

    with get_db() as conn:
        # Hent scheduled campaigns
        if user['role'] == 'admin':
            campaigns = conn.execute("""
                SELECT c.*, ou.name as target_name, ou.full_path
                FROM campaigns c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE c.status = 'scheduled'
                ORDER BY c.scheduled_at ASC
            """).fetchall()
        else:
            campaigns = conn.execute("""
                SELECT c.*, ou.name as target_name, ou.full_path
                FROM campaigns c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE c.status = 'scheduled' AND ou.customer_id = ?
                ORDER BY c.scheduled_at ASC
            """, [user['customer_id']]).fetchall()

    return render_template('admin/scheduled_campaigns.html',
                         campaigns=[dict(c) for c in campaigns])


@app.route('/admin/campaign/<campaign_id>/cancel', methods=['POST'])
@login_required
def cancel_campaign(campaign_id):
    """Annuller en planlagt måling"""
    user = get_current_user()

    # Verificer at brugeren har adgang til kampagnen
    with get_db() as conn:
        where_clause, params = get_customer_filter(user['role'], user['customer_id'])
        campaign = conn.execute(f"""
            SELECT c.* FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ? AND c.status = 'scheduled' AND ({where_clause})
        """, [campaign_id] + params).fetchone()

        if not campaign:
            flash('Måling ikke fundet eller kan ikke annulleres', 'error')
            return redirect(url_for('scheduled_campaigns'))

    # Annuller kampagnen
    success = cancel_scheduled_campaign(campaign_id)
    if success:
        flash('Planlagt måling annulleret', 'success')
    else:
        flash('Kunne ikke annullere målingen', 'error')

    return redirect(url_for('scheduled_campaigns'))


@app.route('/admin/campaign/<campaign_id>/reschedule', methods=['POST'])
@login_required
def reschedule_campaign_route(campaign_id):
    """Ændr tidspunkt for en planlagt måling"""
    user = get_current_user()
    from datetime import datetime

    # Verificer at brugeren har adgang til kampagnen
    with get_db() as conn:
        where_clause, params = get_customer_filter(user['role'], user['customer_id'])
        campaign = conn.execute(f"""
            SELECT c.* FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ? AND c.status = 'scheduled' AND ({where_clause})
        """, [campaign_id] + params).fetchone()

        if not campaign:
            flash('Måling ikke fundet eller kan ikke ændres', 'error')
            return redirect(url_for('scheduled_campaigns'))

    # Hent nyt tidspunkt fra form
    new_date = request.form.get('new_date', '').strip()
    new_time = request.form.get('new_time', '08:00').strip()

    if not new_date:
        flash('Vælg en ny dato', 'error')
        return redirect(url_for('scheduled_campaigns'))

    new_scheduled_at = datetime.fromisoformat(f"{new_date}T{new_time}:00")

    success = reschedule_campaign(campaign_id, new_scheduled_at)
    if success:
        flash(f'Måling flyttet til {new_date} kl. {new_time}', 'success')
    else:
        flash('Kunne ikke ændre tidspunkt', 'error')

    return redirect(url_for('scheduled_campaigns'))


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
    """Bulk upload af units fra CSV med hierarkisk struktur - Step 1: Preview"""
    import base64
    import io
    import csv

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


@app.route('/admin/bulk-upload/confirm', methods=['POST'])
@login_required
def bulk_upload_confirm():
    """Bulk upload af units fra CSV - Step 2: Bekræft og importer"""
    import base64
    user = get_current_user()

    csv_data_encoded = request.form.get('csv_data', '')
    if not csv_data_encoded:
        flash('Ingen data at importere', 'error')
        return redirect(url_for('bulk_upload'))

    try:
        content = base64.b64decode(csv_data_encoded).decode('utf-8')
    except Exception as e:
        flash(f'Fejl ved dekodning af data: {str(e)}', 'error')
        return redirect(url_for('bulk_upload'))

    # Upload med customer_id
    stats = bulk_upload_from_csv(content, customer_id=user['customer_id'])

    if stats['errors']:
        for error in stats['errors']:
            flash(error, 'warning')

    flash(f"{stats['units_created']} organisationer oprettet! {stats['contacts_created']} kontakter tilføjet.", 'success')
    return redirect(url_for('admin_home'))


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


@app.route('/admin/customer/<customer_id>/delete', methods=['POST'])
@admin_required
def delete_customer(customer_id):
    """Slet kunde og alle tilhørende data (kun admin)"""
    with get_db() as conn:
        # Tjek at kunden eksisterer
        customer = conn.execute(
            "SELECT * FROM customers WHERE id = ?",
            (customer_id,)
        ).fetchone()

        if not customer:
            flash('Kunde ikke fundet', 'error')
            return redirect(url_for('admin_home'))

        customer_name = customer['name']

        # CASCADE DELETE vil automatisk slette:
        # - organizational_units (og deres children)
        # - campaigns
        # - responses
        # - users tilknyttet kunden
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

    flash(f'Kunde "{customer_name}" og alle tilhørende data er slettet', 'success')
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


@app.route('/api/units/<unit_id>/move', methods=['POST'])
@login_required
def api_move_unit(unit_id):
    """API: Flyt organisation til ny parent"""
    from db_hierarchical import move_unit

    user = get_current_user()
    if user['role'] != 'admin':
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


@app.route('/admin/campaign/new', methods=['GET', 'POST'])
@login_required
def new_campaign():
    """Opret og send ny kampagne (eller planlæg til senere)"""
    user = get_current_user()

    if request.method == 'POST':
        target_unit_id = request.form['target_unit_id']
        name = request.form['name']
        period = request.form['period']
        sent_from = request.form.get('sent_from', 'admin')
        sender_name = request.form.get('sender_name', 'HR')

        # Tjek om det er en scheduled campaign
        scheduled_date = request.form.get('scheduled_date', '').strip()
        scheduled_time = request.form.get('scheduled_time', '').strip()

        scheduled_at = None
        if scheduled_date:
            # Kombiner dato og tid (default til 08:00 hvis ikke angivet)
            if not scheduled_time:
                scheduled_time = '08:00'
            scheduled_at = f"{scheduled_date}T{scheduled_time}:00"

        # Opret kampagne
        campaign_id = create_campaign(
            target_unit_id=target_unit_id,
            name=name,
            period=period,
            sent_from=sent_from,
            scheduled_at=scheduled_at,
            sender_name=sender_name
        )

        if scheduled_at:
            # Scheduled campaign - send ikke nu
            flash(f'📅 Måling planlagt til {scheduled_date} kl. {scheduled_time}', 'success')
            return redirect(url_for('scheduled_campaigns'))
        else:
            # Send nu
            tokens_by_unit = generate_tokens_for_campaign(campaign_id)

            total_sent = 0
            for unit_id, tokens in tokens_by_unit.items():
                contacts = get_unit_contacts(unit_id)
                if not contacts:
                    continue

                results = send_campaign_batch(contacts, tokens, name, sender_name)
                total_sent += results['emails_sent'] + results['sms_sent']

            flash(f'Måling sendt! {sum(len(t) for t in tokens_by_unit.values())} tokens genereret, {total_sent} sendt.', 'success')
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


@app.route('/admin/campaign/<campaign_id>/delete', methods=['POST'])
@login_required
def delete_campaign(campaign_id):
    """Slet en kampagne og alle tilhørende data"""
    user = get_current_user()

    with get_db() as conn:
        # Hent campaign med customer filter for at verificere adgang
        where_clause, params = get_customer_filter(user['role'], user['customer_id'])
        campaign = conn.execute(f"""
            SELECT c.*, ou.name as unit_name FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.id = ? AND ({where_clause})
        """, [campaign_id] + params).fetchone()

        if not campaign:
            flash("Måling ikke fundet eller ingen adgang", 'error')
            return redirect(url_for('campaigns_overview'))

        campaign_name = campaign['name']

        # Slet kampagnen (CASCADE sletter responses og tokens automatisk)
        conn.execute("DELETE FROM campaigns WHERE id = ?", [campaign_id])
        conn.commit()

        flash(f'Målingen "{campaign_name}" blev slettet', 'success')

    return redirect(url_for('campaigns_overview'))


@app.route('/admin/customers')
@admin_required
def manage_customers():
    """Customer management - kun admin"""
    customers = list_customers()
    users = list_users()  # Alle users
    return render_template('admin/customers.html',
                         customers=customers,
                         users=users)


@app.route('/admin/domains')
@admin_required
def manage_domains():
    """Domain management - kun admin"""
    domains = list_domains()
    customers = list_customers()
    return render_template('admin/domains.html',
                         domains=domains,
                         customers=customers)


@app.route('/admin/domain/new', methods=['POST'])
@admin_required
def create_new_domain():
    """Opret nyt domain mapping - kun admin"""
    domain = request.form['domain'].strip().lower()
    customer_id = request.form.get('customer_id') or None
    default_language = request.form.get('default_language', 'da')
    branding = {
        'logo_url': request.form.get('branding_logo_url') or None,
        'primary_color': request.form.get('branding_primary_color') or None,
        'company_name': request.form.get('branding_company_name') or None
    }

    domain_id = create_domain(domain, customer_id, default_language, branding)
    flash(f'Domain "{domain}" oprettet!', 'success')
    return redirect(url_for('manage_domains'))


@app.route('/admin/domain/<domain_id>/edit', methods=['POST'])
@admin_required
def edit_domain(domain_id):
    """Rediger domain - kun admin"""
    update_domain(
        domain_id,
        customer_id=request.form.get('customer_id') or None,
        default_language=request.form.get('default_language', 'da'),
        branding_logo_url=request.form.get('branding_logo_url') or None,
        branding_primary_color=request.form.get('branding_primary_color') or None,
        branding_company_name=request.form.get('branding_company_name') or None
    )
    flash('Domain opdateret!', 'success')
    return redirect(url_for('manage_domains'))


@app.route('/admin/domain/<domain_id>/delete', methods=['POST'])
@admin_required
def delete_domain_route(domain_id):
    """Slet domain - kun admin"""
    delete_domain(domain_id)
    flash('Domain slettet!', 'success')
    return redirect(url_for('manage_domains'))


@app.route('/admin/customer/new', methods=['POST'])
@admin_required
def create_new_customer():
    """Opret ny customer - kun admin"""
    name = request.form['name']
    contact_email = request.form.get('contact_email')

    customer_id = create_customer(name, contact_email)

    flash(f'Customer "{name}" oprettet!', 'success')
    return redirect(url_for('manage_customers'))


@app.route('/admin/customer/<customer_id>/email-settings', methods=['GET', 'POST'])
@admin_required
def customer_email_settings(customer_id):
    """Email-indstillinger for en kunde - kun admin"""
    import os

    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('manage_customers'))

    if request.method == 'POST':
        email_from_address = request.form.get('email_from_address', '').strip() or None
        email_from_name = request.form.get('email_from_name', '').strip() or None

        update_customer(customer_id,
                       email_from_address=email_from_address,
                       email_from_name=email_from_name)

        flash(t('email_settings.saved', 'Email-indstillinger gemt!'), 'success')
        return redirect(url_for('customer_email_settings', customer_id=customer_id))

    # Default values fra environment
    default_from_email = os.getenv('FROM_EMAIL', 'info@friktionskompasset.dk')
    default_from_name = os.getenv('FROM_NAME', 'Friktionskompasset')

    return render_template('admin/email_settings.html',
                         customer=customer,
                         default_from_email=default_from_email,
                         default_from_name=default_from_name)


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


@app.route('/admin/user/<user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Rediger bruger - kun admin"""
    import bcrypt

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        if not user:
            flash('Bruger ikke fundet', 'error')
            return redirect(url_for('manage_customers'))

        if request.method == 'POST':
            name = request.form.get('name', user['name'])
            email = request.form.get('email', user['email'])
            role = request.form.get('role', user['role'])
            customer_id = request.form.get('customer_id') or None
            new_password = request.form.get('new_password')

            # Update user
            if new_password:
                password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                conn.execute("""
                    UPDATE users SET name = ?, email = ?, role = ?, customer_id = ?, password_hash = ?
                    WHERE id = ?
                """, (name, email, role, customer_id, password_hash, user_id))
            else:
                conn.execute("""
                    UPDATE users SET name = ?, email = ?, role = ?, customer_id = ?
                    WHERE id = ?
                """, (name, email, role, customer_id, user_id))

            flash(f'Bruger "{user["username"]}" opdateret!', 'success')
            return redirect(url_for('manage_customers'))

        # GET - vis formular
        customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()

    return f'''
    <html>
    <head><title>Rediger bruger</title>
    <style>
        body {{ font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }}
        label {{ display: block; margin-top: 15px; font-weight: bold; }}
        input, select {{ width: 100%; padding: 8px; margin-top: 5px; }}
        button {{ margin-top: 20px; padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }}
        a {{ display: inline-block; margin-top: 10px; }}
    </style>
    </head>
    <body>
    <h1>Rediger bruger: {user["username"]}</h1>
    <form method="post">
        <label>Navn</label>
        <input type="text" name="name" value="{user["name"] or ""}">

        <label>Email</label>
        <input type="email" name="email" value="{user["email"] or ""}">

        <label>Rolle</label>
        <select name="role">
            <option value="superadmin" {"selected" if user["role"] == "superadmin" else ""}>Superadmin</option>
            <option value="admin" {"selected" if user["role"] == "admin" else ""}>Admin</option>
            <option value="manager" {"selected" if user["role"] == "manager" else ""}>Manager</option>
        </select>

        <label>Kunde (for managers)</label>
        <select name="customer_id">
            <option value="">- Ingen -</option>
            {"".join(f'<option value="{c["id"]}" {"selected" if user["customer_id"] == c["id"] else ""}>{c["name"]}</option>' for c in customers)}
        </select>

        <label>Nyt password (lad være tom for at beholde)</label>
        <input type="password" name="new_password" placeholder="Nyt password...">

        <button type="submit">Gem ændringer</button>
    </form>
    <a href="/admin/customers">&larr; Tilbage</a>
    </body>
    </html>
    '''


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

    # Return to the page we came from, or adapt URL for new customer context
    next_url = request.args.get('next', '')
    if next_url:
        # If on dashboard with specific customer/unit, go to that customer's dashboard
        if '/dashboard' in next_url:
            return redirect(url_for('org_dashboard', customer_id=customer_id))
        # For other pages, just go back to that page type
        return redirect(next_url)
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

    # Return to the page we came from
    next_url = request.args.get('next', '')
    if next_url:
        # If on dashboard with specific customer, go to main dashboard
        if '/dashboard' in next_url:
            return redirect(url_for('org_dashboard'))
        return redirect(next_url)
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


@app.route('/admin/campaign/<campaign_id>/pdf')
@login_required
def campaign_pdf_export(campaign_id):
    """Eksporter måling til PDF"""
    from datetime import datetime
    from io import BytesIO

    user = get_current_user()

    try:
        with get_db() as conn:
            # Hent campaign
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

        # Check anonymity
        anonymity = check_anonymity_threshold(campaign_id, target_unit_id)
        if not anonymity.get('can_show_results'):
            flash("Ikke nok svar til at generere PDF", 'warning')
            return redirect(url_for('view_campaign', campaign_id=campaign_id))

        # Get all data
        breakdown = get_detailed_breakdown(target_unit_id, campaign_id, include_children=True)
        substitution = calculate_substitution(target_unit_id, campaign_id, 'employee')
        free_text_comments = get_free_text_comments(target_unit_id, campaign_id, include_children=True)

        employee_stats = breakdown.get('employee', {})
        comparison = breakdown.get('comparison', {})
        kkc_recommendations = get_kkc_recommendations(employee_stats, comparison)
        start_here = get_start_here_recommendation(kkc_recommendations)

        from analysis import get_alerts_and_findings
        alerts = get_alerts_and_findings(breakdown, comparison, substitution)

        # Token stats
        with get_db() as conn:
            token_stats = conn.execute("""
                SELECT
                    COUNT(*) as tokens_sent,
                    SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as tokens_used
                FROM tokens
                WHERE campaign_id = ?
            """, (campaign_id,)).fetchone()

        # Calculate overall score
        emp = breakdown.get('employee', {})
        if emp:
            fields = ['MENING', 'TRYGHED', 'KAN', 'BESVÆR']
            scores = [emp.get(f, {}).get('avg_score', 3) for f in fields]
            avg_score = sum(scores) / len(scores)
            overall_score = (avg_score - 1) / 4 * 100
        else:
            overall_score = 0

        response_rate = (token_stats['tokens_used'] / token_stats['tokens_sent'] * 100) if token_stats['tokens_sent'] > 0 else 0

        # Render HTML template
        html = render_template('admin/campaign_pdf.html',
            campaign=dict(campaign),
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
                return redirect(url_for('view_campaign', campaign_id=campaign_id))

            pdf_buffer.seek(0)

            # Create filename
            safe_name = campaign['name'].replace(' ', '_').replace('/', '-')
            filename = f"Friktionsmaaling_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"

            return Response(
                pdf_buffer.getvalue(),
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'}
            )
        except ImportError:
            flash("PDF bibliotek ikke installeret. Kontakt administrator.", 'error')
            return redirect(url_for('view_campaign', campaign_id=campaign_id))

    except Exception as e:
        import traceback
        print(f"PDF export error: {traceback.format_exc()}")
        flash(f"Fejl ved PDF eksport: {str(e)}", 'error')
        return redirect(url_for('view_campaign', campaign_id=campaign_id))


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
# SURVEY ROUTES (for respondents)
# ========================================

@app.route('/s/<token>')
def survey(token):
    """Survey landing page - validates token and shows questions"""
    if not token:
        return render_template('survey_error.html',
            error="Ingen token angivet. Du skal have et link fra din organisation.")

    # Validate token (without marking as used yet)
    with get_db() as conn:
        token_info = conn.execute("""
            SELECT t.*, c.name as campaign_name
            FROM tokens t
            JOIN campaigns c ON t.campaign_id = c.id
            WHERE t.token = ?
        """, (token,)).fetchone()

        if not token_info:
            return render_template('survey_error.html',
                error="Ugyldig token. Linket er muligvis forkert.")

        if token_info['is_used']:
            return render_template('survey_error.html',
                error="Dette link er allerede blevet brugt. Hvert link kan kun bruges én gang.")

    # Get questions
    questions = get_questions()

    respondent_type = token_info['respondent_type']
    respondent_name = token_info['respondent_name']

    # Instructions based on respondent type
    instructions = {
        'employee': {
            'title': 'Medarbejder-spørgeskema',
            'instruction': 'Svar ud fra din egen oplevelse af arbejdet',
            'description': 'Besvar spørgsmålene ærligt baseret på hvordan DU oplever din arbejdssituation.'
        },
        'leader_assess': {
            'title': 'Leder: Vurdering af teamet',
            'instruction': 'Svar IKKE om dig selv, men om hvad du tror dine medarbejdere oplever',
            'description': 'Forestil dig gennemsnitsmedarbejderen i dit team. Hvad ville de svare på disse spørgsmål?'
        },
        'leader_self': {
            'title': 'Leder: Egne friktioner',
            'instruction': 'Svar om dine EGNE friktioner som leder',
            'description': 'Har DU de værktøjer, den tryghed og mening du skal bruge for at lede godt?'
        }
    }

    instr = instructions.get(respondent_type, instructions['employee'])

    return render_template('survey.html',
        token=token,
        questions=questions,
        respondent_type=respondent_type,
        respondent_name=respondent_name,
        title=instr['title'],
        instruction=instr['instruction'],
        description=instr['description'],
        is_preview=False
    )


@app.route('/s/<token>/submit', methods=['POST'])
def survey_submit(token):
    """Save survey responses and mark token as used"""
    if not token:
        flash('Ingen token angivet', 'error')
        return redirect(url_for('index'))

    # Get token info
    with get_db() as conn:
        token_info = conn.execute("""
            SELECT campaign_id, unit_id, respondent_type, respondent_name, is_used
            FROM tokens
            WHERE token = ?
        """, (token,)).fetchone()

        if not token_info:
            flash('Ugyldig token', 'error')
            return redirect(url_for('index'))

        if token_info['is_used']:
            return render_template('survey_error.html',
                error="Dette link er allerede blevet brugt.")

    campaign_id = token_info['campaign_id']
    unit_id = token_info['unit_id']
    respondent_type = token_info['respondent_type']
    respondent_name = token_info['respondent_name']

    # Get free text responses
    free_text_situation = request.form.get('free_text_situation', '').strip()
    free_text_general = request.form.get('free_text_general', '').strip()

    # Combine free text
    combined_comment = ""
    if free_text_situation:
        combined_comment += f"SITUATION: {free_text_situation}"
    if free_text_general:
        if combined_comment:
            combined_comment += "\n\n"
        combined_comment += f"GENERELT: {free_text_general}"

    # Save all responses
    questions = get_questions()
    saved_count = 0

    for question in questions:
        q_id = question['id']
        score = request.form.get(f'q_{q_id}')

        if score:
            score = int(score)

            # Save response with respondent_type, name, and free text (only on first response)
            with get_db() as conn:
                comment = combined_comment if saved_count == 0 and combined_comment else None

                conn.execute("""
                    INSERT INTO responses
                    (campaign_id, unit_id, question_id, score, respondent_type, respondent_name, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (campaign_id, unit_id, q_id, score, respondent_type, respondent_name, comment))

            saved_count += 1

    # Mark token as used
    with get_db() as conn:
        conn.execute("""
            UPDATE tokens
            SET is_used = 1, used_at = CURRENT_TIMESTAMP
            WHERE token = ?
        """, (token,))

    # Check if campaign is now complete and send notification
    # Default threshold is 100% (all tokens used)
    try:
        check_and_notify_campaign_completed(campaign_id)
    except Exception as e:
        # Don't fail the survey submission if notification fails
        print(f"Warning: Could not send completion notification: {e}")

    return render_template('survey_thanks.html',
        saved_count=saved_count,
        respondent_type=respondent_type
    )


@app.route('/survey/preview')
def survey_preview():
    """Preview mode - no token required"""
    respondent_type = request.args.get('type', 'employee')

    questions = get_questions()

    instructions = {
        'employee': {
            'title': 'Medarbejder-spørgeskema',
            'instruction': 'Svar ud fra din egen oplevelse af arbejdet',
            'description': 'Besvar spørgsmålene ærligt baseret på hvordan DU oplever din arbejdssituation.'
        },
        'leader_assess': {
            'title': 'Leder: Vurdering af teamet',
            'instruction': 'Svar IKKE om dig selv, men om hvad du tror dine medarbejdere oplever',
            'description': 'Forestil dig gennemsnitsmedarbejderen i dit team. Hvad ville de svare på disse spørgsmål?'
        },
        'leader_self': {
            'title': 'Leder: Egne friktioner',
            'instruction': 'Svar om dine EGNE friktioner som leder',
            'description': 'Har DU de værktøjer, den tryghed og mening du skal bruge for at lede godt?'
        }
    }

    instr = instructions.get(respondent_type, instructions['employee'])

    return render_template('survey.html',
        token='preview',
        questions=questions,
        respondent_type=respondent_type,
        respondent_name='Preview',
        title=instr['title'],
        instruction=instr['instruction'],
        description=instr['description'],
        is_preview=True
    )


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
                flash(f"Importeret: {result['units_imported']} units, {result['campaigns_imported']} målinger, {result['responses_imported']} responses", 'success')
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
            <p>Målinger: {stats['campaigns']}</p>
            <p>Responses: {stats['responses']}</p>
        </div>

        <div class="warning">
            <strong>Bemærk:</strong> Seed tilføjer demo-data. Import erstatter demo-data med rigtige kommune-data.
        </div>

        <h3>Vælg handling:</h3>

        <form method="POST" style="margin-bottom: 15px;">
            <input type="hidden" name="action" value="import_local">
            <button type="submit" class="btn" style="background: #10b981;">Importer Kommune-data (anbefalet)</button>
            <p style="font-size: 0.9em; color: #666; margin-top: 5px;">Importerer 25 units, 11 målinger og 2376 responses fra lokal database</p>
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


@app.route('/admin/dev-tools')
@admin_required
def dev_tools():
    """Dev tools samlet side - kun admin"""
    with get_db() as conn:
        stats = {
            'customers': conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            'users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'units': conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0],
            'campaigns': conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
            'responses': conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0],
            'tokens': conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0],
            'translations': conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0],
        }

    # Get cache stats
    cache_stats = get_cache_stats()

    return render_template('admin/dev_tools.html', stats=stats, cache_stats=cache_stats)


@app.route('/admin/clear-cache', methods=['POST'])
@admin_required
def clear_cache():
    """Ryd hele cachen - kun admin"""
    count = invalidate_all()
    flash(f'Cache ryddet! ({count} entries fjernet)', 'success')
    return redirect(url_for('dev_tools'))


@app.route('/admin/backup')
@admin_required
def backup_page():
    """Backup/restore side"""
    with get_db() as conn:
        stats = {
            'customers': conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            'users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'units': conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0],
            'campaigns': conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
            'responses': conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0],
            'contacts': conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
            'tokens': conn.execute("SELECT COUNT(*) FROM tokens").fetchone()[0],
        }
    return render_template('admin/backup.html', stats=stats)


@app.route('/admin/backup/download')
@admin_required
def backup_download():
    """Download fuld database backup som JSON"""
    import json
    from datetime import datetime

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
            'campaigns',
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

    # Returner som downloadbar JSON fil
    json_str = json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
    filename = f"friktionskompas_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    return Response(
        json_str,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@app.route('/admin/backup/restore', methods=['POST'])
@admin_required
def backup_restore():
    """Restore database fra uploadet JSON backup"""
    import json

    if 'backup_file' not in request.files:
        flash('Ingen fil uploadet', 'error')
        return redirect(url_for('backup_page'))

    file = request.files['backup_file']
    if file.filename == '':
        flash('Ingen fil valgt', 'error')
        return redirect(url_for('backup_page'))

    try:
        backup_data = json.load(file)
    except json.JSONDecodeError:
        flash('Ugyldig JSON fil', 'error')
        return redirect(url_for('backup_page'))

    if 'tables' not in backup_data:
        flash('Ugyldig backup fil format', 'error')
        return redirect(url_for('backup_page'))

    # Valider at det er en rigtig backup
    if 'version' not in backup_data:
        flash('Backup fil mangler versionsnummer', 'error')
        return redirect(url_for('backup_page'))

    restore_mode = request.form.get('restore_mode', 'merge')
    stats = {'inserted': 0, 'skipped': 0, 'errors': 0}

    with get_db() as conn:
        conn.execute("PRAGMA foreign_keys=OFF")

        if restore_mode == 'replace':
            # Slet eksisterende data først (i omvendt rækkefølge pga. foreign keys)
            delete_order = ['responses', 'tokens', 'email_logs', 'contacts', 'campaigns',
                           'organizational_units', 'users', 'customers']
            for table in delete_order:
                try:
                    conn.execute(f"DELETE FROM {table}")
                except:
                    pass

        # Restore tabeller i rigtig rækkefølge (parents før children)
        restore_order = ['customers', 'users', 'organizational_units', 'contacts',
                        'campaigns', 'tokens', 'responses', 'questions', 'translations']

        for table in restore_order:
            if table not in backup_data['tables']:
                continue

            table_data = backup_data['tables'][table]
            if isinstance(table_data, dict) and 'error' in table_data:
                continue

            for row in table_data:
                try:
                    # Check om row allerede eksisterer (baseret på id)
                    if 'id' in row:
                        existing = conn.execute(f"SELECT id FROM {table} WHERE id = ?", (row['id'],)).fetchone()
                        if existing and restore_mode == 'merge':
                            stats['skipped'] += 1
                            continue

                    # Insert row
                    columns = ', '.join(row.keys())
                    placeholders = ', '.join(['?' for _ in row])
                    conn.execute(f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
                               list(row.values()))
                    stats['inserted'] += 1
                except Exception as e:
                    stats['errors'] += 1

        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()

    flash(f"Restore gennemført: {stats['inserted']} rækker importeret, {stats['skipped']} sprunget over, {stats['errors']} fejl", 'success')
    return redirect(url_for('backup_page'))


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

        # Questions check
        try:
            questions_count = conn.execute("SELECT COUNT(*) FROM questions WHERE is_default = 1").fetchone()[0]
            questions_total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        except:
            questions_count = 0
            questions_total = 0

        # Translations check
        try:
            translations_count = conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0]
            translations_sample = conn.execute("SELECT key, da, en FROM translations LIMIT 5").fetchall()
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

    <h2>Campaigns ({len(campaigns)})</h2>
    <table><tr><th>ID</th><th>Name</th><th>Target</th></tr>
    {''.join(f"<tr><td>{c['id']}</td><td>{c['name']}</td><td>{c['target_unit_id'][:12]}...</td></tr>" for c in campaigns)}
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
    <br><br>
    <p><a href="/admin/full-reset">FULD RESET - Slet alt og genimporter</a></p>
    <p><a href="/admin/upload-database">Upload database fil</a></p>
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


@app.route('/admin/upload-database', methods=['GET', 'POST'])
@login_required
def upload_database():
    """Upload en database fil direkte"""
    if session['user']['role'] != 'admin':
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

        flash(f'Database erstattet! Før: {before_units} units/{before_responses} responses, Nu: {units} units, {campaigns} målinger, {responses} responses. Toplevel: {names}', 'success')
    except Exception as e:
        import traceback
        return f'FEJL: {str(e)}.<br><br>Traceback:<pre>{traceback.format_exc()}</pre><br>Debug: {debug}'

    return redirect('/admin')


# ============================================
# ORGANISATIONS-DASHBOARD MED DRILL-DOWN
# ============================================

@app.route('/admin/dashboard')
@app.route('/admin/dashboard/<customer_id>')
@app.route('/admin/dashboard/<customer_id>/<unit_id>')
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

    # Hvis ikke admin, tving til egen kunde
    if user['role'] != 'admin':
        customer_id = user['customer_id']

    with get_db() as conn:
        # Niveau 1: Vis alle kunder (kun admin uden customer_id)
        if not customer_id and user['role'] == 'admin':
            customers = conn.execute("""
                SELECT
                    c.id,
                    c.name,
                    COUNT(DISTINCT ou.id) as unit_count,
                    COUNT(DISTINCT camp.id) as campaign_count,
                    COUNT(DISTINCT r.id) as response_count,
                    AVG(CASE
                        WHEN r.respondent_type = 'employee' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                    END) as avg_score
                FROM customers c
                LEFT JOIN organizational_units ou ON ou.customer_id = c.id
                LEFT JOIN campaigns camp ON camp.target_unit_id = ou.id
                LEFT JOIN responses r ON r.campaign_id = camp.id
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
            return redirect(url_for('org_dashboard'))

        # Niveau 2 & 3: Vis units under kunde eller parent unit
        if unit_id:
            # Drill-down: vis børn af denne unit
            parent_unit = conn.execute("SELECT * FROM organizational_units WHERE id = ?", [unit_id]).fetchone()
            if not parent_unit:
                flash('Enhed ikke fundet', 'error')
                return redirect(url_for('org_dashboard', customer_id=customer_id))

            parent_id_filter = unit_id
            current_level = parent_unit['level'] + 1

            # Byg breadcrumb
            breadcrumb = [{'name': 'Alle Organisationer', 'url': url_for('org_dashboard')}]
            breadcrumb.append({'name': customer['name'], 'url': url_for('org_dashboard', customer_id=customer_id)})

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
                breadcrumb.append({'name': pu['name'], 'url': url_for('org_dashboard', customer_id=customer_id, unit_id=pu['id'])})
            breadcrumb.append({'name': parent_unit['name'], 'url': None})

        else:
            # Top-level: vis root units for denne kunde
            parent_id_filter = None
            current_level = 0
            breadcrumb = [
                {'name': 'Alle Organisationer', 'url': url_for('org_dashboard')},
                {'name': customer['name'], 'url': None}
            ]
            parent_unit = None

        # Hent units på dette niveau med aggregerede scores
        if parent_id_filter:
            # Simplere query - henter direkte data for hver unit
            units_query = """
                SELECT
                    ou.id,
                    ou.name,
                    ou.level,
                    ou.leader_name,
                    (SELECT COUNT(*) FROM organizational_units WHERE parent_id = ou.id) as child_count,
                    (SELECT COUNT(DISTINCT camp.id) FROM campaigns camp WHERE camp.target_unit_id = ou.id) as campaign_count,
                    (SELECT COUNT(DISTINCT r.id) FROM responses r
                     JOIN campaigns camp ON r.campaign_id = camp.id WHERE camp.target_unit_id = ou.id) as response_count,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r
                     JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee') as avg_score,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee' AND q.field = 'MENING') as score_mening,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee' AND q.field = 'TRYGHED') as score_tryghed,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee' AND q.field = 'KAN') as score_kan,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee' AND q.field = 'BESVÆR') as score_besvaer,
                    (SELECT camp.id FROM campaigns camp WHERE camp.target_unit_id = ou.id LIMIT 1) as direct_campaign_id
                FROM organizational_units ou
                WHERE ou.parent_id = ?
                ORDER BY ou.name
            """
            units = conn.execute(units_query, [parent_id_filter]).fetchall()

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
            units = [dict(u) for u in units]
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
            # Root units for kunde - simplere query
            units_query = """
                SELECT
                    ou.id,
                    ou.name,
                    ou.level,
                    ou.leader_name,
                    (SELECT COUNT(*) FROM organizational_units WHERE parent_id = ou.id) as child_count,
                    (SELECT COUNT(DISTINCT camp.id) FROM campaigns camp WHERE camp.target_unit_id = ou.id) as campaign_count,
                    (SELECT COUNT(DISTINCT r.id) FROM responses r
                     JOIN campaigns camp ON r.campaign_id = camp.id WHERE camp.target_unit_id = ou.id) as response_count,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r
                     JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee') as avg_score,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee' AND q.field = 'MENING') as score_mening,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee' AND q.field = 'TRYGHED') as score_tryghed,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee' AND q.field = 'KAN') as score_kan,
                    (SELECT AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END)
                     FROM responses r JOIN campaigns camp ON r.campaign_id = camp.id
                     JOIN questions q ON r.question_id = q.id
                     WHERE camp.target_unit_id = ou.id AND r.respondent_type = 'employee' AND q.field = 'BESVÆR') as score_besvaer,
                    (SELECT camp.id FROM campaigns camp WHERE camp.target_unit_id = ou.id LIMIT 1) as direct_campaign_id
                FROM organizational_units ou
                WHERE ou.customer_id = ? AND ou.parent_id IS NULL
                ORDER BY ou.name
            """
            units = conn.execute(units_query, [customer_id]).fetchall()

            # Add profil_count to units
            units = [dict(u) for u in units]
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
                    AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                    AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as mening,
                    AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as tryghed,
                    AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as kan,
                    AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as besvaer,
                    COUNT(DISTINCT r.id) as response_count
                FROM responses r
                JOIN campaigns camp ON r.campaign_id = camp.id
                JOIN questions q ON r.question_id = q.id
                JOIN subtree st ON camp.target_unit_id = st.id
                WHERE r.respondent_type = 'employee'
            """, [unit_id]).fetchone()
        else:
            # Aggregér for hele kunden
            agg_scores = conn.execute("""
                SELECT
                    AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                    AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as mening,
                    AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as tryghed,
                    AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as kan,
                    AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as besvaer,
                    COUNT(DISTINCT r.id) as response_count
                FROM responses r
                JOIN campaigns camp ON r.campaign_id = camp.id
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
# BRANDING ROUTES (for admin users)
# ========================================

@app.route('/admin/my-branding')
@admin_required
def my_branding():
    """Admin users can edit branding for their customer's domains"""
    user = session['user']

    with get_db() as conn:
        # Superadmin can see all domains, admin sees their customer's domains
        if user['role'] == 'superadmin':
            domains = conn.execute("""
                SELECT d.*, c.name as customer_name
                FROM domains d
                LEFT JOIN customers c ON d.customer_id = c.id
                ORDER BY d.domain
            """).fetchall()
        else:
            # Admin sees only their customer's domains
            customer_id = user.get('customer_id')
            if not customer_id:
                flash('Ingen kunde tilknyttet din bruger', 'error')
                return redirect(url_for('analyser'))

            domains = conn.execute("""
                SELECT d.*, c.name as customer_name
                FROM domains d
                LEFT JOIN customers c ON d.customer_id = c.id
                WHERE d.customer_id = ?
                ORDER BY d.domain
            """, (customer_id,)).fetchall()

    return render_template('admin/my_branding.html', domains=domains)


@app.route('/admin/my-branding/<domain_id>/edit', methods=['POST'])
@admin_required
def edit_my_branding(domain_id):
    """Edit branding for a domain (with permission check)"""
    user = session['user']

    with get_db() as conn:
        # Get domain and check permission
        domain = conn.execute(
            "SELECT * FROM domains WHERE id = ?", (domain_id,)
        ).fetchone()

        if not domain:
            flash('Domæne ikke fundet', 'error')
            return redirect(url_for('my_branding'))

        # Check permission (superadmin can edit all, admin only their own)
        if user['role'] != 'superadmin':
            if domain['customer_id'] != user.get('customer_id'):
                flash('Du har ikke adgang til dette domæne', 'error')
                return redirect(url_for('my_branding'))

        # Update branding
        update_domain(
            domain_id,
            branding_logo_url=request.form.get('branding_logo_url') or None,
            branding_primary_color=request.form.get('branding_primary_color') or None,
            branding_company_name=request.form.get('branding_company_name') or None
        )

        flash(f'Branding for {domain["domain"]} opdateret!', 'success')

    return redirect(url_for('my_branding'))


# ========================================
# AUTH CONFIG ROUTES (superadmin only)
# ========================================

@app.route('/admin/auth-config')
@superadmin_required
def auth_config():
    """Configure authentication providers per customer (superadmin only)"""
    customers = list_customers()
    domains = list_domains()

    # Parse auth_providers JSON for each
    import json
    for customer in customers:
        try:
            customer['auth_providers_parsed'] = json.loads(customer.get('auth_providers') or '{}')
        except:
            customer['auth_providers_parsed'] = {}

    for domain in domains:
        try:
            domain['auth_providers_parsed'] = json.loads(domain.get('auth_providers') or '{}')
        except:
            domain['auth_providers_parsed'] = {}

    return render_template('admin/auth_config.html',
                         customers=customers,
                         domains=domains,
                         default_providers=DEFAULT_AUTH_PROVIDERS)


@app.route('/admin/auth-config/customer/<customer_id>', methods=['POST'])
@superadmin_required
def update_customer_auth(customer_id):
    """Update auth providers for a customer (superadmin only)"""
    import json

    providers = {
        'email_password': 'email_password' in request.form,
        'microsoft': {
            'enabled': 'microsoft' in request.form
        },
        'google': {
            'enabled': 'google' in request.form
        },
        'apple': {
            'enabled': 'apple' in request.form
        },
        'facebook': {
            'enabled': 'facebook' in request.form
        }
    }

    save_auth_providers('customer', customer_id, providers)
    flash('Auth providers opdateret for kunde!', 'success')

    return redirect(url_for('auth_config'))


@app.route('/admin/auth-config/domain/<domain_id>', methods=['POST'])
@superadmin_required
def update_domain_auth(domain_id):
    """Update auth providers for a domain (superadmin only)"""
    import json

    providers = {
        'email_password': 'email_password' in request.form,
        'microsoft': {
            'enabled': 'microsoft' in request.form
        },
        'google': {
            'enabled': 'google' in request.form
        },
        'apple': {
            'enabled': 'apple' in request.form
        },
        'facebook': {
            'enabled': 'facebook' in request.form
        }
    }

    save_auth_providers('domain', domain_id, providers)
    flash('Auth providers opdateret for domæne!', 'success')

    return redirect(url_for('auth_config'))


if __name__ == '__main__':
    app.run(debug=True, port=5001)

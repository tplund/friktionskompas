"""
Admin interface for Friktionskompasset v3
Hierarkisk organisationsstruktur med units + Multi-tenant
"""
from flask import Flask, render_template, request, redirect, url_for, flash, Response, session, jsonify, send_from_directory
import csv
import io
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from db_hierarchical import (
    init_db, create_unit, create_unit_from_path, create_assessment,
    create_individual_assessment, generate_tokens_for_assessment,
    get_unit_children, get_unit_path, get_leaf_units, validate_and_use_token,
    save_response, get_unit_stats, get_assessment_overview, get_questions,
    get_db, add_contacts_bulk, get_unit_contacts
)
from analysis import (
    get_detailed_breakdown, check_anonymity_threshold,
    get_layer_interpretation, calculate_substitution_db,
    get_free_text_comments, get_kkc_recommendations,
    get_start_here_recommendation, get_trend_data
)
# Import beregningsfunktioner fra central motor
from friction_engine import (
    score_to_percent, get_percent_class as engine_get_percent_class,
    get_severity, get_spread_level, THRESHOLDS, FRICTION_FIELDS,
    Severity, SpreadLevel
)
from db_multitenant import (
    authenticate_user, create_customer, create_user, list_customers,
    list_users, get_customer_filter, init_multitenant_db, get_customer, update_customer,
    get_domain_config, list_domains, create_domain, update_domain, delete_domain,
    generate_email_code, verify_email_code, find_user_by_email, create_b2c_user,
    get_or_create_b2c_customer, authenticate_by_email_code, reset_password_with_code,
    seed_assessment_types, get_all_assessment_types, get_all_presets,
    get_customer_assessment_config, set_customer_assessment_types, get_available_assessments,
    hash_password, verify_password
)
from csv_upload_hierarchical import (
    validate_csv_format, bulk_upload_from_csv, generate_csv_template
)
from mailjet_integration import (
    send_assessment_batch, get_email_stats, get_email_logs, update_email_status,
    get_template, save_template, list_templates, DEFAULT_TEMPLATES,
    check_and_notify_assessment_completed, send_login_code
)
from db_hierarchical import init_db
from db_profil import (
    init_profil_tables, get_all_questions as get_profil_questions,
    get_db as get_profil_db
)
from translations import t, get_user_language, set_language, SUPPORTED_LANGUAGES, seed_translations, clear_translation_cache
from scheduler import start_scheduler, get_scheduled_assessments, cancel_scheduled_assessment, reschedule_assessment
from oauth import (
    init_oauth, oauth, get_enabled_providers, get_provider_info,
    handle_oauth_callback, get_auth_providers_for_domain, save_auth_providers,
    DEFAULT_AUTH_PROVIDERS, get_user_oauth_links, link_oauth_to_user, unlink_oauth_from_user
)
from cache import get_cache_stats, invalidate_all, invalidate_assessment_cache, Pagination
from audit import log_action, AuditAction, get_audit_logs, get_audit_log_count, get_action_summary, init_audit_tables

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

# Start scheduler for planned assessments
start_scheduler()

# Seed translations and clear cache on startup
seed_translations()  # Ensures translations exist in database
clear_translation_cache()  # Clear any stale cached values

app = Flask(__name__)

# Sikker secret key fra miljøvariabel (fallback til autogeneret i development)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Session configuration - timeout efter 8 timers inaktivitet
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Refresh timeout ved aktivitet

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
        # Auto-set customer filter based on domain if user is admin/superadmin and no filter set
        if domain_config.get('customer_id') and 'user' in session:
            if session['user']['role'] in ('admin', 'superadmin') and 'customer_filter' not in session:
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
        """Convert 1-5 score to percent (1=0%, 5=100%)"""
        if score is None or score == 0:
            return 0
        # Convert 1-5 scale to 0-100%
        return ((score - 1) / 4) * 100

    # Rolle-simulation info
    simulated_role = session.get('simulated_role')
    is_simulating = 'user' in session and session['user'].get('role') == 'superadmin' and simulated_role is not None
    # Effective role - hvad brugeren ser systemet som
    actual_role = session['user'].get('role') if 'user' in session else None
    effective_role = simulated_role if is_simulating else actual_role

    return dict(
        customers=customers,
        get_score_class=get_score_class,
        get_percent_class=get_percent_class,
        get_gap_class=get_gap_class,
        to_percent=to_percent,
        simulated_role=simulated_role,
        is_simulating=is_simulating,
        effective_role=effective_role,
        actual_role=actual_role
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
            return redirect(url_for('admin_home'))
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
            return redirect(url_for('admin_home'))
        return f(*args, **kwargs)
    return decorated_function


def check_admin_api_key():
    """Check for valid admin API key in request header.
    Returns True if valid API key found, False otherwise.
    API key should be passed in X-Admin-API-Key header.
    """
    api_key = request.headers.get('X-Admin-API-Key')
    if not api_key:
        return False
    expected_key = os.environ.get('ADMIN_API_KEY')
    if not expected_key:
        return False
    return api_key == expected_key


def is_api_request():
    """Check if request is from API client (expects JSON response)"""
    return (
        request.headers.get('Accept') == 'application/json' or
        check_admin_api_key() or
        request.args.get('format') == 'json'
    )


def api_or_admin_required(f):
    """Decorator that accepts either admin session OR valid API key.
    Returns JSON for API requests, HTML redirect for browser requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check API key first
        if check_admin_api_key():
            return f(*args, **kwargs)
        # Fall back to session auth
        if 'user' not in session:
            if is_api_request():
                return jsonify({'error': 'Authentication required'}), 401
            flash('Du skal være logget ind', 'error')
            return redirect(url_for('login'))
        if session['user']['role'] not in ('admin', 'superadmin'):
            if is_api_request():
                return jsonify({'error': 'Admin access required'}), 403
            flash('Kun admin har adgang til denne side', 'error')
            return redirect(url_for('admin_home'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Hent current user fra session"""
    return session.get('user')


def get_effective_role():
    """Returnerer den effektive rolle - simuleret eller faktisk"""
    user = get_current_user()
    if not user:
        return None
    # Superadmin kan simulere andre roller
    if user.get('role') == 'superadmin' and 'simulated_role' in session:
        return session['simulated_role']
    return user.get('role')


def is_role_simulated():
    """Returnerer True hvis superadmin simulerer en anden rolle"""
    user = get_current_user()
    if not user:
        return False
    return user.get('role') == 'superadmin' and 'simulated_role' in session


@app.route('/')
def index():
    """Root route - show landing page or redirect to admin if logged in"""
    if 'user' in session:
        return redirect(url_for('admin_home'))
    return render_template('landing.html')


@app.route('/landing')
def landing():
    """Public landing page"""
    return render_template('landing.html')


@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for SEO"""
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')


# Admin API endpoints - authenticated via X-Admin-API-Key header
@app.route('/api/admin/status')
@api_or_admin_required
def api_admin_status():
    """Get admin API status and database info.

    API Usage:
        curl https://friktionskompasset.dk/api/admin/status \
             -H "X-Admin-API-Key: YOUR_KEY"
    """
    with get_db() as conn:
        counts = {}
        for table in ['customers', 'users', 'assessments', 'responses', 'domains', 'translations']:
            try:
                count = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                counts[table] = count
            except:
                counts[table] = 'N/A'

        domains = conn.execute('SELECT domain, default_language FROM domains WHERE is_active = 1').fetchall()

    return jsonify({
        'status': 'ok',
        'database': counts,
        'active_domains': [{'domain': d[0], 'language': d[1]} for d in domains],
        'available_endpoints': [
            {'endpoint': '/api/admin/status', 'method': 'GET', 'description': 'Get API status'},
            {'endpoint': '/admin/seed-domains', 'method': 'GET/POST', 'description': 'Seed default domains'},
            {'endpoint': '/admin/seed-translations', 'method': 'GET/POST', 'description': 'Seed translations'},
            {'endpoint': '/api/admin/clear-cache', 'method': 'POST', 'description': 'Clear all caches'},
        ]
    })


@app.route('/api/admin/clear-cache', methods=['POST'])
@api_or_admin_required
def api_admin_clear_cache():
    """Clear all caches.

    API Usage:
        curl -X POST https://friktionskompasset.dk/api/admin/clear-cache \
             -H "X-Admin-API-Key: YOUR_KEY"
    """
    clear_translation_cache()
    invalidate_all()
    return jsonify({'success': True, 'message': 'All caches cleared'})


@app.route('/sitemap.xml')
def sitemap_xml():
    """Generate dynamic sitemap.xml"""
    base_url = request.url_root.rstrip('/')
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{base_url}/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{base_url}/profil/local</loc>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{base_url}/help</loc>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>'''
    return Response(xml, mimetype='application/xml')


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
            session.permanent = True  # Aktivér session timeout
            # Audit log successful login
            log_action(
                AuditAction.LOGIN_SUCCESS,
                entity_type="user",
                entity_id=user.get('id'),
                details=f"User {username} logged in",
                user_id=user.get('id'),
                username=username,
                customer_id=user.get('customer_id')
            )
            flash(f'Velkommen {user["name"]}!', 'success')
            return redirect(url_for('admin_home'))
        else:
            # Audit log failed login attempt
            log_action(
                AuditAction.LOGIN_FAILED,
                entity_type="user",
                details=f"Failed login attempt for username: {username}",
                username=username
            )
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
            session.permanent = True  # Aktivér session timeout
            flash(f'Velkommen {user["name"]}!', 'success')
            return redirect(url_for('admin_home'))
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
    # Audit log logout
    user = session.get('user')
    if user:
        log_action(
            AuditAction.LOGOUT,
            entity_type="user",
            entity_id=user.get('id'),
            details=f"User {user.get('username')} logged out"
        )
    session.pop('user', None)
    flash('Du er nu logget ud', 'success')
    return redirect('/')


# ========================================
# ACCOUNT SETTINGS & OAUTH LINKING
# ========================================

@app.route('/admin/my-account', methods=['GET', 'POST'])
@login_required
def admin_my_account():
    """Account settings page - manage profile and linked OAuth accounts"""
    user = session.get('user')
    user_id = user.get('id')

    # Get full user details from database
    with get_db() as conn:
        user_details = conn.execute("""
            SELECT u.*, c.name as customer_name, c.allow_profile_edit
            FROM users u
            LEFT JOIN customers c ON u.customer_id = c.id
            WHERE u.id = ?
        """, (user_id,)).fetchone()

    # Determine if user can edit profile
    # Superadmin can always edit, otherwise check customer setting
    effective_role = session.get('simulated_role') or user.get('role')
    if user_details:
        allow_edit = user_details['allow_profile_edit']
        can_edit_profile = (
            effective_role == 'superadmin' or
            allow_edit == 1 or
            allow_edit is None  # Default to true
        )
    else:
        can_edit_profile = effective_role == 'superadmin'

    if request.method == 'POST' and can_edit_profile:
        name = request.form.get('name', '').strip()
        recovery_email = request.form.get('recovery_email', '').strip() or None

        if not name:
            flash('Navn må ikke være tomt', 'error')
        else:
            with get_db() as conn:
                conn.execute("""
                    UPDATE users SET name = ?, recovery_email = ? WHERE id = ?
                """, (name, recovery_email, user_id))

            # Update session
            session['user']['name'] = name
            flash('Profil opdateret', 'success')

        return redirect(url_for('admin_my_account'))

    # Get linked OAuth accounts
    linked_accounts = get_user_oauth_links(user_id)
    linked_providers = {link['provider'] for link in linked_accounts}

    # Get available providers that are enabled for this domain
    domain = request.host.split(':')[0].lower()
    enabled_providers = get_enabled_providers(domain)

    # Filter to only OAuth providers (not email_password)
    available_providers = []
    for provider in ['microsoft', 'google']:
        if provider in enabled_providers and provider not in linked_providers:
            available_providers.append({
                'id': provider,
                'info': get_provider_info(provider)
            })

    # Add info to linked accounts
    for link in linked_accounts:
        link['info'] = get_provider_info(link['provider'])

    # Check if user has password (not OAuth-only)
    has_password = False
    if user_details and user_details['password_hash']:
        pw_hash = user_details['password_hash']
        has_password = not (pw_hash.startswith('oauth-') or pw_hash.startswith('b2c-'))

    return render_template('admin/my_account.html',
                           user_details=dict(user_details) if user_details else {},
                           can_edit_profile=can_edit_profile,
                           has_password=has_password,
                           linked_accounts=linked_accounts,
                           available_providers=available_providers)


@app.route('/admin/change-password', methods=['POST'])
@login_required
def admin_change_password():
    """Change user password"""
    user = session.get('user')
    user_id = user.get('id')

    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        flash('Alle felter skal udfyldes', 'error')
        return redirect(url_for('admin_my_account'))

    if new_password != confirm_password:
        flash('De nye passwords matcher ikke', 'error')
        return redirect(url_for('admin_my_account'))

    if len(new_password) < 8:
        flash('Password skal være mindst 8 tegn', 'error')
        return redirect(url_for('admin_my_account'))

    # Get current password hash
    with get_db() as conn:
        user_row = conn.execute("""
            SELECT password_hash FROM users WHERE id = ?
        """, (user_id,)).fetchone()

    if not user_row:
        flash('Bruger ikke fundet', 'error')
        return redirect(url_for('admin_my_account'))

    # Check if user has OAuth-only login (no password set)
    if user_row['password_hash'].startswith('oauth-') or user_row['password_hash'].startswith('b2c-'):
        flash('Du bruger OAuth login og har ikke et password at ændre', 'error')
        return redirect(url_for('admin_my_account'))

    # Verify current password
    if not verify_password(current_password, user_row['password_hash']):
        flash('Nuværende password er forkert', 'error')
        return redirect(url_for('admin_my_account'))

    # Hash and save new password
    new_hash = hash_password(new_password)
    with get_db() as conn:
        conn.execute("""
            UPDATE users SET password_hash = ? WHERE id = ?
        """, (new_hash, user_id))

    flash('Password ændret succesfuldt', 'success')
    return redirect(url_for('admin_my_account'))


@app.route('/admin/link-oauth/<provider>')
@login_required
def admin_link_oauth(provider):
    """Start OAuth flow to link account"""
    if provider not in ['microsoft', 'google']:
        flash('Ukendt login-metode', 'error')
        return redirect(url_for('admin_my_account'))

    # Check if provider is enabled for this domain
    domain = request.host.split(':')[0].lower()
    enabled = get_enabled_providers(domain)

    if provider not in enabled:
        flash(f'{provider.title()} er ikke aktiveret for dette domæne', 'error')
        return redirect(url_for('admin_my_account'))

    # Check if already linked
    user = session.get('user')
    linked_accounts = get_user_oauth_links(user.get('id'))
    if any(link['provider'] == provider for link in linked_accounts):
        flash(f'{provider.title()} er allerede tilknyttet din konto', 'warning')
        return redirect(url_for('admin_my_account'))

    # Get the OAuth client
    client = oauth.create_client(provider)
    if not client:
        flash(f'{provider.title()} er ikke konfigureret', 'error')
        return redirect(url_for('admin_my_account'))

    # Store that we're linking (not logging in)
    session['oauth_linking'] = True

    # Generate redirect URI to the linking callback
    redirect_uri = url_for('admin_link_oauth_callback', provider=provider, _external=True)

    return client.authorize_redirect(redirect_uri)


@app.route('/admin/link-oauth/<provider>/callback')
@login_required
def admin_link_oauth_callback(provider):
    """Handle OAuth callback for account linking"""
    if provider not in ['microsoft', 'google']:
        flash('Ukendt login-metode', 'error')
        return redirect(url_for('admin_my_account'))

    # Check that we initiated linking
    if not session.pop('oauth_linking', False):
        flash('Ugyldig linking-anmodning', 'error')
        return redirect(url_for('admin_my_account'))

    try:
        client = oauth.create_client(provider)
        if not client:
            flash(f'{provider.title()} er ikke konfigureret', 'error')
            return redirect(url_for('admin_my_account'))

        # Get token - compliance_fix in oauth.py handles Microsoft multi-tenant
        token = client.authorize_access_token()

        # Get user info
        if provider == 'microsoft':
            # Always fetch from Graph API for Microsoft
            resp = client.get('https://graph.microsoft.com/oidc/userinfo', token=token)
            userinfo = resp.json()
        elif provider == 'google':
            userinfo = token.get('userinfo')
            if not userinfo:
                resp = client.get('https://openidconnect.googleapis.com/v1/userinfo')
                userinfo = resp.json()
        else:
            userinfo = token.get('userinfo', {})

        # Extract provider user ID
        provider_user_id = userinfo.get('sub') or userinfo.get('oid')
        provider_email = userinfo.get('email') or userinfo.get('preferred_username')

        if not provider_user_id:
            flash('Kunne ikke hente bruger-ID fra provider', 'error')
            return redirect(url_for('admin_my_account'))

        # Link to current user
        user = session.get('user')
        success = link_oauth_to_user(
            user_id=user.get('id'),
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            access_token=token.get('access_token'),
            refresh_token=token.get('refresh_token')
        )

        if success:
            provider_name = get_provider_info(provider).get('name', provider.title())
            flash(f'{provider_name} er nu tilknyttet din konto', 'success')

            # Log the action
            log_action(
                AuditAction.USER_UPDATED,
                entity_type="user",
                entity_id=user.get('id'),
                details=f"Linked {provider} account ({provider_email})"
            )
        else:
            flash('Kunne ikke tilknytte konto', 'error')

    except Exception as e:
        import traceback
        print(f"[OAuth] Link callback error for {provider}: {e}")
        print(f"[OAuth] Traceback: {traceback.format_exc()}")
        flash(f'Fejl ved tilknytning af {provider.title()}: {str(e)}', 'error')

    return redirect(url_for('admin_my_account'))


@app.route('/admin/unlink-oauth/<provider>', methods=['POST'])
@login_required
def admin_unlink_oauth(provider):
    """Unlink an OAuth account"""
    user = session.get('user')

    # Check that user has this provider linked
    linked_accounts = get_user_oauth_links(user.get('id'))
    if not any(link['provider'] == provider for link in linked_accounts):
        flash(f'{provider.title()} er ikke tilknyttet din konto', 'warning')
        return redirect(url_for('admin_my_account'))

    # Don't allow unlinking if it's the only login method
    # (user must have email/password or another OAuth provider)
    with get_db() as conn:
        user_row = conn.execute("""
            SELECT password_hash FROM users WHERE id = ?
        """, (user.get('id'),)).fetchone()

    has_password = user_row and user_row['password_hash'] and not user_row['password_hash'].startswith('oauth-')
    other_oauth_count = len([l for l in linked_accounts if l['provider'] != provider])

    if not has_password and other_oauth_count == 0:
        flash('Du kan ikke fjerne din eneste login-metode. Tilknyt en anden konto eller opret en adgangskode først.', 'error')
        return redirect(url_for('admin_my_account'))

    # Unlink
    success = unlink_oauth_from_user(user.get('id'), provider)

    if success:
        provider_name = get_provider_info(provider).get('name', provider.title())
        flash(f'{provider_name} er nu fjernet fra din konto', 'success')

        # Log the action
        log_action(
            AuditAction.USER_UPDATED,
            entity_type="user",
            entity_id=user.get('id'),
            details=f"Unlinked {provider} account"
        )
    else:
        flash('Kunne ikke fjerne tilknytning', 'error')

    return redirect(url_for('admin_my_account'))


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
                    session.permanent = True  # Aktivér session timeout
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
            session.permanent = True  # Aktivér session timeout
            session.pop('pending_email_login', None)
            flash(f'Velkommen {user["name"]}!', 'success')

            # Redirect baseret på rolle
            if user['role'] == 'user':
                return redirect(url_for('user_home'))
            else:
                return redirect(url_for('admin_home'))
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
        return redirect(url_for('admin_home'))

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


@app.route('/admin/seed-translations', methods=['GET', 'POST'])
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
    return redirect(request.referrer or url_for('admin_home'))


@app.route('/admin/seed-domains', methods=['GET', 'POST'])
@api_or_admin_required
def admin_seed_domains():
    """Seed standard domæner til database. Supports both browser and API access.

    API Usage:
        curl https://friktionskompasset.dk/admin/seed-domains \
             -H "X-Admin-API-Key: YOUR_KEY"
    """
    import json
    import secrets

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
    return redirect(request.referrer or url_for('manage_domains'))


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
        conn.execute("DELETE FROM assessments")
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
    from db_hierarchical import create_assessment, get_questions, get_all_leaf_units_under

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
                    target_unit_id=unit['id'],
                    name=f"{unit['name']} - {period}",
                    period=period,
                    sent_from='admin'
                )
                assessments_created += 1

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
                                INSERT INTO responses (assessment_id, unit_id, question_id, score)
                                VALUES (?, ?, ?, ?)
                            """, (assessment_id, leaf_unit['id'], question['id'], score))
                            responses_created += 1

    flash(f'Testdata genereret! {stats["units_created"]} organisationer, {stats["contacts_created"]} kontakter, {assessments_created} målinger og {responses_created} svar oprettet.', 'success')
    return redirect(url_for('admin_home'))


@app.route('/admin')
@login_required
def admin_home():
    """Dashboard v2 - kombineret oversigt med KPIs, trend, og analyser"""
    user = get_current_user()
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
                AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
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
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_mening,

                AVG(CASE
                    WHEN q.field = 'TRYGHED' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_tryghed,

                AVG(CASE
                    WHEN q.field = 'KAN' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
                END) as employee_kan,

                AVG(CASE
                    WHEN q.field = 'BESVÆR' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
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


@app.route('/admin/units')
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
                AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
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


@app.route('/admin/trend')
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


@app.route('/admin/assessments-overview')
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
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
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
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
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


@app.route('/admin/scheduled-assessments')
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


@app.route('/admin/assessment/<assessment_id>/cancel', methods=['POST'])
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
            return redirect(url_for('scheduled_assessments'))

    # Annuller kampagnen
    success = cancel_scheduled_assessment(assessment_id)
    if success:
        flash('Planlagt måling annulleret', 'success')
    else:
        flash('Kunne ikke annullere målingen', 'error')

    return redirect(url_for('scheduled_assessments'))


@app.route('/admin/assessment/<assessment_id>/reschedule', methods=['POST'])
@login_required
def reschedule_assessment_route(assessment_id):
    """Ændr tidspunkt for en planlagt måling"""
    user = get_current_user()
    from datetime import datetime

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
            return redirect(url_for('scheduled_assessments'))

    # Hent nyt tidspunkt fra form
    new_date = request.form.get('new_date', '').strip()
    new_time = request.form.get('new_time', '08:00').strip()

    if not new_date:
        flash('Vælg en ny dato', 'error')
        return redirect(url_for('scheduled_assessments'))

    new_scheduled_at = datetime.fromisoformat(f"{new_date}T{new_time}:00")

    success = reschedule_assessment(assessment_id, new_scheduled_at)
    if success:
        flash(f'Måling flyttet til {new_date} kl. {new_time}', 'success')
    else:
        flash('Kunne ikke ændre tidspunkt', 'error')

    return redirect(url_for('scheduled_assessments'))


@app.route('/admin/analyser')
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

                # Get trend data if there are multiple assessments
                trend_data = None
                assessment_count = conn.execute("""
                    SELECT COUNT(*) FROM assessments WHERE target_unit_id = ?
                """, [unit_id]).fetchone()[0]

                if assessment_count >= 2:
                    # Calculate trend from oldest to newest assessment
                    trend_query = """
                        SELECT
                            a.id,
                            a.name,
                            a.created_at,
                            AVG(CASE WHEN r.respondent_type = 'employee' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as overall,
                            AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as mening,
                            AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as tryghed,
                            AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as kan,
                            AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                                CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as besvaer
                        FROM assessments a
                        JOIN responses r ON a.id = r.assessment_id
                        JOIN questions q ON r.question_id = q.id
                        WHERE a.target_unit_id = ?
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
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_overall,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_mening,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_tryghed,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_kan,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_besvaer,

                        AVG(CASE WHEN r.respondent_type = 'leader_assess' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_overall,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_mening,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_tryghed,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_kan,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_besvaer

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
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_overall,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_mening,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_tryghed,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_kan,
                        AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_besvaer,

                        AVG(CASE WHEN r.respondent_type = 'leader_assess' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_overall,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'MENING' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_mening,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'TRYGHED' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_tryghed,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'KAN' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_kan,
                        AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'BESVÆR' THEN
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_besvaer

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
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_overall,
                    AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_mening,
                    AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_tryghed,
                    AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_kan,
                    AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_besvaer,

                    -- Leader assessment scores
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_overall,
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'MENING' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_mening,
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'TRYGHED' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_tryghed,
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'KAN' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_kan,
                    AVG(CASE WHEN r.respondent_type = 'leader_assess' AND q.field = 'BESVÆR' THEN
                        CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as leader_besvaer

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


@app.route('/api/debug-analyser/<unit_id>')
def debug_analyser(unit_id):
    """Debug endpoint - viser raw data for analyser beregning"""
    from flask import jsonify

    with get_db() as conn:
        # Først: tjek reverse_scored statistik i denne database
        reverse_stats = conn.execute("""
            SELECT
                COUNT(*) as total_questions,
                SUM(CASE WHEN reverse_scored = 1 THEN 1 ELSE 0 END) as reverse_questions,
                SUM(CASE WHEN reverse_scored = 0 THEN 1 ELSE 0 END) as normal_questions
            FROM questions
            WHERE is_default = 1
        """).fetchone()

        # Tjek specifikt for denne unit's responses
        response_check = conn.execute("""
            SELECT
                q.reverse_scored,
                COUNT(*) as count,
                AVG(r.score) as raw_avg,
                AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as adj_avg
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            JOIN assessments a ON r.assessment_id = a.id
            WHERE a.target_unit_id = ?
              AND r.respondent_type = 'employee'
            GROUP BY q.reverse_scored
        """, [unit_id]).fetchall()

        # Tjek for responses der IKKE matcher questions (orphan responses)
        orphan_check = conn.execute("""
            SELECT
                COUNT(*) as orphan_count,
                GROUP_CONCAT(DISTINCT r.question_id) as orphan_question_ids
            FROM responses r
            LEFT JOIN questions q ON r.question_id = q.id
            JOIN assessments a ON r.assessment_id = a.id
            WHERE a.target_unit_id = ?
              AND r.respondent_type = 'employee'
              AND q.id IS NULL
        """, [unit_id]).fetchone()

        # List alle unikke question_ids i responses
        response_question_ids = conn.execute("""
            SELECT DISTINCT r.question_id, q.id as q_found, q.reverse_scored
            FROM responses r
            LEFT JOIN questions q ON r.question_id = q.id
            JOIN assessments a ON r.assessment_id = a.id
            WHERE a.target_unit_id = ?
              AND r.respondent_type = 'employee'
            ORDER BY r.question_id
        """, [unit_id]).fetchall()

        # Samme query som analyser endpoint
        query = """
            SELECT
                ou.id,
                ou.name,
                c.id as assessment_id,
                c.name as assessment_name,
                COUNT(DISTINCT r.id) as total_responses,

                AVG(CASE WHEN r.respondent_type = 'employee' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_overall,
                AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'MENING' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_mening,
                AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'TRYGHED' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_tryghed,
                AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'KAN' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_kan,
                AVG(CASE WHEN r.respondent_type = 'employee' AND q.field = 'BESVÆR' THEN
                    CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as employee_besvaer

            FROM organizational_units ou
            JOIN assessments c ON c.target_unit_id = ou.id
            JOIN responses r ON c.id = r.assessment_id
            JOIN questions q ON r.question_id = q.id
            WHERE ou.id = ?
            GROUP BY ou.id, c.id
        """

        result = conn.execute(query, [unit_id]).fetchone()

        if not result:
            return jsonify({'error': 'No data found', 'unit_id': unit_id})

        def to_percent(score):
            if score is None:
                return None
            return round(((score - 1) / 4) * 100, 1)

        return jsonify({
            'unit_id': result['id'],
            'unit_name': result['name'],
            'assessment_id': result['assessment_id'],
            'assessment_name': result['assessment_name'],
            'total_responses': result['total_responses'],
            'database_check': {
                'total_default_questions': reverse_stats['total_questions'],
                'reverse_scored_questions': reverse_stats['reverse_questions'],
                'normal_questions': reverse_stats['normal_questions'],
            },
            'response_breakdown': [
                {
                    'reverse_scored': row['reverse_scored'],
                    'count': row['count'],
                    'raw_avg': round(row['raw_avg'], 2) if row['raw_avg'] else None,
                    'adjusted_avg': round(row['adj_avg'], 2) if row['adj_avg'] else None,
                }
                for row in response_check
            ],
            'orphan_responses': {
                'count': orphan_check['orphan_count'],
                'question_ids': orphan_check['orphan_question_ids'],
            },
            'question_id_mapping': [
                {
                    'response_question_id': row['question_id'],
                    'found_in_questions': row['q_found'],
                    'reverse_scored': row['reverse_scored'],
                }
                for row in response_question_ids
            ],
            'raw_scores': {
                'employee_overall': round(result['employee_overall'], 2) if result['employee_overall'] else None,
                'employee_mening': round(result['employee_mening'], 2) if result['employee_mening'] else None,
                'employee_tryghed': round(result['employee_tryghed'], 2) if result['employee_tryghed'] else None,
                'employee_kan': round(result['employee_kan'], 2) if result['employee_kan'] else None,
                'employee_besvaer': round(result['employee_besvaer'], 2) if result['employee_besvaer'] else None,
            },
            'percentages': {
                'employee_overall': to_percent(result['employee_overall']),
                'employee_mening': to_percent(result['employee_mening']),
                'employee_tryghed': to_percent(result['employee_tryghed']),
                'employee_kan': to_percent(result['employee_kan']),
                'employee_besvaer': to_percent(result['employee_besvaer']),
            }
        })


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
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
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
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
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

        # Audit log unit deletion
        log_action(
            AuditAction.UNIT_DELETED,
            entity_type="unit",
            entity_id=unit_id,
            details=f"Deleted unit: {unit_name}"
        )

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
        # - assessments
        # - responses
        # - users tilknyttet kunden
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

        # Audit log customer deletion
        log_action(
            AuditAction.CUSTOMER_DELETED,
            entity_type="customer",
            entity_id=customer_id,
            details=f"Deleted customer: {customer_name}"
        )

    flash(f'Kunde "{customer_name}" og alle tilhørende data er slettet', 'success')
    return redirect(url_for('admin_home'))


@app.route('/admin/units/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_units():
    """Slet flere organisationer på én gang"""
    user = get_current_user()

    if user['role'] not in ('admin', 'superadmin'):
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


@app.route('/admin/assessment/new', methods=['GET', 'POST'])
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
                return redirect(url_for('new_assessment'))

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
                flash(f'📅 Individuel måling planlagt til {scheduled_date} kl. {scheduled_time}', 'success')
                return redirect(url_for('scheduled_assessments'))
            else:
                flash(f'Individuel måling sendt til {target_email}!', 'success')
                return redirect(url_for('view_assessment', assessment_id=assessment_id))

        else:
            # ===== ORGANISATIONS MÅLING (original logik) =====
            target_unit_id = request.form.get('target_unit_id')
            if not target_unit_id:
                flash('Vælg en organisation', 'error')
                return redirect(url_for('new_assessment'))

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
                flash(f'📅 Måling planlagt til {scheduled_date} kl. {scheduled_time}', 'success')
                return redirect(url_for('scheduled_assessments'))
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
                return redirect(url_for('view_assessment', assessment_id=assessment_id))

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


@app.route('/admin/assessment/<assessment_id>')
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
            return redirect(url_for('admin_home'))

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


@app.route('/admin/assessment/<assessment_id>/delete', methods=['POST'])
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
            return redirect(url_for('assessments_overview'))

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

    return redirect(url_for('assessments_overview'))


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
    # Audit log impersonation end
    if 'original_user' in session and session.get('impersonating'):
        original_user = session.get('original_user', {})
        impersonated_user = session.get('user', {})
        log_action(
            AuditAction.IMPERSONATE_END,
            entity_type="user",
            entity_id=impersonated_user.get('id'),
            details=f"Admin {original_user.get('username')} stopped impersonating {impersonated_user.get('username')}",
            user_id=original_user.get('id'),
            username=original_user.get('username')
        )

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


@app.route('/admin/simulate-role/<role>')
@login_required
def simulate_role(role):
    """Superadmin: Simuler en anden rolle for at se systemet som den rolle"""
    user = get_current_user()
    if user['role'] != 'superadmin':
        flash('Kun superadmin kan simulere roller', 'error')
        return redirect(url_for('admin_home'))

    if role == 'clear' or role == '':
        session.pop('simulated_role', None)
        flash('Viser som Superadmin', 'info')
    elif role in ('admin', 'manager'):
        session['simulated_role'] = role
        flash(f'Viser systemet som {role.title()}', 'info')
    else:
        flash('Ugyldig rolle', 'error')

    # Return to originating page
    next_url = request.args.get('next', '')
    if next_url:
        return redirect(next_url)
    return redirect(url_for('admin_home'))


@app.route('/admin/impersonate')
@superadmin_required
def impersonate_user_page():
    """Superadmin: Søg og vælg bruger at impersonere"""
    search = request.args.get('search', '').strip()

    with get_db() as conn:
        if search:
            users = conn.execute("""
                SELECT u.id, u.username, u.name, u.email, u.role, u.is_active,
                       c.name as customer_name
                FROM users u
                LEFT JOIN customers c ON u.customer_id = c.id
                WHERE u.role != 'superadmin'
                  AND (u.username LIKE ? OR u.name LIKE ? OR u.email LIKE ? OR c.name LIKE ?)
                ORDER BY u.name
                LIMIT 50
            """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()
        else:
            users = conn.execute("""
                SELECT u.id, u.username, u.name, u.email, u.role, u.is_active,
                       c.name as customer_name
                FROM users u
                LEFT JOIN customers c ON u.customer_id = c.id
                WHERE u.role != 'superadmin'
                ORDER BY u.name
                LIMIT 50
            """).fetchall()

    return render_template('admin/impersonate.html',
                         users=[dict(u) for u in users],
                         search=search)


@app.route('/admin/impersonate/<user_id>', methods=['POST'])
@superadmin_required
def impersonate_user(user_id):
    """Superadmin: Log ind som en anden bruger"""
    with get_db() as conn:
        target_user = conn.execute("""
            SELECT u.*, c.name as customer_name
            FROM users u
            LEFT JOIN customers c ON u.customer_id = c.id
            WHERE u.id = ? AND u.role != 'superadmin'
        """, (user_id,)).fetchone()

        if not target_user:
            flash('Bruger ikke fundet eller kan ikke impersoneres', 'error')
            return redirect(url_for('impersonate_user_page'))

        # Gem original bruger så vi kan vende tilbage
        session['original_user'] = session['user']
        session['impersonating'] = True

        # Skift til target user
        session['user'] = {
            'id': target_user['id'],
            'username': target_user['username'],
            'name': target_user['name'],
            'email': target_user['email'],
            'role': target_user['role'],
            'customer_id': target_user['customer_id'],
            'customer_name': target_user['customer_name']
        }
        session.permanent = True  # Behold session timeout ved impersonation

        # Sæt customer filter til brugerens kunde
        if target_user['customer_id']:
            session['customer_filter'] = target_user['customer_id']
            session['customer_filter_name'] = target_user['customer_name']

        # Audit log impersonation start
        original_user = session.get('original_user', {})
        log_action(
            AuditAction.IMPERSONATE_START,
            entity_type="user",
            entity_id=user_id,
            details=f"Admin {original_user.get('username')} impersonating {target_user['username']}",
            user_id=original_user.get('id'),
            username=original_user.get('username')
        )

        flash(f'Du er nu logget ind som {target_user["name"]} ({target_user["role"]})', 'info')

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
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))

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
        assessments = conn.execute(f"""
            SELECT c.*, ou.name as unit_name
            FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE {where_clause}
            ORDER BY c.created_at DESC
            LIMIT 10
        """, params).fetchall()

    return render_template('manager_dashboard.html',
                         units=[dict(u) for u in units],
                         assessments=[dict(c) for c in assessments])


@app.route('/admin/unit/<unit_id>/dashboard')
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
            return redirect(url_for('admin_home'))

        # Find seneste kampagne for denne unit
        latest_assessment = conn.execute("""
            SELECT * FROM assessments
            WHERE target_unit_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (unit_id,)).fetchone()

    if not latest_assessment:
        flash('❌ Ingen målinger endnu', 'error')
        return redirect(url_for('view_unit', unit_id=unit_id))

    # Breadcrumbs
    breadcrumbs = get_unit_path(unit_id)

    # Overview af leaf units
    overview = get_assessment_overview(latest_assessment['id'])

    return render_template('admin/unit_dashboard.html',
                         unit=dict(unit),
                         breadcrumbs=breadcrumbs,
                         assessment=dict(latest_assessment),
                         units=overview)


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


@app.route('/admin/assessment/<assessment_id>/detailed')
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
                return redirect(url_for('admin_home'))

        target_unit_id = assessment['target_unit_id']
        assessment_customer_id = assessment['customer_id']

        # Check anonymity
        anonymity = check_anonymity_threshold(assessment_id, target_unit_id)

        if not anonymity.get('can_show_results'):
            flash(f"Ikke nok svar endnu. {anonymity.get('response_count', 0)} af {anonymity.get('min_required', 5)} modtaget.", 'warning')
            return redirect(url_for('view_assessment', assessment_id=assessment_id))

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
        from analysis import get_alerts_and_findings
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
                from datetime import datetime
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


# DEVELOPMENT ONLY - TEST ENDPOINT (REMOVE BEFORE PRODUCTION!)
@app.route('/test/assessment/<assessment_id>/detailed')
def assessment_detailed_test(assessment_id):
    """TEST ENDPOINT - Detaljeret analyse UDEN login krav.
    VIGTIGT: Fjern denne endpoint før produktion!"""
    import traceback

    try:
        with get_db() as conn:
            # Hent assessment uden adgangskontrol
            assessment = conn.execute("""
                SELECT c.*, ou.customer_id FROM assessments c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE c.id = ?
            """, [assessment_id]).fetchone()

            if not assessment:
                return f"<h1>Måling ikke fundet: {assessment_id}</h1>", 404

        target_unit_id = assessment['target_unit_id']
        assessment_customer_id = assessment['customer_id']

        # Check anonymity
        anonymity = check_anonymity_threshold(assessment_id, target_unit_id)

        if not anonymity.get('can_show_results'):
            return f"<h1>Ikke nok svar endnu</h1><p>{anonymity.get('response_count', 0)} af {anonymity.get('min_required', 5)} modtaget.</p>", 400

        # Get detailed breakdown
        breakdown = get_detailed_breakdown(target_unit_id, assessment_id, include_children=True)

        # Calculate substitution (tid-bias)
        substitution = calculate_substitution_db(target_unit_id, assessment_id, 'employee')
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
        from analysis import get_alerts_and_findings
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
                from datetime import datetime
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
        return f"<h1>Fejl i assessment_detailed_test</h1><pre>{error_details}</pre>", 500


@app.route('/admin/assessment/<assessment_id>/pdf')
@login_required
def assessment_pdf_export(assessment_id):
    """Eksporter måling til PDF"""
    from datetime import datetime
    from io import BytesIO

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
                return redirect(url_for('admin_home'))

        target_unit_id = assessment['target_unit_id']

        # Check anonymity
        anonymity = check_anonymity_threshold(assessment_id, target_unit_id)
        if not anonymity.get('can_show_results'):
            flash("Ikke nok svar til at generere PDF", 'warning')
            return redirect(url_for('view_assessment', assessment_id=assessment_id))

        # Get all data
        breakdown = get_detailed_breakdown(target_unit_id, assessment_id, include_children=True)
        substitution = calculate_substitution_db(target_unit_id, assessment_id, 'employee')
        free_text_comments = get_free_text_comments(target_unit_id, assessment_id, include_children=True)

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
                return redirect(url_for('view_assessment', assessment_id=assessment_id))

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
            return redirect(url_for('view_assessment', assessment_id=assessment_id))

    except Exception as e:
        import traceback
        print(f"PDF export error: {traceback.format_exc()}")
        flash(f"Fejl ved PDF eksport: {str(e)}", 'error')
        return redirect(url_for('view_assessment', assessment_id=assessment_id))


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

    # Filter på customer hvis ikke admin/superadmin
    customer_id = None
    if user['role'] not in ('admin', 'superadmin'):
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
# FRIKTIONSPROFIL API (Stateless - Privacy by Design)
# ========================================
# Disse endpoints gemmer IKKE data på serveren.
# B2C brugere kan bruge localStorage i browseren.

@app.route('/profil/api/questions', methods=['GET'])
def profil_api_questions():
    """
    Hent alle profil-spørgsmål (stateless - ingen session oprettet)

    Query params:
        types: comma-separated liste af typer (sensitivity,capacity,bandwidth,screening,baseline)
               Default: sensitivity

    Returns JSON:
        {
            questions: [...],
            fields: ['TRYGHED', 'MENING', 'KAN', 'BESVÆR'],
            layers: ['BIOLOGI', 'EMOTION', 'INDRE', 'KOGNITION'],
            version: "1.0"
        }
    """
    from db_profil import get_questions_by_type, get_all_questions

    # Parse question types fra query param
    types_param = request.args.get('types', 'sensitivity')
    question_types = [t.strip() for t in types_param.split(',')]

    # Hent spørgsmål
    if 'all' in question_types:
        questions = get_all_questions()
    else:
        questions = get_questions_by_type(question_types)

    # Konverter til serialiserbar liste
    questions_list = []
    for q in questions:
        questions_list.append({
            'id': q['id'],
            'field': q['field'],
            'layer': q['layer'],
            'text_da': q['text_da'],
            'state_text_da': q.get('state_text_da'),
            'question_type': q.get('question_type', 'sensitivity'),
            'reverse_scored': bool(q.get('reverse_scored', 0)),
            'sequence': q['sequence']
        })

    return jsonify({
        'questions': questions_list,
        'fields': ['TRYGHED', 'MENING', 'KAN', 'BESVÆR'],
        'layers': ['BIOLOGI', 'EMOTION', 'INDRE', 'KOGNITION'],
        'version': '1.0',
        'count': len(questions_list)
    })


@app.route('/profil/api/calculate', methods=['POST'])
def profil_api_calculate():
    """
    Beregn profil-analyse fra responses (stateless - gemmer INTET)

    Request body:
        {
            responses: [{question_id: 1, score: 3}, ...],
            context: "general"  // optional
        }

    Returns JSON:
        {
            score_matrix: {...},
            color_matrix: {...},
            columns: {...},
            summary: {...},
            interpretations: {...}
        }
    """
    from analysis_profil import (
        score_to_color, analyze_column, interpret_bandwidth,
        generate_interpretations, FIELDS, LAYERS, COLOR_LABELS
    )
    from db_profil import get_all_questions

    data = request.get_json()
    if not data or 'responses' not in data:
        return jsonify({'error': 'Missing responses in request body'}), 400

    responses = data['responses']
    if not isinstance(responses, list) or len(responses) == 0:
        return jsonify({'error': 'Responses must be a non-empty array'}), 400

    # Hent spørgsmål for at kende reverse_scored
    all_questions = {q['id']: q for q in get_all_questions()}

    # Byg score matrix fra responses
    score_matrix = {
        'TRYGHED': {},
        'MENING': {},
        'KAN': {},
        'BESVÆR': {}
    }

    for resp in responses:
        q_id = resp.get('question_id')
        score = resp.get('score')

        if q_id is None or score is None:
            continue

        question = all_questions.get(q_id)
        if not question:
            continue

        field = question['field']
        layer = question['layer']

        # Ignorer spørgsmål der ikke passer i 4x4 matrix
        if field not in score_matrix or layer not in LAYERS:
            continue

        # Håndter reverse scoring
        if question.get('reverse_scored'):
            score = 6 - score

        score_matrix[field][layer] = score

    # Beregn color matrix
    color_matrix = {}
    for field in FIELDS:
        color_matrix[field] = {}
        for layer in LAYERS:
            score = score_matrix.get(field, {}).get(layer)
            if score is not None:
                color_matrix[field][layer] = score_to_color(score)
            else:
                color_matrix[field][layer] = 'unknown'

    # Analyser hver søjle
    columns = {}
    for field in FIELDS:
        layer_scores = score_matrix.get(field, {})
        columns[field] = analyze_column(field, layer_scores)

    # Samlet profil-analyse
    all_scores = []
    for field_data in columns.values():
        all_scores.extend(field_data['scores'].values())

    total_avg = sum(all_scores) / len(all_scores) if all_scores else 0

    # Find dominerende manifestationslag
    manifestations = [c['manifestation_layer'] for c in columns.values() if c['manifestation_layer']]
    dominant_manifestation = max(set(manifestations), key=manifestations.count) if manifestations else None

    # Beregn samlet båndbredde
    bandwidths = [c['bandwidth'] for c in columns.values()]
    avg_bandwidth = sum(bandwidths) / len(bandwidths) if bandwidths else 0

    summary = {
        'total_avg_score': round(total_avg, 2),
        'overall_color': score_to_color(total_avg),
        'overall_label': COLOR_LABELS.get(score_to_color(total_avg), 'Ukendt'),
        'dominant_manifestation': dominant_manifestation,
        'avg_bandwidth': round(avg_bandwidth, 2),
        'bandwidth_interpretation': interpret_bandwidth(avg_bandwidth)
    }

    interpretations = generate_interpretations(columns)

    return jsonify({
        'score_matrix': score_matrix,
        'color_matrix': color_matrix,
        'columns': columns,
        'summary': summary,
        'interpretations': interpretations,
        'context': data.get('context', 'general'),
        'calculated_at': datetime.now().isoformat()
    })


@app.route('/profil/local')
def profil_local():
    """
    Client-side friktionsprofil (Privacy by Design)
    Alt gemmes i brugerens browser - serveren gemmer intet.
    """
    return render_template('profil/local.html')


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
            SELECT t.*, c.name as assessment_name
            FROM tokens t
            JOIN assessments c ON t.assessment_id = c.id
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
            SELECT assessment_id, unit_id, respondent_type, respondent_name, is_used
            FROM tokens
            WHERE token = ?
        """, (token,)).fetchone()

        if not token_info:
            flash('Ugyldig token', 'error')
            return redirect(url_for('index'))

        if token_info['is_used']:
            return render_template('survey_error.html',
                error="Dette link er allerede blevet brugt.")

    assessment_id = token_info['assessment_id']
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
                    (assessment_id, unit_id, question_id, score, respondent_type, respondent_name, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (assessment_id, unit_id, q_id, score, respondent_type, respondent_name, comment))

            saved_count += 1

    # Mark token as used
    with get_db() as conn:
        conn.execute("""
            UPDATE tokens
            SET is_used = 1, used_at = CURRENT_TIMESTAMP
            WHERE token = ?
        """, (token,))

    # Check if assessment is now complete and send notification
    # Default threshold is 100% (all tokens used)
    try:
        check_and_notify_assessment_completed(assessment_id)
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
    assessment_id = request.args.get('assessment_id')
    stats = get_email_stats(assessment_id)
    logs = get_email_logs(assessment_id, limit=100)
    return render_template('admin/email_stats.html', stats=stats, logs=logs, assessment_id=assessment_id)


@app.route('/api/email-stats')
@login_required
def api_email_stats():
    """API endpoint for email stats"""
    assessment_id = request.args.get('assessment_id')
    stats = get_email_stats(assessment_id)
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
        if user['role'] in ('admin', 'superadmin'):
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
    if session['user']['role'] not in ('admin', 'superadmin'):
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
    if session['user']['role'] not in ('admin', 'superadmin'):
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
    if session['user']['role'] not in ('admin', 'superadmin'):
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
    if session['user']['role'] not in ('admin', 'superadmin'):
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
    if session['user']['role'] not in ('admin', 'superadmin'):
        return jsonify({'success': False, 'error': 'Ikke autoriseret'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Ingen data'}), 400

    success = save_profil_intro_texts(data)
    return jsonify({'success': success})


@app.route('/admin/seed-herning', methods=['GET', 'POST'])
def seed_herning_direct():
    """Direkte endpoint til at seede Herning testdata (ingen auth for initial setup)"""
    try:
        import seed_herning_testdata
        seed_herning_testdata.main()
        return jsonify({'success': True, 'message': 'Herning testdata genereret!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/seed-testdata', methods=['POST'])
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


@app.route('/admin/seed-testdata')
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


@app.route('/admin/dev-tools')
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


@app.route('/admin/audit-log')
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


@app.route('/admin/clear-cache', methods=['POST'])
@admin_required
def clear_cache():
    """Ryd hele cachen - kun admin"""
    count = invalidate_all()
    flash(f'Cache ryddet! ({count} entries fjernet)', 'success')
    return redirect(url_for('dev_tools'))


@app.route('/api/clear-cache/<secret>')
def clear_cache_api(secret):
    """Midlertidigt endpoint til cache rydning - FJERN EFTER BRUG"""
    if secret != 'frik2025cache':
        return {'error': 'Invalid secret'}, 403
    count = invalidate_all()
    return {'success': True, 'cleared': count}


@app.route('/admin/rename-assessments', methods=['POST'])
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
    return redirect(url_for('dev_tools'))


@app.route('/admin/vary-testdata', methods=['POST'])
@admin_required
def vary_testdata():
    """Tilføj realistisk variation til testdata - forskellige organisationer får forskellige profiler"""
    import random

    # Profiler for forskellige organisationstyper - med bredere ranges for mere variation
    # Hvert felt har: (target_mean, std_dev, extreme_chance)
    # extreme_chance = sandsynlighed for at producere 1 eller 5 i stedet
    PROFILES = {
        'Birk Skole': {
            'MENING': (4.0, 0.8, 0.08), 'TRYGHED': (3.8, 0.9, 0.06),
            'KAN': (2.5, 1.0, 0.10), 'BESVÆR': (3.3, 0.8, 0.05)
        },
        'Gødstrup Skole': {
            'MENING': (2.3, 1.0, 0.12), 'TRYGHED': (2.8, 0.9, 0.08),
            'KAN': (3.0, 0.8, 0.05), 'BESVÆR': (2.2, 1.1, 0.15)
        },
        'Hammerum Skole': {
            'MENING': (4.3, 0.7, 0.10), 'TRYGHED': (4.5, 0.6, 0.12),
            'KAN': (3.8, 0.8, 0.08), 'BESVÆR': (4.1, 0.7, 0.10)
        },
        'Snejbjerg Skole': {
            'MENING': (3.3, 0.9, 0.06), 'TRYGHED': (2.3, 1.0, 0.10),
            'KAN': (3.5, 0.8, 0.06), 'BESVÆR': (3.3, 0.9, 0.05)
        },
        'Aktivitetscentret Midt': {
            'MENING': (3.8, 0.9, 0.08), 'TRYGHED': (3.3, 1.0, 0.07),
            'KAN': (2.0, 1.1, 0.15), 'BESVÆR': (1.8, 1.0, 0.18)
        },
        'Bofællesskabet Åparken': {
            'MENING': (4.5, 0.6, 0.15), 'TRYGHED': (4.0, 0.8, 0.10),
            'KAN': (3.3, 0.9, 0.06), 'BESVÆR': (2.8, 1.0, 0.08)
        },
        'Støttecentret Vestergade': {
            'MENING': (2.5, 1.0, 0.10), 'TRYGHED': (3.8, 0.8, 0.06),
            'KAN': (4.3, 0.7, 0.12), 'BESVÆR': (3.8, 0.8, 0.08)
        },
    }
    DEFAULT = {'MENING': (3.0, 1.0, 0.08), 'TRYGHED': (3.0, 1.0, 0.08), 'KAN': (3.0, 1.0, 0.08), 'BESVÆR': (3.0, 1.0, 0.08)}

    def get_score(profile, field):
        mean, std, extreme_chance = profile.get(field, DEFAULT[field])
        # Chance for ekstreme scores (1 eller 5)
        if random.random() < extreme_chance:
            return 5 if mean > 3.0 else 1
        # Normal distribution med bredere spredning
        score = random.gauss(mean, std)
        return max(1, min(5, round(score)))

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
            # For reverse_scored spørgsmål: invert scoren
            if r['reverse_scored'] == 1:
                new_score = 6 - target_score
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
            # Ledere vurderer typisk 0.4 point højere (positiv bias)
            leader_profile = {r['field']: (min(5, mean + 0.4), std * 0.9, extreme_chance * 0.8)}
            target_score = get_score(leader_profile, r['field'])
            # For reverse_scored spørgsmål: invert scoren
            if r['reverse_scored'] == 1:
                new_score = 6 - target_score
            else:
                new_score = target_score
            conn.execute("UPDATE responses SET score = ? WHERE id = ?", (new_score, r['id']))
            count += 1

        # Opdater leader_self (varierer mere)
        leader_self = conn.execute("""
            SELECT r.id FROM responses r WHERE r.respondent_type = 'leader_self'
        """).fetchall()

        for r in leader_self:
            new_score = random.choice([2, 3, 3, 4, 4, 4, 5])
            conn.execute("UPDATE responses SET score = ? WHERE id = ?", (new_score, r['id']))
            count += 1

    # Ryd cache så nye værdier vises
    invalidate_all()

    flash(f'Opdateret {count} responses med realistisk variation og ryddet cache', 'success')
    return redirect(url_for('dev_tools'))


@app.route('/admin/fix-missing-leader-data', methods=['POST'])
@admin_required
def fix_missing_leader_data():
    """Tilføj manglende leader_assess og leader_self data til gruppe_friktion assessments"""
    import random
    import uuid

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
            'assessments': conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0],
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
            delete_order = ['responses', 'tokens', 'email_logs', 'contacts', 'assessments',
                           'organizational_units', 'users', 'customers']
            for table in delete_order:
                try:
                    conn.execute(f"DELETE FROM {table}")
                except:
                    pass

        # Restore tabeller i rigtig rækkefølge (parents før children)
        restore_order = ['customers', 'users', 'organizational_units', 'contacts',
                        'assessments', 'tokens', 'responses', 'questions', 'translations']

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

    # Audit log restore
    log_action(
        AuditAction.BACKUP_RESTORED,
        entity_type="database",
        details=f"Database restored from backup (mode: {restore_mode}). {stats['inserted']} inserted, {stats['skipped']} skipped, {stats['errors']} errors"
    )

    flash(f"Restore gennemført: {stats['inserted']} rækker importeret, {stats['skipped']} sprunget over, {stats['errors']} fejl", 'success')
    return redirect(url_for('backup_page'))


@app.route('/admin/restore-db-from-backup', methods=['GET', 'POST'])
def restore_db_from_backup():
    """Restore database fra git-pushed db_backup.b64 fil.

    Denne endpoint bruges til at synkronisere lokal database til Render:
    1. Lokalt: python -c "import base64; open('db_backup.b64','w').write(base64.b64encode(open('friktionskompas_v3.db','rb').read()).decode())"
    2. git add db_backup.b64 && git commit -m "DB sync" && git push
    3. Vent på deployment
    4. curl -X POST https://friktionskompasset.dk/admin/restore-db-from-backup
    """
    import base64
    import shutil
    from db_hierarchical import DB_PATH

    # Find backup fil i repo
    backup_path = os.path.join(os.path.dirname(__file__), 'db_backup.b64')

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


@app.route('/admin/recreate-assessments', methods=['POST'])
def recreate_assessments():
    """Genskab manglende assessments baseret på eksisterende responses"""
    from datetime import datetime

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
            return redirect(url_for('db_status'))

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

    return redirect(url_for('db_status'))


@app.route('/admin/seed-assessments', methods=['POST'])
def seed_assessments():
    """Seed assessments og responses fra JSON filer"""
    import json
    import os

    base_path = os.path.dirname(__file__)
    assessments_path = os.path.join(base_path, 'seed_assessments.json')
    responses_path = os.path.join(base_path, 'seed_responses.json')

    if not os.path.exists(assessments_path):
        flash('seed_assessments.json ikke fundet!', 'error')
        return redirect(url_for('db_status'))

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

    return redirect(url_for('db_status'))


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
            for table in ['responses', 'assessments', 'organizational_units', 'customers', 'users']:
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

            # Importer assessments
            camp_count = 0
            for camp in data.get('assessments', []):
                try:
                    conn.execute('''
                        INSERT INTO assessments (id, name, target_unit_id, period, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (camp['id'], camp['name'], camp['target_unit_id'], camp.get('period'), camp.get('created_at')))
                    camp_count += 1
                except Exception as e:
                    results.append(f"Fejl assessment {camp.get('name')}: {e}")
            results.append(f"Importeret {camp_count} assessments")

            # Importer responses
            resp_count = 0
            for resp in data.get('responses', []):
                try:
                    conn.execute('''
                        INSERT INTO responses (assessment_id, unit_id, question_id, score, respondent_type, respondent_name, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (resp['assessment_id'], resp['unit_id'], resp['question_id'],
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


@app.route('/admin/cleanup-empty')
@login_required
def cleanup_empty_units():
    """SLET ALT og importer ren lokal database"""
    if session['user']['role'] not in ('admin', 'superadmin'):
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
                            CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
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
                        AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                        AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as score_mening,
                        AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as score_tryghed,
                        AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as score_kan,
                        AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as score_besvaer
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
                        AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                        AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as score_mening,
                        AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as score_tryghed,
                        AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as score_kan,
                        AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as score_besvaer
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
                    AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                    AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as mening,
                    AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as tryghed,
                    AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as kan,
                    AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as besvaer,
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
                    AVG(CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END) as avg_score,
                    AVG(CASE WHEN q.field = 'MENING' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as mening,
                    AVG(CASE WHEN q.field = 'TRYGHED' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as tryghed,
                    AVG(CASE WHEN q.field = 'KAN' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as kan,
                    AVG(CASE WHEN q.field = 'BESVÆR' THEN CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END END) as besvaer,
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
                return redirect(url_for('admin_home'))

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


# ========================================
# ASSESSMENT TYPES ROUTES
# ========================================

@app.route('/admin/assessment-types')
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


@app.route('/admin/seed-assessment-types', methods=['GET', 'POST'])
def seed_assessment_types_route():
    """Seed/re-seed assessment types - no auth for initial setup"""
    seed_assessment_types()
    if request.method == 'GET':
        return jsonify({'status': 'ok', 'message': 'Assessment types og presets seedet!'})
    flash('Målingstyper og presets seedet!', 'success')
    return redirect(url_for('assessment_types'))


@app.route('/admin/fix-default-preset', methods=['GET'])
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


@app.route('/admin/assessment-type/<type_id>/toggle', methods=['POST'])
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

    return redirect(url_for('assessment_types'))


@app.route('/admin/customer/<customer_id>/assessments')
@admin_required
def customer_assessments(customer_id):
    """Konfigurer målingstyper for en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('manage_customers'))

    config = get_customer_assessment_config(customer_id)
    presets = get_all_presets()

    return render_template('admin/customer_assessments.html',
                         customer=customer,
                         config=config,
                         presets=presets)


@app.route('/admin/customer/<customer_id>/assessments', methods=['POST'])
@admin_required
def update_customer_assessments(customer_id):
    """Opdater målingstyper for en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('manage_customers'))

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

    return redirect(url_for('customer_assessments', customer_id=customer_id))


@app.route('/admin/customer/<customer_id>/assessments/preset/<int:preset_id>', methods=['POST'])
@admin_required
def apply_preset_to_customer(customer_id, preset_id):
    """Anvend et preset til en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('manage_customers'))

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

    return redirect(url_for('customer_assessments', customer_id=customer_id))


# ========================================
# SITUATIONSMÅLING ROUTES
# ========================================

@app.route('/admin/tasks')
@admin_required
def admin_tasks():
    """Liste over opgaver (tasks) for situationsmåling"""
    from db_hierarchical import get_tasks

    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))

    # Brug customer_id fra params hvis tilgængelig
    customer_id = params[0] if params else None
    tasks = get_tasks(customer_id)

    return render_template('admin/tasks.html',
                           tasks=tasks,
                           active_page='tasks')


@app.route('/admin/tasks/new', methods=['GET', 'POST'])
@admin_required
def admin_task_new():
    """Opret ny opgave"""
    from db_hierarchical import create_task, get_toplevel_units

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        situation = request.form.get('situation', '').strip()
        unit_id = request.form.get('unit_id') or None

        if not name:
            flash('Navn er påkrævet', 'error')
            return redirect(url_for('admin_task_new'))

        # Find customer_id
        user = get_current_user()
        where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
        if params:
            # Har customer filter
            customer_id = params[0]
        else:
            # Superadmin uden filter - brug customer fra valgt unit
            if unit_id:
                with get_db() as conn:
                    unit = conn.execute('SELECT customer_id FROM organizational_units WHERE id = ?', (unit_id,)).fetchone()
                    customer_id = unit['customer_id'] if unit else None
            else:
                flash('Vælg en organisation eller sæt kundefilter', 'error')
                return redirect(url_for('admin_task_new'))

        task_id = create_task(
            customer_id=customer_id,
            name=name,
            description=description,
            situation=situation or None,
            unit_id=unit_id,
            created_by=session['user'].get('email')
        )

        flash('Opgave oprettet! Tilføj nu handlinger.', 'success')
        return redirect(url_for('admin_task_detail', task_id=task_id))

    # GET - vis formular
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
    customer_id = params[0] if params else None
    units = get_toplevel_units(customer_id)

    return render_template('admin/task_new.html',
                           units=units,
                           active_page='tasks')


@app.route('/admin/tasks/<task_id>')
@admin_required
def admin_task_detail(task_id):
    """Vis opgave med handlinger"""
    from db_hierarchical import get_task

    task = get_task(task_id)
    if not task:
        flash('Opgave ikke fundet', 'error')
        return redirect(url_for('admin_tasks'))

    return render_template('admin/task_detail.html',
                           task=task,
                           active_page='tasks')


@app.route('/admin/tasks/<task_id>/add-action', methods=['POST'])
@admin_required
def admin_add_action(task_id):
    """Tilføj handling til opgave"""
    from db_hierarchical import add_action, get_task

    task = get_task(task_id)
    if not task:
        flash('Opgave ikke fundet', 'error')
        return redirect(url_for('admin_tasks'))

    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Handlingens navn er påkrævet', 'error')
        return redirect(url_for('admin_task_detail', task_id=task_id))

    if len(task['actions']) >= 5:
        flash('Maksimalt 5 handlinger per opgave', 'error')
        return redirect(url_for('admin_task_detail', task_id=task_id))

    add_action(task_id, name, description or None)
    flash('Handling tilføjet', 'success')
    return redirect(url_for('admin_task_detail', task_id=task_id))


@app.route('/admin/tasks/<task_id>/delete-action/<action_id>', methods=['POST'])
@admin_required
def admin_delete_action(task_id, action_id):
    """Slet handling fra opgave"""
    from db_hierarchical import delete_action

    delete_action(action_id)
    flash('Handling slettet', 'success')
    return redirect(url_for('admin_task_detail', task_id=task_id))


@app.route('/admin/tasks/<task_id>/delete', methods=['POST'])
@admin_required
def admin_delete_task(task_id):
    """Slet opgave"""
    from db_hierarchical import delete_task

    delete_task(task_id)
    flash('Opgave slettet', 'success')
    return redirect(url_for('admin_tasks'))


@app.route('/admin/tasks/<task_id>/new-assessment', methods=['GET', 'POST'])
@admin_required
def admin_situation_assessment_new(task_id):
    """Opret ny situationsmåling for en opgave"""
    from db_hierarchical import (get_task, get_toplevel_units, get_unit_contacts,
                                  create_situation_assessment, generate_situation_tokens)

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
            return redirect(url_for('admin_situation_assessment_new', task_id=task_id))

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
            return redirect(url_for('admin_situation_assessment_new', task_id=task_id))

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

        return redirect(url_for('admin_situation_assessment_view', assessment_id=assessment_id))

    # GET - vis formular
    user = get_current_user()
    where_clause, params = get_customer_filter(user['role'], user['customer_id'], session.get('customer_filter'))
    customer_id = params[0] if params else None
    units = get_toplevel_units(customer_id)

    return render_template('admin/situation_assessment_new.html',
                           task=task,
                           units=units,
                           active_page='tasks')


@app.route('/admin/situation-assessments/<assessment_id>')
@admin_required
def admin_situation_assessment_view(assessment_id):
    """Vis resultater for situationsmåling"""
    from db_hierarchical import get_situation_results

    results = get_situation_results(assessment_id)
    if not results:
        flash('Måling ikke fundet', 'error')
        return redirect(url_for('admin_tasks'))

    return render_template('admin/situation_assessment.html',
                           results=results,
                           active_page='tasks')


# ========================================
# GDPR / DPO DASHBOARD
# ========================================

# Underdatabehandlere (sub-processors)
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


@app.route('/admin/gdpr')
@admin_required
def admin_gdpr():
    """GDPR/DPO Dashboard - overblik over data og compliance"""
    from db_hierarchical import get_db

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


@app.route('/admin/gdpr/delete-customer/<customer_id>', methods=['POST'])
@admin_required
def admin_gdpr_delete_customer(customer_id):
    """Slet al data for en kunde (GDPR sletning)"""
    from db_hierarchical import get_db

    user = get_current_user()
    if user['role'] != 'superadmin':
        flash('Kun superadmin kan slette kundedata', 'error')
        return redirect(url_for('admin_gdpr'))

    with get_db() as conn:
        # Hent kundenavn til bekræftelse
        customer = conn.execute('SELECT name FROM customers WHERE id = ?', (customer_id,)).fetchone()
        if not customer:
            flash('Kunde ikke fundet', 'error')
            return redirect(url_for('admin_gdpr'))

        customer_name = customer['name']

        # CASCADE DELETE vil slette alt relateret data
        conn.execute('DELETE FROM customers WHERE id = ?', (customer_id,))

        # Log sletningen
        from audit import log_action
        log_action('gdpr_delete_customer', f'Slettet kunde: {customer_name} ({customer_id})')

    flash(f'Al data for "{customer_name}" er slettet permanent', 'success')
    return redirect(url_for('admin_gdpr'))


if __name__ == '__main__':
    app.run(debug=True, port=5001)

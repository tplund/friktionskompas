"""
Admin interface for Friktionskompasset v3
Hierarkisk organisationsstruktur med units + Multi-tenant

This module uses the Flask app factory pattern (see app_factory.py).
Routes and business logic are defined here.
"""
import os
from app_factory import create_app

# Import Flask components needed for routes
from flask import render_template, request, redirect, url_for, flash, Response, session, jsonify, send_from_directory
import csv
import io
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps

# Setup logging first (before other imports that might log)
from logging_config import get_logger, log_request, log_security_event

logger = get_logger(__name__)

# Import database and analysis functions
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
from friction_engine import (
    score_to_percent, get_percent_class as engine_get_percent_class,
    get_severity, get_spread_level, THRESHOLDS, FRICTION_FIELDS,
    Severity, SpreadLevel
)
from db_multitenant import (
    authenticate_user, create_customer, create_user, list_customers,
    list_users, get_customer_filter, get_customer, update_customer,
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
from db_profil import (
    init_profil_tables, get_all_questions as get_profil_questions,
    get_db as get_profil_db
)
from translations import t, get_user_language, set_language, SUPPORTED_LANGUAGES
from scheduler import get_scheduled_assessments, cancel_scheduled_assessment, reschedule_assessment
from oauth import (
    oauth, get_enabled_providers, get_provider_info,
    handle_oauth_callback, get_auth_providers_for_domain, save_auth_providers,
    DEFAULT_AUTH_PROVIDERS, get_user_oauth_links, link_oauth_to_user, unlink_oauth_from_user
)
from cache import get_cache_stats, invalidate_all, invalidate_assessment_cache, Pagination
from audit import log_action, AuditAction, get_audit_logs, get_audit_log_count, get_action_summary
from extensions import csrf, limiter

# Determine environment and create app instance
# Check if we're in production (Render) or development
if os.path.exists('/var/data'):
    # Production environment (Render has /var/data persistent disk)
    app = create_app('production')
elif os.environ.get('TESTING', '').lower() == 'true':
    # Testing environment
    app = create_app('testing')
else:
    # Development environment
    app = create_app('development')


# ============================================================================
# ROUTES START HERE (line ~350 in original file)
# ============================================================================


# Auth decorators imported from shared module
from auth_helpers import (
    login_required, admin_required, superadmin_required,
    api_or_admin_required, get_current_user, get_effective_role,
    is_role_simulated, check_admin_api_key, is_api_request
)


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


@app.route('/my-data/export')
@login_required
def export_my_data():
    """GDPR Data Export - Export user's own data as JSON"""
    import json
    from datetime import datetime, timedelta
    from flask import jsonify, make_response

    user = session.get('user')
    user_id = user.get('id')

    # Rate limiting: Check last export time
    with get_db() as conn:
        # Check if user exported within last 24 hours
        last_export = conn.execute("""
            SELECT created_at FROM audit_log
            WHERE user_id = ? AND action = 'data_export'
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,)).fetchone()

        if last_export:
            last_export_time = datetime.fromisoformat(last_export['created_at'])
            if datetime.now() - last_export_time < timedelta(hours=24):
                flash('Du kan kun eksportere dine data én gang per dag. Prøv igen senere.', 'error')
                return redirect(url_for('admin_my_account'))

        # Collect user data
        user_details = conn.execute(
            "SELECT id, username, name, email, role, created_at, last_login, language FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        # Get user's responses
        responses = conn.execute("""
            SELECT r.id, r.question_id, r.score, r.created_at, q.text as question_text,
                   c.name as assessment_name, c.period
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            JOIN assessments c ON r.assessment_id = c.id
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
        """, (user_id,)).fetchall()

        # Get linked OAuth accounts
        oauth_links = conn.execute("""
            SELECT provider, provider_email, created_at
            FROM user_oauth_links
            WHERE user_id = ?
        """, (user_id,)).fetchall()

        # Get consent history (if exists)
        consents = []
        try:
            consents = conn.execute("""
                SELECT consent_type, granted, created_at
                FROM user_consents
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,)).fetchall()
        except:
            pass  # Table might not exist

        # Audit log this export
        from db_multitenant import audit_log
        audit_log(user_id, 'data_export', f'User exported their personal data')

    # Build export data
    export_data = {
        'export_date': datetime.now().isoformat(),
        'user': dict(user_details) if user_details else {},
        'responses': [dict(r) for r in responses],
        'oauth_accounts': [dict(o) for o in oauth_links],
        'consents': [dict(c) for c in consents],
        'data_rights': {
            'right_to_access': 'You have the right to access your personal data (this export)',
            'right_to_rectification': 'You can update your profile via My Account page',
            'right_to_erasure': 'You can delete your account via My Account page',
            'right_to_portability': 'This export is in JSON format for portability',
            'right_to_object': 'You can unsubscribe from emails via unsubscribe link'
        }
    }

    # Create JSON response with download
    response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False, default=str))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=my_data_export_{user_id}_{datetime.now().strftime("%Y%m%d")}.json'

    return response


@app.route('/admin/my-account/delete', methods=['POST'])
@login_required
def delete_my_account():
    """GDPR Account Deletion - Soft delete user account with 30-day grace period"""
    from datetime import datetime

    user = session.get('user')
    user_id = user.get('id')

    # Confirm password or require re-authentication
    password_confirm = request.form.get('password_confirm')

    with get_db() as conn:
        user_row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        # Check password if user has one
        if user_row and not (user_row['password_hash'].startswith('oauth-') or user_row['password_hash'].startswith('b2c-')):
            if not password_confirm:
                flash('Du skal bekræfte dit password for at slette din konto', 'error')
                return redirect(url_for('admin_my_account'))

            if not verify_password(password_confirm, user_row['password_hash']):
                flash('Forkert password', 'error')
                return redirect(url_for('admin_my_account'))

        # Soft delete: Mark account as deleted (30-day grace period)
        conn.execute("""
            UPDATE users
            SET deleted_at = ?, is_active = 0
            WHERE id = ?
        """, (datetime.now().isoformat(), user_id))

        # Audit log
        from db_multitenant import audit_log
        audit_log(user_id, 'account_deletion_requested', 'User requested account deletion (30-day grace period)')

    # Log out user
    session.clear()
    flash('Din konto er markeret til sletning. Du har 30 dage til at fortryde. Kontakt support@friktionskompasset.dk for at genaktivere.', 'success')
    return redirect(url_for('public.index'))


# PASSWORDLESS LOGIN & REGISTRATION ROUTES moved to blueprints/auth.py


@app.route('/user')
@login_required
def user_home():
    """Hjemmeside for B2C brugere"""
    user = session.get('user')
    if user['role'] != 'user':
        return redirect(url_for('admin_core.admin_home'))

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

    return redirect(url_for('customers.manage_customers'))


@app.route('/admin/user/<user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Rediger bruger - kun admin"""
    import bcrypt

    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        if not user:
            flash('Bruger ikke fundet', 'error')
            return redirect(url_for('customers.manage_customers'))

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
            return redirect(url_for('customers.manage_customers'))

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
        return redirect(url_for('customers.manage_customers'))

    # Store filter in session - but keep admin role!
    session['customer_filter'] = customer_id
    session['customer_filter_name'] = customer['name']

    flash(f'Viser kun data for: {customer["name"]}', 'success')

    # Return to the page we came from, or adapt URL for new customer context
    next_url = request.args.get('next', '')
    if next_url:
        # If on dashboard with specific customer/unit, go to that customer's dashboard
        if '/dashboard' in next_url:
            return redirect(url_for('admin_core.org_dashboard', customer_id=customer_id))
        # For other pages, just go back to that page type
        return redirect(next_url)
    return redirect(url_for('admin_core.admin_home'))


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
            return redirect(url_for('admin_core.org_dashboard'))
        return redirect(next_url)
    return redirect(url_for('admin_core.admin_home'))


@app.route('/admin/simulate-role/<role>')
@login_required
def simulate_role(role):
    """Superadmin: Simuler en anden rolle for at se systemet som den rolle"""
    user = get_current_user()
    if user['role'] != 'superadmin':
        flash('Kun superadmin kan simulere roller', 'error')
        return redirect(url_for('admin_core.admin_home'))

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
    return redirect(url_for('admin_core.admin_home'))


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

    return redirect(url_for('admin_core.admin_home'))


@app.route('/admin/view/<view_mode>')
@admin_required
def switch_view_mode(view_mode):
    """Switch mellem user/manager/admin visning"""
    if view_mode not in ['user', 'manager', 'admin']:
        flash('Ugyldig visning', 'error')
        return redirect(url_for('admin_core.admin_home'))

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
        return redirect(url_for('admin_core.admin_home'))


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
                WHEN q.reverse_scored = 1 THEN 8 - r.score
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
                WHEN q.reverse_scored = 1 THEN 8 - r.score
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

from db_profil import (
    init_profil_tables,
    create_session as create_profil_session,
    get_session as get_profil_session,
    complete_session as complete_profil_session,
    get_questions_by_field as get_profil_questions_by_field,
    save_responses as save_profil_responses,
    list_sessions as list_profil_sessions,
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
    analysis = get_profil_analysis(session_id)
    if not analysis:
        flash('Profil ikke fundet', 'error')
        return redirect(url_for('profil_start'))

    # Tilføj screening-resultater
    from screening_profil import screen_profil
    screening = screen_profil(session_id)

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
        screening=screening,
        pair=pair  # Tilføjet for at vise link til par-sammenligning
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
    comparison = compare_profil_profiles(
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


@app.route('/profil/generate-test-data')
@admin_required  # Tilføjet i go-live security audit 2025-12-18
def profil_generate_test():
    """Generer testprofiler - KUN for admins"""
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
@csrf.exempt  # Stateless B2C API - no session
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
@csrf.exempt  # Survey uses token-based auth
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
@csrf.exempt  # External webhook from Mailjet
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
    except Exception:
        return {}  # Return empty dict if table doesn't exist or query fails


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
                return redirect(url_for('admin_core.admin_home'))

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


@app.route('/admin/cleanup-status')
@admin_required
def admin_cleanup_status():
    """Get data retention cleanup status (GDPR Phase 2)"""
    from data_retention import get_cleanup_status, get_last_cleanup_run
    from scheduler import _last_cleanup_date

    status = get_cleanup_status()
    last_run = get_last_cleanup_run()

    # Add scheduler info
    if _last_cleanup_date:
        status['last_scheduled_cleanup'] = _last_cleanup_date.isoformat()
    else:
        status['last_scheduled_cleanup'] = None

    status['last_cleanup_run'] = last_run

    return jsonify(status)


@app.route('/admin/cleanup-run', methods=['POST'])
@admin_required
def admin_cleanup_run():
    """Manually trigger data retention cleanup (GDPR Phase 2)"""
    from data_retention import run_all_cleanups

    user = get_current_user()
    if user['role'] != 'superadmin':
        return jsonify({'error': 'Kun superadmin kan køre cleanup'}), 403

    results = run_all_cleanups()

    # Log manual cleanup
    log_action(
        AuditAction.DATA_DELETED,
        entity_type='manual_cleanup',
        details=f"Manual cleanup: {results['total_deleted']} records deleted"
    )

    return jsonify(results)


@app.route('/admin/dpa/<customer_id>')
@admin_required
def admin_dpa(customer_id):
    """Generate Data Processing Agreement (DPA) for a customer"""
    from db_hierarchical import get_db

    user = get_current_user()

    # Superadmin kan se alle kunder, andre kun egen kunde
    if user['role'] != 'superadmin' and user['customer_id'] != customer_id:
        flash('Du kan kun se DPA for din egen kunde', 'error')
        return redirect(url_for('admin_gdpr'))

    with get_db() as conn:
        customer = conn.execute(
            'SELECT * FROM customers WHERE id = ?',
            (customer_id,)
        ).fetchone()

        if not customer:
            flash('Kunde ikke fundet', 'error')
            return redirect(url_for('admin_gdpr'))

        customer_data = dict(customer)

    # Current date for DPA
    dpa_date = datetime.now().strftime('%Y-%m-%d')

    return render_template('legal/dpa.html',
                           customer=customer_data,
                           sub_processors=SUB_PROCESSORS,
                           dpa_date=dpa_date)


@app.route('/admin/dpa/<customer_id>/pdf')
@admin_required
def admin_dpa_pdf(customer_id):
    """Download DPA as PDF"""
    from weasyprint import HTML
    from db_hierarchical import get_db

    user = get_current_user()

    # Superadmin kan se alle kunder, andre kun egen kunde
    if user['role'] != 'superadmin' and user['customer_id'] != customer_id:
        return "Unauthorized", 403

    with get_db() as conn:
        customer = conn.execute(
            'SELECT * FROM customers WHERE id = ?',
            (customer_id,)
        ).fetchone()

        if not customer:
            return "Customer not found", 404

        customer_data = dict(customer)

    # Current date for DPA
    dpa_date = datetime.now().strftime('%Y-%m-%d')

    # Render HTML
    html = render_template('legal/dpa.html',
                           customer=customer_data,
                           sub_processors=SUB_PROCESSORS,
                           dpa_date=dpa_date,
                           pdf_mode=True)

    # Generate PDF with WeasyPrint
    pdf_buffer = io.BytesIO()
    HTML(string=html).write_pdf(pdf_buffer)
    pdf_buffer.seek(0)

    # Log DPA generation
    log_action(
        AuditAction.DATA_EXPORTED,
        entity_type='dpa',
        entity_id=customer_id,
        details=f"Generated DPA for {customer_data['name']}"
    )

    return Response(
        pdf_buffer.getvalue(),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename=DPA_{customer_data["name"]}_{dpa_date}.pdf'
        }
    )


# Error handlers
@app.errorhandler(500)
def handle_500(e):
    """Hide error tracebacks in production"""
    if app.debug:
        raise e
    # In production, show generic error page
    return render_template('errors/500.html'), 500


if __name__ == '__main__':
    # Debug mode controlled by FLASK_DEBUG environment variable
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=5001)

"""
Authentication blueprint - login, logout, register, OAuth, password reset.

Routes:
- /login (GET, POST) - Login page
- /logout - Logout
- /register (GET, POST) - Registration
- /register/verify (GET, POST) - Verify registration
- /login/email (GET, POST) - Email login
- /login/email/verify (GET, POST) - Verify email login
- /forgot-password (GET, POST) - Forgot password
- /reset-password (GET, POST) - Reset password
- /resend-code (POST) - Resend verification code
- /auth/<provider> - Start OAuth flow
- /auth/<provider>/callback - OAuth callback
"""

from flask import Blueprint, render_template, redirect, url_for, session, \
    request, flash

from extensions import limiter
from auth_helpers import login_required
from oauth import oauth, get_enabled_providers, get_provider_info, handle_oauth_callback
from db_multitenant import (
    authenticate_user,
    find_user_by_email,
    generate_email_code,
    verify_email_code,
    create_b2c_user,
    get_or_create_b2c_customer,
    authenticate_by_email_code,
    reset_password_with_code
)
from mailjet_integration import send_login_code
from translations import get_user_language
from audit import log_action, AuditAction

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    """Login side"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = authenticate_user(username, password)

        if user:
            session['user'] = user
            session.permanent = True
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
            return redirect(url_for('admin_core.admin_home'))
        else:
            log_action(
                AuditAction.LOGIN_FAILED,
                entity_type="user",
                details=f"Failed login attempt for username: {username}",
                username=username
            )
            flash('Forkert brugernavn eller password', 'error')

    domain = request.host.split(':')[0].lower()
    enabled_providers = get_enabled_providers(domain)
    providers_info = {p: get_provider_info(p) for p in enabled_providers if p != 'email_password'}
    show_email_password = 'email_password' in enabled_providers

    return render_template('login.html',
                           oauth_providers=providers_info,
                           show_email_password=show_email_password)


@auth_bp.route('/auth/<provider>')
def oauth_login(provider):
    """Start OAuth flow for a provider"""
    if provider not in ['microsoft', 'google', 'apple', 'facebook']:
        flash('Ukendt login-metode', 'error')
        return redirect(url_for('auth.login'))

    domain = request.host.split(':')[0].lower()
    enabled = get_enabled_providers(domain)

    if provider not in enabled:
        flash(f'{provider.title()} login er ikke aktiveret', 'error')
        return redirect(url_for('auth.login'))

    client = oauth.create_client(provider)
    if not client:
        flash(f'{provider.title()} er ikke konfigureret', 'error')
        return redirect(url_for('auth.login'))

    redirect_uri = url_for('auth.oauth_callback', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/<provider>/callback')
def oauth_callback(provider):
    """Handle OAuth callback"""
    if provider not in ['microsoft', 'google', 'apple', 'facebook']:
        flash('Ukendt login-metode', 'error')
        return redirect(url_for('auth.login'))

    try:
        client = oauth.create_client(provider)
        if not client:
            flash(f'{provider.title()} er ikke konfigureret', 'error')
            return redirect(url_for('auth.login'))

        token = client.authorize_access_token()

        if provider == 'microsoft':
            userinfo = token.get('userinfo')
            if not userinfo:
                resp = client.get('https://graph.microsoft.com/oidc/userinfo')
                userinfo = resp.json()
        elif provider == 'google':
            userinfo = token.get('userinfo')
            if not userinfo:
                resp = client.get('https://openidconnect.googleapis.com/v1/userinfo')
                userinfo = resp.json()
        else:
            userinfo = token.get('userinfo', {})

        user = handle_oauth_callback(provider, token, userinfo)

        if user:
            session['user'] = user
            session.permanent = True
            flash(f'Velkommen {user["name"]}!', 'success')
            return redirect(url_for('admin_core.admin_home'))
        else:
            flash('Kunne ikke logge ind - kontakt administrator', 'error')
            return redirect(url_for('auth.login'))

    except Exception as e:
        print(f"[OAuth] Callback error for {provider}: {e}")
        flash(f'Fejl ved login med {provider.title()}', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
def logout():
    """Logout"""
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


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
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

        existing_user = find_user_by_email(email)
        if existing_user:
            flash('Denne email er allerede registreret. Prøv at logge ind.', 'error')
            return redirect(url_for('auth.login'))

        session['pending_registration'] = {'email': email, 'name': name}

        code = generate_email_code(email, 'register')
        if send_login_code(email, code, 'register', get_user_language()):
            flash('Vi har sendt en kode til din email', 'success')
            return redirect(url_for('auth.verify_registration'))
        else:
            flash('Kunne ikke sende email. Prøv igen.', 'error')

    return render_template('register.html')


@auth_bp.route('/register/verify', methods=['GET', 'POST'])
def verify_registration():
    """Verificer registrering med email-kode"""
    pending = session.get('pending_registration')
    if not pending:
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()

        if verify_email_code(pending['email'], code, 'register'):
            b2c_customer_id = get_or_create_b2c_customer()
            try:
                user_id = create_b2c_user(
                    email=pending['email'],
                    name=pending['name'],
                    customer_id=b2c_customer_id
                )

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
                    session.permanent = True
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


@auth_bp.route('/login/email', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def email_login():
    """Passwordless login med email-kode"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or '@' not in email:
            flash('Indtast venligst en gyldig email', 'error')
            return render_template('email_login.html')

        user = find_user_by_email(email)
        if not user:
            flash('Hvis emailen er registreret, sender vi en kode', 'success')
            return redirect(url_for('auth.verify_email_login', email=email))

        code = generate_email_code(email, 'login')
        session['pending_email_login'] = email

        if send_login_code(email, code, 'login', get_user_language()):
            flash('Vi har sendt en kode til din email', 'success')
        else:
            flash('Hvis emailen er registreret, sender vi en kode', 'success')

        return redirect(url_for('auth.verify_email_login'))

    return render_template('email_login.html')


@auth_bp.route('/login/email/verify', methods=['GET', 'POST'])
def verify_email_login():
    """Verificer email login-kode"""
    email = session.get('pending_email_login')
    if not email:
        return redirect(url_for('auth.email_login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()

        user = authenticate_by_email_code(email, code)
        if user:
            session['user'] = user
            session.permanent = True
            session.pop('pending_email_login', None)
            flash(f'Velkommen {user["name"]}!', 'success')

            if user['role'] == 'user':
                return redirect(url_for('user_home'))
            else:
                return redirect(url_for('admin_core.admin_home'))
        else:
            flash('Forkert eller udløbet kode. Prøv igen.', 'error')

    return render_template('verify_code.html',
                          email=email,
                          action='login',
                          title='Indtast din loginkode')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("3 per minute", methods=["POST"])
def forgot_password():
    """Glemt password - send reset kode"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or '@' not in email:
            flash('Indtast venligst en gyldig email', 'error')
            return render_template('forgot_password.html')

        user = find_user_by_email(email)
        if user:
            code = generate_email_code(email, 'reset')
            send_login_code(email, code, 'reset', get_user_language())

        session['pending_password_reset'] = email
        flash('Hvis emailen er registreret, sender vi en kode til nulstilling', 'success')
        return redirect(url_for('auth.reset_password'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Nulstil password med kode"""
    email = session.get('pending_password_reset')
    if not email:
        return redirect(url_for('auth.forgot_password'))

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
                return redirect(url_for('auth.login'))
            else:
                flash('Forkert eller udløbet kode. Prøv igen.', 'error')

    return render_template('reset_password.html', email=email)


@auth_bp.route('/resend-code', methods=['POST'])
@limiter.limit("3 per minute")
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

    return redirect(request.referrer or url_for('auth.login'))

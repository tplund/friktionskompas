"""
Shared authentication decorators and helpers for Friktionskompasset.

Used by both admin_app.py and all blueprints to ensure consistent auth handling.
"""

import os
from functools import wraps
from flask import session, request, redirect, url_for, flash, jsonify, g


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


def login_required(f):
    """Decorator til at kræve login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Du skal være logget ind for at se denne side', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator til at kræve admin eller superadmin rolle"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Du skal være logget ind', 'error')
            return redirect(url_for('auth.login'))
        role = session['user']['role']
        if role not in ('admin', 'superadmin'):
            flash('Kun admin har adgang til denne side', 'error')
            # User rolle sendes til user_home, andre til admin_home
            if role == 'user':
                return redirect(url_for('user_home'))
            return redirect(url_for('admin_home'))
        return f(*args, **kwargs)
    return decorated_function


def superadmin_required(f):
    """Decorator til at kræve superadmin rolle"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Du skal være logget ind', 'error')
            return redirect(url_for('auth.login'))
        role = session['user']['role']
        if role != 'superadmin':
            flash('Kun system administrator har adgang til denne side', 'error')
            # User rolle sendes til user_home, andre til admin_home
            if role == 'user':
                return redirect(url_for('user_home'))
            return redirect(url_for('admin_home'))
        return f(*args, **kwargs)
    return decorated_function


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
            return redirect(url_for('auth.login'))
        role = session['user']['role']
        if role not in ('admin', 'superadmin'):
            if is_api_request():
                return jsonify({'error': 'Admin access required'}), 403
            flash('Kun admin har adgang til denne side', 'error')
            # User rolle sendes til user_home, andre til admin_home
            if role == 'user':
                return redirect(url_for('user_home'))
            return redirect(url_for('admin_home'))
        return f(*args, **kwargs)
    return decorated_function


def customer_api_required(f):
    """
    Decorator for Customer API endpoints.

    Validates X-API-Key header and sets:
    - g.api_customer_id: The customer's ID
    - g.api_permissions: Dict with read/write permissions
    - g.api_rate_limit: Rate limit for this key

    Usage:
        @app.route('/api/v1/assessments')
        @csrf.exempt
        @customer_api_required
        def api_v1_assessments():
            customer_id = g.api_customer_id
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from db_multitenant import validate_customer_api_key

        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({
                'error': 'API key required',
                'code': 'AUTH_MISSING',
                'hint': 'Include X-API-Key header with your API key'
            }), 401

        auth = validate_customer_api_key(api_key)
        if not auth:
            return jsonify({
                'error': 'Invalid or inactive API key',
                'code': 'AUTH_INVALID'
            }), 401

        # Store auth info in Flask g object for endpoint use
        g.api_customer_id = auth['customer_id']
        g.api_customer_name = auth['customer_name']
        g.api_permissions = auth['permissions']
        g.api_rate_limit = auth['rate_limit']
        g.api_key_name = auth['key_name']

        return f(*args, **kwargs)
    return decorated_function


def customer_api_write_required(f):
    """
    Decorator that requires write permission.
    Must be used AFTER @customer_api_required.

    Usage:
        @app.route('/api/v1/assessments', methods=['POST'])
        @csrf.exempt
        @customer_api_required
        @customer_api_write_required
        def create_assessment():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.get('api_permissions', {}).get('write', False):
            return jsonify({
                'error': 'Write permission required',
                'code': 'FORBIDDEN',
                'hint': 'This API key only has read access'
            }), 403
        return f(*args, **kwargs)
    return decorated_function

"""
OAuth Authentication for Friktionskompasset
Supports Microsoft, Google, and other OAuth providers
"""
import os
import json
import secrets
import sqlite3
from typing import Optional, Dict
from datetime import datetime
from authlib.integrations.flask_client import OAuth
from flask import session, url_for, redirect, flash, request

# Database path
RENDER_DISK_PATH = "/var/data"
if os.path.exists(RENDER_DISK_PATH):
    DB_PATH = os.path.join(RENDER_DISK_PATH, "friktionskompas_v3.db")
else:
    DB_PATH = "friktionskompas_v3.db"

# OAuth instance (initialized in init_oauth)
oauth = OAuth()

# Default auth providers config
DEFAULT_AUTH_PROVIDERS = {
    "email_password": True,
    "microsoft": {"enabled": False},
    "google": {"enabled": False},
    "apple": {"enabled": False},
    "facebook": {"enabled": False}
}


def _microsoft_compliance_fix(client, token, refresh_token=None, access_token=None):
    """
    Compliance fix for Microsoft OAuth multi-tenant tokens.
    Azure AD returns ID tokens with tenant-specific issuers, but the metadata
    contains a template. We skip ID token parsing and rely on access token + userinfo.
    """
    # Remove id_token to prevent authlib from trying to parse/validate it
    # We'll get user info from Microsoft Graph API instead
    if 'id_token' in token:
        # Store it but don't let authlib parse it
        token['_raw_id_token'] = token.pop('id_token')
    return token


def init_oauth(app):
    """Initialize OAuth with Flask app"""
    oauth.init_app(app)

    # Register Microsoft OAuth
    # Note: For multi-tenant apps, we must handle issuer validation specially.
    # Azure AD returns issuer with {tenantid} placeholder in metadata, but
    # actual tokens have the real tenant ID, causing validation failures.
    # Solution: Use compliance_fix to skip ID token parsing entirely
    if os.getenv('MICROSOFT_CLIENT_ID'):
        oauth.register(
            name='microsoft',
            client_id=os.getenv('MICROSOFT_CLIENT_ID'),
            client_secret=os.getenv('MICROSOFT_CLIENT_SECRET'),
            authorize_url='https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
            access_token_url='https://login.microsoftonline.com/common/oauth2/v2.0/token',
            userinfo_endpoint='https://graph.microsoft.com/oidc/userinfo',
            jwks_uri='https://login.microsoftonline.com/common/discovery/v2.0/keys',
            client_kwargs={
                'scope': 'openid email profile',
                'token_endpoint_auth_method': 'client_secret_post'
            },
            # Use compliance fix to skip ID token parsing for multi-tenant
            compliance_fix=_microsoft_compliance_fix
        )

    # Register Google OAuth
    if os.getenv('GOOGLE_CLIENT_ID'):
        oauth.register(
            name='google',
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile'
            }
        )


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_auth_providers_for_domain(domain: str = None) -> Dict:
    """
    Get auth providers config for a domain.
    Falls back to customer config, then default.
    """
    try:
        conn = get_db_connection()

        # First check domain-specific config
        if domain:
            row = conn.execute("""
                SELECT d.auth_providers, c.auth_providers as customer_auth_providers
                FROM domains d
                LEFT JOIN customers c ON d.customer_id = c.id
                WHERE d.domain = ? AND d.is_active = 1
            """, (domain.lower(),)).fetchone()

            if row:
                # Domain-specific takes precedence
                if row['auth_providers']:
                    conn.close()
                    return json.loads(row['auth_providers'])
                # Fallback to customer config
                if row['customer_auth_providers']:
                    conn.close()
                    return json.loads(row['customer_auth_providers'])

        conn.close()
    except Exception as e:
        print(f"[OAuth] Error getting auth providers: {e}")

    return DEFAULT_AUTH_PROVIDERS.copy()


def get_enabled_providers(domain: str = None) -> list:
    """Get list of enabled provider names for a domain"""
    config = get_auth_providers_for_domain(domain)
    enabled = []

    if config.get('email_password', True):
        enabled.append('email_password')

    for provider in ['microsoft', 'google', 'apple', 'facebook']:
        provider_config = config.get(provider, {})
        if isinstance(provider_config, dict) and provider_config.get('enabled'):
            # Also check if we have the required env vars
            if provider == 'microsoft' and os.getenv('MICROSOFT_CLIENT_ID'):
                enabled.append('microsoft')
            elif provider == 'google' and os.getenv('GOOGLE_CLIENT_ID'):
                enabled.append('google')
            elif provider == 'apple' and os.getenv('APPLE_CLIENT_ID'):
                enabled.append('apple')
            elif provider == 'facebook' and os.getenv('FACEBOOK_CLIENT_ID'):
                enabled.append('facebook')

    return enabled


def find_user_by_oauth(provider: str, provider_user_id: str) -> Optional[Dict]:
    """Find user by OAuth provider link"""
    try:
        conn = get_db_connection()
        row = conn.execute("""
            SELECT u.*, c.name as customer_name
            FROM user_oauth_links ol
            JOIN users u ON ol.user_id = u.id
            LEFT JOIN customers c ON u.customer_id = c.id
            WHERE ol.provider = ? AND ol.provider_user_id = ?
            AND u.is_active = 1
        """, (provider, provider_user_id)).fetchone()
        conn.close()

        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"[OAuth] Error finding user by OAuth: {e}")
        return None


def find_user_by_email(email: str) -> Optional[Dict]:
    """Find user by email"""
    try:
        conn = get_db_connection()
        row = conn.execute("""
            SELECT u.*, c.name as customer_name
            FROM users u
            LEFT JOIN customers c ON u.customer_id = c.id
            WHERE u.email = ? AND u.is_active = 1
        """, (email.lower(),)).fetchone()
        conn.close()

        if row:
            return dict(row)
        return None
    except Exception as e:
        print(f"[OAuth] Error finding user by email: {e}")
        return None


def link_oauth_to_user(user_id: str, provider: str, provider_user_id: str,
                       provider_email: str = None, access_token: str = None,
                       refresh_token: str = None) -> bool:
    """Link an OAuth account to an existing user"""
    try:
        conn = get_db_connection()
        conn.execute("""
            INSERT OR REPLACE INTO user_oauth_links
            (user_id, provider, provider_user_id, provider_email, access_token, refresh_token)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, provider, provider_user_id, provider_email, access_token, refresh_token))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[OAuth] Error linking OAuth: {e}")
        return False


def get_user_oauth_links(user_id: str) -> list:
    """Get all OAuth links for a user"""
    try:
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT provider, provider_email, created_at
            FROM user_oauth_links
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,)).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[OAuth] Error getting user OAuth links: {e}")
        return []


def unlink_oauth_from_user(user_id: str, provider: str) -> bool:
    """Remove an OAuth link from a user"""
    try:
        conn = get_db_connection()
        conn.execute("""
            DELETE FROM user_oauth_links
            WHERE user_id = ? AND provider = ?
        """, (user_id, provider))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[OAuth] Error unlinking OAuth: {e}")
        return False


def create_user_from_oauth(provider: str, provider_user_id: str, email: str,
                           name: str, customer_id: str = None) -> Optional[str]:
    """Create a new user from OAuth login"""
    try:
        conn = get_db_connection()

        user_id = f"user-{secrets.token_urlsafe(8)}"
        # OAuth users get a random password they'll never use
        dummy_password_hash = f"oauth-{secrets.token_urlsafe(32)}"

        conn.execute("""
            INSERT INTO users (id, username, password_hash, name, email, role, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email.lower(), dummy_password_hash, name, email.lower(), 'manager', customer_id))

        # Link OAuth account
        conn.execute("""
            INSERT INTO user_oauth_links (user_id, provider, provider_user_id, provider_email)
            VALUES (?, ?, ?, ?)
        """, (user_id, provider, provider_user_id, email.lower()))

        conn.commit()
        conn.close()

        print(f"[OAuth] Created new user {email} via {provider}")
        return user_id

    except Exception as e:
        print(f"[OAuth] Error creating user from OAuth: {e}")
        return None


def handle_oauth_callback(provider: str, token: dict, userinfo: dict) -> Optional[Dict]:
    """
    Handle OAuth callback - find or create user, return user info for session.

    Args:
        provider: 'microsoft', 'google', etc.
        token: OAuth token response
        userinfo: User info from OAuth provider

    Returns:
        User dict for session, or None if failed
    """
    # Extract info based on provider
    if provider == 'microsoft':
        provider_user_id = userinfo.get('sub') or userinfo.get('oid')
        email = userinfo.get('email') or userinfo.get('preferred_username')
        name = userinfo.get('name', email.split('@')[0] if email else 'Unknown')
    elif provider == 'google':
        provider_user_id = userinfo.get('sub')
        email = userinfo.get('email')
        name = userinfo.get('name', email.split('@')[0] if email else 'Unknown')
    else:
        print(f"[OAuth] Unknown provider: {provider}")
        return None

    if not provider_user_id or not email:
        print(f"[OAuth] Missing user info from {provider}")
        return None

    # Step 1: Check if this OAuth account is already linked
    user = find_user_by_oauth(provider, provider_user_id)

    if user:
        # Update last login
        update_last_login(user['id'])
        return format_user_for_session(user)

    # Step 2: Check if email exists (link OAuth to existing user)
    user = find_user_by_email(email)

    if user:
        # Link this OAuth account to existing user
        link_oauth_to_user(
            user_id=user['id'],
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=email,
            access_token=token.get('access_token'),
            refresh_token=token.get('refresh_token')
        )
        update_last_login(user['id'])
        print(f"[OAuth] Linked {provider} to existing user {email}")
        return format_user_for_session(user)

    # Step 3: Create new user (for self-service signup domains)
    # Note: For controlled environments, you might want to disable auto-creation
    # and require admin to pre-create users

    # Get customer_id from domain if available
    customer_id = get_customer_id_for_domain(request.host if request else None)

    user_id = create_user_from_oauth(
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        name=name,
        customer_id=customer_id
    )

    if user_id:
        user = find_user_by_email(email)
        if user:
            return format_user_for_session(user)

    return None


def format_user_for_session(user: Dict) -> Dict:
    """Format user dict for session storage"""
    return {
        'id': user['id'],
        'username': user.get('username', user.get('email')),
        'name': user['name'],
        'email': user.get('email'),
        'role': user['role'],
        'customer_id': user.get('customer_id'),
        'customer_name': user.get('customer_name')
    }


def update_last_login(user_id: str):
    """Update user's last login timestamp"""
    try:
        conn = get_db_connection()
        conn.execute("""
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
        """, (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[OAuth] Error updating last login: {e}")


def get_customer_id_for_domain(domain: str) -> Optional[str]:
    """Get customer_id associated with a domain"""
    if not domain:
        return None

    try:
        conn = get_db_connection()
        row = conn.execute("""
            SELECT customer_id FROM domains WHERE domain = ? AND is_active = 1
        """, (domain.lower(),)).fetchone()
        conn.close()

        if row:
            return row['customer_id']
    except Exception as e:
        print(f"[OAuth] Error getting customer for domain: {e}")

    return None


def save_auth_providers(entity_type: str, entity_id: str, providers: Dict) -> bool:
    """
    Save auth providers config for a customer or domain.

    Args:
        entity_type: 'customer' or 'domain'
        entity_id: ID of the entity
        providers: Auth providers config dict
    """
    try:
        conn = get_db_connection()
        providers_json = json.dumps(providers)

        if entity_type == 'customer':
            conn.execute("""
                UPDATE customers SET auth_providers = ? WHERE id = ?
            """, (providers_json, entity_id))
        elif entity_type == 'domain':
            conn.execute("""
                UPDATE domains SET auth_providers = ? WHERE id = ?
            """, (providers_json, entity_id))
        else:
            conn.close()
            return False

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"[OAuth] Error saving auth providers: {e}")
        return False


# Provider-specific info for UI
PROVIDER_INFO = {
    'microsoft': {
        'name': 'Microsoft',
        'icon': 'microsoft',
        'color': '#00a4ef',
        'button_text': 'Log ind med Microsoft'
    },
    'google': {
        'name': 'Google',
        'icon': 'google',
        'color': '#4285f4',
        'button_text': 'Log ind med Google'
    },
    'apple': {
        'name': 'Apple',
        'icon': 'apple',
        'color': '#000000',
        'button_text': 'Log ind med Apple'
    },
    'facebook': {
        'name': 'Facebook',
        'icon': 'facebook',
        'color': '#1877f2',
        'button_text': 'Log ind med Facebook'
    }
}


def get_provider_info(provider: str) -> Dict:
    """Get display info for a provider"""
    return PROVIDER_INFO.get(provider, {
        'name': provider.title(),
        'icon': provider,
        'color': '#666666',
        'button_text': f'Log ind med {provider.title()}'
    })

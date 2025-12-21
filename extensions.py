"""
Shared Flask extensions for use by both admin_app.py and blueprints.

Extensions are created here without app context, then initialized
with init_app() in admin_app.py.
"""
import os
from flask import g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

# CSRF Protection
csrf = CSRFProtect()


def get_api_key_or_ip():
    """
    Get rate limit key based on API customer ID if available, else IP address.
    This allows per-customer rate limiting for API endpoints.
    """
    if hasattr(g, 'api_customer_id') and g.api_customer_id:
        return f"api_customer:{g.api_customer_id}"
    return get_remote_address()


# Rate Limiter - disabled in test environment
_ratelimit_enabled = os.environ.get('RATELIMIT_ENABLED', 'true').lower() != 'false'

limiter = Limiter(
    key_func=get_api_key_or_ip,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    enabled=_ratelimit_enabled,
)

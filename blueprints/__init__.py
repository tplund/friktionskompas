"""
Blueprints for Friktionskompasset.

Import all blueprints for easy registration in admin_app.py.
"""

from blueprints.public import public_bp
from blueprints.api_customer import api_customer_bp
from blueprints.api_admin import api_admin_bp
from blueprints.auth import auth_bp

__all__ = [
    'public_bp',
    'api_customer_bp',
    'api_admin_bp',
    'auth_bp',
]

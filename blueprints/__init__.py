"""
Blueprints for Friktionskompasset.

Import all blueprints for easy registration in admin_app.py.
"""

from blueprints.public import public_bp
from blueprints.auth import auth_bp
from blueprints.api_admin import api_admin_bp
from blueprints.api_customer import api_customer_bp
from blueprints.admin_core import admin_core_bp
from blueprints.export import export_bp
from blueprints.assessments import assessments_bp
from blueprints.units import units_bp
from blueprints.customers import customers_bp
from blueprints.dev_tools import dev_tools_bp

__all__ = [
    'public_bp',
    'auth_bp',
    'api_admin_bp',
    'api_customer_bp',
    'admin_core_bp',
    'export_bp',
    'assessments_bp',
    'units_bp',
    'customers_bp',
    'dev_tools_bp',
]

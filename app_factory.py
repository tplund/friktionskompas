"""
Flask Application Factory for Friktionskompasset v3

This module implements the Flask app factory pattern, allowing for different
configurations for development, testing, and production environments.
"""
import os
import secrets
from datetime import timedelta
from flask import Flask, g, session, request, redirect, flash, url_for
from flask_cors import CORS
from flask_wtf.csrf import CSRFError

# Import database initialization functions
from db_hierarchical import init_db, init_db as init_hierarchical_db
from db_profil import init_profil_tables
from db_multitenant import init_multitenant_db, get_domain_config
from audit import init_audit_tables

# Import extensions
from extensions import csrf, limiter

# Import translations
from translations import (
    t, get_user_language, set_language, SUPPORTED_LANGUAGES,
    seed_translations, clear_translation_cache
)

# Import OAuth
from oauth import init_oauth

# Import scheduler
from scheduler import start_scheduler


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


def create_app(config_name='development'):
    """
    Flask application factory.

    Args:
        config_name: One of 'development', 'testing', or 'production'

    Returns:
        Flask application instance
    """
    # Copy seed database on production if needed
    if config_name == 'production':
        copy_seed_database()

    # Initialize databases (unless testing - tests handle their own DB)
    if config_name != 'testing':
        init_db()  # Main hierarchical database
        init_profil_tables()  # Profil tables
        init_multitenant_db()  # Multi-tenant tables
        init_audit_tables()  # Audit logging tables

    # Create Flask app
    app = Flask(__name__)

    # Load configuration based on environment
    _configure_app(app, config_name)

    # Initialize extensions
    _init_extensions(app)

    # Register blueprints
    _register_blueprints(app)

    # Register middleware and handlers
    _register_middleware(app)
    _register_error_handlers(app)
    _register_context_processors(app)

    # Start scheduler for planned assessments (not in testing)
    if config_name != 'testing':
        start_scheduler()

        # Seed translations and clear cache on startup
        seed_translations()
        clear_translation_cache()

    return app


def _configure_app(app, config_name):
    """Configure app based on environment."""
    # Determine if we're in dev/test mode
    is_dev_or_test = (
        config_name in ('development', 'testing') or
        os.environ.get('FLASK_DEBUG', '').lower() == 'true' or
        os.environ.get('RATELIMIT_ENABLED', '').lower() == 'false' or
        os.environ.get('TESTING', '').lower() == 'true'
    )

    # Secret key configuration
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY and not is_dev_or_test:
        raise RuntimeError('SECRET_KEY must be set in production')
    app.secret_key = SECRET_KEY or secrets.token_hex(32)

    # Debug mode
    if config_name == 'development':
        app.debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    elif config_name == 'testing':
        app.debug = False
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
    else:  # production
        app.debug = False

    # Session configuration - timeout after 8 hours of inactivity
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True

    # Security configuration
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
    app.config['SESSION_COOKIE_SECURE'] = not app.debug  # True in production
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


def _init_extensions(app):
    """Initialize Flask extensions."""
    # Initialize OAuth
    init_oauth(app)

    # Initialize CSRF protection
    csrf.init_app(app)

    # Initialize rate limiter
    limiter.init_app(app)

    # CORS Configuration for API endpoints
    CORS(app, resources={
        r"/api/*": {
            "origins": os.environ.get('CORS_ORIGINS', 'https://friktionskompasset.dk,https://frictioncompass.com').split(','),
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "X-API-Key", "X-Admin-API-Key"]
        }
    })


def _register_blueprints(app):
    """Register all application blueprints."""
    # Register Friktionsprofil Blueprint
    from friktionsprofil_routes import friktionsprofil
    app.register_blueprint(friktionsprofil)

    # Register modular blueprints
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

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_admin_bp)
    app.register_blueprint(api_customer_bp)
    app.register_blueprint(admin_core_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(assessments_bp)
    app.register_blueprint(units_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(dev_tools_bp)

    # Register routes from admin_app.py (legacy routes not yet migrated to blueprints)
    # These routes are registered by importing admin_routes module which uses current_app
    try:
        import admin_routes
        admin_routes.register_routes(app)
    except ImportError:
        # admin_routes.py doesn't exist yet - routes are defined directly in admin_app.py
        # This is expected during transition to factory pattern
        pass


def _register_middleware(app):
    """Register middleware functions."""
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

    # Security headers middleware
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses"""
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://track.friktionskompasset.dk https://track.frictioncompass.com https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://unpkg.com; "
            "connect-src 'self' https://track.friktionskompasset.dk https://track.frictioncompass.com"
        )
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        # Only add HSTS in production (not in debug mode)
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response


def _register_error_handlers(app):
    """Register error handlers."""
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        flash('Sessionen er udløbet. Prøv igen.', 'error')
        return redirect(request.referrer or url_for('auth.login'))


def _register_context_processors(app):
    """Register context processors for templates."""
    @app.context_processor
    def inject_domain_config():
        """Make domain config available in all templates"""
        return {
            'domain_config': getattr(g, 'domain_config', None)
        }

    @app.context_processor
    def inject_translation_helpers():
        """Inject translation helpers in all templates"""
        return {
            't': t,
            'get_user_language': get_user_language,
            'supported_languages': SUPPORTED_LANGUAGES
        }

    @app.context_processor
    def inject_customers():
        """Make customer list available in all templates"""
        from db_multitenant import list_customers
        from db_hierarchical import get_db

        customers = []
        if 'user' in session and session['user']['role'] in ('admin', 'superadmin'):
            with get_db() as conn:
                customers = conn.execute("""
                    SELECT id, name
                    FROM customers
                    ORDER BY name
                """).fetchall()

        def get_score_class(score):
            """Return CSS class based on friction score (1-7 scale)

            Thresholds: > 4.9 (70%) = high, >= 3.5 (50%) = medium
            """
            if score is None:
                return 'score-none'
            if score > 4.9:
                return 'score-high'
            elif score >= 3.5:
                return 'score-medium'
            else:
                return 'score-low'

        def get_percent_class(score):
            """Return CSS class based on friction score as percent (1-7 scale)"""
            if score is None:
                return 'score-none'
            percent = (score / 7) * 100
            if percent > 70:
                return 'score-high'
            elif percent >= 50:
                return 'score-medium'
            else:
                return 'score-low'

        def get_gap_class(employee_score, leader_score):
            """Return CSS class and icon based on gap (1-7 scale)

            Thresholds: > 1.4 (20%) = critical, > 0.84 (12%) = warning
            """
            if employee_score is None or leader_score is None:
                return 'gap-none', ''
            gap = abs(employee_score - leader_score)
            if gap > 1.4:  # More than 20% difference on 1-7 scale
                return 'gap-critical', ''
            elif gap > 0.84:  # More than 12% difference
                return 'gap-warning', ''
            else:
                return 'gap-ok', ''

        def to_percent(score):
            """Convert 1-7 score to percent (1=~14%, 7=100%)"""
            if score is None or score == 0:
                return 0
            # Convert 1-7 scale to percent
            return (score / 7) * 100

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

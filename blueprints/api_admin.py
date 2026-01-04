"""
Admin API blueprint - system administration endpoints.

Routes:
- /api/admin/status (GET) - Get system status
- /api/admin/clear-cache (POST) - Clear all caches
- /api/docs - Swagger UI
- /api/docs/openapi.yaml - OpenAPI spec
- /api/docs/openapi.json - OpenAPI spec as JSON
"""

import os
from flask import Blueprint, jsonify, request, send_from_directory, current_app

from extensions import csrf
from auth_helpers import api_or_admin_required
from db_hierarchical import get_db
from translations import clear_translation_cache
from cache import invalidate_all

api_admin_bp = Blueprint('api_admin', __name__, url_prefix='/api')


@api_admin_bp.route('/admin/status')
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
            except Exception:
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


@api_admin_bp.route('/admin/clear-cache', methods=['POST'])
@csrf.exempt
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


def _is_english_domain():
    """Check if request is from English domain (frictioncompass.com)."""
    host = request.host.lower()
    return 'frictioncompass' in host


@api_admin_bp.route('/docs')
def api_docs():
    """
    Swagger UI for Customer API documentation.

    Renders interactive API documentation using Swagger UI.
    Language is automatically selected based on domain.
    """
    is_english = _is_english_domain()

    if is_english:
        title = "Friction Compass API Documentation"
        header_title = "Friction Compass API"
        manage_keys = "Manage API Keys"
        download_spec = "Download OpenAPI Spec"
        lang = "en"
    else:
        title = "Friktionskompasset API Documentation"
        header_title = "Friktionskompasset API"
        manage_keys = "Administrer API Keys"
        download_spec = "Download OpenAPI Spec"
        lang = "da"

    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css">
    <style>
        body {{ margin: 0; padding: 0; }}
        .swagger-ui .topbar {{ display: none; }}
        .swagger-ui .info {{ margin: 20px 0; }}
        .swagger-ui .info .title {{ font-size: 2rem; }}
        .header-bar {{
            background: #1f2937;
            color: white;
            padding: 15px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header-bar h1 {{ margin: 0; font-size: 1.25rem; font-weight: 500; }}
        .header-bar a {{
            color: #60a5fa;
            text-decoration: none;
            font-size: 0.875rem;
        }}
        .header-bar a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="header-bar">
        <h1>{header_title}</h1>
        <div>
            <a href="/admin/api-keys">{manage_keys}</a>
            &nbsp;|&nbsp;
            <a href="/api/docs/openapi.yaml">{download_spec}</a>
        </div>
    </div>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {{
            SwaggerUIBundle({{
                url: "/api/docs/openapi.yaml",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true
            }});
        }};
    </script>
</body>
</html>'''


@api_admin_bp.route('/docs/openapi.yaml')
def api_docs_openapi_yaml():
    """Serve the OpenAPI specification as YAML (language based on domain)."""
    if _is_english_domain():
        return send_from_directory('static', 'openapi_en.yaml', mimetype='text/yaml')
    return send_from_directory('static', 'openapi.yaml', mimetype='text/yaml')


@api_admin_bp.route('/docs/openapi.json')
def api_docs_openapi_json():
    """Serve the OpenAPI specification as JSON (language based on domain)."""
    import yaml

    filename = 'openapi_en.yaml' if _is_english_domain() else 'openapi.yaml'
    yaml_path = os.path.join(current_app.root_path, 'static', filename)
    with open(yaml_path, 'r', encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    return jsonify(spec)


@api_admin_bp.route('/admin/fix-user-role', methods=['POST'])
@csrf.exempt
@api_or_admin_required
def api_fix_user_role():
    """Fix user role - set a user to superadmin.

    API Usage:
        curl -X POST https://friktionskompasset.dk/api/admin/fix-user-role \
             -H "X-Admin-API-Key: YOUR_KEY" \
             -H "Content-Type: application/json" \
             -d '{"email": "user@example.com", "role": "superadmin"}'
    """
    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()
    new_role = data.get('role', 'superadmin')

    if not email:
        return jsonify({'success': False, 'error': 'Email required'}), 400

    if new_role not in ('superadmin', 'admin', 'manager', 'user'):
        return jsonify({'success': False, 'error': 'Invalid role'}), 400

    with get_db() as conn:
        # Find user
        user = conn.execute('SELECT id, email, role FROM users WHERE email = ?', (email,)).fetchone()
        if not user:
            return jsonify({'success': False, 'error': f'User not found: {email}'}), 404

        old_role = user['role']

        # Update role
        conn.execute('UPDATE users SET role = ? WHERE email = ?', (new_role, email))
        conn.commit()

    return jsonify({
        'success': True,
        'message': f'Updated {email} from {old_role} to {new_role}'
    })

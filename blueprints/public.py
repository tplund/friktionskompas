"""
Public routes blueprint - no authentication required.

Routes:
- / (index)
- /landing
- /robots.txt
- /sitemap.xml
- Zoho verification files
"""

from flask import Blueprint, render_template, redirect, url_for, session, \
    send_from_directory, request, Response

public_bp = Blueprint('public', __name__)


@public_bp.route('/')
def index():
    """Root route - show landing page or redirect to admin if logged in"""
    if 'user' in session:
        return redirect(url_for('admin_core.admin_home'))
    return render_template('landing.html')


@public_bp.route('/landing')
def landing():
    """Public landing page"""
    return render_template('landing.html')


@public_bp.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for SEO"""
    return send_from_directory('static', 'robots.txt', mimetype='text/plain')


@public_bp.route('/sitemap.xml')
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


@public_bp.route('/verifyforzoho.html')
def zoho_verify():
    """Zoho domain verification"""
    return send_from_directory('.', 'verifyforzoho.html')


@public_bp.route('/zoho-domain-verification.html')
def zoho_domain_verify():
    """Zoho domain verification (alternative file)"""
    return send_from_directory('.', 'zoho-domain-verification.html')

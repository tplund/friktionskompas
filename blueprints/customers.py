"""
Customers Blueprint - Customer and domain management routes.

Routes:
- /admin/customers - Customer management (admin_required)
- /admin/customer/new - Create new customer (admin_required)
- /admin/customer/<customer_id>/delete - Delete customer (admin_required)
- /admin/customer/<customer_id>/email-settings - Email settings for customer (admin_required)
- /admin/customer/<customer_id>/assessments - Assessment type configuration (admin_required)
- /admin/customer/<customer_id>/assessments - Update assessment types (admin_required)
- /admin/customer/<customer_id>/assessments/preset/<preset_id> - Apply preset (admin_required)
- /admin/domains - Domain management (admin_required)
- /admin/domain/new - Create new domain (admin_required)
- /admin/domain/<domain_id>/edit - Edit domain (admin_required)
- /admin/domain/<domain_id>/delete - Delete domain (admin_required)
- /admin/api-keys - API key management (admin_required)
- /admin/api-keys - Create new API key (admin_required)
- /admin/api-keys/<key_id>/revoke - Revoke API key (admin_required)
- /admin/api-keys/<key_id>/delete - Delete API key (admin_required)
- /admin/auth-config - Auth provider configuration (superadmin_required)
- /admin/auth-config/customer/<customer_id> - Update customer auth (superadmin_required)
- /admin/auth-config/domain/<domain_id> - Update domain auth (superadmin_required)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import os

from auth_helpers import admin_required, superadmin_required, get_current_user
from db_hierarchical import get_db
from db_multitenant import (
    list_customers, list_users, create_customer, get_customer, update_customer,
    list_domains, create_domain, update_domain, delete_domain,
    list_customer_api_keys, generate_customer_api_key, revoke_customer_api_key,
    delete_customer_api_key, get_customer_assessment_config, get_all_presets,
    set_customer_assessment_types
)
from oauth import save_auth_providers, DEFAULT_AUTH_PROVIDERS
from translations import t
from audit import log_action, AuditAction

customers_bp = Blueprint('customers', __name__)


# ========================================
# CUSTOMER MANAGEMENT
# ========================================

@customers_bp.route('/admin/customers')
@admin_required
def manage_customers():
    """Customer management - kun admin"""
    customers = list_customers()
    users = list_users()  # Alle users
    return render_template('admin/customers.html',
                         customers=customers,
                         users=users)


@customers_bp.route('/admin/customer/new', methods=['POST'])
@admin_required
def create_new_customer():
    """Opret ny customer - kun admin"""
    name = request.form['name']
    contact_email = request.form.get('contact_email')

    customer_id = create_customer(name, contact_email)

    flash(f'Customer "{name}" oprettet!', 'success')
    return redirect(url_for('customers.manage_customers'))


@customers_bp.route('/admin/customer/<customer_id>/delete', methods=['POST'])
@admin_required
def delete_customer(customer_id):
    """Slet kunde og alle tilhørende data (kun admin)"""
    with get_db() as conn:
        # Tjek at kunden eksisterer
        customer = conn.execute(
            "SELECT * FROM customers WHERE id = ?",
            (customer_id,)
        ).fetchone()

        if not customer:
            flash('Kunde ikke fundet', 'error')
            return redirect(url_for('admin_core.admin_home'))

        customer_name = customer['name']

        # CASCADE DELETE vil automatisk slette:
        # - organizational_units (og deres children)
        # - assessments
        # - responses
        # - users tilknyttet kunden
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

        # Audit log customer deletion
        log_action(
            AuditAction.CUSTOMER_DELETED,
            entity_type="customer",
            entity_id=customer_id,
            details=f"Deleted customer: {customer_name}"
        )

    flash(f'Kunde "{customer_name}" og alle tilhørende data er slettet', 'success')
    return redirect(url_for('admin_core.admin_home'))


@customers_bp.route('/admin/customer/<customer_id>/email-settings', methods=['GET', 'POST'])
@admin_required
def customer_email_settings(customer_id):
    """Email-indstillinger for en kunde - kun admin"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('customers.manage_customers'))

    if request.method == 'POST':
        email_from_address = request.form.get('email_from_address', '').strip() or None
        email_from_name = request.form.get('email_from_name', '').strip() or None

        update_customer(customer_id,
                       email_from_address=email_from_address,
                       email_from_name=email_from_name)

        flash(t('email_settings.saved', 'Email-indstillinger gemt!'), 'success')
        return redirect(url_for('customers.customer_email_settings', customer_id=customer_id))

    # Default values fra environment
    default_from_email = os.getenv('FROM_EMAIL', 'info@friktionskompasset.dk')
    default_from_name = os.getenv('FROM_NAME', 'Friktionskompasset')

    return render_template('admin/email_settings.html',
                         customer=customer,
                         default_from_email=default_from_email,
                         default_from_name=default_from_name)


@customers_bp.route('/admin/customer/<customer_id>/assessments')
@admin_required
def customer_assessments(customer_id):
    """Konfigurer målingstyper for en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('customers.manage_customers'))

    config = get_customer_assessment_config(customer_id)
    presets = get_all_presets()

    return render_template('admin/customer_assessments.html',
                         customer=customer,
                         config=config,
                         presets=presets)


@customers_bp.route('/admin/customer/<customer_id>/assessments', methods=['POST'])
@admin_required
def update_customer_assessments(customer_id):
    """Opdater målingstyper for en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('customers.manage_customers'))

    # Hent valgte typer fra form
    enabled_types = request.form.getlist('assessment_types')

    if enabled_types:
        set_customer_assessment_types(customer_id, enabled_types)
        flash('Målingstyper opdateret for kunde!', 'success')
    else:
        # Hvis ingen valgt, slet custom config (brug default preset)
        with get_db() as conn:
            conn.execute(
                "DELETE FROM customer_assessment_types WHERE customer_id = ?",
                (customer_id,)
            )
        flash('Kunde bruger nu standard preset!', 'success')

    return redirect(url_for('customers.customer_assessments', customer_id=customer_id))


@customers_bp.route('/admin/customer/<customer_id>/assessments/preset/<int:preset_id>', methods=['POST'])
@admin_required
def apply_preset_to_customer(customer_id, preset_id):
    """Anvend et preset til en kunde"""
    customer = get_customer(customer_id)
    if not customer:
        flash('Kunde ikke fundet', 'error')
        return redirect(url_for('customers.manage_customers'))

    with get_db() as conn:
        # Hent typer fra preset
        preset_types = conn.execute('''
            SELECT assessment_type_id FROM preset_assessment_types
            WHERE preset_id = ?
        ''', (preset_id,)).fetchall()

        type_ids = [t['assessment_type_id'] for t in preset_types]

    if type_ids:
        set_customer_assessment_types(customer_id, type_ids)
        flash('Preset anvendt på kunde!', 'success')

    return redirect(url_for('customers.customer_assessments', customer_id=customer_id))


# ========================================
# DOMAIN MANAGEMENT
# ========================================

@customers_bp.route('/admin/domains')
@admin_required
def manage_domains():
    """Domain management - kun admin"""
    domains = list_domains()
    customers = list_customers()
    return render_template('admin/domains.html',
                         domains=domains,
                         customers=customers)


@customers_bp.route('/admin/domain/new', methods=['POST'])
@admin_required
def create_new_domain():
    """Opret nyt domain mapping - kun admin"""
    domain = request.form['domain'].strip().lower()
    customer_id = request.form.get('customer_id') or None
    default_language = request.form.get('default_language', 'da')
    branding = {
        'logo_url': request.form.get('branding_logo_url') or None,
        'primary_color': request.form.get('branding_primary_color') or None,
        'company_name': request.form.get('branding_company_name') or None
    }

    domain_id = create_domain(domain, customer_id, default_language, branding)
    flash(f'Domain "{domain}" oprettet!', 'success')
    return redirect(url_for('customers.manage_domains'))


@customers_bp.route('/admin/domain/<domain_id>/edit', methods=['POST'])
@admin_required
def edit_domain(domain_id):
    """Rediger domain - kun admin"""
    update_domain(
        domain_id,
        customer_id=request.form.get('customer_id') or None,
        default_language=request.form.get('default_language', 'da'),
        branding_logo_url=request.form.get('branding_logo_url') or None,
        branding_primary_color=request.form.get('branding_primary_color') or None,
        branding_company_name=request.form.get('branding_company_name') or None
    )
    flash('Domain opdateret!', 'success')
    return redirect(url_for('customers.manage_domains'))


@customers_bp.route('/admin/domain/<domain_id>/delete', methods=['POST'])
@admin_required
def delete_domain_route(domain_id):
    """Slet domain - kun admin"""
    delete_domain(domain_id)
    flash('Domain slettet!', 'success')
    return redirect(url_for('customers.manage_domains'))


# ========================================
# API KEY MANAGEMENT
# ========================================

@customers_bp.route('/admin/api-keys')
@admin_required
def admin_api_keys():
    """API Key management page"""
    user = get_current_user()
    new_key = request.args.get('new_key')

    # Determine which customer(s) to show keys for
    if user['role'] == 'superadmin':
        customer_filter = session.get('customer_filter')
        if customer_filter:
            customer = get_customer(customer_filter)
            api_keys = list_customer_api_keys(customer_filter)
            customers = None
        else:
            # Show all customers' keys
            customer = None
            customers = list_customers()
            api_keys = []
            for c in customers:
                keys = list_customer_api_keys(c['id'])
                for k in keys:
                    k['customer_name'] = c['name']
                api_keys.extend(keys)
    else:
        # Admin/manager sees only their customer
        customer = get_customer(user['customer_id'])
        api_keys = list_customer_api_keys(user['customer_id'])
        customers = None

    return render_template('admin/api_keys.html',
                         api_keys=api_keys,
                         customer=customer,
                         customers=customers,
                         new_key=new_key)


@customers_bp.route('/admin/api-keys', methods=['POST'])
@admin_required
def admin_create_api_key():
    """Create new API key"""
    user = get_current_user()

    # Get customer_id from form or user's customer
    customer_id = request.form.get('customer_id')
    if not customer_id:
        customer_id = user.get('customer_id')

    # Verify access - superadmin can create for any, others only for their customer
    if user['role'] != 'superadmin' and customer_id != user.get('customer_id'):
        flash('Du kan kun oprette API-nøgler for din egen kunde', 'error')
        return redirect(url_for('customers.admin_api_keys'))

    if not customer_id:
        flash('Vælg en kunde', 'error')
        return redirect(url_for('customers.admin_api_keys'))

    # Get form data
    name = request.form.get('name', 'API Key').strip()
    permissions = {
        'read': True,
        'write': 'perm_write' in request.form
    }

    # Generate key
    full_key, key_id = generate_customer_api_key(customer_id, name, permissions)

    flash('API-nøgle oprettet! Kopier nøglen nu - den vises kun denne ene gang.', 'success')
    return redirect(url_for('customers.admin_api_keys', new_key=full_key))


@customers_bp.route('/admin/api-keys/<int:key_id>/revoke', methods=['POST'])
@admin_required
def admin_revoke_api_key(key_id):
    """Revoke (deactivate) an API key"""
    if revoke_customer_api_key(key_id):
        flash('API-nøgle deaktiveret', 'success')
    else:
        flash('Kunne ikke deaktivere nøglen', 'error')

    return redirect(url_for('customers.admin_api_keys'))


@customers_bp.route('/admin/api-keys/<int:key_id>/delete', methods=['POST'])
@admin_required
def admin_delete_api_key(key_id):
    """Permanently delete an API key"""
    if delete_customer_api_key(key_id):
        flash('API-nøgle slettet permanent', 'success')
    else:
        flash('Kunne ikke slette nøglen', 'error')

    return redirect(url_for('customers.admin_api_keys'))


# ========================================
# AUTH CONFIG (Superadmin only)
# ========================================

@customers_bp.route('/admin/auth-config')
@superadmin_required
def auth_config():
    """Configure authentication providers per customer (superadmin only)"""
    customers = list_customers()
    domains = list_domains()

    # Parse auth_providers JSON for each
    import json
    for customer in customers:
        try:
            customer['auth_providers_parsed'] = json.loads(customer.get('auth_providers') or '{}')
        except (json.JSONDecodeError, ValueError, TypeError):
            customer['auth_providers_parsed'] = {}

    for domain in domains:
        try:
            domain['auth_providers_parsed'] = json.loads(domain.get('auth_providers') or '{}')
        except (json.JSONDecodeError, ValueError, TypeError):
            domain['auth_providers_parsed'] = {}

    return render_template('admin/auth_config.html',
                         customers=customers,
                         domains=domains,
                         default_providers=DEFAULT_AUTH_PROVIDERS)


@customers_bp.route('/admin/auth-config/customer/<customer_id>', methods=['POST'])
@superadmin_required
def update_customer_auth(customer_id):
    """Update auth providers for a customer (superadmin only)"""
    providers = {
        'email_password': 'email_password' in request.form,
        'microsoft': {
            'enabled': 'microsoft' in request.form
        },
        'google': {
            'enabled': 'google' in request.form
        },
        'apple': {
            'enabled': 'apple' in request.form
        },
        'facebook': {
            'enabled': 'facebook' in request.form
        }
    }

    save_auth_providers('customer', customer_id, providers)
    flash('Auth providers opdateret for kunde!', 'success')

    return redirect(url_for('customers.auth_config'))


@customers_bp.route('/admin/auth-config/domain/<domain_id>', methods=['POST'])
@superadmin_required
def update_domain_auth(domain_id):
    """Update auth providers for a domain (superadmin only)"""
    providers = {
        'email_password': 'email_password' in request.form,
        'microsoft': {
            'enabled': 'microsoft' in request.form
        },
        'google': {
            'enabled': 'google' in request.form
        },
        'apple': {
            'enabled': 'apple' in request.form
        },
        'facebook': {
            'enabled': 'facebook' in request.form
        }
    }

    save_auth_providers('domain', domain_id, providers)
    flash('Auth providers opdateret for domæne!', 'success')

    return redirect(url_for('customers.auth_config'))

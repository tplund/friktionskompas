"""
Tests for API routes and endpoints.
"""
import pytest


class TestPublicRoutes:
    """Test publicly accessible routes."""

    def test_index_page(self, client):
        """Test that index page loads."""
        response = client.get('/')
        assert response.status_code in [200, 302]

    def test_login_page(self, client):
        """Test that login page loads."""
        response = client.get('/login')
        assert response.status_code == 200

    def test_health_check(self, client):
        """Test health check endpoint if it exists."""
        response = client.get('/health')
        # May or may not exist
        assert response.status_code in [200, 404]


class TestAdminRoutes:
    """Test admin routes."""

    def test_admin_home(self, authenticated_client):
        """Test admin home page."""
        response = authenticated_client.get('/admin')
        assert response.status_code == 200

    def test_admin_dashboard(self, authenticated_client):
        """Test admin dashboard."""
        response = authenticated_client.get('/admin/dashboard')
        assert response.status_code == 200

    def test_admin_analyser(self, authenticated_client):
        """Test analyser page."""
        response = authenticated_client.get('/admin/analyser')
        assert response.status_code == 200

    def test_admin_customers(self, authenticated_client):
        """Test customers page (admin only)."""
        response = authenticated_client.get('/admin/customers')
        assert response.status_code == 200

    def test_admin_profiler(self, authenticated_client):
        """Test profiler page."""
        response = authenticated_client.get('/admin/profiler')
        assert response.status_code == 200

    def test_admin_email_templates(self, authenticated_client):
        """Test email templates page."""
        response = authenticated_client.get('/admin/email-templates')
        assert response.status_code == 200

    def test_admin_profil_questions(self, authenticated_client):
        """Test profil questions page."""
        response = authenticated_client.get('/admin/profil-questions')
        assert response.status_code == 200

    def test_admin_noegletal(self, authenticated_client):
        """Test nøgletal dashboard page."""
        response = authenticated_client.get('/admin/noegletal')
        assert response.status_code == 200
        # Check that key elements are present
        html = response.data.decode('utf-8')
        assert 'Besvarelser' in html or 'Responses' in html

    def test_admin_trend(self, authenticated_client):
        """Test trend analysis page."""
        response = authenticated_client.get('/admin/trend')
        assert response.status_code == 200
        # Check that key elements are present
        html = response.data.decode('utf-8')
        assert 'Trend' in html

    def test_admin_domains(self, authenticated_client):
        """Test domains management page."""
        response = authenticated_client.get('/admin/domains')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'Domæne' in html or 'domain' in html.lower()


class TestManagerRoutes:
    """Test routes accessible by managers."""

    def test_manager_can_access_admin(self, manager_client):
        """Test that manager can access basic admin."""
        response = manager_client.get('/admin')
        assert response.status_code == 200

    def test_manager_can_access_analyser(self, manager_client):
        """Test that manager can access analyser."""
        response = manager_client.get('/admin/analyser')
        assert response.status_code == 200


class TestAPIEndpoints:
    """Test API endpoints."""

    def test_api_email_templates(self, authenticated_client):
        """Test email templates API."""
        response = authenticated_client.get('/api/email-templates')
        assert response.status_code == 200
        # Should return JSON
        assert response.content_type == 'application/json'

    def test_api_requires_auth(self, client):
        """Test that API endpoints require authentication."""
        response = client.get('/api/email-templates', follow_redirects=False)
        # Should redirect to login or return 401
        assert response.status_code in [302, 401]


class TestLinkIntegrity:
    """Test that all internal links work."""

    def test_navigation_links(self, authenticated_client):
        """Test that main navigation links work."""
        # Get admin page and check links
        response = authenticated_client.get('/admin')
        assert response.status_code == 200

        # Extract and test common navigation links
        nav_links = [
            '/admin',
            '/admin/dashboard',
            '/admin/analyser',
            '/admin/profiler',
            '/admin/customers',
            '/admin/trend',
            '/admin/domains',
        ]

        for link in nav_links:
            response = authenticated_client.get(link)
            assert response.status_code == 200, f"Link {link} should return 200"

    def test_no_broken_static_links(self, authenticated_client):
        """Test that static assets are accessible."""
        # Test favicon
        response = authenticated_client.get('/static/favicon.svg')
        assert response.status_code == 200


class TestViewModes:
    """Test view mode switching."""

    def test_switch_to_user_view(self, authenticated_client):
        """Test switching to user view."""
        response = authenticated_client.get('/admin/view/user', follow_redirects=True)
        assert response.status_code == 200

    def test_switch_to_manager_view(self, authenticated_client):
        """Test switching to manager view."""
        response = authenticated_client.get('/admin/view/manager', follow_redirects=True)
        assert response.status_code == 200

    def test_switch_to_admin_view(self, authenticated_client):
        """Test switching to admin view."""
        response = authenticated_client.get('/admin/view/admin', follow_redirects=True)
        assert response.status_code == 200


class TestErrorHandling:
    """Test error handling."""

    def test_404_for_nonexistent_page(self, authenticated_client):
        """Test 404 for non-existent pages."""
        response = authenticated_client.get('/admin/this-page-does-not-exist')
        assert response.status_code == 404

    def test_404_for_nonexistent_unit(self, authenticated_client):
        """Test 404 for non-existent unit."""
        response = authenticated_client.get('/admin/unit/nonexistent-unit-id')
        assert response.status_code in [404, 302]  # May redirect

    def test_404_for_nonexistent_assessment(self, authenticated_client):
        """Test 404 for non-existent assessment."""
        response = authenticated_client.get('/admin/assessment/nonexistent-assessment-id')
        assert response.status_code in [404, 302]  # May redirect


class TestDeleteOperations:
    """Test delete operations for organizations."""

    def test_delete_unit_route_exists(self, authenticated_client):
        """Test that delete unit route accepts POST."""
        # Trying to delete non-existent unit should return redirect (not 404/405)
        response = authenticated_client.post('/admin/unit/fake-unit-id/delete', follow_redirects=False)
        assert response.status_code == 302  # Redirects after delete attempt

    def test_delete_toplevel_unit(self, authenticated_client, app):
        """Test deleting a toplevel organization."""
        # Create a toplevel unit to delete
        from db_multitenant import get_db

        with app.app_context():
            with get_db() as conn:
                # Get first customer for testing
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

                customer_id = customer['id']

                # Create a toplevel unit (parent_id = NULL)
                test_unit_id = 'test-toplevel-delete'
                conn.execute("""
                    INSERT INTO organizational_units (id, name, customer_id, parent_id, level, full_path)
                    VALUES (?, 'Test Toplevel Delete', ?, NULL, 0, 'Test Toplevel Delete')
                """, (test_unit_id, customer_id))
                conn.commit()

                # Verify unit exists
                unit = conn.execute("SELECT * FROM organizational_units WHERE id = ?", (test_unit_id,)).fetchone()
                assert unit is not None, "Test unit should exist before delete"

        # Delete the unit via POST
        response = authenticated_client.post(f'/admin/unit/{test_unit_id}/delete', follow_redirects=False)
        assert response.status_code == 302  # Should redirect after delete

        # Verify unit is gone
        with app.app_context():
            with get_db() as conn:
                unit = conn.execute("SELECT * FROM organizational_units WHERE id = ?", (test_unit_id,)).fetchone()
                assert unit is None, "Toplevel unit should be deleted"

    def test_bulk_delete_requires_admin(self, manager_client):
        """Test that bulk delete is admin-only."""
        response = manager_client.post('/admin/units/bulk-delete',
                                       data={'unit_ids': '[]'},
                                       follow_redirects=True)
        # Manager should see error or be denied
        assert response.status_code == 200  # Shows page with error message
        assert b'administrator' in response.data.lower() or b'admin' in response.data.lower()

    def test_bulk_delete_toplevel_units(self, authenticated_client, app):
        """Test bulk deleting toplevel organizations."""
        import json
        from db_multitenant import get_db

        with app.app_context():
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

                customer_id = customer['id']

                # Create two toplevel units
                test_ids = ['bulk-test-1', 'bulk-test-2']
                for test_id in test_ids:
                    conn.execute("""
                        INSERT INTO organizational_units (id, name, customer_id, parent_id, level, full_path)
                        VALUES (?, ?, ?, NULL, 0, ?)
                    """, (test_id, f'Bulk Test {test_id}', customer_id, f'Bulk Test {test_id}'))
                conn.commit()

        # Bulk delete
        response = authenticated_client.post('/admin/units/bulk-delete',
                                            data={'unit_ids': json.dumps(test_ids)},
                                            follow_redirects=False)
        assert response.status_code == 302

        # Verify units are gone
        with app.app_context():
            with get_db() as conn:
                for test_id in test_ids:
                    unit = conn.execute("SELECT * FROM organizational_units WHERE id = ?", (test_id,)).fetchone()
                    assert unit is None, f"Unit {test_id} should be deleted"

    def test_delete_customer_requires_admin(self, manager_client):
        """Test that deleting customers requires admin role."""
        response = manager_client.post('/admin/customer/fake-customer-id/delete', follow_redirects=False)
        # Should redirect to login or home (access denied)
        assert response.status_code == 302

    def test_delete_customer(self, authenticated_client, app):
        """Test deleting a customer and all related data."""
        from db_multitenant import get_db

        with app.app_context():
            with get_db() as conn:
                # Create test customer
                test_customer_id = 'test-customer-delete'
                conn.execute("""
                    INSERT INTO customers (id, name, created_at)
                    VALUES (?, 'Test Customer Delete', datetime('now'))
                """, (test_customer_id,))

                # Create a unit under this customer
                conn.execute("""
                    INSERT INTO organizational_units (id, name, customer_id, parent_id, level, full_path)
                    VALUES ('test-unit-under-customer', 'Test Unit', ?, NULL, 0, 'Test Unit')
                """, (test_customer_id,))
                conn.commit()

                # Verify data exists
                customer = conn.execute("SELECT * FROM customers WHERE id = ?", (test_customer_id,)).fetchone()
                assert customer is not None

        # Delete customer
        response = authenticated_client.post(f'/admin/customer/{test_customer_id}/delete', follow_redirects=False)
        assert response.status_code == 302

        # Verify customer and units are gone
        with app.app_context():
            with get_db() as conn:
                customer = conn.execute("SELECT * FROM customers WHERE id = ?", (test_customer_id,)).fetchone()
                assert customer is None, "Customer should be deleted"

                unit = conn.execute("SELECT * FROM organizational_units WHERE id = ?", ('test-unit-under-customer',)).fetchone()
                assert unit is None, "Units under customer should be cascade deleted"

    def test_backup_page(self, authenticated_client):
        """Test backup page loads."""
        response = authenticated_client.get('/admin/backup')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'Backup' in html

    def test_backup_download(self, authenticated_client):
        """Test backup download returns valid JSON."""
        import json
        response = authenticated_client.get('/admin/backup/download')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        data = json.loads(response.data)
        assert 'version' in data
        assert 'tables' in data
        assert 'backup_date' in data

    def test_bulk_export_page(self, authenticated_client):
        """Test bulk export page loads."""
        response = authenticated_client.get('/admin/bulk-export')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        assert 'Bulk' in html or 'Eksport' in html

    def test_bulk_export_download_json(self, authenticated_client):
        """Test bulk export download returns valid JSON."""
        import json
        response = authenticated_client.post('/admin/bulk-export/download', data={
            'format': 'json',
            'anonymization': 'pseudonymized',
            'include_responses': '1',
            'include_scores': '1',
            'include_questions': '1'
        })
        assert response.status_code == 200
        assert 'application/json' in response.content_type
        data = json.loads(response.data)
        assert 'export_date' in data
        assert 'export_version' in data
        assert 'anonymization_level' in data

    def test_bulk_export_download_csv(self, authenticated_client):
        """Test bulk export download returns valid CSV."""
        response = authenticated_client.post('/admin/bulk-export/download', data={
            'format': 'csv',
            'anonymization': 'full',
            'include_responses': '1'
        })
        assert response.status_code == 200
        assert 'text/csv' in response.content_type

    def test_delete_assessment(self, authenticated_client, app):
        """Test deleting a assessment."""
        from db_multitenant import get_db

        with app.app_context():
            with get_db() as conn:
                # Get first customer and unit for testing
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

                unit = conn.execute(
                    "SELECT id FROM organizational_units WHERE customer_id = ? LIMIT 1",
                    (customer['id'],)
                ).fetchone()
                if not unit:
                    pytest.skip("No units in test database")

                # Create a test assessment
                test_assessment_id = 'test-assessment-delete'
                conn.execute("""
                    INSERT INTO assessments (id, name, target_unit_id, period)
                    VALUES (?, 'Test Assessment Delete', ?, 'Q1 2025')
                """, (test_assessment_id, unit['id']))
                conn.commit()

                # Verify assessment exists
                assessment = conn.execute("SELECT * FROM assessments WHERE id = ?", (test_assessment_id,)).fetchone()
                assert assessment is not None

        # Delete assessment
        response = authenticated_client.post(f'/admin/assessment/{test_assessment_id}/delete', follow_redirects=False)
        assert response.status_code == 302

        # Verify assessment is gone
        with app.app_context():
            with get_db() as conn:
                assessment = conn.execute("SELECT * FROM assessments WHERE id = ?", (test_assessment_id,)).fetchone()
                assert assessment is None, "Assessment should be deleted"


class TestMenuLinks:
    """Test that all menu links in the navigation are valid routes.

    This catches issues where menu hrefs don't match actual route definitions.
    """

    # All links that should appear in the main navigation menu
    MENU_LINKS = [
        # Dashboard
        '/admin',
        # Målinger dropdown
        '/admin/assessments-overview',
        '/admin/scheduled-assessments',
        '/admin/assessment/new',  # NOT /admin/new-assessment!
        '/admin/analyser',
        # Friktionsprofil dropdown
        '/admin/profiler',
        # Organisation dropdown
        '/admin/units',
        '/admin/customers',
        '/admin/domains',
        # Indstillinger dropdown
        '/admin/my-branding',
        '/admin/auth-config',
        '/admin/assessment-types',
        '/admin/profil-questions',
        '/admin/email-stats',
        '/admin/email-templates',
        '/admin/backup',
        '/admin/dev-tools',
    ]

    def test_all_menu_links_are_valid(self, authenticated_client):
        """Test that every link in MENU_LINKS returns 200 or valid redirect."""
        for link in self.MENU_LINKS:
            response = authenticated_client.get(link)
            # 200 = OK, 302 = redirect (some pages redirect to setup or similar)
            assert response.status_code in [200, 302], f"Menu link {link} should return 200/302, got {response.status_code}"

    def test_menu_links_in_layout_match_routes(self, authenticated_client):
        """Test that menu links extracted from layout.html actually work."""
        import re

        # Get a page that uses layout.html
        response = authenticated_client.get('/admin')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Extract all href="/admin/..." links from navigation
        links = re.findall(r'href="(/admin[^"]*)"', html)

        # Filter out external links, anchors, and dynamic URLs
        valid_links = [
            link for link in links
            if not link.startswith('/admin/impersonate')
            and not link.startswith('/admin/view/')
            and not link.startswith('/admin/unit/')
            and not link.startswith('/admin/assessment/')
            and not link.startswith('/admin/customer/')
            and not 'stop-impersonate' in link
            and '{{' not in link  # Jinja variables
        ]

        # Remove duplicates
        valid_links = list(set(valid_links))

        # Test each link
        for link in valid_links:
            response = authenticated_client.get(link)
            assert response.status_code in [200, 302], f"Link {link} from layout should be valid, got {response.status_code}"

    def test_wrong_urls_return_404(self, authenticated_client):
        """Test that common wrong URLs return 404 (not 500/502)."""
        wrong_urls = [
            '/admin/new-assessment',  # Wrong - should be /admin/assessment/new
            '/admin/new-campaign',    # Old terminology
            '/admin/kampagne/new',    # Old terminology
        ]

        for url in wrong_urls:
            response = authenticated_client.get(url)
            assert response.status_code == 404, f"Wrong URL {url} should return 404, got {response.status_code}"

    def test_all_pages_have_consistent_navigation(self, authenticated_client):
        """Test that key pages all have the same navigation structure."""
        pages_to_test = [
            '/admin',
            '/admin/analyser',
            '/admin/profil-questions',
            '/admin/email-templates',
            '/admin/backup',
        ]

        nav_items = None
        for page in pages_to_test:
            response = authenticated_client.get(page)
            assert response.status_code == 200, f"Page {page} should load"
            html = response.data.decode('utf-8')

            # Check for key navigation elements that should be on ALL pages
            assert 'Dashboard' in html or 'dashboard' in html.lower(), f"{page} should have Dashboard link"
            assert 'Indstillinger' in html or 'indstillinger' in html.lower(), f"{page} should have Indstillinger menu"

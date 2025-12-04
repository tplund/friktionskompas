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

    def test_404_for_nonexistent_campaign(self, authenticated_client):
        """Test 404 for non-existent campaign."""
        response = authenticated_client.get('/admin/campaign/nonexistent-campaign-id')
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

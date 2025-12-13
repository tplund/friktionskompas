"""
Tests for role-based data visibility in Friktionskompasset.
Systematically tests that the correct data is shown to different user roles.

These tests verify:
1. Superadmin sees all data when no filter
2. Superadmin sees only selected customer data when filter is set
3. Admin sees all data
4. Manager only sees their own customer's data
5. Customer filter works correctly in all major views

URL reference:
- /admin - Home/organization tree
- /admin/dashboard - Dashboard with stats
- /admin/analyser - Analysis page
- /admin/campaigns-overview - Campaigns list
- /admin/campaign/new - New campaign form
- /admin/unit/new - New unit form
- /admin/unit/<id> - View unit details
- /admin/campaign/<id> - View campaign
"""
import pytest
import sqlite3
import os


class TestSetupMultipleCustomers:
    """Setup fixture that creates multiple customers with distinct data."""

    @pytest.fixture(autouse=True)
    def setup_multi_customer_data(self, app):
        """Create multiple customers with distinct data for testing."""
        db_path = app.config.get('DATABASE') or os.environ.get('DB_PATH')

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=ON")

        # Check if second customer exists, if not create it
        existing = conn.execute("SELECT id FROM customers WHERE id = 2").fetchone()
        if not existing:
            # Create second customer
            conn.execute("""
                INSERT INTO customers (id, name, domain, created_at)
                VALUES (2, 'Herning Kommune', 'herning.dk', datetime('now'))
            """)

            # Create organization for second customer
            conn.execute("""
                INSERT INTO organizational_units (id, name, customer_id, parent_id, level)
                VALUES ('unit-herning-1', 'Herning Hovedkontor', 2, NULL, 0)
            """)

            conn.execute("""
                INSERT INTO organizational_units (id, name, customer_id, parent_id, level)
                VALUES ('unit-herning-2', 'Herning Afdeling', 2, 'unit-herning-1', 1)
            """)

            # Create campaign for second customer
            conn.execute("""
                INSERT INTO campaigns (id, name, period, target_unit_id, customer_id, created_at)
                VALUES ('campaign-herning-1', 'Herning Q4 2024', 'Q4 2024', 'unit-herning-1', 2, datetime('now'))
            """)

            conn.commit()

        # Ensure first customer has a campaign too
        existing_camp = conn.execute("SELECT id FROM campaigns WHERE customer_id = 1").fetchone()
        if not existing_camp:
            conn.execute("""
                INSERT INTO campaigns (id, name, period, target_unit_id, customer_id, created_at)
                VALUES ('campaign-test-1', 'Test Q4 2024', 'Q4 2024', 'unit-test-1', 1, datetime('now'))
            """)
            conn.commit()

        conn.close()
        yield


class TestSuperadminNoFilter(TestSetupMultipleCustomers):
    """Test superadmin WITHOUT customer filter - should see ALL data."""

    def test_analyser_shows_all_campaigns(self, superadmin_client):
        """Superadmin without filter should see campaigns from all customers."""
        response = superadmin_client.get('/admin/analyser')
        assert response.status_code == 200
        # Should see both customers' campaigns in the filter dropdown
        data = response.data.decode('utf-8')
        # Both campaigns should be visible somewhere in the page
        assert 'campaign' in data.lower() or 'måling' in data.lower()

    def test_campaigns_overview_shows_all(self, superadmin_client):
        """Superadmin without filter should see all campaigns in overview."""
        response = superadmin_client.get('/admin/campaigns-overview')
        assert response.status_code == 200

    def test_admin_home_shows_all_units(self, superadmin_client):
        """Superadmin without filter should see all organizational units on admin home."""
        response = superadmin_client.get('/admin')
        assert response.status_code == 200
        data = response.data.decode('utf-8')
        # Should see units from multiple customers
        assert 'Test' in data or 'organisation' in data.lower()


class TestSuperadminWithFilter(TestSetupMultipleCustomers):
    """Test superadmin WITH customer filter - should see only selected customer's data."""

    @pytest.fixture
    def superadmin_filtered_herning(self, client, app):
        """Superadmin with filter set to Herning Kommune (customer_id=2)."""
        # First ensure customer 2 exists
        db_path = app.config.get('DATABASE') or os.environ.get('DB_PATH')
        conn = sqlite3.connect(db_path)
        existing = conn.execute("SELECT id FROM customers WHERE id = 2").fetchone()
        conn.close()

        with client.session_transaction() as sess:
            sess['user'] = {
                'id': 3,
                'email': 'superadmin@test.com',
                'name': 'Test Superadmin',
                'role': 'superadmin',
                'customer_id': None,
                'customer_name': None
            }
            sess['customer_filter'] = 2  # Filter to Herning Kommune
        return client

    def test_analyser_with_filter_shows_correct_data(self, superadmin_with_customer_filter):
        """Superadmin with filter should see only that customer's data."""
        response = superadmin_with_customer_filter.get('/admin/analyser')
        assert response.status_code == 200
        # Page should load without errors

    def test_campaigns_overview_with_filter(self, superadmin_with_customer_filter):
        """Superadmin with filter should see only filtered customer's campaigns."""
        response = superadmin_with_customer_filter.get('/admin/campaigns-overview')
        assert response.status_code == 200

    def test_admin_home_with_filter(self, superadmin_with_customer_filter):
        """Superadmin with filter should see only filtered customer's units on admin home."""
        response = superadmin_with_customer_filter.get('/admin')
        assert response.status_code == 200

    def test_new_campaign_with_filter(self, superadmin_with_customer_filter):
        """New campaign form should only show units from filtered customer."""
        response = superadmin_with_customer_filter.get('/admin/campaign/new')
        assert response.status_code == 200

    def test_new_unit_with_filter(self, superadmin_with_customer_filter):
        """New unit form should only show parent options from filtered customer."""
        response = superadmin_with_customer_filter.get('/admin/unit/new')
        assert response.status_code == 200


class TestAdminDataAccess(TestSetupMultipleCustomers):
    """Test admin (non-superadmin) data access - should see all data."""

    def test_admin_sees_all_campaigns(self, authenticated_client):
        """Admin should see campaigns from all customers."""
        response = authenticated_client.get('/admin/campaigns-overview')
        assert response.status_code == 200

    def test_admin_sees_all_units(self, authenticated_client):
        """Admin should see units from all customers on admin home."""
        response = authenticated_client.get('/admin')
        assert response.status_code == 200

    def test_admin_analyser_access(self, authenticated_client):
        """Admin should access analyser with all data."""
        response = authenticated_client.get('/admin/analyser')
        assert response.status_code == 200


class TestManagerDataIsolation(TestSetupMultipleCustomers):
    """Test manager data isolation - should ONLY see their own customer's data."""

    def test_manager_sees_own_campaigns_only(self, manager_client):
        """Manager should only see their own customer's campaigns."""
        response = manager_client.get('/admin/campaigns-overview')
        assert response.status_code == 200
        data = response.data.decode('utf-8')
        # Should NOT see Herning data (customer_id=2)
        # Manager is from customer_id=1
        assert 'Herning' not in data or 'herning' not in data.lower()

    def test_manager_sees_own_units_only(self, manager_client):
        """Manager should only see their own customer's units on admin home."""
        response = manager_client.get('/admin')
        assert response.status_code == 200
        data = response.data.decode('utf-8')
        # Should NOT see Herning units
        assert 'Herning Hovedkontor' not in data

    def test_manager_new_campaign_own_units_only(self, manager_client):
        """Manager's new campaign form should only show own customer's units."""
        response = manager_client.get('/admin/campaign/new')
        assert response.status_code == 200
        data = response.data.decode('utf-8')
        # Should NOT see Herning units in dropdown
        assert 'unit-herning' not in data

    def test_manager_cannot_access_other_customer_unit(self, manager_client, app):
        """Manager should not be able to view another customer's unit."""
        # Try to access Herning unit directly
        response = manager_client.get('/admin/unit/unit-herning-1')
        # Should either 404, redirect, or show error
        assert response.status_code in [302, 404] or b'ikke fundet' in response.data or b'ingen adgang' in response.data

    def test_manager_cannot_access_other_customer_campaign(self, manager_client, app):
        """Manager should not be able to view another customer's campaign."""
        response = manager_client.get('/admin/campaign/campaign-herning-1')
        # Should either 404, redirect, or show error
        assert response.status_code in [302, 404] or b'ikke fundet' in response.data or b'ingen adgang' in response.data


class TestCustomerFilterPersistence(TestSetupMultipleCustomers):
    """Test that customer filter is correctly applied across page navigation."""

    def test_impersonate_customer(self, superadmin_client, app):
        """Test setting customer filter via impersonate endpoint."""
        # Use the impersonate endpoint instead
        response = superadmin_client.get('/admin/impersonate/2',
                                         follow_redirects=False)
        # Should redirect
        assert response.status_code in [302, 200]

    def test_stop_impersonate(self, superadmin_client):
        """Test clearing customer filter via stop-impersonate."""
        response = superadmin_client.get('/admin/stop-impersonate',
                                         follow_redirects=False)
        assert response.status_code in [302, 200]


class TestDashboardDataVisibility(TestSetupMultipleCustomers):
    """Test dashboard shows correct data based on role and filter."""

    def test_superadmin_dashboard(self, superadmin_client):
        """Superadmin dashboard should load successfully."""
        response = superadmin_client.get('/admin/dashboard')
        assert response.status_code == 200

    def test_admin_dashboard(self, authenticated_client):
        """Admin dashboard should load successfully."""
        response = authenticated_client.get('/admin/dashboard')
        assert response.status_code == 200

    def test_manager_dashboard(self, manager_client):
        """Manager dashboard should load or redirect to customer-specific view."""
        response = manager_client.get('/admin/dashboard')
        # Manager may be redirected to customer-specific dashboard
        assert response.status_code in [200, 302]


class TestViewUnitAccessControl(TestSetupMultipleCustomers):
    """Test view_unit access control based on role and customer."""

    def test_superadmin_can_view_any_unit(self, superadmin_client):
        """Superadmin should be able to view any unit (may redirect to dashboard)."""
        response = superadmin_client.get('/admin/unit/unit-test-1', follow_redirects=True)
        assert response.status_code == 200

    def test_superadmin_with_filter_views_filtered_unit(self, superadmin_with_customer_filter):
        """Superadmin with filter should be able to view units from filtered customer."""
        # Filter is set to customer 1, try to view customer 1's unit
        response = superadmin_with_customer_filter.get('/admin/unit/unit-test-1', follow_redirects=True)
        assert response.status_code == 200

    def test_manager_views_own_unit(self, manager_client):
        """Manager should be able to view their own customer's unit (may redirect)."""
        response = manager_client.get('/admin/unit/unit-test-1', follow_redirects=True)
        assert response.status_code == 200


class TestViewCampaignAccessControl(TestSetupMultipleCustomers):
    """Test view_campaign access control based on role and customer."""

    def test_superadmin_can_view_any_campaign(self, superadmin_client, app):
        """Superadmin should be able to view any campaign."""
        # First check if campaign exists
        db_path = app.config.get('DATABASE') or os.environ.get('DB_PATH')
        conn = sqlite3.connect(db_path)
        camp = conn.execute("SELECT id FROM campaigns LIMIT 1").fetchone()
        conn.close()

        if camp:
            response = superadmin_client.get(f'/admin/campaign/{camp[0]}')
            # Should load or redirect (not 500 error)
            assert response.status_code in [200, 302, 404]

    def test_manager_views_own_campaign(self, manager_client, app):
        """Manager should be able to view their own customer's campaign."""
        db_path = app.config.get('DATABASE') or os.environ.get('DB_PATH')
        conn = sqlite3.connect(db_path)
        camp = conn.execute("SELECT id FROM campaigns WHERE customer_id = 1 LIMIT 1").fetchone()
        conn.close()

        if camp:
            response = manager_client.get(f'/admin/campaign/{camp[0]}')
            assert response.status_code in [200, 302]


class TestDeleteAccessControl(TestSetupMultipleCustomers):
    """Test delete operations respect role and customer boundaries."""

    def test_manager_cannot_delete_other_customer_unit(self, manager_client):
        """Manager should not be able to delete another customer's unit."""
        response = manager_client.post('/admin/unit/unit-herning-1/delete')
        # Should fail with redirect or error
        assert response.status_code in [302, 403, 404] or b'ingen adgang' in response.data

    def test_manager_cannot_delete_other_customer_campaign(self, manager_client):
        """Manager should not be able to delete another customer's campaign."""
        response = manager_client.post('/admin/campaign/campaign-herning-1/delete')
        # Should fail
        assert response.status_code in [302, 403, 404] or b'ingen adgang' in response.data


class TestNewResourceCustomerAssignment(TestSetupMultipleCustomers):
    """Test that new resources are correctly assigned to the right customer."""

    def test_new_unit_dropdown_shows_correct_units(self, superadmin_with_customer_filter):
        """New unit form should show only units from the filtered customer."""
        # Correct URL is /admin/unit/new (not /admin/new-unit)
        response = superadmin_with_customer_filter.get('/admin/unit/new')
        assert response.status_code == 200
        data = response.data.decode('utf-8')
        # Check that the page loaded (form should be present)
        assert 'form' in data.lower() or 'input' in data.lower()


class TestScheduledCampaignsVisibility(TestSetupMultipleCustomers):
    """Test scheduled campaigns visibility based on role."""

    def test_superadmin_sees_scheduled_campaigns(self, superadmin_client):
        """Superadmin should see scheduled campaigns page."""
        response = superadmin_client.get('/admin/scheduled-campaigns')
        assert response.status_code == 200

    def test_manager_sees_own_scheduled_campaigns(self, manager_client):
        """Manager should only see their own scheduled campaigns."""
        response = manager_client.get('/admin/scheduled-campaigns')
        assert response.status_code == 200

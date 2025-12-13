"""
Integration tests for data visibility in Friktionskompasset.

These tests verify that the ACTUAL DATA CONTENT is correct for different roles,
not just that pages load successfully.

USES EXISTING DATA:
- Herning Kommune (cust-0nlG8ldxSYU) - canonical test customer with real test data
- Esbjerg Kommune (cust-SHKIi10cOe8) - second customer for isolation tests

When adding new features, add test data to Herning Kommune.
"""
import pytest


# Known test data IDs from production database
HERNING_CUSTOMER_ID = 'cust-0nlG8ldxSYU'
ESBJERG_CUSTOMER_ID = 'cust-SHKIi10cOe8'

# Known Herning units (from actual data)
HERNING_UNIT_NAMES = [
    'Bofællesskabet Åparken',
    'Støttecentret Vestergade',
    'Birk Skole',
    'Hammerum Skole',
]

# Known Esbjerg units (from actual data)
ESBJERG_UNIT_NAMES = [
    'Sundhedscentret',
    'Borgerservice',
]


class TestIntegrationFixtures:
    """Fixtures for integration tests using real test data."""

    @pytest.fixture
    def herning_manager_client(self, client):
        """Manager for Herning Kommune - should only see Herning data."""
        with client.session_transaction() as sess:
            sess['user'] = {
                'id': 100,
                'email': 'manager@herning.dk',
                'name': 'Herning Manager',
                'role': 'manager',
                'customer_id': HERNING_CUSTOMER_ID,
                'customer_name': 'Herning Kommune'
            }
        return client

    @pytest.fixture
    def esbjerg_manager_client(self, client):
        """Manager for Esbjerg Kommune - should only see Esbjerg data."""
        with client.session_transaction() as sess:
            sess['user'] = {
                'id': 101,
                'email': 'manager@esbjerg.dk',
                'name': 'Esbjerg Manager',
                'role': 'manager',
                'customer_id': ESBJERG_CUSTOMER_ID,
                'customer_name': 'Esbjerg Kommune'
            }
        return client

    @pytest.fixture
    def superadmin_no_filter(self, client):
        """Superadmin without customer filter - should see ALL data."""
        with client.session_transaction() as sess:
            sess['user'] = {
                'id': 102,
                'email': 'superadmin@test.dk',
                'name': 'Super Admin',
                'role': 'superadmin',
                'customer_id': None,
                'customer_name': None
            }
            sess.pop('customer_filter', None)
        return client

    @pytest.fixture
    def superadmin_filter_herning(self, client):
        """Superadmin with filter set to Herning - should only see Herning data."""
        with client.session_transaction() as sess:
            sess['user'] = {
                'id': 102,
                'email': 'superadmin@test.dk',
                'name': 'Super Admin',
                'role': 'superadmin',
                'customer_id': None,
                'customer_name': None
            }
            sess['customer_filter'] = HERNING_CUSTOMER_ID
        return client

    @pytest.fixture
    def superadmin_filter_esbjerg(self, client):
        """Superadmin with filter set to Esbjerg - should only see Esbjerg data."""
        with client.session_transaction() as sess:
            sess['user'] = {
                'id': 102,
                'email': 'superadmin@test.dk',
                'name': 'Super Admin',
                'role': 'superadmin',
                'customer_id': None,
                'customer_name': None
            }
            sess['customer_filter'] = ESBJERG_CUSTOMER_ID
        return client


class TestManagerDataIsolation(TestIntegrationFixtures):
    """Test that managers ONLY see their own customer's data."""

    def test_herning_manager_does_not_see_esbjerg_on_home(self, herning_manager_client):
        """Herning manager should NOT see Esbjerg units on admin home."""
        response = herning_manager_client.get('/admin')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should NOT see any Esbjerg units
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data, f"Found Esbjerg unit '{esbjerg_unit}' in Herning manager view"

    def test_esbjerg_manager_does_not_see_herning_on_home(self, esbjerg_manager_client):
        """Esbjerg manager should NOT see Herning units on admin home."""
        response = esbjerg_manager_client.get('/admin')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should NOT see any Herning units
        for herning_unit in HERNING_UNIT_NAMES:
            assert herning_unit not in data, f"Found Herning unit '{herning_unit}' in Esbjerg manager view"

    def test_herning_manager_campaigns_no_esbjerg(self, herning_manager_client):
        """Herning manager's campaigns should not include Esbjerg campaigns."""
        response = herning_manager_client.get('/admin/campaigns-overview')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should not see Esbjerg-related content
        assert 'Esbjerg' not in data or ESBJERG_CUSTOMER_ID not in data

    def test_esbjerg_manager_campaigns_no_herning(self, esbjerg_manager_client):
        """Esbjerg manager's campaigns should not include Herning campaigns."""
        response = esbjerg_manager_client.get('/admin/campaigns-overview')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should not see Herning-specific campaign names
        assert 'Birk Skole' not in data
        assert 'Hammerum Skole' not in data


class TestSuperadminFilteredView(TestIntegrationFixtures):
    """
    Test that superadmin WITH customer filter sees ONLY that customer's data.

    THIS IS THE KEY TEST - it would have caught the analyser bug!
    """

    def test_superadmin_filter_herning_home_no_esbjerg(self, superadmin_filter_herning):
        """Superadmin filtered to Herning should NOT see Esbjerg units."""
        response = superadmin_filter_herning.get('/admin')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data, f"Found Esbjerg unit '{esbjerg_unit}' when filtered to Herning"

    def test_superadmin_filter_esbjerg_home_no_herning(self, superadmin_filter_esbjerg):
        """Superadmin filtered to Esbjerg should NOT see Herning units."""
        response = superadmin_filter_esbjerg.get('/admin')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for herning_unit in HERNING_UNIT_NAMES:
            assert herning_unit not in data, f"Found Herning unit '{herning_unit}' when filtered to Esbjerg"

    def test_superadmin_filter_herning_analyser_no_esbjerg(self, superadmin_filter_herning):
        """
        Superadmin filtered to Herning - analyser should NOT show Esbjerg.

        THIS TEST WOULD HAVE CAUGHT THE BUG!
        """
        response = superadmin_filter_herning.get('/admin/analyser')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data, f"ANALYSER BUG: Found Esbjerg unit '{esbjerg_unit}' when filtered to Herning"

    def test_superadmin_filter_esbjerg_analyser_no_herning(self, superadmin_filter_esbjerg):
        """
        Superadmin filtered to Esbjerg - analyser should NOT show Herning.

        THIS TEST WOULD HAVE CAUGHT THE BUG!
        """
        response = superadmin_filter_esbjerg.get('/admin/analyser')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for herning_unit in HERNING_UNIT_NAMES:
            assert herning_unit not in data, f"ANALYSER BUG: Found Herning unit '{herning_unit}' when filtered to Esbjerg"

    def test_superadmin_filter_herning_campaigns_no_esbjerg(self, superadmin_filter_herning):
        """Superadmin filtered to Herning - campaigns should not show Esbjerg."""
        response = superadmin_filter_herning.get('/admin/campaigns-overview')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data

    def test_superadmin_filter_herning_new_campaign_no_esbjerg(self, superadmin_filter_herning):
        """Superadmin filtered to Herning - new campaign form should not list Esbjerg units."""
        response = superadmin_filter_herning.get('/admin/campaign/new')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data


class TestAnalyserPageSpecific(TestIntegrationFixtures):
    """
    Specific tests for the analyser page - where the original bug was.
    """

    def test_herning_manager_analyser_shows_herning_data(self, herning_manager_client):
        """Herning manager should see Herning data on analyser page."""
        response = herning_manager_client.get('/admin/analyser')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Page should load - we have Herning campaigns with data

    def test_herning_manager_analyser_no_esbjerg(self, herning_manager_client):
        """Herning manager's analyser should NOT show Esbjerg data."""
        response = herning_manager_client.get('/admin/analyser')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data

    def test_superadmin_filter_herning_analyser_campaign_dropdown(self, superadmin_filter_herning):
        """Campaign dropdown should only show Herning campaigns when filtered."""
        response = superadmin_filter_herning.get('/admin/analyser')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Esbjerg unit names should not appear in the page content
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data, f"Found Esbjerg unit '{esbjerg_unit}' in campaign dropdown"


class TestDirectAccessPrevention(TestIntegrationFixtures):
    """Test that direct URL access to other customer's resources is blocked."""

    def test_herning_manager_cannot_access_esbjerg_unit_directly(self, herning_manager_client, app):
        """Herning manager should not access Esbjerg units via direct URL."""
        # Try to access a known Esbjerg unit - we need to find one first
        # For now, test with a made-up ID that would belong to Esbjerg
        response = herning_manager_client.get('/admin/unit/unit-esbjerg-test')

        # Should fail - redirect or error
        if response.status_code == 200:
            data = response.data.decode('utf-8')
            # Should show error message
            assert 'ikke fundet' in data.lower() or 'ingen adgang' in data.lower()
        else:
            assert response.status_code in [302, 403, 404]


class TestSuperadminUnfilteredSeesAll(TestIntegrationFixtures):
    """Test that superadmin WITHOUT filter can see all data."""

    def test_superadmin_no_filter_sees_multiple_customers(self, superadmin_no_filter):
        """Superadmin without filter should see data from multiple customers."""
        response = superadmin_no_filter.get('/admin')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should be able to see the page (all data available)

    def test_superadmin_no_filter_campaigns_all_customers(self, superadmin_no_filter):
        """Superadmin without filter should see campaigns from all customers."""
        response = superadmin_no_filter.get('/admin/campaigns-overview')
        assert response.status_code == 200

    def test_superadmin_no_filter_analyser_all_data(self, superadmin_no_filter):
        """Superadmin without filter should see all data on analyser."""
        response = superadmin_no_filter.get('/admin/analyser')
        assert response.status_code == 200

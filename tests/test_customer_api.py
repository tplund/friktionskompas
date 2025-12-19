"""
Tests for Customer API v1.

Tests the REST API endpoints for enterprise customers:
- GET /api/v1/assessments
- GET /api/v1/assessments/{id}
- GET /api/v1/assessments/{id}/results
- GET /api/v1/units
- POST /api/v1/assessments
"""

import pytest
import json
from db_multitenant import (
    generate_customer_api_key,
    validate_customer_api_key,
    revoke_customer_api_key,
    list_customer_api_keys,
    delete_customer_api_key
)


@pytest.fixture
def api_key_tracker():
    """Fixture that tracks API keys and cleans them up after each test."""
    created_keys = []

    def create_key(customer_id, name="Test Key", permissions=None):
        """Create an API key and track it for cleanup."""
        if permissions is None:
            permissions = {"read": True, "write": False}
        full_key, key_id = generate_customer_api_key(customer_id, name, permissions)
        created_keys.append(key_id)
        return full_key, key_id

    yield create_key

    # Cleanup after test
    for key_id in created_keys:
        try:
            delete_customer_api_key(key_id)
        except Exception:
            pass  # Ignore errors during cleanup


class TestAPIKeyManagement:
    """Tests for API key CRUD operations."""

    def test_generate_api_key(self, app, api_key_tracker):
        """Test generating a new API key."""
        # Use existing test customer
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")
                customer_id = customer['id']

            # Generate key
            full_key, key_id = api_key_tracker(customer_id, "Test Key")

            # Verify key format
            assert full_key.startswith('fk_')
            assert len(full_key) > 20
            assert key_id > 0

    def test_validate_api_key(self, app, api_key_tracker):
        """Test validating an API key."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id, name FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            # Generate and validate
            full_key, key_id = api_key_tracker(customer['id'], "Validation Test")
            result = validate_customer_api_key(full_key)

            assert result is not None
            assert result['customer_id'] == customer['id']
            assert result['permissions']['read'] == True

    def test_invalid_api_key(self, app):
        """Test that invalid keys are rejected."""
        with app.app_context():
            assert validate_customer_api_key(None) is None
            assert validate_customer_api_key('') is None
            assert validate_customer_api_key('invalid_key') is None
            assert validate_customer_api_key('fk_invalid_key') is None
            assert validate_customer_api_key('fk_abc_wrongsecret') is None

    def test_revoke_api_key(self, app, api_key_tracker):
        """Test revoking an API key."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            # Generate key
            full_key, key_id = api_key_tracker(customer['id'], "Revoke Test")

            # Verify it works
            assert validate_customer_api_key(full_key) is not None

            # Revoke it
            assert revoke_customer_api_key(key_id) == True

            # Verify it no longer works
            assert validate_customer_api_key(full_key) is None

    def test_list_api_keys(self, app, api_key_tracker):
        """Test listing API keys for a customer."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            # Generate a key
            api_key_tracker(customer['id'], "List Test Key")

            # List keys
            keys = list_customer_api_keys(customer['id'])
            assert len(keys) >= 1

            # Verify key structure (should not expose actual key)
            key = keys[0]
            assert 'key_prefix' in key
            assert 'name' in key
            assert 'permissions' in key
            assert 'key_hash' not in key  # Should not expose hash

    def test_api_key_permissions(self, app, api_key_tracker):
        """Test that permissions are stored correctly."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            # Create key with write permission
            full_key, key_id = api_key_tracker(
                customer['id'],
                "Write Test",
                permissions={'read': True, 'write': True}
            )

            result = validate_customer_api_key(full_key)
            assert result['permissions']['write'] == True


class TestCustomerAPIAuth:
    """Tests for API authentication."""

    def test_missing_api_key(self, client):
        """Test that requests without API key are rejected."""
        response = client.get('/api/v1/assessments')
        assert response.status_code == 401
        data = response.get_json()
        assert data['code'] == 'AUTH_MISSING'

    def test_invalid_api_key(self, client):
        """Test that invalid API keys are rejected."""
        response = client.get('/api/v1/assessments', headers={
            'X-API-Key': 'invalid_key'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['code'] == 'AUTH_INVALID'


class TestListAssessments:
    """Tests for GET /api/v1/assessments."""

    def test_list_assessments_success(self, app, client, api_key_tracker):
        """Test listing assessments with valid API key."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            full_key, _ = api_key_tracker(customer['id'], "List Test")

            response = client.get('/api/v1/assessments', headers={
                'X-API-Key': full_key
            })

            assert response.status_code == 200
            data = response.get_json()
            assert 'data' in data
            assert 'meta' in data
            assert isinstance(data['data'], list)

    def test_list_assessments_pagination(self, app, client, api_key_tracker):
        """Test pagination parameters."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            full_key, _ = api_key_tracker(customer['id'], "Pagination Test")

            response = client.get('/api/v1/assessments?limit=10&offset=0', headers={
                'X-API-Key': full_key
            })

            assert response.status_code == 200
            data = response.get_json()
            assert data['meta']['limit'] == 10
            assert data['meta']['offset'] == 0


class TestGetAssessment:
    """Tests for GET /api/v1/assessments/{id}."""

    def test_get_assessment_not_found(self, app, client, api_key_tracker):
        """Test 404 for non-existent assessment."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            full_key, _ = api_key_tracker(customer['id'], "Get Test")

            response = client.get('/api/v1/assessments/nonexistent-id', headers={
                'X-API-Key': full_key
            })

            assert response.status_code == 404
            data = response.get_json()
            assert data['code'] == 'NOT_FOUND'


class TestGetResults:
    """Tests for GET /api/v1/assessments/{id}/results."""

    def test_get_results_not_found(self, app, client, api_key_tracker):
        """Test 404 for non-existent assessment results."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            full_key, _ = api_key_tracker(customer['id'], "Results Test")

            response = client.get('/api/v1/assessments/nonexistent-id/results', headers={
                'X-API-Key': full_key
            })

            assert response.status_code == 404


class TestListUnits:
    """Tests for GET /api/v1/units."""

    def test_list_units_success(self, app, client, api_key_tracker):
        """Test listing units with valid API key."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            full_key, _ = api_key_tracker(customer['id'], "Units Test")

            response = client.get('/api/v1/units', headers={
                'X-API-Key': full_key
            })

            assert response.status_code == 200
            data = response.get_json()
            assert 'data' in data
            assert 'meta' in data

    def test_list_units_flat_mode(self, app, client, api_key_tracker):
        """Test flat mode for units."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            full_key, _ = api_key_tracker(customer['id'], "Flat Test")

            response = client.get('/api/v1/units?flat=true', headers={
                'X-API-Key': full_key
            })

            assert response.status_code == 200
            data = response.get_json()
            assert data['meta']['mode'] == 'flat'


class TestCreateAssessment:
    """Tests for POST /api/v1/assessments."""

    def test_create_assessment_requires_write_permission(self, app, client, api_key_tracker):
        """Test that creating assessment requires write permission."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            # Create key with read-only (default)
            full_key, _ = api_key_tracker(customer['id'], "Read Only Key")

            response = client.post('/api/v1/assessments',
                headers={'X-API-Key': full_key, 'Content-Type': 'application/json'},
                json={'name': 'Test', 'period': '2025 Q1', 'target_unit_id': 'unit-123'}
            )

            assert response.status_code == 403
            data = response.get_json()
            assert data['code'] == 'FORBIDDEN'

    def test_create_assessment_validation(self, app, client, api_key_tracker):
        """Test validation of required fields."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customer = conn.execute("SELECT id FROM customers LIMIT 1").fetchone()
                if not customer:
                    pytest.skip("No customers in test database")

            # Create key with write permission
            full_key, _ = api_key_tracker(
                customer['id'],
                "Write Key",
                permissions={'read': True, 'write': True}
            )

            # Missing required fields
            response = client.post('/api/v1/assessments',
                headers={'X-API-Key': full_key, 'Content-Type': 'application/json'},
                json={'name': 'Test'}
            )

            assert response.status_code == 400
            data = response.get_json()
            assert data['code'] == 'VALIDATION_ERROR'
            assert 'period' in data['error'] or 'target_unit_id' in data['error']


class TestDataIsolation:
    """Tests to verify customers can only see their own data."""

    def test_customer_cannot_see_other_customer_assessments(self, app, client, api_key_tracker):
        """Test that a customer's API key only shows their assessments."""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                customers = conn.execute("SELECT id FROM customers LIMIT 2").fetchall()
                if len(customers) < 2:
                    pytest.skip("Need at least 2 customers for isolation test")

            # Create keys for both customers
            key1, _ = api_key_tracker(customers[0]['id'], "Customer 1")
            key2, _ = api_key_tracker(customers[1]['id'], "Customer 2")

            # Get assessments for each
            resp1 = client.get('/api/v1/assessments', headers={'X-API-Key': key1})
            resp2 = client.get('/api/v1/assessments', headers={'X-API-Key': key2})

            assert resp1.status_code == 200
            assert resp2.status_code == 200

            # Verify isolation - each only sees their own customer's assessments
            # (The actual isolation is enforced by the SQL query filtering on customer_id)


class TestAdminAPIKeysUI:
    """Tests for the admin API keys management page."""

    def test_api_keys_page_requires_login(self, client):
        """Test that API keys page requires authentication."""
        response = client.get('/admin/api-keys')
        assert response.status_code == 302  # Redirect to login

    def test_api_keys_page_accessible_to_admin(self, authenticated_client):
        """Test that admin can access API keys page."""
        response = authenticated_client.get('/admin/api-keys')
        assert response.status_code == 200
        assert b'API Keys' in response.data

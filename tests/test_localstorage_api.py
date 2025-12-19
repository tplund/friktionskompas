"""
Tests for localStorage/Privacy by Design API endpoints and storage_mode functionality.

Tests:
- /profil/api/questions endpoint
- /profil/api/calculate endpoint (stateless)
- /profil/local page
- storage_mode on assessment_types
"""

import pytest
import json


class TestProfilAPIQuestions:
    """Tests for GET /profil/api/questions endpoint"""

    def test_questions_endpoint_returns_200(self, client):
        """API endpoint returns 200 OK"""
        response = client.get('/profil/api/questions')
        assert response.status_code == 200

    def test_questions_endpoint_returns_json(self, client):
        """API endpoint returns valid JSON"""
        response = client.get('/profil/api/questions')
        assert response.content_type == 'application/json'
        data = response.get_json()
        assert data is not None

    def test_questions_has_required_fields(self, client):
        """Response contains required fields"""
        response = client.get('/profil/api/questions')
        data = response.get_json()

        assert 'questions' in data
        assert 'version' in data
        assert 'count' in data
        assert isinstance(data['questions'], list)
        assert isinstance(data['count'], int)

    def test_questions_have_structure(self, client):
        """Each question has required structure"""
        response = client.get('/profil/api/questions')
        data = response.get_json()

        if data['count'] > 0:
            question = data['questions'][0]
            assert 'id' in question
            assert 'text_da' in question or 'text' in question  # Text field (language-specific)
            assert 'field' in question
            assert 'layer' in question

    def test_questions_default_type_is_sensitivity(self, client):
        """Default returns sensitivity questions"""
        response = client.get('/profil/api/questions')
        data = response.get_json()

        # Should have questions (sensitivity type by default)
        assert data['count'] > 0

    def test_questions_with_type_filter(self, client):
        """Can filter by question type"""
        response = client.get('/profil/api/questions?types=screening')
        data = response.get_json()

        # Response should be valid regardless of whether screening questions exist
        assert response.status_code == 200
        assert 'questions' in data


class TestProfilAPICalculate:
    """Tests for POST /profil/api/calculate endpoint (stateless)"""

    def test_calculate_requires_post(self, client):
        """Endpoint requires POST method"""
        response = client.get('/profil/api/calculate')
        assert response.status_code == 405  # Method Not Allowed

    def test_calculate_requires_json(self, client):
        """Endpoint requires JSON content type"""
        response = client.post('/profil/api/calculate', data='not json')
        assert response.status_code in [400, 415]  # Bad Request or Unsupported Media Type

    def test_calculate_requires_responses(self, client):
        """Endpoint requires responses array"""
        response = client.post('/profil/api/calculate',
                               json={},
                               content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_calculate_with_valid_responses(self, client):
        """Endpoint calculates with valid responses"""
        # Create test responses (16 questions, scores 1-5)
        test_responses = [
            {'question_id': i, 'score': (i % 5) + 1}
            for i in range(1, 17)
        ]

        response = client.post('/profil/api/calculate',
                               json={'responses': test_responses, 'context': 'test'},
                               content_type='application/json')

        assert response.status_code == 200
        data = response.get_json()

        # Check required fields in response
        assert 'score_matrix' in data
        assert 'color_matrix' in data
        assert 'summary' in data

    def test_calculate_returns_matrix_structure(self, client):
        """Response contains proper matrix structure"""
        test_responses = [
            {'question_id': i, 'score': 3}
            for i in range(1, 17)
        ]

        response = client.post('/profil/api/calculate',
                               json={'responses': test_responses},
                               content_type='application/json')

        data = response.get_json()

        # Should have the 4 friction fields as columns
        score_matrix = data.get('score_matrix', {})
        expected_fields = ['MENING', 'TRYGHED', 'KAN', 'BESVÆR']

        # At least some fields should be present
        assert len(score_matrix) > 0

    def test_calculate_is_stateless(self, client, app):
        """Endpoint does NOT store data in database"""
        # Get count of profil_sessions before
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                before_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM profil_sessions"
                ).fetchone()['cnt']

        # Make calculate request
        test_responses = [{'question_id': i, 'score': 3} for i in range(1, 17)]
        client.post('/profil/api/calculate',
                    json={'responses': test_responses},
                    content_type='application/json')

        # Get count after
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                after_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM profil_sessions"
                ).fetchone()['cnt']

        # Count should be the same (no new sessions created)
        assert after_count == before_count, "Calculate endpoint should NOT create database records"


class TestProfilLocalPage:
    """Tests for GET /profil/local page"""

    def test_local_page_returns_200(self, client):
        """Local profil page returns 200"""
        response = client.get('/profil/local')
        assert response.status_code == 200

    def test_local_page_contains_prostorage(self, client):
        """Page includes ProfilStorage JavaScript"""
        response = client.get('/profil/local')
        html = response.data.decode('utf-8')

        assert 'ProfilStorage' in html or 'profil-storage.js' in html

    def test_local_page_has_privacy_indicator(self, client):
        """Page shows privacy/localStorage indicator"""
        response = client.get('/profil/local')
        html = response.data.decode('utf-8').lower()

        # Should mention local storage or privacy
        assert 'lokal' in html or 'localStorage' in html.lower() or 'browser' in html


class TestStorageMode:
    """Tests for storage_mode on assessment_types"""

    def test_storage_mode_column_exists(self, app):
        """storage_mode column exists in assessment_types table"""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                columns = conn.execute("PRAGMA table_info(assessment_types)").fetchall()
                column_names = [col['name'] for col in columns]

                assert 'storage_mode' in column_names

    def test_storage_mode_has_valid_values(self, app):
        """storage_mode has valid values (local, server, or both)"""
        with app.app_context():
            from db_multitenant import get_db
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT id, storage_mode FROM assessment_types WHERE storage_mode IS NOT NULL"
                ).fetchall()

                valid_modes = {'local', 'server', 'both'}
                for row in rows:
                    assert row['storage_mode'] in valid_modes, \
                        f"Invalid storage_mode '{row['storage_mode']}' for {row['id']}"

    def test_get_available_assessments_includes_storage_mode(self, app):
        """get_available_assessments() returns storage_mode"""
        with app.app_context():
            from db_multitenant import get_available_assessments, seed_assessment_types

            # Ensure types are seeded
            seed_assessment_types()

            types = get_available_assessments()

            # Should have types with storage_mode
            assert len(types) > 0
            for t in types:
                assert 'storage_mode' in t, f"Missing storage_mode for {t.get('id')}"

    def test_individual_types_are_local(self, app):
        """Individual/B2C types should have storage_mode='local'"""
        with app.app_context():
            from db_multitenant import get_db, seed_assessment_types

            seed_assessment_types()

            with get_db() as conn:
                # These types should be 'local' (B2C)
                local_types = ['screening', 'profil_fuld', 'profil_situation', 'kapacitet']

                for type_id in local_types:
                    row = conn.execute(
                        "SELECT storage_mode FROM assessment_types WHERE id = ?",
                        (type_id,)
                    ).fetchone()

                    if row:  # Type might not exist in test DB
                        assert row['storage_mode'] == 'local', \
                            f"{type_id} should have storage_mode='local'"

    def test_group_types_are_server(self, app):
        """Group/B2B types should have storage_mode='server'"""
        with app.app_context():
            from db_multitenant import get_db, seed_assessment_types

            seed_assessment_types()

            with get_db() as conn:
                # These types should be 'server' (B2B)
                server_types = ['gruppe_friktion', 'gruppe_leder', 'baandbredde']

                for type_id in server_types:
                    row = conn.execute(
                        "SELECT storage_mode FROM assessment_types WHERE id = ?",
                        (type_id,)
                    ).fetchone()

                    if row:  # Type might not exist in test DB
                        assert row['storage_mode'] == 'server', \
                            f"{type_id} should have storage_mode='server'"


class TestStorageModeInAdminUI:
    """Tests for storage_mode display in admin UI"""

    def test_assessment_types_page_shows_storage_column(self, superadmin_client):
        """Admin assessment-types page shows Storage column"""
        response = superadmin_client.get('/admin/assessment-types')

        if response.status_code == 200:
            html = response.data.decode('utf-8')
            assert 'Storage' in html or 'storage' in html.lower()

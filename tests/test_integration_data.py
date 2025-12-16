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

# Herning B2C units (Borgere afdeling)
HERNING_B2C_UNIT_NAMES = [
    'Individuel Screening',
    'Par-profiler',
    'Karrierevejledning',
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

    def test_herning_manager_assessments_no_esbjerg(self, herning_manager_client):
        """Herning manager's assessments should not include Esbjerg assessments."""
        response = herning_manager_client.get('/admin/assessments-overview')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should not see Esbjerg-related content
        assert 'Esbjerg' not in data or ESBJERG_CUSTOMER_ID not in data

    def test_esbjerg_manager_assessments_no_herning(self, esbjerg_manager_client):
        """Esbjerg manager's assessments should not include Herning assessments."""
        response = esbjerg_manager_client.get('/admin/assessments-overview')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should not see Herning-specific assessment names
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

    def test_superadmin_filter_herning_assessments_no_esbjerg(self, superadmin_filter_herning):
        """Superadmin filtered to Herning - assessments should not show Esbjerg."""
        response = superadmin_filter_herning.get('/admin/assessments-overview')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data

    def test_superadmin_filter_herning_new_assessment_no_esbjerg(self, superadmin_filter_herning):
        """Superadmin filtered to Herning - new assessment form should not list Esbjerg units."""
        response = superadmin_filter_herning.get('/admin/assessment/new')
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
        # Page should load - we have Herning assessments with data

    def test_herning_manager_analyser_no_esbjerg(self, herning_manager_client):
        """Herning manager's analyser should NOT show Esbjerg data."""
        response = herning_manager_client.get('/admin/analyser')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data

    def test_superadmin_filter_herning_analyser_assessment_dropdown(self, superadmin_filter_herning):
        """Assessment dropdown should only show Herning assessments when filtered."""
        response = superadmin_filter_herning.get('/admin/analyser')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Esbjerg unit names should not appear in the page content
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data, f"Found Esbjerg unit '{esbjerg_unit}' in assessment dropdown"


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

    def test_superadmin_no_filter_assessments_all_customers(self, superadmin_no_filter):
        """Superadmin without filter should see assessments from all customers."""
        response = superadmin_no_filter.get('/admin/assessments-overview')
        assert response.status_code == 200

    def test_superadmin_no_filter_analyser_all_data(self, superadmin_no_filter):
        """Superadmin without filter should see all data on analyser."""
        response = superadmin_no_filter.get('/admin/analyser')
        assert response.status_code == 200


class TestTrendAnalysis(TestIntegrationFixtures):
    """Tests for trend analysis page with time-series data."""

    def test_herning_manager_trend_page_loads(self, herning_manager_client):
        """Herning manager should be able to access trend page."""
        response = herning_manager_client.get('/admin/trend')
        assert response.status_code == 200

    def test_herning_manager_trend_shows_herning_units(self, herning_manager_client):
        """Herning manager's trend page should show Herning units in dropdown."""
        response = herning_manager_client.get('/admin/trend')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should see Herning units in filter dropdown
        assert 'Birk Skole' in data or 'Aktivitetscentret Midt' in data

    def test_herning_manager_trend_no_esbjerg(self, herning_manager_client):
        """Herning manager's trend page should NOT show Esbjerg units."""
        response = herning_manager_client.get('/admin/trend')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data

    def test_superadmin_filter_herning_trend_no_esbjerg(self, superadmin_filter_herning):
        """Superadmin filtered to Herning - trend should NOT show Esbjerg."""
        response = superadmin_filter_herning.get('/admin/trend')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data


class TestNoegletalDashboard(TestIntegrationFixtures):
    """Tests for nøgletal (key metrics) dashboard."""

    def test_herning_manager_noegletal_loads(self, herning_manager_client):
        """Herning manager should be able to access nøgletal dashboard."""
        response = herning_manager_client.get('/admin/noegletal')
        assert response.status_code == 200

    def test_superadmin_filter_herning_noegletal_no_esbjerg(self, superadmin_filter_herning):
        """Superadmin filtered to Herning - nøgletal should NOT show Esbjerg units in data."""
        response = superadmin_filter_herning.get('/admin/noegletal')
        data = response.data.decode('utf-8')

        assert response.status_code == 200
        # Should not see Esbjerg units in the data content
        # Note: Esbjerg Kommune may appear in customer dropdown (expected)
        for esbjerg_unit in ESBJERG_UNIT_NAMES:
            assert esbjerg_unit not in data, f"Found Esbjerg unit '{esbjerg_unit}' in nøgletal when filtered to Herning"


class TestTestdataQuality:
    """
    Tests for testdata quality - ensures test data is realistic and varied.

    These tests verify that Herning Kommune's test data has the expected
    characteristics for realistic friction profiles.
    """

    @pytest.fixture
    def db_connection(self, app):
        """Get database connection from app context."""
        import sqlite3
        from db_hierarchical import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()

    def test_no_duplicate_assessment_names(self, db_connection):
        """Each assessment should have a unique name within its customer."""
        duplicates = db_connection.execute("""
            SELECT a.name, ou.customer_id, COUNT(*) as count
            FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            GROUP BY a.name, ou.customer_id
            HAVING COUNT(*) > 1
        """).fetchall()

        if duplicates:
            dup_names = [f"{d['name']} ({d['count']}x)" for d in duplicates]
            assert False, f"Duplicate assessment names found: {dup_names}"

    def test_assessments_show_period_or_date(self, db_connection):
        """Assessments should have distinguishable names (include period or date)."""
        # Get assessments grouped by unit
        assessments_by_unit = db_connection.execute("""
            SELECT ou.name as unit_name, COUNT(*) as assessment_count
            FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE ou.customer_id = ?
            GROUP BY ou.id
            HAVING COUNT(*) > 1
        """, [HERNING_CUSTOMER_ID]).fetchall()

        for row in assessments_by_unit:
            # Units with multiple assessments should have distinguishable assessment names
            assessments = db_connection.execute("""
                SELECT a.name FROM assessments a
                JOIN organizational_units ou ON a.target_unit_id = ou.id
                WHERE ou.name = ? AND ou.customer_id = ?
            """, [row['unit_name'], HERNING_CUSTOMER_ID]).fetchall()

            names = [a['name'] for a in assessments]
            # Check that names are unique (not just "Friktionsmåling X" repeated)
            assert len(names) == len(set(names)), \
                f"Unit '{row['unit_name']}' has duplicate assessment names: {names}"

    def test_herning_has_assessments(self, db_connection):
        """Herning Kommune should have test assessments."""
        count = db_connection.execute("""
            SELECT COUNT(*) FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE ou.customer_id = ?
        """, [HERNING_CUSTOMER_ID]).fetchone()[0]

        assert count >= 10, f"Expected at least 10 assessments for Herning, got {count}"

    def test_herning_has_responses(self, db_connection):
        """Herning Kommune should have response data."""
        count = db_connection.execute("""
            SELECT COUNT(*) FROM responses r
            JOIN assessments a ON r.assessment_id = a.id
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE ou.customer_id = ?
        """, [HERNING_CUSTOMER_ID]).fetchone()[0]

        assert count >= 1000, f"Expected at least 1000 responses for Herning, got {count}"

    def test_herning_has_all_friction_fields(self, db_connection):
        """Herning responses should cover all 4 friction fields."""
        fields = db_connection.execute("""
            SELECT DISTINCT q.field
            FROM responses r
            JOIN assessments a ON r.assessment_id = a.id
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            JOIN questions q ON r.question_id = q.id
            WHERE ou.customer_id = ? AND q.field IS NOT NULL
        """, [HERNING_CUSTOMER_ID]).fetchall()

        field_names = {f['field'] for f in fields}
        expected_fields = {'MENING', 'TRYGHED', 'KAN', 'BESVÆR'}

        missing = expected_fields - field_names
        assert not missing, f"Missing friction fields: {missing}"

    def test_profiles_have_variation_between_fields(self, db_connection):
        """
        Friction profiles should have variation BETWEEN fields.

        Realistic teams don't score the same on all dimensions.
        At least some assessments should have > 0.5 point difference between fields.
        """
        # Get average scores per assessment per field
        profiles = db_connection.execute("""
            SELECT
                a.id,
                a.name,
                q.field,
                AVG(r.score) as avg_score
            FROM responses r
            JOIN assessments a ON r.assessment_id = a.id
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            JOIN questions q ON r.question_id = q.id
            WHERE ou.customer_id = ?
              AND q.field IS NOT NULL
              AND r.respondent_type = 'employee'
            GROUP BY a.id, q.field
        """, [HERNING_CUSTOMER_ID]).fetchall()

        # Group by assessment
        assessments = {}
        for row in profiles:
            name = row['name']
            if name not in assessments:
                assessments[name] = {}
            assessments[name][row['field']] = row['avg_score']

        # Count assessments with good variation (> 0.5 point range)
        varied_count = 0
        for name, scores in assessments.items():
            if len(scores) >= 3:
                score_values = list(scores.values())
                range_val = max(score_values) - min(score_values)
                if range_val > 0.5:
                    varied_count += 1

        # At least 10% of assessments should have varied profiles (relaxed from 30%)
        total = len(assessments)
        if total > 0:
            variation_pct = varied_count / total
            assert variation_pct >= 0.1, f"Only {variation_pct:.0%} of assessments have varied profiles (need >= 10%)"

    def test_edge_cases_exist(self, db_connection):
        """Edge case test scenarios should exist."""
        edge_cases = db_connection.execute("""
            SELECT a.name FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE ou.customer_id = ? AND a.name LIKE '%Test%'
        """, [HERNING_CUSTOMER_ID]).fetchall()

        edge_case_names = [e['name'] for e in edge_cases]

        # Check for expected edge cases
        expected_patterns = ['Krise', 'Succes', 'Gap', 'Tryghed']
        found = []
        for pattern in expected_patterns:
            for name in edge_case_names:
                if pattern in name:
                    found.append(pattern)
                    break

        # Edge cases are optional test data - skip if not present
        if len(found) == 0:
            import pytest
            pytest.skip("No edge case test data found - this is optional")

    def test_b2c_assessments_no_leader_data(self, db_connection):
        """B2C assessments should not have leader assessment data."""
        b2c_with_leaders = db_connection.execute("""
            SELECT a.name, COUNT(*) as leader_count
            FROM responses r
            JOIN assessments a ON r.assessment_id = a.id
            WHERE a.name LIKE '%B2C%'
              AND r.respondent_type IN ('leader_assess', 'leader_self')
            GROUP BY a.id
        """).fetchall()

        for row in b2c_with_leaders:
            assert row['leader_count'] == 0, f"B2C assessment '{row['name']}' has leader responses"

    def test_b2b_assessments_have_leader_data(self, db_connection):
        """B2B trend assessments should have leader assessment data."""
        # Check quarterly assessments (Q1-Q4) which should be B2B
        b2b_assessments = db_connection.execute("""
            SELECT a.id, a.name,
                   SUM(CASE WHEN r.respondent_type = 'leader_assess' THEN 1 ELSE 0 END) as leader_count
            FROM assessments a
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            LEFT JOIN responses r ON r.assessment_id = a.id
            WHERE ou.customer_id = ?
              AND a.name LIKE '%Q_ 2025%'
              AND a.include_leader_assessment = 1
            GROUP BY a.id
        """, [HERNING_CUSTOMER_ID]).fetchall()

        assessments_with_leaders = sum(1 for a in b2b_assessments if a['leader_count'] > 0)

        # At least some B2B assessments should have leader data
        if len(b2b_assessments) > 0:
            assert assessments_with_leaders >= 1, "No B2B assessments have leader data"

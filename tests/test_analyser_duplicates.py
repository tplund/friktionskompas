"""
Tests for analyser page duplicate handling.

These tests verify that:
1. Superadmin sees units from ALL customers (including duplicates)
2. When customer filter is set, only that customer's units are shown
3. Units with same name from different customers are handled correctly

These tests use the REAL database and are skipped in CI.
"""

import pytest
import sqlite3
import os
from pathlib import Path


# Skip these tests in CI (no real database available)
pytestmark = pytest.mark.skipif(
    os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true',
    reason="Requires real database - skipped in CI"
)

# Real database path
DB_PATH = Path(__file__).parent.parent / 'friktionskompas_v3.db'

# Customer IDs
ESBJERG_ID = 'cust-SHKIi10cOe8'
HERNING_ID = 'cust-0nlG8ldxSYU'


@pytest.fixture
def real_db():
    """Connect to real database."""
    if not DB_PATH.exists():
        pytest.skip("Real database not found")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    yield conn
    conn.close()


@pytest.fixture
def real_app():
    """Create app with real database."""
    if not DB_PATH.exists():
        pytest.skip("Real database not found")

    os.environ['DB_PATH'] = str(DB_PATH)

    from admin_app import app as flask_app
    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
    })
    return flask_app


@pytest.fixture
def superadmin_client(real_app):
    """Superadmin client without customer filter."""
    client = real_app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 1,
            'email': 'admin@test.com',
            'name': 'Test Admin',
            'role': 'superadmin',
            'customer_id': None,
            'customer_name': None
        }
        sess['language'] = 'da'
    return client


@pytest.fixture
def herning_filter_client(real_app):
    """Superadmin client with Herning filter."""
    client = real_app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 1,
            'email': 'admin@test.com',
            'name': 'Test Admin',
            'role': 'superadmin',
            'customer_id': None,
            'customer_name': None
        }
        sess['customer_filter'] = HERNING_ID
        sess['customer_filter_name'] = 'Herning Kommune'
        sess['language'] = 'da'
    return client


@pytest.fixture
def esbjerg_filter_client(real_app):
    """Superadmin client with Esbjerg filter."""
    client = real_app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 1,
            'email': 'admin@test.com',
            'name': 'Test Admin',
            'role': 'superadmin',
            'customer_id': None,
            'customer_name': None
        }
        sess['customer_filter'] = ESBJERG_ID
        sess['customer_filter_name'] = 'Esbjerg Kommune'
        sess['language'] = 'da'
    return client


class TestDatabaseSetup:
    """Verify database is correctly set up for testing."""

    def test_both_customers_exist(self, real_db):
        """Both Herning and Esbjerg should exist."""
        result = real_db.execute(
            "SELECT name FROM customers WHERE id IN (?, ?)",
            [HERNING_ID, ESBJERG_ID]
        ).fetchall()

        names = [r['name'] for r in result]
        assert 'Herning Kommune' in names
        assert 'Esbjerg Kommune' in names

    def test_duplicate_unit_name_exists(self, real_db):
        """Both customers should have 'Social- og Sundhedsforvaltningen'."""
        result = real_db.execute("""
            SELECT c.name as customer, ou.name as unit
            FROM organizational_units ou
            JOIN customers c ON ou.customer_id = c.id
            WHERE ou.name = 'Social- og Sundhedsforvaltningen'
        """).fetchall()

        customers = [r['customer'] for r in result]
        assert 'Herning Kommune' in customers, "Herning should have Social- og Sundhedsforvaltningen"
        assert 'Esbjerg Kommune' in customers, "Esbjerg should have Social- og Sundhedsforvaltningen"

    def test_both_customers_have_data(self, real_db):
        """Both customers should have assessment data."""
        result = real_db.execute("""
            SELECT
                c.name,
                COUNT(DISTINCT a.id) as assessments,
                COUNT(DISTINCT r.id) as responses
            FROM customers c
            JOIN organizational_units ou ON ou.customer_id = c.id
            JOIN assessments a ON a.target_unit_id = ou.id
            JOIN responses r ON r.assessment_id = a.id
            WHERE c.id IN (?, ?)
            GROUP BY c.id
        """, [HERNING_ID, ESBJERG_ID]).fetchall()

        for row in result:
            assert row['assessments'] > 0, f"{row['name']} should have assessments"
            assert row['responses'] > 0, f"{row['name']} should have responses"


class TestAnalyserPageContent:
    """Test analyser page content with different filters."""

    def test_analyser_page_loads(self, superadmin_client):
        """Analyser page should load successfully."""
        response = superadmin_client.get('/admin/analyser')
        assert response.status_code == 200

    def test_superadmin_sees_data_from_both_customers(self, superadmin_client):
        """Without filter, superadmin should see units from both customers."""
        response = superadmin_client.get('/admin/analyser')
        html = response.data.decode('utf-8')

        # Both should appear in dropdown at minimum
        assert 'Herning Kommune' in html
        assert 'Esbjerg Kommune' in html

    def test_herning_filter_shows_herning_data(self, herning_filter_client):
        """With Herning filter, should see Herning-specific units."""
        response = herning_filter_client.get('/admin/analyser')
        assert response.status_code == 200

        html = response.data.decode('utf-8')

        # Should indicate filtering to Herning
        # (filter name shown in dropdown as selected)
        assert 'Herning Kommune' in html

    def test_esbjerg_filter_shows_esbjerg_data(self, esbjerg_filter_client):
        """With Esbjerg filter, should see Esbjerg-specific units."""
        response = esbjerg_filter_client.get('/admin/analyser')
        assert response.status_code == 200

        html = response.data.decode('utf-8')

        # Should show Esbjerg units
        # Check for Esbjerg-specific unit names
        esbjerg_units = ['Birkebo', 'Skovbrynet', 'Solhjem', 'Strandparken']
        found_esbjerg = any(unit in html for unit in esbjerg_units)
        assert found_esbjerg, "Should see at least one Esbjerg unit"

    def test_herning_filter_excludes_esbjerg_leaf_units(self, herning_filter_client):
        """With Herning filter, Esbjerg's leaf units should NOT appear."""
        response = herning_filter_client.get('/admin/analyser')
        html = response.data.decode('utf-8')

        # These are Esbjerg-only units (from canonical test data)
        esbjerg_only_units = ['Birkebo', 'Skovbrynet', 'Solhjem', 'Strandparken',
                              'Individuel Profil Test', 'Minimal Data Test', 'Substitution Test']

        for unit in esbjerg_only_units:
            # Unit should NOT appear in the data table (it might appear in navigation etc)
            # We check the table specifically
            assert f"onclick=\"window.location='/admin/analyser?unit_id=" not in html or unit not in html, \
                f"Esbjerg unit '{unit}' should not be clickable when filtered to Herning"


class TestAnalyserScoreDisplay:
    """Test that scores are displayed correctly."""

    def test_esbjerg_scores_match_expectations(self, esbjerg_filter_client, real_db):
        """Esbjerg canonical data should show expected score patterns."""
        response = esbjerg_filter_client.get('/admin/analyser')
        assert response.status_code == 200

        # Verify database has expected data
        # Skovbrynet should have high scores (>80%)
        result = real_db.execute("""
            SELECT AVG(
                CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
            ) as avg_score
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            JOIN assessments a ON r.assessment_id = a.id
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE ou.name = 'Skovbrynet' AND ou.customer_id = ?
              AND r.respondent_type = 'employee'
        """, [ESBJERG_ID]).fetchone()

        if result['avg_score']:
            assert result['avg_score'] > 4.0, "Skovbrynet should have high scores (>4.0)"

        # Solhjem should have low scores (<2.5)
        result = real_db.execute("""
            SELECT AVG(
                CASE WHEN q.reverse_scored = 1 THEN 6 - r.score ELSE r.score END
            ) as avg_score
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            JOIN assessments a ON r.assessment_id = a.id
            JOIN organizational_units ou ON a.target_unit_id = ou.id
            WHERE ou.name = 'Solhjem' AND ou.customer_id = ?
              AND r.respondent_type = 'employee'
        """, [ESBJERG_ID]).fetchone()

        if result['avg_score']:
            assert result['avg_score'] < 2.5, "Solhjem should have crisis scores (<2.5)"


class TestEmptyUnitHandling:
    """Test handling of units without data."""

    def test_empty_unit_exists_in_database(self, real_db):
        """Handicapområdet should exist but have no assessments."""
        result = real_db.execute("""
            SELECT ou.name, COUNT(a.id) as assessment_count
            FROM organizational_units ou
            LEFT JOIN assessments a ON a.target_unit_id = ou.id
            WHERE ou.name = 'Handicapområdet' AND ou.customer_id = ?
            GROUP BY ou.id
        """, [ESBJERG_ID]).fetchone()

        assert result is not None, "Handicapområdet should exist"
        assert result['assessment_count'] == 0, "Handicapområdet should have no assessments"

    def test_analyser_page_handles_empty_units(self, esbjerg_filter_client):
        """Analyser page should not crash with empty units."""
        response = esbjerg_filter_client.get('/admin/analyser')
        assert response.status_code == 200
        # The page loads without error - empty units are simply not shown in the list

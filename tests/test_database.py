"""
Database tests - CRUD operations, constraints, cascade delete.
"""
import pytest
import sqlite3
import tempfile
import os


def _create_test_schema(db_path):
    """Create minimal test database schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'manager', 'user')),
            customer_id INTEGER,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizational_units (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            customer_id INTEGER,
            parent_id TEXT,
            level INTEGER DEFAULT 0,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            period TEXT,
            target_unit_id TEXT,
            customer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id TEXT,
            unit_id TEXT,
            respondent_type TEXT,
            field TEXT,
            score INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


class TestDatabaseConstraints:
    """Test database constraints and referential integrity."""

    @pytest.fixture
    def test_db(self):
        """Create a fresh test database."""
        fd, path = tempfile.mkstemp(suffix='.db')

        _create_test_schema(path)

        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        yield conn

        conn.close()
        os.close(fd)
        try:
            os.unlink(path)
        except:
            pass

    def test_foreign_keys_enabled(self, test_db):
        """Test that foreign keys are enabled."""
        result = test_db.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1, "Foreign keys should be enabled"

    def test_customer_required_for_unit(self, test_db):
        """Test that organizational units require a valid customer."""
        # Try to insert unit with non-existent customer
        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute("""
                INSERT INTO organizational_units (id, name, customer_id, level)
                VALUES ('test-unit', 'Test', 99999, 0)
            """)

    def test_cascade_delete_customer(self, test_db):
        """Test that deleting customer cascades to units."""
        # Create customer
        test_db.execute("""
            INSERT INTO customers (id, name, domain, created_at)
            VALUES (100, 'Cascade Test', 'cascade.dk', datetime('now'))
        """)

        # Create unit under customer
        test_db.execute("""
            INSERT INTO organizational_units (id, name, customer_id, level)
            VALUES ('cascade-unit', 'Cascade Unit', 100, 0)
        """)
        test_db.commit()

        # Verify unit exists
        unit = test_db.execute(
            "SELECT * FROM organizational_units WHERE id = 'cascade-unit'"
        ).fetchone()
        assert unit is not None

        # Delete customer
        test_db.execute("DELETE FROM customers WHERE id = 100")
        test_db.commit()

        # Verify unit is also deleted
        unit = test_db.execute(
            "SELECT * FROM organizational_units WHERE id = 'cascade-unit'"
        ).fetchone()
        assert unit is None, "Unit should be deleted when customer is deleted"

    def test_cascade_delete_parent_unit(self, test_db):
        """Test that deleting parent unit cascades to children."""
        # Create customer first
        test_db.execute("""
            INSERT INTO customers (id, name, domain, created_at)
            VALUES (101, 'Parent Test', 'parent.dk', datetime('now'))
        """)

        # Create parent unit
        test_db.execute("""
            INSERT INTO organizational_units (id, name, customer_id, parent_id, level)
            VALUES ('parent-unit', 'Parent', 101, NULL, 0)
        """)

        # Create child unit
        test_db.execute("""
            INSERT INTO organizational_units (id, name, customer_id, parent_id, level)
            VALUES ('child-unit', 'Child', 101, 'parent-unit', 1)
        """)
        test_db.commit()

        # Delete parent
        test_db.execute("DELETE FROM organizational_units WHERE id = 'parent-unit'")
        test_db.commit()

        # Verify child is also deleted
        child = test_db.execute(
            "SELECT * FROM organizational_units WHERE id = 'child-unit'"
        ).fetchone()
        assert child is None, "Child should be deleted when parent is deleted"


class TestCRUDOperations:
    """Test basic CRUD operations."""

    @pytest.fixture
    def test_db(self):
        """Create a fresh test database."""
        fd, path = tempfile.mkstemp(suffix='.db')

        _create_test_schema(path)

        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row

        # Create test customer
        conn.execute("""
            INSERT INTO customers (id, name, domain, created_at)
            VALUES (1, 'CRUD Test', 'crud.dk', datetime('now'))
        """)
        conn.commit()

        yield conn

        conn.close()
        os.close(fd)
        try:
            os.unlink(path)
        except:
            pass

    def test_create_user(self, test_db):
        """Test creating a user."""
        test_db.execute("""
            INSERT INTO users (email, password_hash, name, role, customer_id)
            VALUES ('test@test.dk', 'hash123', 'Test User', 'manager', 1)
        """)
        test_db.commit()

        user = test_db.execute(
            "SELECT * FROM users WHERE email = 'test@test.dk'"
        ).fetchone()

        assert user is not None
        assert user['name'] == 'Test User'
        assert user['role'] == 'manager'

    def test_create_assessment(self, test_db):
        """Test creating a assessment."""
        # Create unit first
        test_db.execute("""
            INSERT INTO organizational_units (id, name, customer_id, level)
            VALUES ('assess-unit', 'Assessment Unit', 1, 0)
        """)

        # Create assessment
        test_db.execute("""
            INSERT INTO assessments (id, name, period, target_unit_id, customer_id, created_at)
            VALUES ('assess-1', 'Test Assessment', '2024Q1', 'assess-unit', 1, datetime('now'))
        """)
        test_db.commit()

        assessment = test_db.execute(
            "SELECT * FROM assessments WHERE id = 'assess-1'"
        ).fetchone()

        assert assessment is not None
        assert assessment['name'] == 'Test Assessment'

    def test_create_response(self, test_db):
        """Test creating a survey response."""
        # Create unit and assessment first
        test_db.execute("""
            INSERT INTO organizational_units (id, name, customer_id, level)
            VALUES ('resp-unit', 'Response Unit', 1, 0)
        """)
        test_db.execute("""
            INSERT INTO assessments (id, name, period, target_unit_id, customer_id, created_at)
            VALUES ('resp-camp', 'Response Assessment', '2024Q1', 'resp-unit', 1, datetime('now'))
        """)

        # Create response
        test_db.execute("""
            INSERT INTO responses (assessment_id, unit_id, respondent_type, field, score, created_at)
            VALUES ('resp-camp', 'resp-unit', 'employee', 'MENING', 4, datetime('now'))
        """)
        test_db.commit()

        response = test_db.execute(
            "SELECT * FROM responses WHERE assessment_id = 'resp-camp'"
        ).fetchone()

        assert response is not None
        assert response['field'] == 'MENING'
        assert response['score'] == 4

    def test_unique_email_constraint(self, test_db):
        """Test that email must be unique."""
        test_db.execute("""
            INSERT INTO users (email, password_hash, name, role, customer_id)
            VALUES ('unique@test.dk', 'hash1', 'User 1', 'manager', 1)
        """)
        test_db.commit()

        # Try to insert another user with same email
        with pytest.raises(sqlite3.IntegrityError):
            test_db.execute("""
                INSERT INTO users (email, password_hash, name, role, customer_id)
                VALUES ('unique@test.dk', 'hash2', 'User 2', 'manager', 1)
            """)

"""
Pytest fixtures for Friktionskompasset tests.
"""
import os

# CRITICAL: Disable rate limiting BEFORE any other imports
# This must be set before admin_app is imported anywhere
os.environ['RATELIMIT_ENABLED'] = 'false'

import pytest
import tempfile
import sys
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _init_test_db(db_path):
    """Initialize test database with required schema."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    # Customers table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT,
            contact_email TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'manager', 'user')),
            customer_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    # Organizational units table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizational_units (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            customer_id INTEGER,
            parent_id TEXT,
            level INTEGER DEFAULT 0,
            employee_count INTEGER DEFAULT 0,
            sick_leave_percent REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    # Assessments table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            period TEXT,
            target_unit_id TEXT,
            customer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (target_unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    # Responses table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id TEXT,
            unit_id TEXT,
            respondent_type TEXT,
            field TEXT,
            score INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    # Questions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field TEXT NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT DEFAULT 'baseline',
            layer TEXT,
            sequence INTEGER DEFAULT 0
        )
    """)

    # Email templates table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            template_type TEXT NOT NULL,
            subject TEXT,
            html_content TEXT,
            text_content TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    # Profil sessions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profil_sessions (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            unit_id TEXT,
            status TEXT DEFAULT 'invited',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


def _seed_test_data(db_path):
    """Seed test database with minimal test data."""
    from werkzeug.security import generate_password_hash

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    # Create test customer
    conn.execute("""
        INSERT INTO customers (id, name, domain, created_at)
        VALUES (1, 'Test Kunde', 'test.dk', datetime('now'))
    """)

    # Create test users
    admin_hash = generate_password_hash('admin123')
    manager_hash = generate_password_hash('manager123')

    conn.execute("""
        INSERT INTO users (id, email, password_hash, name, role, customer_id)
        VALUES (1, 'admin@test.com', ?, 'Test Admin', 'admin', NULL)
    """, (admin_hash,))

    conn.execute("""
        INSERT INTO users (id, email, password_hash, name, role, customer_id)
        VALUES (2, 'manager@test.com', ?, 'Test Manager', 'manager', 1)
    """, (manager_hash,))

    # Create test organization
    conn.execute("""
        INSERT INTO organizational_units (id, name, customer_id, parent_id, level)
        VALUES ('unit-test-1', 'Test Organisation', 1, NULL, 0)
    """)

    conn.execute("""
        INSERT INTO organizational_units (id, name, customer_id, parent_id, level)
        VALUES ('unit-test-2', 'Test Afdeling', 1, 'unit-test-1', 1)
    """)

    conn.commit()
    conn.close()


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    # Use a temporary database for tests
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    # Set environment BEFORE importing app
    os.environ['DB_PATH'] = db_path
    os.environ['RATELIMIT_ENABLED'] = 'false'  # Disable rate limiting in tests

    # Initialize the test database with schema BEFORE importing app
    _init_test_db(db_path)
    _seed_test_data(db_path)

    # Now import app (it will use our DB_PATH)
    from admin_app import app as flask_app

    flask_app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'DATABASE': db_path,
    })

    yield flask_app

    # Cleanup
    os.close(db_fd)
    try:
        os.unlink(db_path)
    except:
        pass  # May fail on Windows


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def authenticated_client(client):
    """Create an authenticated test client (as admin)."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 1,
            'email': 'admin@test.com',
            'name': 'Test Admin',
            'role': 'admin',
            'customer_id': None,
            'customer_name': None
        }
    return client


@pytest.fixture
def manager_client(client):
    """Create an authenticated test client (as manager)."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 2,
            'email': 'manager@test.com',
            'name': 'Test Manager',
            'role': 'manager',
            'customer_id': 1,
            'customer_name': 'Test Kunde'
        }
    return client


@pytest.fixture
def superadmin_client(client):
    """Create an authenticated test client (as superadmin)."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 3,
            'email': 'superadmin@test.com',
            'name': 'Test Superadmin',
            'role': 'superadmin',
            'customer_id': None,
            'customer_name': None
        }
    return client


@pytest.fixture
def superadmin_with_customer_filter(client):
    """Create superadmin client with customer filter set (simulating customer selection)."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 3,
            'email': 'superadmin@test.com',
            'name': 'Test Superadmin',
            'role': 'superadmin',
            'customer_id': None,
            'customer_name': None
        }
        sess['customer_filter'] = 1  # Set customer filter to Test Kunde
    return client


@pytest.fixture
def user_client(client):
    """Create an authenticated test client (as B2C user)."""
    with client.session_transaction() as sess:
        sess['user'] = {
            'id': 4,
            'email': 'user@test.com',
            'name': 'Test User',
            'role': 'user',
            'customer_id': 1,
            'customer_name': 'Test Kunde'
        }
    return client

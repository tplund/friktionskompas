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
    # Use DELETE journal mode for tests (more deterministic than WAL)
    conn.execute("PRAGMA journal_mode=DELETE")

    # Customers table (using TEXT id like production)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            domain TEXT,
            contact_email TEXT,
            is_active INTEGER DEFAULT 1,
            allow_profile_edit INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'manager', 'user')),
            customer_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    # Organizational units table (matches production schema)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizational_units (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            customer_id TEXT,
            parent_id TEXT,
            level INTEGER DEFAULT 0,
            full_path TEXT,
            leader_name TEXT,
            leader_email TEXT,
            employee_count INTEGER DEFAULT 0,
            sick_leave_percent REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    # Assessments table (full schema to match production)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            period TEXT,
            target_unit_id TEXT,
            customer_id TEXT,
            sent_from TEXT DEFAULT 'admin',
            sent_at TIMESTAMP,
            scheduled_at TIMESTAMP,
            status TEXT DEFAULT 'sent',
            mode TEXT DEFAULT 'anonymous',
            min_responses INTEGER DEFAULT 5,
            include_leader_assessment INTEGER DEFAULT 0,
            include_leader_self INTEGER DEFAULT 0,
            sender_name TEXT DEFAULT 'HR',
            assessment_type_id TEXT DEFAULT 'gruppe_friktion',
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
            question_id INTEGER,
            respondent_type TEXT,
            respondent_name TEXT,
            field TEXT,
            score INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        )
    """)

    # Questions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field TEXT NOT NULL,
            text_da TEXT NOT NULL,
            text_en TEXT,
            question_type TEXT DEFAULT 'baseline',
            layer TEXT,
            sequence INTEGER DEFAULT 0,
            reverse_scored INTEGER DEFAULT 0,
            is_default INTEGER DEFAULT 1,
            org_unit_id TEXT,
            respondent_types TEXT DEFAULT 'medarbejder,leder',
            FOREIGN KEY (org_unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    # Contacts table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT NOT NULL,
            name TEXT,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    # Tasks table (for situation assessments)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            unit_id TEXT,
            name TEXT NOT NULL,
            description TEXT,
            situation TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE SET NULL
        )
    """)

    # Email templates table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            template_type TEXT NOT NULL,
            subject TEXT,
            html_content TEXT,
            text_content TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    # Customer API keys table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            key_prefix TEXT NOT NULL UNIQUE,
            name TEXT DEFAULT 'API Key',
            permissions TEXT DEFAULT '{"read": true, "write": false}',
            rate_limit INTEGER DEFAULT 100,
            is_active INTEGER DEFAULT 1,
            last_used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Profil sessions table (matches production schema in db_profil.py)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profil_sessions (
            id TEXT PRIMARY KEY,
            person_name TEXT,
            person_email TEXT,
            context TEXT DEFAULT 'general',
            measurement_type TEXT DEFAULT 'profile',
            situation_context TEXT,
            customer_id TEXT,
            unit_id TEXT,
            is_complete INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    # Profil responses table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profil_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 7),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES profil_sessions(id) ON DELETE CASCADE
        )
    """)

    # Pair sessions table for par-maaling
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pair_sessions (
            id TEXT PRIMARY KEY,
            pair_code TEXT NOT NULL UNIQUE,
            person_a_name TEXT,
            person_a_email TEXT,
            person_a_session_id TEXT,
            person_b_name TEXT,
            person_b_email TEXT,
            person_b_session_id TEXT,
            status TEXT DEFAULT 'waiting',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (person_a_session_id) REFERENCES profil_sessions(id),
            FOREIGN KEY (person_b_session_id) REFERENCES profil_sessions(id)
        )
    """)

    # Profil questions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profil_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field TEXT NOT NULL,
            text_da TEXT NOT NULL,
            text_en TEXT,
            layer TEXT,
            sequence INTEGER DEFAULT 0,
            reverse_scored INTEGER DEFAULT 0,
            respondent_types TEXT DEFAULT 'medarbejder,leder',
            question_type TEXT DEFAULT 'sensitivity'
        )
    """)

    # Translations table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            language TEXT NOT NULL,
            value TEXT NOT NULL,
            context TEXT,
            UNIQUE(key, language)
        )
    """)

    # Domains table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domains (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL UNIQUE,
            customer_id TEXT,
            default_language TEXT DEFAULT 'da',
            branding_logo_url TEXT,
            branding_primary_color TEXT,
            branding_company_name TEXT,
            microsoft_auth_enabled INTEGER DEFAULT 0,
            google_auth_enabled INTEGER DEFAULT 0,
            email_password_enabled INTEGER DEFAULT 1,
            auth_providers TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    # User OAuth links table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_oauth_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            provider_email TEXT,
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(provider, provider_user_id)
        )
    """)

    # Actions table (for situation assessments)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            sequence INTEGER DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
    """)

    # Situation assessments table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS situation_assessments (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            unit_id TEXT,
            name TEXT,
            period TEXT,
            sent_from TEXT,
            sender_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE SET NULL
        )
    """)

    # Situation tokens table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS situation_tokens (
            token TEXT PRIMARY KEY,
            situation_assessment_id TEXT NOT NULL,
            recipient_email TEXT,
            recipient_name TEXT,
            is_used INTEGER DEFAULT 0,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (situation_assessment_id) REFERENCES situation_assessments(id) ON DELETE CASCADE
        )
    """)

    # Situation responses table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS situation_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            situation_assessment_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            field TEXT NOT NULL,
            score INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (situation_assessment_id) REFERENCES situation_assessments(id) ON DELETE CASCADE,
            FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
        )
    """)

    # Tokens table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            assessment_id TEXT,
            unit_id TEXT,
            is_used INTEGER DEFAULT 0,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
        )
    """)

    # Assessment types table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessment_types (
            id TEXT PRIMARY KEY,
            name_da TEXT NOT NULL,
            name_en TEXT NOT NULL,
            description_da TEXT,
            description_en TEXT,
            question_count INTEGER,
            duration_minutes INTEGER,
            is_individual INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            sequence INTEGER DEFAULT 0,
            icon TEXT,
            storage_mode TEXT DEFAULT 'server' CHECK(storage_mode IN ('local', 'server', 'both')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Customer assessment types
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_assessment_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            assessment_type_id TEXT NOT NULL,
            is_enabled INTEGER DEFAULT 1,
            custom_name_da TEXT,
            custom_name_en TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (assessment_type_id) REFERENCES assessment_types(id) ON DELETE CASCADE,
            UNIQUE(customer_id, assessment_type_id)
        )
    """)

    # Domain assessment types
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domain_assessment_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_id TEXT NOT NULL,
            assessment_type_id TEXT NOT NULL,
            is_enabled INTEGER DEFAULT 1,
            FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
            FOREIGN KEY (assessment_type_id) REFERENCES assessment_types(id) ON DELETE CASCADE,
            UNIQUE(domain_id, assessment_type_id)
        )
    """)

    # Assessment presets
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessment_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Preset assessment types
    conn.execute("""
        CREATE TABLE IF NOT EXISTS preset_assessment_types (
            preset_id INTEGER NOT NULL,
            assessment_type_id TEXT NOT NULL,
            FOREIGN KEY (preset_id) REFERENCES assessment_presets(id) ON DELETE CASCADE,
            FOREIGN KEY (assessment_type_id) REFERENCES assessment_types(id) ON DELETE CASCADE,
            PRIMARY KEY(preset_id, assessment_type_id)
        )
    """)

    conn.commit()
    conn.close()


def _seed_test_data(db_path):
    """Seed test database with minimal test data."""
    import bcrypt  # Use bcrypt to match production verify_password()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    # Create test customers (using string IDs like production)
    conn.execute("""
        INSERT INTO customers (id, name, domain, created_at)
        VALUES ('cust-test1', 'Test Kunde', 'test.dk', datetime('now'))
    """)
    conn.execute("""
        INSERT INTO customers (id, name, domain, created_at)
        VALUES ('cust-test2', 'Test Kunde 2', 'test2.dk', datetime('now'))
    """)

    # Create test users - using bcrypt to match verify_password() in db_multitenant.py
    admin_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    manager_hash = bcrypt.hashpw('manager123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    conn.execute("""
        INSERT INTO users (id, username, email, password_hash, name, role, customer_id)
        VALUES (1, 'admin', 'admin@test.com', ?, 'Test Admin', 'admin', NULL)
    """, (admin_hash,))

    conn.execute("""
        INSERT INTO users (id, username, email, password_hash, name, role, customer_id)
        VALUES (2, 'manager', 'manager@test.com', ?, 'Test Manager', 'manager', 'cust-test1')
    """, (manager_hash,))

    # Create test organization
    conn.execute("""
        INSERT INTO organizational_units (id, name, customer_id, parent_id, level)
        VALUES ('unit-test-1', 'Test Organisation', 'cust-test1', NULL, 0)
    """)

    conn.execute("""
        INSERT INTO organizational_units (id, name, customer_id, parent_id, level)
        VALUES ('unit-test-2', 'Test Afdeling', 'cust-test1', 'unit-test-1', 1)
    """)

    # Create default domain (required for app startup)
    conn.execute("""
        INSERT INTO domains (id, domain, customer_id, default_language, is_active)
        VALUES ('dom-default', 'localhost', NULL, 'da', 1)
    """)
    conn.execute("""
        INSERT INTO domains (id, domain, customer_id, default_language, is_active)
        VALUES ('dom-test1', 'test.dk', 'cust-test1', 'da', 1)
    """)

    # Add basic translations
    translations = [
        ('btn.create', 'da', 'Opret'), ('btn.create', 'en', 'Create'),
        ('btn.save', 'da', 'Gem'), ('btn.save', 'en', 'Save'),
        ('btn.delete', 'da', 'Slet'), ('btn.delete', 'en', 'Delete'),
        ('trend.title', 'da', 'Trendanalyse'), ('trend.title', 'en', 'Trend Analysis'),
        ('trend.subtitle', 'da', 'Se udvikling over tid'), ('trend.subtitle', 'en', 'View development over time'),
        ('nav.my_account', 'da', 'Min konto'), ('nav.my_account', 'en', 'My Account'),
        ('nav.logout', 'da', 'Log ud'), ('nav.logout', 'en', 'Log out'),
    ]
    for key, lang, value in translations:
        conn.execute("INSERT INTO translations (key, language, value) VALUES (?, ?, ?)", (key, lang, value))

    # Add profil_questions seed data
    profil_questions = [
        ('TRYGHED', 'Jeg føler mig tryg på arbejdet', 'I feel safe at work', 'baseline', 1, 0, 'sensitivity'),
        ('MENING', 'Mit arbejde giver mening', 'My work is meaningful', 'baseline', 2, 0, 'sensitivity'),
        ('KAN', 'Jeg kan udføre mine opgaver', 'I can perform my tasks', 'baseline', 3, 0, 'sensitivity'),
        ('BESVÆR', 'Jeg oplever besvær i arbejdet', 'I experience difficulties at work', 'baseline', 4, 1, 'sensitivity'),
    ]
    for field, text_da, text_en, layer, seq, reverse, qtype in profil_questions:
        conn.execute("""
            INSERT INTO profil_questions (field, text_da, text_en, layer, sequence, reverse_scored, question_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (field, text_da, text_en, layer, seq, reverse, qtype))

    # Add baseline questions too
    questions = [
        ('TRYGHED', 'Jeg føler mig tryg på arbejdet', 'I feel safe at work', 'baseline', 1, 0),
        ('MENING', 'Mit arbejde giver mening', 'My work is meaningful', 'baseline', 2, 0),
        ('KAN', 'Jeg kan udføre mine opgaver', 'I can perform my tasks', 'baseline', 3, 0),
        ('BESVÆR', 'Jeg oplever besvær i arbejdet', 'I experience difficulties at work', 'baseline', 4, 1),
    ]
    for field, text_da, text_en, layer, seq, reverse in questions:
        conn.execute("""
            INSERT INTO questions (field, text_da, text_en, layer, sequence, reverse_scored)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (field, text_da, text_en, layer, seq, reverse))

    conn.commit()
    conn.close()


# Global app instance (created once, reused)
_cached_app = None
_cached_db_path = None


def _reset_database(db_path):
    """Reset database to clean state by dropping and recreating all tables."""
    import time

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=OFF")
    # Use DELETE journal mode for consistency
    conn.execute("PRAGMA journal_mode=DELETE")

    # Get all tables
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    # Drop all tables
    for (table,) in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()
    conn.close()

    # Recreate schema and seed data
    _init_test_db(db_path)
    _seed_test_data(db_path)

    # Ensure database file is fully synced
    time.sleep(0.05)


@pytest.fixture(scope='function')
def app():
    """Create application for testing with fresh database per test.

    The app is cached but the database is reset for each test to ensure isolation.
    """
    global _cached_app, _cached_db_path

    # Create app only once (expensive operation)
    if _cached_app is None:
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        _cached_db_path = db_path

        # Set environment BEFORE importing app
        os.environ['DB_PATH'] = db_path
        os.environ['RATELIMIT_ENABLED'] = 'false'
        os.environ['TESTING'] = 'true'

        # Initialize the test database with schema
        _init_test_db(db_path)
        _seed_test_data(db_path)

        # Import admin_app which creates the app via factory
        from admin_app import app as flask_app

        flask_app.config.update({
            'DATABASE': db_path,
        })

        _cached_app = flask_app
    else:
        # Reset database to clean state for each test
        _reset_database(_cached_db_path)

    # Ensure environment is still set correctly (paranoia check)
    os.environ['DB_PATH'] = _cached_db_path
    os.environ['TESTING'] = 'true'

    yield _cached_app


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
            'customer_id': 'cust-test1',
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
        sess['customer_filter'] = 'cust-test1'  # Set customer filter to Test Kunde
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
            'customer_id': 'cust-test1',
            'customer_name': 'Test Kunde'
        }
    return client

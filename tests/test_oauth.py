"""
Tests for OAuth authentication module.
Tests OAuth flows, provider configuration, user linking, and token handling.
"""
import pytest
import sqlite3
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


def _create_test_connection(db_path):
    """Create a sqlite3 connection to the test database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database with OAuth tables."""
    db_path = str(tmp_path / "test_oauth.db")

    # Save original DB_PATH to restore later
    original_db_path = os.environ.get('DB_PATH')

    # Set environment to use test db
    os.environ['DB_PATH'] = db_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create customers table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            auth_providers TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create domains table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domains (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL UNIQUE,
            customer_id TEXT,
            auth_providers TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # Create users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT,
            customer_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # Create user_oauth_links table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_oauth_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            provider_email TEXT,
            access_token TEXT,
            refresh_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, provider),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()

    # Mock get_db_connection to use our test database
    with patch('oauth.get_db_connection', lambda: _create_test_connection(db_path)):
        yield db_path

    # Cleanup - use try/except for Windows compatibility
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except PermissionError:
        pass  # Windows may hold the file lock

    # Restore original DB_PATH
    if original_db_path is not None:
        os.environ['DB_PATH'] = original_db_path
    elif 'DB_PATH' in os.environ:
        del os.environ['DB_PATH']


@pytest.fixture
def mock_oauth_app():
    """Mock Flask app with OAuth."""
    app = Mock()
    app.config = {}
    return app


class TestOAuthInitialization:
    """Test OAuth initialization and configuration."""

    @pytest.mark.skip(reason="Requires real Flask app for oauth.init_app()")
    def test_init_oauth_registers_microsoft(self, test_db):
        """Test that init_oauth registers Microsoft provider."""
        from oauth import init_oauth, oauth

        # Set environment variables
        os.environ['MICROSOFT_CLIENT_ID'] = 'test-ms-client-id'
        os.environ['MICROSOFT_CLIENT_SECRET'] = 'test-ms-secret'

        mock_app = Mock()
        mock_app.config = {}

        init_oauth(mock_app)

        # Verify oauth was initialized
        assert oauth is not None

    @pytest.mark.skip(reason="Requires real Flask app for oauth.init_app()")
    def test_init_oauth_registers_google(self, test_db):
        """Test that init_oauth registers Google provider."""
        from oauth import init_oauth, oauth

        # Set environment variables
        os.environ['GOOGLE_CLIENT_ID'] = 'test-google-client-id'
        os.environ['GOOGLE_CLIENT_SECRET'] = 'test-google-secret'

        mock_app = Mock()
        mock_app.config = {}

        init_oauth(mock_app)

        assert oauth is not None

    @pytest.mark.skip(reason="Requires real Flask app for oauth.init_app()")
    def test_init_oauth_without_credentials(self, test_db):
        """Test that init_oauth works without OAuth credentials."""
        from oauth import init_oauth

        # Clear environment variables
        os.environ.pop('MICROSOFT_CLIENT_ID', None)
        os.environ.pop('GOOGLE_CLIENT_ID', None)

        mock_app = Mock()
        mock_app.config = {}

        # Should not raise exception
        init_oauth(mock_app)


class TestAuthProviderConfig:
    """Test authentication provider configuration."""

    def test_get_auth_providers_default(self, test_db):
        """Test getting default auth providers."""
        from oauth import get_auth_providers_for_domain, DEFAULT_AUTH_PROVIDERS

        providers = get_auth_providers_for_domain()

        assert providers == DEFAULT_AUTH_PROVIDERS

    def test_get_auth_providers_for_domain(self, test_db):
        """Test getting domain-specific auth providers."""
        # Insert domain with custom config
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO domains (id, domain, auth_providers, is_active)
            VALUES ('dom-1', 'test.com', ?, 1)
        """, (json.dumps({
            'email_password': True,
            'microsoft': {'enabled': True},
            'google': {'enabled': False}
        }),))
        conn.commit()
        conn.close()

        from oauth import get_auth_providers_for_domain

        providers = get_auth_providers_for_domain('test.com')

        assert providers['email_password'] is True
        assert providers['microsoft']['enabled'] is True
        assert providers['google']['enabled'] is False

    def test_get_auth_providers_fallback_to_customer(self, test_db):
        """Test fallback to customer config when domain has no config."""
        conn = sqlite3.connect(test_db)

        # Insert customer with config
        conn.execute("""
            INSERT INTO customers (id, name, auth_providers)
            VALUES ('cust-1', 'Test Customer', ?)
        """, (json.dumps({
            'email_password': False,
            'microsoft': {'enabled': True}
        }),))

        # Insert domain without config
        conn.execute("""
            INSERT INTO domains (id, domain, customer_id, auth_providers, is_active)
            VALUES ('dom-1', 'test.com', 'cust-1', NULL, 1)
        """)

        conn.commit()
        conn.close()

        from oauth import get_auth_providers_for_domain

        providers = get_auth_providers_for_domain('test.com')

        # Should use customer config
        assert providers['email_password'] is False
        assert providers['microsoft']['enabled'] is True

    def test_get_auth_providers_inactive_domain(self, test_db):
        """Test that inactive domains fall back to default."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO domains (id, domain, auth_providers, is_active)
            VALUES ('dom-1', 'inactive.com', ?, 0)
        """, (json.dumps({'email_password': False}),))
        conn.commit()
        conn.close()

        from oauth import get_auth_providers_for_domain, DEFAULT_AUTH_PROVIDERS

        providers = get_auth_providers_for_domain('inactive.com')

        # Should use default since domain is inactive
        assert providers == DEFAULT_AUTH_PROVIDERS


class TestEnabledProviders:
    """Test getting enabled providers."""

    def test_get_enabled_providers_default(self, test_db):
        """Test getting enabled providers with default config."""
        from oauth import get_enabled_providers

        # Clear OAuth env vars
        os.environ.pop('MICROSOFT_CLIENT_ID', None)
        os.environ.pop('GOOGLE_CLIENT_ID', None)

        enabled = get_enabled_providers()

        assert 'email_password' in enabled
        assert 'microsoft' not in enabled
        assert 'google' not in enabled

    def test_get_enabled_providers_with_microsoft(self, test_db):
        """Test enabled providers when Microsoft is configured."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO domains (id, domain, auth_providers, is_active)
            VALUES ('dom-1', 'test.com', ?, 1)
        """, (json.dumps({
            'email_password': True,
            'microsoft': {'enabled': True}
        }),))
        conn.commit()
        conn.close()

        # Set environment variable
        os.environ['MICROSOFT_CLIENT_ID'] = 'test-ms-id'

        from oauth import get_enabled_providers

        enabled = get_enabled_providers('test.com')

        assert 'email_password' in enabled
        assert 'microsoft' in enabled

    def test_get_enabled_providers_without_env_vars(self, test_db):
        """Test that providers are not enabled without environment variables."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO domains (id, domain, auth_providers, is_active)
            VALUES ('dom-1', 'test.com', ?, 1)
        """, (json.dumps({
            'microsoft': {'enabled': True},
            'google': {'enabled': True}
        }),))
        conn.commit()
        conn.close()

        # Clear environment variables
        os.environ.pop('MICROSOFT_CLIENT_ID', None)
        os.environ.pop('GOOGLE_CLIENT_ID', None)

        from oauth import get_enabled_providers

        enabled = get_enabled_providers('test.com')

        # Should not include microsoft/google without env vars
        assert 'microsoft' not in enabled
        assert 'google' not in enabled


class TestUserLookup:
    """Test user lookup functions."""

    def test_find_user_by_email_exists(self, test_db):
        """Test finding an existing user by email."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO users (id, email, name, is_active)
            VALUES (1, 'test@example.com', 'Test User', 1)
        """)
        conn.commit()
        conn.close()

        from oauth import find_user_by_email

        user = find_user_by_email('test@example.com')

        assert user is not None
        assert user['email'] == 'test@example.com'
        assert user['name'] == 'Test User'

    def test_find_user_by_email_case_insensitive(self, test_db):
        """Test that email lookup is case-insensitive."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO users (id, email, name, is_active)
            VALUES (1, 'test@example.com', 'Test User', 1)
        """)
        conn.commit()
        conn.close()

        from oauth import find_user_by_email

        user = find_user_by_email('TEST@EXAMPLE.COM')

        assert user is not None
        assert user['email'] == 'test@example.com'

    def test_find_user_by_email_not_found(self, test_db):
        """Test finding non-existent user returns None."""
        from oauth import find_user_by_email

        user = find_user_by_email('nonexistent@example.com')

        assert user is None

    def test_find_user_by_email_inactive(self, test_db):
        """Test that inactive users are not found."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO users (id, email, name, is_active)
            VALUES (1, 'inactive@example.com', 'Inactive User', 0)
        """)
        conn.commit()
        conn.close()

        from oauth import find_user_by_email

        user = find_user_by_email('inactive@example.com')

        assert user is None

    def test_find_user_by_oauth_exists(self, test_db):
        """Test finding user by OAuth link."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO users (id, email, name, is_active)
            VALUES (1, 'test@example.com', 'Test User', 1)
        """)
        conn.execute("""
            INSERT INTO user_oauth_links (user_id, provider, provider_user_id, provider_email)
            VALUES (1, 'microsoft', 'ms-12345', 'test@example.com')
        """)
        conn.commit()
        conn.close()

        from oauth import find_user_by_oauth

        user = find_user_by_oauth('microsoft', 'ms-12345')

        assert user is not None
        assert user['email'] == 'test@example.com'

    def test_find_user_by_oauth_not_found(self, test_db):
        """Test finding non-existent OAuth link."""
        from oauth import find_user_by_oauth

        user = find_user_by_oauth('google', 'nonexistent-id')

        assert user is None


class TestOAuthLinking:
    """Test OAuth account linking."""

    def test_link_oauth_to_user(self, test_db):
        """Test linking OAuth account to user."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO users (id, email, name, is_active)
            VALUES (1, 'test@example.com', 'Test User', 1)
        """)
        conn.commit()
        conn.close()

        from oauth import link_oauth_to_user

        result = link_oauth_to_user(
            user_id=1,
            provider='google',
            provider_user_id='google-67890',
            provider_email='test@example.com',
            access_token='access-token-123',
            refresh_token='refresh-token-456'
        )

        assert result is True

        # Verify link in database
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        link = conn.execute("""
            SELECT * FROM user_oauth_links WHERE user_id = 1 AND provider = 'google'
        """).fetchone()

        assert link is not None
        assert link['provider_user_id'] == 'google-67890'
        assert link['access_token'] == 'access-token-123'

        conn.close()

    def test_link_oauth_replace_existing(self, test_db):
        """Test that linking replaces existing OAuth link."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO users (id, email, name, is_active)
            VALUES (1, 'test@example.com', 'Test User', 1)
        """)
        conn.execute("""
            INSERT INTO user_oauth_links (user_id, provider, provider_user_id)
            VALUES (1, 'microsoft', 'old-id')
        """)
        conn.commit()
        conn.close()

        from oauth import link_oauth_to_user

        link_oauth_to_user(
            user_id=1,
            provider='microsoft',
            provider_user_id='new-id'
        )

        # Verify only one link exists with new ID
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        links = conn.execute("""
            SELECT * FROM user_oauth_links WHERE user_id = 1 AND provider = 'microsoft'
        """).fetchall()

        assert len(links) == 1
        assert links[0]['provider_user_id'] == 'new-id'

        conn.close()

    def test_get_user_oauth_links(self, test_db):
        """Test getting all OAuth links for a user."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO users (id, email, name, is_active)
            VALUES (1, 'test@example.com', 'Test User', 1)
        """)
        conn.execute("""
            INSERT INTO user_oauth_links (user_id, provider, provider_user_id, provider_email)
            VALUES (1, 'microsoft', 'ms-12345', 'test@microsoft.com')
        """)
        conn.execute("""
            INSERT INTO user_oauth_links (user_id, provider, provider_user_id, provider_email)
            VALUES (1, 'google', 'google-67890', 'test@gmail.com')
        """)
        conn.commit()
        conn.close()

        from oauth import get_user_oauth_links

        links = get_user_oauth_links(1)

        assert len(links) == 2
        providers = [link['provider'] for link in links]
        assert 'microsoft' in providers
        assert 'google' in providers

    def test_get_user_oauth_links_empty(self, test_db):
        """Test getting OAuth links for user with no links."""
        from oauth import get_user_oauth_links

        links = get_user_oauth_links(999)

        assert links == []

    def test_unlink_oauth_from_user(self, test_db):
        """Test removing OAuth link from user."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO users (id, email, name, is_active)
            VALUES (1, 'test@example.com', 'Test User', 1)
        """)
        conn.execute("""
            INSERT INTO user_oauth_links (user_id, provider, provider_user_id)
            VALUES (1, 'microsoft', 'ms-12345')
        """)
        conn.commit()
        conn.close()

        from oauth import unlink_oauth_from_user

        result = unlink_oauth_from_user(1, 'microsoft')

        assert result is True

        # Verify link is removed
        conn = sqlite3.connect(test_db)
        link = conn.execute("""
            SELECT * FROM user_oauth_links WHERE user_id = 1 AND provider = 'microsoft'
        """).fetchone()

        assert link is None

        conn.close()


class TestErrorHandling:
    """Test error handling in OAuth operations."""

    def test_find_user_by_email_database_error(self, test_db):
        """Test that find_user_by_email handles database errors."""
        # Delete database to force error
        if os.path.exists(test_db):
            os.remove(test_db)

        from oauth import find_user_by_email

        user = find_user_by_email('test@example.com')

        assert user is None

    def test_link_oauth_database_error(self, test_db):
        """Test that link_oauth_to_user handles errors gracefully."""
        # Delete database
        if os.path.exists(test_db):
            os.remove(test_db)

        from oauth import link_oauth_to_user

        result = link_oauth_to_user(1, 'microsoft', 'ms-12345')

        assert result is False

    def test_get_user_oauth_links_database_error(self, test_db):
        """Test that get_user_oauth_links handles errors gracefully."""
        # Delete database
        if os.path.exists(test_db):
            os.remove(test_db)

        from oauth import get_user_oauth_links

        links = get_user_oauth_links(1)

        assert links == []


class TestComplianceFix:
    """Test Microsoft OAuth compliance fix."""

    def test_microsoft_token_response_fix(self, test_db):
        """Test that Microsoft token response fix removes id_token."""
        from oauth import _microsoft_token_response_fix

        # Mock response with id_token
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'access-123',
            'id_token': 'id-token-with-invalid-issuer',
            'refresh_token': 'refresh-456'
        }

        # Apply fix
        fixed_response = _microsoft_token_response_fix(mock_response)

        # Get modified data
        data = fixed_response.json()

        assert 'id_token' not in data
        assert '_raw_id_token' in data
        assert data['access_token'] == 'access-123'

    def test_microsoft_token_response_fix_no_id_token(self, test_db):
        """Test compliance fix when id_token is not present."""
        from oauth import _microsoft_token_response_fix

        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'access-123'
        }

        # Should not raise exception
        fixed_response = _microsoft_token_response_fix(mock_response)

        data = fixed_response.json()
        assert data['access_token'] == 'access-123'


class TestDomainConfiguration:
    """Test domain-based configuration."""

    def test_domain_with_customer_inheritance(self, test_db):
        """Test that domain inherits customer config."""
        conn = sqlite3.connect(test_db)

        # Customer with Microsoft enabled
        conn.execute("""
            INSERT INTO customers (id, name, auth_providers)
            VALUES ('cust-1', 'Test Corp', ?)
        """, (json.dumps({
            'microsoft': {'enabled': True},
            'google': {'enabled': False}
        }),))

        # Domain without specific config
        conn.execute("""
            INSERT INTO domains (id, domain, customer_id, is_active)
            VALUES ('dom-1', 'testcorp.com', 'cust-1', 1)
        """)

        conn.commit()
        conn.close()

        from oauth import get_auth_providers_for_domain

        providers = get_auth_providers_for_domain('testcorp.com')

        assert providers['microsoft']['enabled'] is True
        assert providers['google']['enabled'] is False

    def test_domain_overrides_customer(self, test_db):
        """Test that domain config overrides customer config."""
        conn = sqlite3.connect(test_db)

        # Customer with Microsoft enabled
        conn.execute("""
            INSERT INTO customers (id, name, auth_providers)
            VALUES ('cust-1', 'Test Corp', ?)
        """, (json.dumps({'microsoft': {'enabled': True}}),))

        # Domain with Microsoft disabled
        conn.execute("""
            INSERT INTO domains (id, domain, customer_id, auth_providers, is_active)
            VALUES ('dom-1', 'testcorp.com', 'cust-1', ?, 1)
        """, (json.dumps({'microsoft': {'enabled': False}}),))

        conn.commit()
        conn.close()

        from oauth import get_auth_providers_for_domain

        providers = get_auth_providers_for_domain('testcorp.com')

        # Domain config should take precedence
        assert providers['microsoft']['enabled'] is False

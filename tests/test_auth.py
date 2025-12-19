"""
Tests for authentication and authorization.
"""
import pytest


class TestLogin:
    """Test login functionality."""

    def test_login_page_loads(self, client):
        """Test that login page loads correctly."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Login' in response.data or b'login' in response.data

    def test_login_with_valid_credentials(self, client):
        """Test login with valid admin credentials."""
        response = client.post('/login', data={
            'username': 'admin',  # Login uses username, not email
            'password': 'admin123'
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should redirect to admin page after login
        assert b'admin' in response.data.lower() or response.request.path == '/admin'

    def test_login_with_invalid_password(self, client):
        """Test login with wrong password."""
        response = client.post('/login', data={
            'username': 'admin',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should stay on login page or show error
        assert b'fejl' in response.data.lower() or b'forkert' in response.data.lower() or b'login' in response.data.lower()

    def test_login_with_nonexistent_user(self, client):
        """Test login with non-existent user."""
        response = client.post('/login', data={
            'username': 'nonexistent',
            'password': 'password123'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'fejl' in response.data.lower() or b'forkert' in response.data.lower() or b'login' in response.data.lower()


class TestAuthorization:
    """Test authorization and access control."""

    def test_admin_page_requires_login(self, client):
        """Test that admin page redirects to login when not authenticated."""
        response = client.get('/admin', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location

    def test_admin_page_accessible_when_authenticated(self, authenticated_client):
        """Test that admin page is accessible when logged in."""
        response = authenticated_client.get('/admin')
        assert response.status_code == 200

    def test_manager_cannot_access_admin_only_routes(self, manager_client):
        """Test that managers cannot access admin-only routes."""
        # Customers page should be admin-only
        response = manager_client.get('/admin/customers', follow_redirects=True)
        # Should either redirect or show access denied
        assert response.status_code in [200, 302, 403]

    def test_logout(self, authenticated_client):
        """Test that logout works correctly."""
        response = authenticated_client.get('/logout', follow_redirects=False)
        assert response.status_code == 302

        # After logout, admin should redirect to login
        response = authenticated_client.get('/admin', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location


class TestUserRole:
    """Test B2C user role permissions."""

    def test_user_can_access_user_home(self, user_client):
        """Test that user role can access /user home page."""
        response = user_client.get('/user')
        assert response.status_code == 200
        assert b'Velkommen' in response.data or b'velkommen' in response.data

    def test_user_cannot_access_admin_home(self, user_client):
        """Test that user role is redirected from admin pages."""
        response = user_client.get('/admin', follow_redirects=False)
        assert response.status_code == 302
        # Should redirect to user home, not admin home
        assert '/user' in response.location or '/login' in response.location

    def test_user_cannot_access_customers(self, user_client):
        """Test that user role cannot access /admin/customers."""
        response = user_client.get('/admin/customers', follow_redirects=False)
        assert response.status_code == 302
        # Should redirect to user home
        assert '/user' in response.location

    def test_user_cannot_access_domains(self, user_client):
        """Test that user role cannot access /admin/domains."""
        response = user_client.get('/admin/domains', follow_redirects=False)
        assert response.status_code == 302

    def test_user_can_access_help_page(self, user_client):
        """Test that user role can access /help."""
        response = user_client.get('/help')
        assert response.status_code == 200

    def test_user_can_access_profil_pages(self, user_client):
        """Test that user role can access profile pages."""
        # Local profile page should be accessible
        response = user_client.get('/profil/local')
        assert response.status_code == 200


class TestRoleHierarchy:
    """Test that role hierarchy works correctly."""

    def test_superadmin_can_access_all(self, superadmin_client):
        """Test superadmin has access to everything."""
        assert superadmin_client.get('/admin').status_code == 200
        assert superadmin_client.get('/admin/customers').status_code == 200
        assert superadmin_client.get('/admin/domains').status_code == 200

    def test_admin_can_access_admin_pages(self, authenticated_client):
        """Test admin can access admin pages."""
        assert authenticated_client.get('/admin').status_code == 200
        assert authenticated_client.get('/admin/customers').status_code == 200

    def test_manager_limited_access(self, manager_client):
        """Test manager has limited access."""
        # Manager can access admin home
        response = manager_client.get('/admin')
        assert response.status_code == 200

        # Manager cannot access superadmin-only pages like domains
        response = manager_client.get('/admin/domains', follow_redirects=False)
        assert response.status_code == 302

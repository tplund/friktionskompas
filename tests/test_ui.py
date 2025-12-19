"""
UI/UX tests using Playwright.
Tests user interactions and visual flows.
"""
import os
# CRITICAL: Set env vars before ANY imports to disable rate limiting
os.environ['RATELIMIT_ENABLED'] = 'false'

import pytest
import threading
import time
from playwright.sync_api import Page, expect


# Server fixture for running the app during tests
@pytest.fixture(scope="module")
def live_server():
    """Start a live server for UI tests."""
    from admin_app import app

    # Configure for testing
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    # Start server in background thread
    server_thread = threading.Thread(
        target=lambda: app.run(port=5099, debug=False, use_reloader=False)
    )
    server_thread.daemon = True
    server_thread.start()

    # Wait for server to start
    time.sleep(1)

    yield "http://localhost:5099"


@pytest.fixture
def logged_in_page(page: Page, live_server):
    """Provide a page with admin logged in."""
    page.goto(f"{live_server}/login")
    page.fill('input[name="username"]', 'admin')
    page.fill('input[name="password"]', 'admin123')
    page.click('button[type="submit"]')
    # Wait for redirect to complete
    page.wait_for_load_state('networkidle', timeout=5000)
    return page


class TestLoginFlow:
    """Test login page interactions."""

    def test_login_page_loads(self, page: Page, live_server):
        """Test that login page loads correctly."""
        page.goto(f"{live_server}/login")
        expect(page).to_have_title("Log ind - Friktionskompasset")
        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()

    def test_login_with_valid_credentials(self, page: Page, live_server):
        """Test successful login."""
        page.goto(f"{live_server}/login")
        page.fill('input[name="username"]', 'admin')
        page.fill('input[name="password"]', 'admin123')
        page.click('button[type="submit"]')

        # Should redirect to admin area (could be /admin, /admin/analyser, etc.)
        page.wait_for_load_state('networkidle', timeout=5000)
        # Verify we're logged in by checking for admin navigation
        expect(page.locator('nav').first).to_be_visible()

    def test_login_with_invalid_credentials(self, page: Page, live_server):
        """Test login failure with wrong password."""
        page.goto(f"{live_server}/login")
        page.fill('input[name="username"]', 'admin')
        page.fill('input[name="password"]', 'wrongpassword')
        page.click('button[type="submit"]')

        # Should stay on login page with error
        expect(page.locator('.toast, .alert, .error, .flash')).to_be_visible(timeout=3000)


class TestAdminNavigation:
    """Test admin interface navigation with dropdown menus."""

    def test_navigation_menu_visible(self, logged_in_page: Page):
        """Test that navigation menu is visible after login."""
        expect(logged_in_page.locator('nav').first).to_be_visible()

    def test_navigate_to_analyser_from_dropdown(self, logged_in_page: Page, live_server):
        """Test navigation to analyser page via Målinger dropdown."""
        # First hover on Målinger dropdown to reveal submenu
        logged_in_page.hover('.submenu-dropdown:has(.dropdown-toggle:has-text("Målinger"))')
        logged_in_page.wait_for_timeout(300)  # Wait for dropdown to open
        logged_in_page.click('.dropdown-menu a:has-text("Analyser")')
        logged_in_page.wait_for_load_state('networkidle', timeout=5000)
        # Should see analyser page content
        assert 'analyser' in logged_in_page.url

    def test_navigate_to_organisationer(self, logged_in_page: Page, live_server):
        """Test navigation to organisations page via dropdown."""
        # First hover on Organisation dropdown to reveal submenu
        logged_in_page.hover('.submenu-dropdown:has(.dropdown-toggle:has-text("Organisation"))')
        logged_in_page.wait_for_timeout(300)  # Wait for dropdown to open
        logged_in_page.click('.dropdown-menu a:has-text("Organisationer")')
        logged_in_page.wait_for_load_state('networkidle', timeout=5000)

    def test_navigate_to_analyser(self, logged_in_page: Page, live_server):
        """Test navigation to analyser page via dropdown."""
        # First hover on Målinger dropdown to reveal submenu
        logged_in_page.hover('.submenu-dropdown:has(.dropdown-toggle:has-text("Målinger"))')
        logged_in_page.wait_for_timeout(300)  # Wait for dropdown to open
        logged_in_page.click('.dropdown-menu a:has-text("Analyser")')
        logged_in_page.wait_for_load_state('networkidle', timeout=5000)

    def test_dashboard_link_visible(self, logged_in_page: Page):
        """Test that Dashboard link is directly visible (first item in submenu)."""
        # Dashboard link is now at /admin in submenu-links
        dashboard_link = logged_in_page.locator('.submenu-links a[href="/admin"]')
        expect(dashboard_link).to_be_visible()


class TestOrganisationTree:
    """Test organisation tree interactions."""

    def test_expand_collapse_tree(self, logged_in_page: Page, live_server):
        """Test expanding and collapsing organisation tree."""
        logged_in_page.goto(f"{live_server}/admin")

        # Find expand/collapse buttons
        expand_btn = logged_in_page.locator('button:has-text("Fold ud")')
        collapse_btn = logged_in_page.locator('button:has-text("Fold sammen")')

        if expand_btn.count() > 0:
            # Click expand
            expand_btn.click()
            # Wait a moment for animation
            logged_in_page.wait_for_timeout(300)

            # Click collapse
            collapse_btn.click()
            logged_in_page.wait_for_timeout(300)

    def test_tree_node_clickable(self, logged_in_page: Page, live_server):
        """Test that tree nodes/rows exist on dashboard (may be collapsed by default)."""
        logged_in_page.goto(f"{live_server}/admin")

        # Dashboard v2 has unit rows - they may be collapsed by default
        # Just verify the tree structure exists in the DOM
        unit_rows = logged_in_page.locator('.unit-row')
        # Tree should have at least some unit rows (even if collapsed/hidden)
        row_count = unit_rows.count()
        assert row_count > 0, "Expected tree to have unit rows"

        # Verify customer/root level is visible (expandable headers)
        customer_headers = logged_in_page.locator('.customer-name, .tree-header, [data-level="0"]')
        if customer_headers.count() > 0:
            expect(customer_headers.first).to_be_visible()


class TestAssessmentOverview:
    """Test assessment/analysis overview page."""

    def test_assessments_overview_loads(self, logged_in_page: Page, live_server):
        """Test that assessments overview page loads."""
        logged_in_page.goto(f"{live_server}/admin/assessments-overview")
        # Should see either assessments or empty state
        page_content = logged_in_page.content()
        assert 'assessment' in page_content.lower() or 'analyse' in page_content.lower()

    def test_assessment_card_clickable(self, logged_in_page: Page, live_server):
        """Test that assessment cards are clickable."""
        logged_in_page.goto(f"{live_server}/admin/assessments-overview")

        assessment_cards = logged_in_page.locator('.assessment-card')
        if assessment_cards.count() > 0:
            # Click first assessment
            assessment_cards.first.click()
            # Should navigate to assessment details
            logged_in_page.wait_for_url(f"{live_server}/admin/assessment/*", timeout=5000)


class TestBackupPage:
    """Test backup functionality UI."""

    def test_backup_page_loads(self, logged_in_page: Page, live_server):
        """Test that backup page loads correctly."""
        logged_in_page.goto(f"{live_server}/admin/backup")
        expect(logged_in_page.locator('h2:has-text("Backup")')).to_be_visible()
        expect(logged_in_page.locator('a:has-text("Download Backup")')).to_be_visible()

    def test_backup_download_link(self, logged_in_page: Page, live_server):
        """Test that download backup link exists and is clickable."""
        logged_in_page.goto(f"{live_server}/admin/backup")
        download_btn = logged_in_page.locator('a:has-text("Download Backup")')
        expect(download_btn).to_be_visible()
        expect(download_btn).to_have_attribute('href', '/admin/backup/download')


class TestResponsiveDesign:
    """Test responsive design at different viewport sizes."""

    def test_mobile_viewport(self, page: Page, live_server):
        """Test page at mobile viewport size."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{live_server}/login")
        # Login form should still be visible
        expect(page.locator('input[name="username"]')).to_be_visible()

    def test_tablet_viewport(self, page: Page, live_server):
        """Test page at tablet viewport size."""
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(f"{live_server}/login")
        expect(page.locator('input[name="username"]')).to_be_visible()

    def test_desktop_viewport(self, page: Page, live_server):
        """Test page at desktop viewport size."""
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(f"{live_server}/login")
        expect(page.locator('input[name="username"]')).to_be_visible()

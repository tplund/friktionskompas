"""
Tests for Mailjet integration module.
Tests email sending, template rendering, tracking, and error handling.
"""
import pytest
import sqlite3
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database with email_logs table."""
    db_path = str(tmp_path / "test_mailjet.db")

    # Set environment to use test db
    os.environ['DB_PATH'] = db_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create email_logs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            to_email TEXT NOT NULL,
            subject TEXT,
            email_type TEXT DEFAULT 'invitation',
            status TEXT DEFAULT 'sent',
            assessment_id TEXT,
            token TEXT,
            error_message TEXT,
            delivered_at TIMESTAMP,
            opened_at TIMESTAMP,
            clicked_at TIMESTAMP,
            bounced_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create customers table for email config
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email_from_address TEXT,
            email_from_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def mock_mailjet_client():
    """Mock Mailjet client."""
    with patch('mailjet_integration.mailjet') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'Messages': [
                {
                    'Status': 'success',
                    'To': [{'Email': 'test@example.com', 'MessageID': 'msg-12345'}]
                }
            ]
        }
        mock_client.send.create.return_value = mock_response
        yield mock_client


class TestEmailLogging:
    """Test email logging functionality."""

    def test_ensure_email_logs_table_creates_table(self, test_db):
        """Test that ensure_email_logs_table creates the table if it doesn't exist."""
        # Import after setting DB_PATH
        from mailjet_integration import ensure_email_logs_table

        # Drop table first
        conn = sqlite3.connect(test_db)
        conn.execute("DROP TABLE IF EXISTS email_logs")
        conn.commit()
        conn.close()

        # Ensure table
        ensure_email_logs_table()

        # Verify table exists
        conn = sqlite3.connect(test_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='email_logs'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_log_email_success(self, test_db):
        """Test logging an email successfully."""
        from mailjet_integration import log_email

        log_id = log_email(
            to_email='test@example.com',
            subject='Test Email',
            email_type='invitation',
            status='sent',
            message_id='msg-12345',
            assessment_id='assess-1',
            token='token-abc'
        )

        assert log_id is not None

        # Verify in database
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        log = conn.execute("SELECT * FROM email_logs WHERE id = ?", (log_id,)).fetchone()

        assert log['to_email'] == 'test@example.com'
        assert log['subject'] == 'Test Email'
        assert log['email_type'] == 'invitation'
        assert log['status'] == 'sent'
        assert log['message_id'] == 'msg-12345'
        assert log['assessment_id'] == 'assess-1'
        assert log['token'] == 'token-abc'

        conn.close()

    def test_log_email_with_error(self, test_db):
        """Test logging an email with error message."""
        from mailjet_integration import log_email

        log_id = log_email(
            to_email='invalid@example.com',
            subject='Test Email',
            email_type='invitation',
            status='error',
            error_message='Invalid recipient'
        )

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        log = conn.execute("SELECT * FROM email_logs WHERE id = ?", (log_id,)).fetchone()

        assert log['status'] == 'error'
        assert log['error_message'] == 'Invalid recipient'

        conn.close()

    def test_update_email_status(self, test_db):
        """Test updating email status via webhook."""
        from mailjet_integration import log_email, update_email_status

        # Log initial email
        log_id = log_email(
            to_email='test@example.com',
            subject='Test',
            email_type='invitation',
            status='sent',
            message_id='msg-12345'
        )

        # Update status to delivered
        update_email_status('msg-12345', 'delivered', 'delivered_at')

        # Verify update
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        log = conn.execute("SELECT * FROM email_logs WHERE message_id = ?", ('msg-12345',)).fetchone()

        assert log['status'] == 'delivered'
        assert log['delivered_at'] is not None

        conn.close()

    def test_update_email_status_opened(self, test_db):
        """Test updating email status to opened."""
        from mailjet_integration import log_email, update_email_status

        log_id = log_email(
            to_email='test@example.com',
            subject='Test',
            email_type='invitation',
            status='sent',
            message_id='msg-67890'
        )

        # Update to opened
        update_email_status('msg-67890', 'opened', 'opened_at')

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        log = conn.execute("SELECT * FROM email_logs WHERE message_id = ?", ('msg-67890',)).fetchone()

        assert log['status'] == 'opened'
        assert log['opened_at'] is not None

        conn.close()


class TestEmailStats:
    """Test email statistics functionality."""

    def test_get_email_stats_for_assessment(self, test_db):
        """Test getting email stats for a specific assessment."""
        from mailjet_integration import log_email, get_email_stats

        # Log multiple emails for assessment
        log_email('test1@example.com', 'Test 1', 'invitation', 'sent', assessment_id='assess-1')
        log_email('test2@example.com', 'Test 2', 'invitation', 'delivered', assessment_id='assess-1')
        log_email('test3@example.com', 'Test 3', 'invitation', 'opened', assessment_id='assess-1')
        log_email('test4@example.com', 'Test 4', 'invitation', 'error', assessment_id='assess-1')
        log_email('other@example.com', 'Other', 'invitation', 'sent', assessment_id='assess-2')

        stats = get_email_stats('assess-1')

        assert stats['total'] == 4
        assert stats['sent'] == 1
        assert stats['delivered'] == 1
        assert stats['opened'] == 1
        assert stats['errors'] == 1

    def test_get_email_stats_all(self, test_db):
        """Test getting email stats for all assessments."""
        from mailjet_integration import log_email, get_email_stats

        log_email('test1@example.com', 'Test 1', 'invitation', 'sent', assessment_id='assess-1')
        log_email('test2@example.com', 'Test 2', 'invitation', 'sent', assessment_id='assess-2')
        log_email('test3@example.com', 'Test 3', 'invitation', 'delivered', assessment_id='assess-3')

        stats = get_email_stats()

        assert stats['total'] == 3
        assert stats['sent'] == 2
        assert stats['delivered'] == 1

    def test_get_email_stats_bounced(self, test_db):
        """Test email stats with bounced emails."""
        from mailjet_integration import log_email, get_email_stats

        log_email('valid@example.com', 'Test', 'invitation', 'sent', assessment_id='assess-1')
        log_email('bounce@example.com', 'Test', 'invitation', 'bounced', assessment_id='assess-1')

        stats = get_email_stats('assess-1')

        assert stats['total'] == 2
        assert stats['bounced'] == 1


class TestEmailLogs:
    """Test email logs retrieval."""

    def test_get_email_logs_for_assessment(self, test_db):
        """Test getting email logs for a specific assessment."""
        from mailjet_integration import log_email, get_email_logs

        log_email('test1@example.com', 'Test 1', 'invitation', 'sent', assessment_id='assess-1')
        log_email('test2@example.com', 'Test 2', 'invitation', 'sent', assessment_id='assess-1')
        log_email('other@example.com', 'Other', 'invitation', 'sent', assessment_id='assess-2')

        logs = get_email_logs('assess-1')

        assert len(logs) == 2
        assert all(log['assessment_id'] == 'assess-1' for log in logs)

    def test_get_email_logs_limit(self, test_db):
        """Test email logs limit parameter."""
        from mailjet_integration import log_email, get_email_logs

        # Create 10 logs
        for i in range(10):
            log_email(f'test{i}@example.com', f'Test {i}', 'invitation', 'sent', assessment_id='assess-1')

        logs = get_email_logs('assess-1', limit=5)

        assert len(logs) == 5

    def test_get_email_logs_order(self, test_db):
        """Test that logs are returned in descending order (newest first)."""
        from mailjet_integration import log_email, get_email_logs

        log_email('old@example.com', 'Old', 'invitation', 'sent', assessment_id='assess-1')
        # Small delay to ensure different timestamps
        import time
        time.sleep(0.01)
        log_email('new@example.com', 'New', 'invitation', 'sent', assessment_id='assess-1')

        logs = get_email_logs('assess-1')

        # Newest should be first
        assert logs[0]['to_email'] == 'new@example.com'
        assert logs[1]['to_email'] == 'old@example.com'


class TestCustomerEmailConfig:
    """Test customer-specific email configuration."""

    def test_get_email_sender_default(self, test_db):
        """Test getting default email sender when no customer config."""
        from mailjet_integration import get_email_sender

        sender = get_email_sender()

        assert 'Email' in sender
        assert 'Name' in sender
        assert sender['Email'] == 'info@friktionskompasset.dk'
        assert sender['Name'] == 'Friktionskompasset'

    def test_get_email_sender_with_customer_config(self, test_db):
        """Test getting customer-specific email sender."""
        # Insert customer with email config
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO customers (id, name, email_from_address, email_from_name)
            VALUES ('cust-1', 'Test Customer', 'custom@example.com', 'Custom Sender')
        """)
        conn.commit()
        conn.close()

        # Mock db_multitenant.get_customer_email_config
        with patch('mailjet_integration.get_customer_email_config') as mock_config:
            mock_config.return_value = {
                'from_address': 'custom@example.com',
                'from_name': 'Custom Sender'
            }

            from mailjet_integration import get_email_sender
            sender = get_email_sender('cust-1')

            assert sender['Email'] == 'custom@example.com'
            assert sender['Name'] == 'Custom Sender'

    def test_get_email_sender_fallback_on_error(self, test_db):
        """Test that get_email_sender falls back to default on error."""
        with patch('mailjet_integration.get_customer_email_config') as mock_config:
            mock_config.side_effect = Exception('Database error')

            from mailjet_integration import get_email_sender
            sender = get_email_sender('cust-1')

            # Should fallback to default
            assert sender['Email'] == 'info@friktionskompasset.dk'


class TestMailjetAPI:
    """Test Mailjet API interactions."""

    def test_check_mailjet_status_success(self, test_db):
        """Test checking Mailjet message status."""
        with patch('mailjet_integration.Client') as MockClient:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'Data': [{
                    'ID': 'msg-12345',
                    'Status': 'delivered'
                }]
            }
            mock_client.message.get.return_value = mock_response
            MockClient.return_value = mock_client

            from mailjet_integration import check_mailjet_status
            result = check_mailjet_status('msg-12345')

            assert result is not None
            assert 'Data' in result

    def test_check_mailjet_status_none_message_id(self, test_db):
        """Test check_mailjet_status with None message_id."""
        from mailjet_integration import check_mailjet_status

        result = check_mailjet_status(None)
        assert result is None

    def test_check_mailjet_status_error(self, test_db):
        """Test check_mailjet_status handles API errors gracefully."""
        with patch('mailjet_integration.Client') as MockClient:
            mock_client = Mock()
            mock_client.message.get.side_effect = Exception('API Error')
            MockClient.return_value = mock_client

            from mailjet_integration import check_mailjet_status
            result = check_mailjet_status('msg-12345')

            assert result is None


class TestEmailTemplates:
    """Test email template functionality."""

    def test_default_templates_exist(self, test_db):
        """Test that default templates are defined."""
        from mailjet_integration import DEFAULT_TEMPLATES_DA

        assert 'invitation' in DEFAULT_TEMPLATES_DA
        assert 'subject' in DEFAULT_TEMPLATES_DA['invitation']
        assert 'html' in DEFAULT_TEMPLATES_DA['invitation']

    def test_template_has_required_variables(self, test_db):
        """Test that invitation template has required placeholders."""
        from mailjet_integration import DEFAULT_TEMPLATES_DA

        html = DEFAULT_TEMPLATES_DA['invitation']['html']

        # Check for required placeholders
        assert '{sender_name}' in html
        assert '{survey_url}' in html
        assert '{header_text}' in html


class TestEmailSending:
    """Test email sending functionality (mocked)."""

    def test_send_email_mocked(self, test_db, mock_mailjet_client):
        """Test sending an email with mocked Mailjet client."""
        # This would test the actual send function if it exists
        # For now, we test the logging which happens after sending
        from mailjet_integration import log_email

        # Simulate successful send
        log_id = log_email(
            to_email='test@example.com',
            subject='Test Email',
            email_type='invitation',
            status='sent',
            message_id='msg-12345',
            assessment_id='assess-1'
        )

        assert log_id is not None

        # Verify log entry
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        log = conn.execute("SELECT * FROM email_logs WHERE id = ?", (log_id,)).fetchone()

        assert log['message_id'] == 'msg-12345'
        assert log['status'] == 'sent'
        conn.close()


class TestErrorHandling:
    """Test error handling in email operations."""

    def test_log_email_database_error(self, test_db):
        """Test that log_email handles database errors gracefully."""
        # Close and delete database to force error
        if os.path.exists(test_db):
            os.remove(test_db)

        from mailjet_integration import log_email

        # Should return None on error, not raise exception
        log_id = log_email(
            to_email='test@example.com',
            subject='Test',
            email_type='invitation',
            status='sent'
        )

        assert log_id is None

    def test_get_email_stats_database_error(self, test_db):
        """Test that get_email_stats handles database errors gracefully."""
        # Delete database to force error
        if os.path.exists(test_db):
            os.remove(test_db)

        from mailjet_integration import get_email_stats

        # Should return empty dict on error
        stats = get_email_stats()
        assert stats == {}

    def test_get_email_logs_database_error(self, test_db):
        """Test that get_email_logs handles database errors gracefully."""
        # Delete database to force error
        if os.path.exists(test_db):
            os.remove(test_db)

        from mailjet_integration import get_email_logs

        # Should return empty list on error
        logs = get_email_logs()
        assert logs == []


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_log_email_with_null_fields(self, test_db):
        """Test logging email with minimal required fields."""
        from mailjet_integration import log_email

        log_id = log_email(
            to_email='test@example.com',
            subject='Test',
            email_type='invitation',
            status='sent'
        )

        assert log_id is not None

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        log = conn.execute("SELECT * FROM email_logs WHERE id = ?", (log_id,)).fetchone()

        assert log['message_id'] is None
        assert log['assessment_id'] is None
        assert log['token'] is None

        conn.close()

    def test_get_email_stats_no_data(self, test_db):
        """Test getting stats when no emails exist."""
        from mailjet_integration import get_email_stats

        stats = get_email_stats('nonexistent-assessment')

        # Should return stats with zeros
        assert stats is not None

    def test_update_status_nonexistent_message(self, test_db):
        """Test updating status for non-existent message_id."""
        from mailjet_integration import update_email_status

        # Should not raise exception
        update_email_status('nonexistent-msg', 'delivered', 'delivered_at')

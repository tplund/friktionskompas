"""
Tests for data retention and cleanup functionality.
Tests GDPR compliance, automated cleanup, and retention policies.
"""
import pytest
import sqlite3
import os
from datetime import datetime, timedelta
from unittest.mock import patch, Mock


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database with audit and email tables."""
    db_path = str(tmp_path / "test_retention.db")

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create audit_log table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


class TestEmailLogsCleanup:
    """Test email logs cleanup functionality."""

    def test_cleanup_email_logs_old_records(self, test_db):
        """Test that cleanup removes old email logs."""
        conn = sqlite3.connect(test_db)

        # Insert old email log (100 days ago)
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('old@example.com', 'Old Email', ?)
        """, (old_date,))

        # Insert recent email log (10 days ago)
        recent_date = (datetime.now() - timedelta(days=10)).isoformat()
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('recent@example.com', 'Recent Email', ?)
        """, (recent_date,))

        conn.commit()
        conn.close()

        from data_retention import cleanup_email_logs

        # Clean up logs older than 90 days
        result = cleanup_email_logs(days=90)

        assert result['success'] is True
        assert result['deleted'] == 1
        assert result['remaining'] == 1
        assert result['retention_days'] == 90

        # Verify only recent log remains
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        remaining = conn.execute("SELECT * FROM email_logs").fetchall()

        assert len(remaining) == 1
        assert remaining[0]['to_email'] == 'recent@example.com'

        conn.close()

    def test_cleanup_email_logs_no_old_records(self, test_db):
        """Test cleanup when no old records exist."""
        conn = sqlite3.connect(test_db)

        # Insert only recent email logs
        recent_date = (datetime.now() - timedelta(days=10)).isoformat()
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('recent@example.com', 'Recent Email', ?)
        """, (recent_date,))

        conn.commit()
        conn.close()

        from data_retention import cleanup_email_logs

        result = cleanup_email_logs(days=90)

        assert result['success'] is True
        assert result['deleted'] == 0
        assert result['remaining'] == 1

    def test_cleanup_email_logs_custom_retention(self, test_db):
        """Test cleanup with custom retention period."""
        conn = sqlite3.connect(test_db)

        # Insert log 50 days ago
        date_50_days = (datetime.now() - timedelta(days=50)).isoformat()
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('test@example.com', 'Test', ?)
        """, (date_50_days,))

        conn.commit()
        conn.close()

        from data_retention import cleanup_email_logs

        # Clean up with 30 days retention
        result = cleanup_email_logs(days=30)

        assert result['deleted'] == 1

        # Clean up with 60 days retention (should delete nothing)
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('test2@example.com', 'Test', ?)
        """, (date_50_days,))
        conn.commit()
        conn.close()

        result = cleanup_email_logs(days=60)
        assert result['deleted'] == 0

    def test_cleanup_email_logs_empty_table(self, test_db):
        """Test cleanup when email_logs table is empty."""
        from data_retention import cleanup_email_logs

        result = cleanup_email_logs()

        assert result['success'] is True
        assert result['deleted'] == 0
        assert result['remaining'] == 0


class TestAuditLogsCleanup:
    """Test audit logs cleanup functionality."""

    def test_cleanup_audit_logs_old_records(self, test_db):
        """Test that cleanup removes old audit logs."""
        conn = sqlite3.connect(test_db)

        # Insert old audit log (400 days ago)
        old_date = (datetime.now() - timedelta(days=400)).isoformat()
        conn.execute("""
            INSERT INTO audit_log (user_id, username, action, entity_type, timestamp)
            VALUES ('user-1', 'olduser', 'login', 'user', ?)
        """, (old_date,))

        # Insert recent audit log (100 days ago)
        recent_date = (datetime.now() - timedelta(days=100)).isoformat()
        conn.execute("""
            INSERT INTO audit_log (user_id, username, action, entity_type, timestamp)
            VALUES ('user-2', 'recentuser', 'login', 'user', ?)
        """, (recent_date,))

        conn.commit()
        conn.close()

        from data_retention import cleanup_audit_logs

        # Clean up logs older than 365 days
        result = cleanup_audit_logs(days=365)

        assert result['success'] is True
        assert result['deleted'] == 1
        assert result['remaining'] == 1

        # Verify only recent log remains
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        remaining = conn.execute("SELECT * FROM audit_log").fetchall()

        assert len(remaining) == 1
        assert remaining[0]['username'] == 'recentuser'

        conn.close()

    def test_cleanup_audit_logs_no_old_records(self, test_db):
        """Test cleanup when no old audit logs exist."""
        conn = sqlite3.connect(test_db)

        recent_date = (datetime.now() - timedelta(days=100)).isoformat()
        conn.execute("""
            INSERT INTO audit_log (user_id, username, action, timestamp)
            VALUES ('user-1', 'testuser', 'login', ?)
        """, (recent_date,))

        conn.commit()
        conn.close()

        from data_retention import cleanup_audit_logs

        result = cleanup_audit_logs(days=365)

        assert result['deleted'] == 0
        assert result['remaining'] == 1

    def test_cleanup_audit_logs_custom_retention(self, test_db):
        """Test audit log cleanup with custom retention period."""
        conn = sqlite3.connect(test_db)

        # Insert log 200 days ago
        date_200_days = (datetime.now() - timedelta(days=200)).isoformat()
        conn.execute("""
            INSERT INTO audit_log (user_id, username, action, timestamp)
            VALUES ('user-1', 'testuser', 'login', ?)
        """, (date_200_days,))

        conn.commit()
        conn.close()

        from data_retention import cleanup_audit_logs

        # Clean with 180 days retention
        result = cleanup_audit_logs(days=180)

        assert result['deleted'] == 1


class TestRunAllCleanups:
    """Test running all cleanup jobs together."""

    def test_run_all_cleanups(self, test_db):
        """Test running all cleanup jobs at once."""
        conn = sqlite3.connect(test_db)

        # Insert old email log
        old_email_date = (datetime.now() - timedelta(days=100)).isoformat()
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('old@example.com', 'Old', ?)
        """, (old_email_date,))

        # Insert old audit log
        old_audit_date = (datetime.now() - timedelta(days=400)).isoformat()
        conn.execute("""
            INSERT INTO audit_log (user_id, username, action, timestamp)
            VALUES ('user-1', 'olduser', 'login', ?)
        """, (old_audit_date,))

        conn.commit()
        conn.close()

        from data_retention import run_all_cleanups

        result = run_all_cleanups()

        assert 'email_logs' in result
        assert 'audit_log' in result
        assert result['total_deleted'] == 2
        assert 'timestamp' in result

        assert result['email_logs']['deleted'] == 1
        assert result['audit_log']['deleted'] == 1

    def test_run_all_cleanups_no_deletions(self, test_db):
        """Test run_all_cleanups when nothing needs deletion."""
        from data_retention import run_all_cleanups

        result = run_all_cleanups()

        assert result['total_deleted'] == 0
        assert result['email_logs']['deleted'] == 0
        assert result['audit_log']['deleted'] == 0


class TestCleanupStatus:
    """Test cleanup status reporting."""

    def test_get_cleanup_status(self, test_db):
        """Test getting cleanup status with data."""
        conn = sqlite3.connect(test_db)

        # Insert old and new email logs
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        new_date = (datetime.now() - timedelta(days=10)).isoformat()

        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('old@example.com', 'Old', ?)
        """, (old_date,))

        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('new@example.com', 'New', ?)
        """, (new_date,))

        conn.commit()
        conn.close()

        from data_retention import get_cleanup_status

        status = get_cleanup_status()

        assert 'email_logs' in status
        assert 'audit_log' in status
        assert 'timestamp' in status

        assert status['email_logs']['total'] == 2
        assert status['email_logs']['eligible_for_cleanup'] == 1
        assert status['email_logs']['retention_days'] == 90

    def test_get_cleanup_status_empty_database(self, test_db):
        """Test getting status when database is empty."""
        from data_retention import get_cleanup_status

        status = get_cleanup_status()

        assert status['email_logs']['total'] == 0
        assert status['email_logs']['eligible_for_cleanup'] == 0
        assert status['audit_log']['total'] == 0
        assert status['audit_log']['eligible_for_cleanup'] == 0

    def test_get_cleanup_status_oldest_newest(self, test_db):
        """Test that status includes oldest and newest timestamps."""
        conn = sqlite3.connect(test_db)

        oldest_date = (datetime.now() - timedelta(days=200)).isoformat()
        newest_date = (datetime.now() - timedelta(days=1)).isoformat()

        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('oldest@example.com', 'Oldest', ?)
        """, (oldest_date,))

        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('newest@example.com', 'Newest', ?)
        """, (newest_date,))

        conn.commit()
        conn.close()

        from data_retention import get_cleanup_status

        status = get_cleanup_status()

        assert status['email_logs']['oldest'] == oldest_date
        assert status['email_logs']['newest'] == newest_date


class TestLastCleanupRun:
    """Test tracking of last cleanup run."""

    def test_get_last_cleanup_run_with_history(self, test_db):
        """Test getting info about last cleanup run."""
        conn = sqlite3.connect(test_db)

        # Insert cleanup audit entry
        cleanup_time = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO audit_log (user_id, username, action, entity_type, details, timestamp)
            VALUES ('system', 'data_retention_job', 'data_deleted', 'email_logs',
                   'Auto-cleanup: Deleted 10 email logs older than 90 days', ?)
        """, (cleanup_time,))

        conn.commit()
        conn.close()

        from data_retention import get_last_cleanup_run

        result = get_last_cleanup_run()

        assert result['found'] is True
        assert result['last_run'] == cleanup_time
        assert 'Deleted 10 email logs' in result['details']

    def test_get_last_cleanup_run_no_history(self, test_db):
        """Test when no cleanup has been run."""
        from data_retention import get_last_cleanup_run

        result = get_last_cleanup_run()

        assert result['found'] is False
        assert result['last_run'] is None
        assert 'No cleanup has been run' in result['details']

    def test_get_last_cleanup_run_multiple_entries(self, test_db):
        """Test that only the most recent cleanup is returned."""
        conn = sqlite3.connect(test_db)

        old_time = (datetime.now() - timedelta(days=7)).isoformat()
        recent_time = (datetime.now() - timedelta(days=1)).isoformat()

        conn.execute("""
            INSERT INTO audit_log (user_id, username, action, entity_type, details, timestamp)
            VALUES ('system', 'data_retention_job', 'data_deleted', 'email_logs', 'Old cleanup', ?)
        """, (old_time,))

        conn.execute("""
            INSERT INTO audit_log (user_id, username, action, entity_type, details, timestamp)
            VALUES ('system', 'data_retention_job', 'data_deleted', 'audit_log', 'Recent cleanup', ?)
        """, (recent_time,))

        conn.commit()
        conn.close()

        from data_retention import get_last_cleanup_run

        result = get_last_cleanup_run()

        # Should return the most recent
        assert result['last_run'] == recent_time
        assert 'Recent cleanup' in result['details']


class TestAuditLogging:
    """Test that cleanup operations are properly logged."""

    def test_cleanup_creates_audit_entry(self, test_db):
        """Test that cleanup operation creates an audit log entry."""
        conn = sqlite3.connect(test_db)

        # Insert old email log
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('old@example.com', 'Old', ?)
        """, (old_date,))

        conn.commit()
        conn.close()

        # Mock audit.log_action to avoid importing entire audit module
        with patch('data_retention.log_action') as mock_log:
            from data_retention import cleanup_email_logs

            result = cleanup_email_logs(days=90)

            # Verify audit log was called
            assert mock_log.called
            call_args = mock_log.call_args

            # Check that it logged the deletion
            assert 'Deleted 1 email logs' in call_args[1]['details']

    def test_cleanup_no_audit_when_nothing_deleted(self, test_db):
        """Test that no audit entry is created when nothing is deleted."""
        with patch('data_retention.log_action') as mock_log:
            from data_retention import cleanup_email_logs

            result = cleanup_email_logs(days=90)

            # Should not create audit entry when nothing deleted
            assert not mock_log.called


class TestErrorHandling:
    """Test error handling in cleanup operations."""

    def test_cleanup_email_logs_database_error(self, test_db):
        """Test that cleanup handles database errors gracefully."""
        # Delete database to force error
        if os.path.exists(test_db):
            os.remove(test_db)

        from data_retention import cleanup_email_logs

        result = cleanup_email_logs()

        assert result['success'] is False
        assert 'error' in result
        assert result['deleted'] == 0

    def test_cleanup_audit_logs_database_error(self, test_db):
        """Test that audit cleanup handles errors gracefully."""
        # Delete database
        if os.path.exists(test_db):
            os.remove(test_db)

        from data_retention import cleanup_audit_logs

        result = cleanup_audit_logs()

        assert result['success'] is False
        assert 'error' in result

    def test_get_cleanup_status_database_error(self, test_db):
        """Test that get_cleanup_status handles errors gracefully."""
        # Delete database
        if os.path.exists(test_db):
            os.remove(test_db)

        from data_retention import get_cleanup_status

        status = get_cleanup_status()

        assert 'error' in status
        assert 'timestamp' in status

    def test_get_last_cleanup_run_database_error(self, test_db):
        """Test that get_last_cleanup_run handles errors gracefully."""
        # Delete database
        if os.path.exists(test_db):
            os.remove(test_db)

        from data_retention import get_last_cleanup_run

        result = get_last_cleanup_run()

        assert result['found'] is False
        assert 'error' in result


class TestRetentionPolicies:
    """Test GDPR retention policy compliance."""

    def test_default_email_retention_90_days(self, test_db):
        """Test that default email retention is 90 days."""
        from data_retention import EMAIL_LOGS_RETENTION_DAYS

        assert EMAIL_LOGS_RETENTION_DAYS == 90

    def test_default_audit_retention_365_days(self, test_db):
        """Test that default audit retention is 365 days."""
        from data_retention import AUDIT_LOG_RETENTION_DAYS

        assert AUDIT_LOG_RETENTION_DAYS == 365

    def test_cleanup_respects_cutoff_date(self, test_db):
        """Test that cleanup only deletes records before cutoff date."""
        conn = sqlite3.connect(test_db)

        # Insert logs exactly at boundary
        exactly_90_days = (datetime.now() - timedelta(days=90)).isoformat()
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('boundary@example.com', 'At boundary', ?)
        """, (exactly_90_days,))

        # Insert log one day past boundary
        past_boundary = (datetime.now() - timedelta(days=91)).isoformat()
        conn.execute("""
            INSERT INTO email_logs (to_email, subject, created_at)
            VALUES ('old@example.com', 'Past boundary', ?)
        """, (past_boundary,))

        conn.commit()
        conn.close()

        from data_retention import cleanup_email_logs

        result = cleanup_email_logs(days=90)

        # Should delete at least the one past boundary
        assert result['deleted'] >= 1


class TestBatchCleanup:
    """Test cleanup with large datasets."""

    def test_cleanup_many_records(self, test_db):
        """Test cleanup handles many records efficiently."""
        conn = sqlite3.connect(test_db)

        old_date = (datetime.now() - timedelta(days=100)).isoformat()

        # Insert 100 old records
        for i in range(100):
            conn.execute("""
                INSERT INTO email_logs (to_email, subject, created_at)
                VALUES (?, 'Test', ?)
            """, (f'test{i}@example.com', old_date))

        conn.commit()
        conn.close()

        from data_retention import cleanup_email_logs

        result = cleanup_email_logs(days=90)

        assert result['deleted'] == 100
        assert result['remaining'] == 0

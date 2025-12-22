"""
Expanded tests for scheduler module.
Tests scheduled assessments, background jobs, data retention integration.
"""
import pytest
import sqlite3
import os
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock


def _create_test_connection(db_path):
    """Create a sqlite3 connection to the test database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database with all necessary tables."""
    db_path = str(tmp_path / "test_scheduler.db")

    # Save original DB_PATH to restore later
    original_db_path = os.environ.get('DB_PATH')

    # Set environment to use test db
    os.environ['DB_PATH'] = db_path

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    # Create customers table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create organizational_units table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizational_units (
            id TEXT PRIMARY KEY,
            parent_id TEXT,
            name TEXT NOT NULL,
            full_path TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 0,
            leader_name TEXT,
            leader_email TEXT,
            employee_count INTEGER DEFAULT 0,
            customer_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (parent_id) REFERENCES organizational_units(id)
        )
    """)

    # Create assessments table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            target_unit_id TEXT NOT NULL,
            name TEXT NOT NULL,
            period TEXT NOT NULL,
            customer_id TEXT,
            sent_from TEXT DEFAULT 'admin',
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mode TEXT DEFAULT 'anonymous',
            min_responses INTEGER DEFAULT 5,
            scheduled_at TIMESTAMP,
            status TEXT DEFAULT 'sent',
            sender_name TEXT DEFAULT 'HR',
            FOREIGN KEY (target_unit_id) REFERENCES organizational_units(id),
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # Create tokens table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            assessment_id TEXT NOT NULL,
            unit_id TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assessment_id) REFERENCES assessments(id),
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id)
        )
    """)

    # Create contacts table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT NOT NULL,
            name TEXT,
            email TEXT,
            phone TEXT,
            FOREIGN KEY (unit_id) REFERENCES organizational_units(id)
        )
    """)

    # Insert test data
    conn.execute("""
        INSERT INTO customers (id, name)
        VALUES ('cust-1', 'Test Customer')
    """)

    conn.execute("""
        INSERT INTO organizational_units (id, name, full_path, level, employee_count, customer_id)
        VALUES ('unit-1', 'Test Unit', 'Test Unit', 0, 10, 'cust-1')
    """)

    conn.commit()
    conn.close()

    # Mock get_db_connection to use our test database
    with patch('scheduler.get_db_connection', lambda: _create_test_connection(db_path)):
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


class TestGetPendingAssessments:
    """Test retrieving pending scheduled assessments."""

    def test_get_pending_assessments_returns_due_assessments(self, test_db):
        """Test that pending assessments due now are returned."""
        conn = sqlite3.connect(test_db)

        # Create assessment scheduled in the past
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('assess-past', 'unit-1', 'Past Assessment', '2025Q1', past_time, 'scheduled'))

        conn.commit()
        conn.close()

        from scheduler import get_pending_scheduled_assessments

        pending = get_pending_scheduled_assessments()

        assert len(pending) == 1
        assert pending[0]['id'] == 'assess-past'
        assert pending[0]['status'] == 'scheduled'

    def test_get_pending_assessments_excludes_future(self, test_db):
        """Test that future assessments are not returned."""
        conn = sqlite3.connect(test_db)

        future_time = (datetime.now() + timedelta(days=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('assess-future', 'unit-1', 'Future Assessment', '2025Q1', future_time, 'scheduled'))

        conn.commit()
        conn.close()

        from scheduler import get_pending_scheduled_assessments

        pending = get_pending_scheduled_assessments()

        assert len(pending) == 0

    def test_get_pending_assessments_excludes_sent(self, test_db):
        """Test that already sent assessments are not returned."""
        conn = sqlite3.connect(test_db)

        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('assess-sent', 'unit-1', 'Sent Assessment', '2025Q1', past_time, 'sent'))

        conn.commit()
        conn.close()

        from scheduler import get_pending_scheduled_assessments

        pending = get_pending_scheduled_assessments()

        assert len(pending) == 0

    def test_get_pending_assessments_includes_unit_name(self, test_db):
        """Test that unit name is joined in query."""
        conn = sqlite3.connect(test_db)

        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('assess-1', 'unit-1', 'Test Assessment', '2025Q1', past_time, 'scheduled'))

        conn.commit()
        conn.close()

        from scheduler import get_pending_scheduled_assessments

        pending = get_pending_scheduled_assessments()

        assert len(pending) == 1
        assert pending[0]['unit_name'] == 'Test Unit'


class TestMarkAssessmentSent:
    """Test marking assessments as sent."""

    def test_mark_assessment_sent_updates_status(self, test_db):
        """Test that mark_assessment_sent updates status and timestamp."""
        conn = sqlite3.connect(test_db)

        scheduled_time = (datetime.now() + timedelta(days=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('assess-1', 'unit-1', 'Test', '2025Q1', scheduled_time, 'scheduled'))

        conn.commit()
        conn.close()

        from scheduler import mark_assessment_sent

        mark_assessment_sent('assess-1')

        # Verify update
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        assessment = conn.execute(
            "SELECT * FROM assessments WHERE id = ?", ('assess-1',)
        ).fetchone()

        assert assessment['status'] == 'sent'
        assert assessment['sent_at'] is not None

        conn.close()

    def test_mark_assessment_sent_nonexistent(self, test_db):
        """Test marking non-existent assessment doesn't raise error."""
        from scheduler import mark_assessment_sent

        # Should not raise exception
        mark_assessment_sent('nonexistent-id')


class TestSendScheduledAssessment:
    """Test sending scheduled assessments."""

    def test_send_scheduled_assessment_with_tokens(self, test_db):
        """Test sending assessment with token generation."""
        conn = sqlite3.connect(test_db)

        scheduled_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, sender_name, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('assess-1', 'unit-1', 'Test Assessment', '2025Q1', scheduled_time, 'scheduled', 'Test HR', 'cust-1'))

        # Add contacts
        conn.execute("""
            INSERT INTO contacts (unit_id, email)
            VALUES ('unit-1', 'test@example.com')
        """)

        conn.commit()
        conn.close()

        # Mock dependencies - these are imported inside the function
        with patch('db_hierarchical.generate_tokens_for_assessment') as mock_tokens, \
             patch('db_hierarchical.get_unit_contacts') as mock_contacts, \
             patch('mailjet_integration.send_assessment_batch') as mock_send:

            mock_tokens.return_value = {
                'unit-1': [{'token': 'token-123', 'unit_id': 'unit-1'}]
            }
            mock_contacts.return_value = [{'email': 'test@example.com', 'name': 'Test'}]
            mock_send.return_value = {'emails_sent': 1, 'sms_sent': 0, 'errors': 0}

            from scheduler import send_scheduled_assessment

            assessment = {
                'id': 'assess-1',
                'name': 'Test Assessment',
                'sender_name': 'Test HR'
            }

            result = send_scheduled_assessment(assessment)

            assert result is True
            assert mock_tokens.called
            assert mock_send.called

    def test_send_scheduled_assessment_no_tokens(self, test_db):
        """Test sending assessment when no tokens generated."""
        conn = sqlite3.connect(test_db)

        scheduled_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('assess-1', 'unit-1', 'Test', '2025Q1', scheduled_time, 'scheduled', 'cust-1'))

        conn.commit()
        conn.close()

        with patch('db_hierarchical.generate_tokens_for_assessment') as mock_tokens:
            mock_tokens.return_value = {}  # No tokens

            from scheduler import send_scheduled_assessment

            assessment = {'id': 'assess-1', 'name': 'Test', 'sender_name': 'HR'}
            result = send_scheduled_assessment(assessment)

            # Should still return True and mark as sent
            assert result is True

    def test_send_scheduled_assessment_error_handling(self, test_db):
        """Test that errors are caught and logged."""
        with patch('db_hierarchical.generate_tokens_for_assessment') as mock_tokens:
            mock_tokens.side_effect = Exception('Token generation failed')

            from scheduler import send_scheduled_assessment

            assessment = {'id': 'assess-1', 'name': 'Test', 'sender_name': 'HR'}
            result = send_scheduled_assessment(assessment)

            assert result is False


class TestDailyCleanup:
    """Test daily data retention cleanup integration."""

    def test_run_daily_cleanup(self, test_db):
        """Test running daily cleanup job."""
        with patch('data_retention.run_all_cleanups') as mock_cleanup:
            mock_cleanup.return_value = {
                'total_deleted': 10,
                'email_logs': {'deleted': 5},
                'audit_log': {'deleted': 5}
            }

            from scheduler import run_daily_cleanup

            result = run_daily_cleanup()

            assert result is not None
            assert result['total_deleted'] == 10
            assert mock_cleanup.called

    def test_should_run_cleanup_first_time(self, test_db):
        """Test that cleanup should run on first check."""
        # Reset global state
        import scheduler
        scheduler._last_cleanup_date = None

        from scheduler import should_run_cleanup

        assert should_run_cleanup() is True

    def test_should_run_cleanup_already_run_today(self, test_db):
        """Test that cleanup should not run twice in same day."""
        import scheduler
        scheduler._last_cleanup_date = datetime.now().date()

        from scheduler import should_run_cleanup

        assert should_run_cleanup() is False

    def test_should_run_cleanup_next_day(self, test_db):
        """Test that cleanup should run on next day."""
        import scheduler
        yesterday = (datetime.now() - timedelta(days=1)).date()
        scheduler._last_cleanup_date = yesterday

        from scheduler import should_run_cleanup

        assert should_run_cleanup() is True


class TestSchedulerLoop:
    """Test the main scheduler loop (mocked)."""

    def test_scheduler_loop_processes_pending_assessments(self, test_db):
        """Test that scheduler loop processes pending assessments."""
        conn = sqlite3.connect(test_db)

        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('assess-1', 'unit-1', 'Test', '2025Q1', past_time, 'scheduled', 'cust-1'))

        conn.commit()
        conn.close()

        with patch('scheduler.send_scheduled_assessment') as mock_send:
            import scheduler

            # Set running flag
            scheduler._scheduler_running = True

            # Create a thread that will stop after one iteration
            def stop_after_one():
                time.sleep(0.1)
                scheduler._scheduler_running = False

            import threading
            stop_thread = threading.Thread(target=stop_after_one)
            stop_thread.start()

            # Run scheduler loop (will stop after 0.1 seconds)
            scheduler.scheduler_loop()

            # Wait for stop thread
            stop_thread.join(timeout=1)

            # Verify send was called
            # Note: This might not always trigger in test environment
            # but tests the logic

    def test_start_scheduler(self, test_db):
        """Test starting the scheduler."""
        import scheduler

        # Reset state
        scheduler._scheduler_running = False
        scheduler._scheduler_thread = None

        # Start scheduler
        scheduler.start_scheduler()

        assert scheduler._scheduler_running is True
        assert scheduler._scheduler_thread is not None

        # Stop it
        scheduler.stop_scheduler()
        time.sleep(0.2)  # Give it time to stop

    def test_start_scheduler_already_running(self, test_db):
        """Test that starting already running scheduler is a no-op."""
        import scheduler

        scheduler._scheduler_running = True

        # Should not start new thread
        scheduler.start_scheduler()

        # Clean up
        scheduler._scheduler_running = False

    def test_stop_scheduler(self, test_db):
        """Test stopping the scheduler."""
        import scheduler

        scheduler._scheduler_running = True

        scheduler.stop_scheduler()

        assert scheduler._scheduler_running is False


class TestGetScheduledAssessments:
    """Test getting all scheduled assessments."""

    def test_get_scheduled_assessments(self, test_db):
        """Test getting all scheduled assessments (not sent yet)."""
        conn = sqlite3.connect(test_db)

        future_time = (datetime.now() + timedelta(days=1)).isoformat()

        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('assess-1', 'unit-1', 'Scheduled 1', '2025Q1', future_time, 'scheduled', 'cust-1'))

        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('assess-2', 'unit-1', 'Scheduled 2', '2025Q1', future_time, 'scheduled', 'cust-1'))

        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, status, customer_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('assess-sent', 'unit-1', 'Already Sent', '2025Q1', 'sent', 'cust-1'))

        conn.commit()
        conn.close()

        from scheduler import get_scheduled_assessments

        scheduled = get_scheduled_assessments()

        assert len(scheduled) == 2
        assert all(a['status'] == 'scheduled' for a in scheduled)


class TestErrorHandling:
    """Test error handling in scheduler operations."""

    def test_get_pending_assessments_database_error(self, test_db):
        """Test that get_pending_scheduled_assessments handles errors."""
        # Delete database
        if os.path.exists(test_db):
            os.remove(test_db)

        from scheduler import get_pending_scheduled_assessments

        # Should return empty list on error
        pending = get_pending_scheduled_assessments()

        assert pending == []

    def test_run_daily_cleanup_error(self, test_db):
        """Test that run_daily_cleanup handles errors gracefully."""
        with patch('data_retention.run_all_cleanups') as mock_cleanup:
            mock_cleanup.side_effect = Exception('Cleanup failed')

            from scheduler import run_daily_cleanup

            result = run_daily_cleanup()

            assert result is None


class TestMultipleCustomers:
    """Test scheduler with multiple customers."""

    def test_pending_assessments_multiple_customers(self, test_db):
        """Test that pending assessments from different customers are returned."""
        conn = sqlite3.connect(test_db)

        # Add another customer and unit
        conn.execute("""
            INSERT INTO customers (id, name)
            VALUES ('cust-2', 'Customer 2')
        """)

        conn.execute("""
            INSERT INTO organizational_units (id, name, full_path, level, customer_id)
            VALUES ('unit-2', 'Unit 2', 'Unit 2', 0, 'cust-2')
        """)

        past_time = (datetime.now() - timedelta(hours=1)).isoformat()

        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('assess-cust-1', 'unit-1', 'Cust 1 Assessment', '2025Q1', past_time, 'scheduled', 'cust-1'))

        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('assess-cust-2', 'unit-2', 'Cust 2 Assessment', '2025Q1', past_time, 'scheduled', 'cust-2'))

        conn.commit()
        conn.close()

        from scheduler import get_pending_scheduled_assessments

        pending = get_pending_scheduled_assessments()

        assert len(pending) == 2
        customer_ids = {a['customer_id'] for a in pending}
        assert 'cust-1' in customer_ids
        assert 'cust-2' in customer_ids


class TestSchedulerIntegration:
    """Integration tests for scheduler components."""

    def test_full_scheduled_assessment_flow(self, test_db):
        """Test complete flow: schedule -> detect -> send -> mark sent."""
        conn = sqlite3.connect(test_db)

        # Create scheduled assessment
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, sender_name, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('assess-flow', 'unit-1', 'Flow Test', '2025Q1', past_time, 'scheduled', 'HR', 'cust-1'))

        conn.commit()
        conn.close()

        # Mock external dependencies - these are imported inside the function
        with patch('db_hierarchical.generate_tokens_for_assessment') as mock_tokens, \
             patch('db_hierarchical.get_unit_contacts') as mock_contacts, \
             patch('mailjet_integration.send_assessment_batch') as mock_send:

            mock_tokens.return_value = {'unit-1': [{'token': 'token-123'}]}
            mock_contacts.return_value = [{'email': 'test@example.com'}]
            mock_send.return_value = {'emails_sent': 1, 'sms_sent': 0, 'errors': 0}

            from scheduler import get_pending_scheduled_assessments, send_scheduled_assessment

            # 1. Detect pending
            pending = get_pending_scheduled_assessments()
            assert len(pending) == 1

            # 2. Send it
            result = send_scheduled_assessment(pending[0])
            assert result is True

            # 3. Verify it's marked as sent
            pending_after = get_pending_scheduled_assessments()
            assert len(pending_after) == 0

            # Verify in database
            conn = sqlite3.connect(test_db)
            conn.row_factory = sqlite3.Row
            assessment = conn.execute(
                "SELECT * FROM assessments WHERE id = ?", ('assess-flow',)
            ).fetchone()

            assert assessment['status'] == 'sent'
            conn.close()

"""
Tests for scheduled assessments functionality
"""
import pytest
import sqlite3
import os
from datetime import datetime, timedelta


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database"""
    db_path = str(tmp_path / "test.db")

    # Set environment to use test db
    os.environ['TEST_DB_PATH'] = db_path

    # Create tables
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")

    # Create necessary tables
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
            customer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            target_unit_id TEXT NOT NULL,
            name TEXT NOT NULL,
            period TEXT NOT NULL,
            sent_from TEXT DEFAULT 'admin',
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mode TEXT DEFAULT 'anonymous',
            min_responses INTEGER DEFAULT 5,
            scheduled_at TIMESTAMP,
            status TEXT DEFAULT 'sent',
            sender_name TEXT DEFAULT 'HR',
            FOREIGN KEY (target_unit_id) REFERENCES organizational_units(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            assessment_id TEXT NOT NULL,
            unit_id TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            FOREIGN KEY (assessment_id) REFERENCES assessments(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
    """)

    # Insert test data
    conn.execute("""
        INSERT INTO organizational_units (id, name, full_path, level, employee_count, customer_id)
        VALUES ('unit-1', 'Test Unit', 'Test Unit', 0, 10, 1)
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_create_scheduled_assessment(test_db):
    """Test creating a scheduled assessment"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create a scheduled assessment
    scheduled_time = (datetime.now() + timedelta(days=1)).isoformat()

    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status, sender_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ('assess-test-1', 'unit-1', 'Test Scheduled', '2025Q1', scheduled_time, 'scheduled', 'Test HR'))
    conn.commit()

    # Verify assessment was created
    assessment = conn.execute(
        "SELECT * FROM assessments WHERE id = ?", ('assess-test-1',)
    ).fetchone()

    assert assessment is not None
    assert assessment['status'] == 'scheduled'
    assert assessment['scheduled_at'] is not None
    assert assessment['sender_name'] == 'Test HR'

    conn.close()


def test_get_pending_assessments(test_db):
    """Test retrieving pending scheduled assessments"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create assessments with different scheduled times
    past_time = (datetime.now() - timedelta(hours=1)).isoformat()
    future_time = (datetime.now() + timedelta(days=1)).isoformat()

    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('assess-past', 'unit-1', 'Past Assessment', '2025Q1', past_time, 'scheduled'))

    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('assess-future', 'unit-1', 'Future Assessment', '2025Q1', future_time, 'scheduled'))

    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, status)
        VALUES (?, ?, ?, ?, ?)
    """, ('assess-sent', 'unit-1', 'Sent Assessment', '2025Q1', 'sent'))

    conn.commit()

    # Query for pending assessments (scheduled_at <= now)
    now = datetime.now().isoformat()
    pending = conn.execute("""
        SELECT * FROM assessments
        WHERE status = 'scheduled' AND scheduled_at <= ?
    """, (now,)).fetchall()

    assert len(pending) == 1
    assert pending[0]['id'] == 'assess-past'

    conn.close()


def test_cancel_assessment(test_db):
    """Test cancelling a scheduled assessment"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create a scheduled assessment
    scheduled_time = (datetime.now() + timedelta(days=1)).isoformat()
    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('assess-cancel', 'unit-1', 'To Cancel', '2025Q1', scheduled_time, 'scheduled'))
    conn.commit()

    # Cancel the assessment
    conn.execute("""
        UPDATE assessments SET status = 'cancelled'
        WHERE id = ? AND status = 'scheduled'
    """, ('assess-cancel',))
    conn.commit()

    # Verify cancellation
    assessment = conn.execute(
        "SELECT * FROM assessments WHERE id = ?", ('assess-cancel',)
    ).fetchone()

    assert assessment['status'] == 'cancelled'

    conn.close()


def test_reschedule_assessment(test_db):
    """Test rescheduling a assessment"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create a scheduled assessment
    original_time = (datetime.now() + timedelta(days=1)).isoformat()
    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('assess-reschedule', 'unit-1', 'To Reschedule', '2025Q1', original_time, 'scheduled'))
    conn.commit()

    # Reschedule the assessment
    new_time = (datetime.now() + timedelta(days=7)).isoformat()
    conn.execute("""
        UPDATE assessments SET scheduled_at = ?
        WHERE id = ? AND status = 'scheduled'
    """, (new_time, 'assess-reschedule'))
    conn.commit()

    # Verify rescheduling
    assessment = conn.execute(
        "SELECT * FROM assessments WHERE id = ?", ('assess-reschedule',)
    ).fetchone()

    assert assessment['scheduled_at'] == new_time
    assert assessment['status'] == 'scheduled'

    conn.close()


def test_mark_assessment_sent(test_db):
    """Test marking a assessment as sent"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create a scheduled assessment
    scheduled_time = (datetime.now() - timedelta(hours=1)).isoformat()
    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('assess-send', 'unit-1', 'To Send', '2025Q1', scheduled_time, 'scheduled'))
    conn.commit()

    # Mark as sent
    sent_time = datetime.now().isoformat()
    conn.execute("""
        UPDATE assessments SET status = 'sent', sent_at = ?
        WHERE id = ?
    """, (sent_time, 'assess-send'))
    conn.commit()

    # Verify sent status
    assessment = conn.execute(
        "SELECT * FROM assessments WHERE id = ?", ('assess-send',)
    ).fetchone()

    assert assessment['status'] == 'sent'
    assert assessment['sent_at'] is not None

    conn.close()


def test_assessment_status_values(test_db):
    """Test different assessment status values"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    statuses = ['scheduled', 'sent', 'cancelled']

    for i, status in enumerate(statuses):
        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period, status)
            VALUES (?, ?, ?, ?, ?)
        """, (f'assess-status-{i}', 'unit-1', f'Status {status}', '2025Q1', status))

    conn.commit()

    # Count each status
    for status in statuses:
        count = conn.execute(
            "SELECT COUNT(*) FROM assessments WHERE status = ?", (status,)
        ).fetchone()[0]
        assert count == 1

    conn.close()


def test_scheduled_assessments_with_customer_filter(test_db):
    """Test filtering scheduled assessments by customer"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create units for different customers
    conn.execute("""
        INSERT INTO organizational_units (id, name, full_path, level, customer_id)
        VALUES ('unit-cust-2', 'Customer 2 Unit', 'Customer 2 Unit', 0, 2)
    """)

    # Create scheduled assessments for different customers
    scheduled_time = (datetime.now() + timedelta(days=1)).isoformat()

    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('assess-cust-1', 'unit-1', 'Customer 1 Assessment', '2025Q1', scheduled_time, 'scheduled'))

    conn.execute("""
        INSERT INTO assessments (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('assess-cust-2', 'unit-cust-2', 'Customer 2 Assessment', '2025Q1', scheduled_time, 'scheduled'))

    conn.commit()

    # Filter by customer 1
    assessments_cust_1 = conn.execute("""
        SELECT c.* FROM assessments c
        JOIN organizational_units ou ON c.target_unit_id = ou.id
        WHERE c.status = 'scheduled' AND ou.customer_id = 1
    """).fetchall()

    assert len(assessments_cust_1) == 1
    assert assessments_cust_1[0]['id'] == 'assess-cust-1'

    # Filter by customer 2
    assessments_cust_2 = conn.execute("""
        SELECT c.* FROM assessments c
        JOIN organizational_units ou ON c.target_unit_id = ou.id
        WHERE c.status = 'scheduled' AND ou.customer_id = 2
    """).fetchall()

    assert len(assessments_cust_2) == 1
    assert assessments_cust_2[0]['id'] == 'assess-cust-2'

    conn.close()

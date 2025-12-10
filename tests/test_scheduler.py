"""
Tests for scheduled campaigns functionality
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
        CREATE TABLE IF NOT EXISTS campaigns (
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
            campaign_id TEXT NOT NULL,
            unit_id TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
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


def test_create_scheduled_campaign(test_db):
    """Test creating a scheduled campaign"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create a scheduled campaign
    scheduled_time = (datetime.now() + timedelta(days=1)).isoformat()

    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, scheduled_at, status, sender_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ('camp-test-1', 'unit-1', 'Test Scheduled', '2025Q1', scheduled_time, 'scheduled', 'Test HR'))
    conn.commit()

    # Verify campaign was created
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?", ('camp-test-1',)
    ).fetchone()

    assert campaign is not None
    assert campaign['status'] == 'scheduled'
    assert campaign['scheduled_at'] is not None
    assert campaign['sender_name'] == 'Test HR'

    conn.close()


def test_get_pending_campaigns(test_db):
    """Test retrieving pending scheduled campaigns"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create campaigns with different scheduled times
    past_time = (datetime.now() - timedelta(hours=1)).isoformat()
    future_time = (datetime.now() + timedelta(days=1)).isoformat()

    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('camp-past', 'unit-1', 'Past Campaign', '2025Q1', past_time, 'scheduled'))

    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('camp-future', 'unit-1', 'Future Campaign', '2025Q1', future_time, 'scheduled'))

    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, status)
        VALUES (?, ?, ?, ?, ?)
    """, ('camp-sent', 'unit-1', 'Sent Campaign', '2025Q1', 'sent'))

    conn.commit()

    # Query for pending campaigns (scheduled_at <= now)
    now = datetime.now().isoformat()
    pending = conn.execute("""
        SELECT * FROM campaigns
        WHERE status = 'scheduled' AND scheduled_at <= ?
    """, (now,)).fetchall()

    assert len(pending) == 1
    assert pending[0]['id'] == 'camp-past'

    conn.close()


def test_cancel_campaign(test_db):
    """Test cancelling a scheduled campaign"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create a scheduled campaign
    scheduled_time = (datetime.now() + timedelta(days=1)).isoformat()
    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('camp-cancel', 'unit-1', 'To Cancel', '2025Q1', scheduled_time, 'scheduled'))
    conn.commit()

    # Cancel the campaign
    conn.execute("""
        UPDATE campaigns SET status = 'cancelled'
        WHERE id = ? AND status = 'scheduled'
    """, ('camp-cancel',))
    conn.commit()

    # Verify cancellation
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?", ('camp-cancel',)
    ).fetchone()

    assert campaign['status'] == 'cancelled'

    conn.close()


def test_reschedule_campaign(test_db):
    """Test rescheduling a campaign"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create a scheduled campaign
    original_time = (datetime.now() + timedelta(days=1)).isoformat()
    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('camp-reschedule', 'unit-1', 'To Reschedule', '2025Q1', original_time, 'scheduled'))
    conn.commit()

    # Reschedule the campaign
    new_time = (datetime.now() + timedelta(days=7)).isoformat()
    conn.execute("""
        UPDATE campaigns SET scheduled_at = ?
        WHERE id = ? AND status = 'scheduled'
    """, (new_time, 'camp-reschedule'))
    conn.commit()

    # Verify rescheduling
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?", ('camp-reschedule',)
    ).fetchone()

    assert campaign['scheduled_at'] == new_time
    assert campaign['status'] == 'scheduled'

    conn.close()


def test_mark_campaign_sent(test_db):
    """Test marking a campaign as sent"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create a scheduled campaign
    scheduled_time = (datetime.now() - timedelta(hours=1)).isoformat()
    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('camp-send', 'unit-1', 'To Send', '2025Q1', scheduled_time, 'scheduled'))
    conn.commit()

    # Mark as sent
    sent_time = datetime.now().isoformat()
    conn.execute("""
        UPDATE campaigns SET status = 'sent', sent_at = ?
        WHERE id = ?
    """, (sent_time, 'camp-send'))
    conn.commit()

    # Verify sent status
    campaign = conn.execute(
        "SELECT * FROM campaigns WHERE id = ?", ('camp-send',)
    ).fetchone()

    assert campaign['status'] == 'sent'
    assert campaign['sent_at'] is not None

    conn.close()


def test_campaign_status_values(test_db):
    """Test different campaign status values"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    statuses = ['scheduled', 'sent', 'cancelled']

    for i, status in enumerate(statuses):
        conn.execute("""
            INSERT INTO campaigns (id, target_unit_id, name, period, status)
            VALUES (?, ?, ?, ?, ?)
        """, (f'camp-status-{i}', 'unit-1', f'Status {status}', '2025Q1', status))

    conn.commit()

    # Count each status
    for status in statuses:
        count = conn.execute(
            "SELECT COUNT(*) FROM campaigns WHERE status = ?", (status,)
        ).fetchone()[0]
        assert count == 1

    conn.close()


def test_scheduled_campaigns_with_customer_filter(test_db):
    """Test filtering scheduled campaigns by customer"""
    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    # Create units for different customers
    conn.execute("""
        INSERT INTO organizational_units (id, name, full_path, level, customer_id)
        VALUES ('unit-cust-2', 'Customer 2 Unit', 'Customer 2 Unit', 0, 2)
    """)

    # Create scheduled campaigns for different customers
    scheduled_time = (datetime.now() + timedelta(days=1)).isoformat()

    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('camp-cust-1', 'unit-1', 'Customer 1 Campaign', '2025Q1', scheduled_time, 'scheduled'))

    conn.execute("""
        INSERT INTO campaigns (id, target_unit_id, name, period, scheduled_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ('camp-cust-2', 'unit-cust-2', 'Customer 2 Campaign', '2025Q1', scheduled_time, 'scheduled'))

    conn.commit()

    # Filter by customer 1
    campaigns_cust_1 = conn.execute("""
        SELECT c.* FROM campaigns c
        JOIN organizational_units ou ON c.target_unit_id = ou.id
        WHERE c.status = 'scheduled' AND ou.customer_id = 1
    """).fetchall()

    assert len(campaigns_cust_1) == 1
    assert campaigns_cust_1[0]['id'] == 'camp-cust-1'

    # Filter by customer 2
    campaigns_cust_2 = conn.execute("""
        SELECT c.* FROM campaigns c
        JOIN organizational_units ou ON c.target_unit_id = ou.id
        WHERE c.status = 'scheduled' AND ou.customer_id = 2
    """).fetchall()

    assert len(campaigns_cust_2) == 1
    assert campaigns_cust_2[0]['id'] == 'camp-cust-2'

    conn.close()

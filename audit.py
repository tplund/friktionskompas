"""
Audit logging system for Friktionskompasset.
Logs important user actions for security, compliance, and debugging.
"""
import sqlite3
import os
from datetime import datetime
from functools import wraps
from flask import request, session, g

# Database path
DB_PATH = os.environ.get('DB_PATH', '/var/data/friktionskompas_v3.db')
if not os.path.exists('/var/data'):
    DB_PATH = 'friktionskompas_v3.db'


def get_audit_db():
    """Get database connection for audit logging."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_audit_tables():
    """Create audit log table if it doesn't exist."""
    with get_audit_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                user_id TEXT,
                username TEXT,
                customer_id TEXT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT
            )
        """)

        # Index for efficient querying
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log(timestamp DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user
            ON audit_log(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_action
            ON audit_log(action)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_customer
            ON audit_log(customer_id)
        """)
        conn.commit()


# Action categories
class AuditAction:
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"

    # Impersonation
    IMPERSONATE_START = "impersonate_start"
    IMPERSONATE_END = "impersonate_end"

    # User management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"

    # Customer management
    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_UPDATED = "customer_updated"
    CUSTOMER_DELETED = "customer_deleted"

    # Organization management
    UNIT_CREATED = "unit_created"
    UNIT_UPDATED = "unit_updated"
    UNIT_DELETED = "unit_deleted"
    UNIT_MOVED = "unit_moved"

    # Assessment management
    ASSESSMENT_CREATED = "assessment_created"
    ASSESSMENT_DELETED = "assessment_deleted"
    ASSESSMENT_SENT = "assessment_sent"

    # Data operations
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"
    DATA_DELETED = "data_deleted"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"

    # Settings
    SETTINGS_CHANGED = "settings_changed"
    BRANDING_CHANGED = "branding_changed"
    DOMAIN_CREATED = "domain_created"
    DOMAIN_UPDATED = "domain_updated"
    DOMAIN_DELETED = "domain_deleted"


def log_action(action: str, entity_type: str = None, entity_id: str = None,
               details: str = None, user_id: str = None, username: str = None,
               customer_id: str = None):
    """
    Log an audit event.

    Args:
        action: The action being performed (use AuditAction constants)
        entity_type: Type of entity affected (user, customer, unit, assessment, etc.)
        entity_id: ID of the affected entity
        details: Additional details about the action
        user_id: Override user ID (defaults to session user)
        username: Override username (defaults to session user)
        customer_id: Override customer ID (defaults to session customer)
    """
    try:
        # Get user info from session if not provided
        if user_id is None:
            user_id = session.get('user_id')
        if username is None:
            username = session.get('username')
        if customer_id is None:
            customer_id = session.get('customer_id')

        # Get request info
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()
            user_agent = request.headers.get('User-Agent', '')[:500]  # Truncate

        with get_audit_db() as conn:
            conn.execute("""
                INSERT INTO audit_log
                (user_id, username, customer_id, action, entity_type, entity_id,
                 details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, customer_id, action, entity_type, entity_id,
                  details, ip_address, user_agent))
            conn.commit()

    except Exception as e:
        # Don't let audit logging failures break the application
        print(f"[AUDIT ERROR] Failed to log action {action}: {e}")


def get_audit_logs(limit: int = 100, offset: int = 0, user_id: str = None,
                   customer_id: str = None, action: str = None,
                   start_date: str = None, end_date: str = None) -> list:
    """
    Retrieve audit logs with optional filtering.

    Args:
        limit: Maximum number of records to return
        offset: Number of records to skip
        user_id: Filter by user ID
        customer_id: Filter by customer ID
        action: Filter by action type
        start_date: Filter by start date (YYYY-MM-DD)
        end_date: Filter by end date (YYYY-MM-DD)

    Returns:
        List of audit log entries
    """
    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []

    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    if customer_id:
        query += " AND customer_id = ?"
        params.append(customer_id)

    if action:
        query += " AND action = ?"
        params.append(action)

    if start_date:
        query += " AND timestamp >= ?"
        params.append(f"{start_date} 00:00:00")

    if end_date:
        query += " AND timestamp <= ?"
        params.append(f"{end_date} 23:59:59")

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_audit_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_audit_log_count(user_id: str = None, customer_id: str = None,
                        action: str = None, start_date: str = None,
                        end_date: str = None) -> int:
    """Get total count of audit logs matching filters."""
    query = "SELECT COUNT(*) FROM audit_log WHERE 1=1"
    params = []

    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    if customer_id:
        query += " AND customer_id = ?"
        params.append(customer_id)

    if action:
        query += " AND action = ?"
        params.append(action)

    if start_date:
        query += " AND timestamp >= ?"
        params.append(f"{start_date} 00:00:00")

    if end_date:
        query += " AND timestamp <= ?"
        params.append(f"{end_date} 23:59:59")

    with get_audit_db() as conn:
        return conn.execute(query, params).fetchone()[0]


def get_recent_actions_for_user(user_id: str, limit: int = 10) -> list:
    """Get recent actions by a specific user."""
    return get_audit_logs(limit=limit, user_id=user_id)


def get_recent_actions_for_entity(entity_type: str, entity_id: str,
                                   limit: int = 20) -> list:
    """Get recent actions on a specific entity."""
    with get_audit_db() as conn:
        rows = conn.execute("""
            SELECT * FROM audit_log
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (entity_type, entity_id, limit)).fetchall()
        return [dict(row) for row in rows]


def get_action_summary(days: int = 30) -> dict:
    """Get summary of actions over the last N days."""
    with get_audit_db() as conn:
        rows = conn.execute("""
            SELECT action, COUNT(*) as count
            FROM audit_log
            WHERE timestamp >= datetime('now', ?)
            GROUP BY action
            ORDER BY count DESC
        """, (f'-{days} days',)).fetchall()
        return {row['action']: row['count'] for row in rows}


def cleanup_old_logs(days: int = 365):
    """Delete audit logs older than N days (GDPR compliance)."""
    with get_audit_db() as conn:
        result = conn.execute("""
            DELETE FROM audit_log
            WHERE timestamp < datetime('now', ?)
        """, (f'-{days} days',))
        deleted = result.rowcount
        conn.commit()

        if deleted > 0:
            log_action(
                AuditAction.DATA_DELETED,
                entity_type="audit_log",
                details=f"Cleaned up {deleted} audit logs older than {days} days"
            )

        return deleted


# Decorator for automatic audit logging
def audit_logged(action: str, entity_type: str = None,
                 get_entity_id=None, get_details=None):
    """
    Decorator to automatically log an action when a function is called.

    Args:
        action: The action to log
        entity_type: Type of entity being affected
        get_entity_id: Function to extract entity ID from function args/kwargs
        get_details: Function to extract details from function args/kwargs

    Example:
        @audit_logged(AuditAction.USER_CREATED, entity_type="user",
                      get_entity_id=lambda args, kwargs: kwargs.get('user_id'))
        def create_user(user_id, name, email):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            entity_id = None
            details = None

            if get_entity_id:
                try:
                    entity_id = get_entity_id(args, kwargs)
                except Exception:
                    pass  # Silently ignore - audit decorator should not break app

            if get_details:
                try:
                    details = get_details(args, kwargs)
                except Exception:
                    pass  # Silently ignore - audit decorator should not break app

            log_action(action, entity_type=entity_type, entity_id=entity_id,
                      details=details)

            return result
        return wrapper
    return decorator


# Initialize tables on import
init_audit_tables()

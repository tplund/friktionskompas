"""
Data Retention & Cleanup for Friktionskompasset
GDPR Phase 2: Automated cleanup of old logs

Retention Policy:
- email_logs: 90 days
- audit_log: 1 year (365 days)
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, Tuple

# Import centralized database functions
from db import get_db_connection, DB_PATH

# Import logging
from logging_config import get_logger

logger = get_logger(__name__)

# Retention periods (in days)
EMAIL_LOGS_RETENTION_DAYS = 90
AUDIT_LOG_RETENTION_DAYS = 365


def cleanup_email_logs(days: int = EMAIL_LOGS_RETENTION_DAYS) -> Dict:
    """
    Delete email_logs older than N days.

    Args:
        days: Number of days to retain (default: 90)

    Returns:
        dict with cleanup stats
    """
    try:
        conn = get_db_connection()
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Count before deletion
        count_before = conn.execute("SELECT COUNT(*) FROM email_logs").fetchone()[0]

        # Delete old records
        result = conn.execute("""
            DELETE FROM email_logs
            WHERE created_at < ?
        """, (cutoff_date,))

        deleted = result.rowcount
        conn.commit()

        # Count after deletion
        count_after = conn.execute("SELECT COUNT(*) FROM email_logs").fetchone()[0]

        conn.close()

        # Log the cleanup action
        if deleted > 0:
            from audit import log_action, AuditAction
            log_action(
                AuditAction.DATA_DELETED,
                entity_type="email_logs",
                details=f"Auto-cleanup: Deleted {deleted} email logs older than {days} days",
                user_id="system",
                username="data_retention_job"
            )

        return {
            'deleted': deleted,
            'remaining': count_after,
            'retention_days': days,
            'cutoff_date': cutoff_date,
            'success': True
        }

    except Exception as e:
        logger.error("Error cleaning email_logs", exc_info=True, extra={'extra_data': {
            'retention_days': days
        }})
        return {
            'deleted': 0,
            'remaining': 0,
            'retention_days': days,
            'error': str(e),
            'success': False
        }


def cleanup_audit_logs(days: int = AUDIT_LOG_RETENTION_DAYS) -> Dict:
    """
    Delete audit_log entries older than N days.

    Args:
        days: Number of days to retain (default: 365)

    Returns:
        dict with cleanup stats
    """
    try:
        conn = get_db_connection()
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Count before deletion
        count_before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

        # Delete old records
        result = conn.execute("""
            DELETE FROM audit_log
            WHERE timestamp < ?
        """, (cutoff_date,))

        deleted = result.rowcount
        conn.commit()

        # Count after deletion
        count_after = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

        conn.close()

        # Log the cleanup action (if any were deleted)
        # We do this AFTER the deletion so we don't delete the log entry we just created
        if deleted > 0:
            from audit import log_action, AuditAction
            log_action(
                AuditAction.DATA_DELETED,
                entity_type="audit_log",
                details=f"Auto-cleanup: Deleted {deleted} audit logs older than {days} days",
                user_id="system",
                username="data_retention_job"
            )

        return {
            'deleted': deleted,
            'remaining': count_after,
            'retention_days': days,
            'cutoff_date': cutoff_date,
            'success': True
        }

    except Exception as e:
        logger.error("Error cleaning audit_log", exc_info=True, extra={'extra_data': {
            'retention_days': days
        }})
        return {
            'deleted': 0,
            'remaining': 0,
            'retention_days': days,
            'error': str(e),
            'success': False
        }


def run_all_cleanups() -> Dict:
    """
    Run all cleanup jobs.

    Returns:
        dict with results from all cleanup jobs
    """
    logger.info("Starting automated cleanup")

    email_result = cleanup_email_logs()
    audit_result = cleanup_audit_logs()

    total_deleted = email_result['deleted'] + audit_result['deleted']

    logger.info("Cleanup completed", extra={'extra_data': {
        'total_deleted': total_deleted,
        'email_logs_deleted': email_result['deleted'],
        'email_logs_remaining': email_result['remaining'],
        'audit_logs_deleted': audit_result['deleted'],
        'audit_logs_remaining': audit_result['remaining']
    }})

    return {
        'email_logs': email_result,
        'audit_log': audit_result,
        'total_deleted': total_deleted,
        'timestamp': datetime.now().isoformat()
    }


def get_cleanup_status() -> Dict:
    """
    Get status of data that would be cleaned up.

    Returns:
        dict with stats about data eligible for cleanup
    """
    try:
        conn = get_db_connection()

        # Email logs stats
        email_cutoff = (datetime.now() - timedelta(days=EMAIL_LOGS_RETENTION_DAYS)).isoformat()
        email_eligible = conn.execute(
            "SELECT COUNT(*) FROM email_logs WHERE created_at < ?",
            (email_cutoff,)
        ).fetchone()[0]
        email_total = conn.execute("SELECT COUNT(*) FROM email_logs").fetchone()[0]

        # Get oldest and newest email log
        email_oldest = conn.execute(
            "SELECT created_at FROM email_logs ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        email_newest = conn.execute(
            "SELECT created_at FROM email_logs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        # Audit logs stats
        audit_cutoff = (datetime.now() - timedelta(days=AUDIT_LOG_RETENTION_DAYS)).isoformat()
        audit_eligible = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE timestamp < ?",
            (audit_cutoff,)
        ).fetchone()[0]
        audit_total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

        # Get oldest and newest audit log
        audit_oldest = conn.execute(
            "SELECT timestamp FROM audit_log ORDER BY timestamp ASC LIMIT 1"
        ).fetchone()
        audit_newest = conn.execute(
            "SELECT timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()

        conn.close()

        return {
            'email_logs': {
                'total': email_total,
                'eligible_for_cleanup': email_eligible,
                'retention_days': EMAIL_LOGS_RETENTION_DAYS,
                'cutoff_date': email_cutoff,
                'oldest': email_oldest[0] if email_oldest else None,
                'newest': email_newest[0] if email_newest else None
            },
            'audit_log': {
                'total': audit_total,
                'eligible_for_cleanup': audit_eligible,
                'retention_days': AUDIT_LOG_RETENTION_DAYS,
                'cutoff_date': audit_cutoff,
                'oldest': audit_oldest[0] if audit_oldest else None,
                'newest': audit_newest[0] if audit_newest else None
            },
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error("Error getting cleanup status", exc_info=True)
        return {
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def get_last_cleanup_run() -> Dict:
    """
    Get info about the last cleanup run from audit log.

    Returns:
        dict with last cleanup timestamp and stats
    """
    try:
        conn = get_db_connection()

        # Find most recent cleanup action
        last_run = conn.execute("""
            SELECT timestamp, details
            FROM audit_log
            WHERE action = 'data_deleted'
            AND entity_type IN ('email_logs', 'audit_log')
            AND username = 'data_retention_job'
            ORDER BY timestamp DESC
            LIMIT 1
        """).fetchone()

        conn.close()

        if last_run:
            return {
                'last_run': last_run['timestamp'],
                'details': last_run['details'],
                'found': True
            }
        else:
            return {
                'last_run': None,
                'details': 'No cleanup has been run yet',
                'found': False
            }

    except Exception as e:
        logger.error("Error getting last cleanup run", exc_info=True)
        return {
            'error': str(e),
            'found': False
        }


if __name__ == "__main__":
    # Test/manual run
    print("=== Data Retention Cleanup ===")
    print()

    # Show status first
    print("Status before cleanup:")
    status = get_cleanup_status()
    print(f"Email logs: {status['email_logs']['total']} total, {status['email_logs']['eligible_for_cleanup']} eligible for cleanup")
    print(f"Audit logs: {status['audit_log']['total']} total, {status['audit_log']['eligible_for_cleanup']} eligible for cleanup")
    print()

    # Run cleanup
    results = run_all_cleanups()
    print()
    print("Cleanup complete!")
    print(f"Total deleted: {results['total_deleted']}")

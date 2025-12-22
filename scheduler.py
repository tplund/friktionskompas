"""
Scheduler for Friktionskompasset
Kører planlagte målinger automatisk
GDPR Phase 2: Includes daily data retention cleanup
"""
import threading
import time
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict

# Import centralized database functions
from db import get_db_connection, DB_PATH

# Import logging
from logging_config import get_logger

logger = get_logger(__name__)

# Global scheduler state
_scheduler_thread = None
_scheduler_running = False
_last_cleanup_date = None  # Track last cleanup run (date only)


def get_pending_scheduled_assessments() -> List[Dict]:
    """Hent alle scheduled assessments der er klar til at blive sendt"""
    try:
        conn = get_db_connection()
        now = datetime.now().isoformat()

        assessments = conn.execute("""
            SELECT c.*, ou.name as unit_name
            FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.status = 'scheduled'
            AND c.scheduled_at <= ?
            ORDER BY c.scheduled_at ASC
        """, (now,)).fetchall()

        conn.close()
        return [dict(c) for c in assessments]
    except Exception as e:
        logger.error("Error getting pending assessments", exc_info=True)
        return []


def send_scheduled_assessment(assessment: Dict) -> bool:
    """Send en scheduled assessment"""
    from db_hierarchical import (
        get_db, generate_tokens_for_assessment,
        get_unit_contacts
    )
    from mailjet_integration import send_assessment_batch

    assessment_id = assessment['id']
    assessment_name = assessment['name']
    sender_name = assessment.get('sender_name', 'HR')

    logger.info("Sending scheduled assessment", extra={'extra_data': {
        'assessment_id': assessment_id,
        'assessment_name': assessment_name
    }})

    try:
        # Generer tokens
        tokens_by_unit = generate_tokens_for_assessment(assessment_id)

        if not tokens_by_unit:
            logger.warning("No tokens generated for assessment", extra={'extra_data': {
                'assessment_id': assessment_id
            }})
            mark_assessment_sent(assessment_id)
            return True

        # Send til hver unit
        total_sent = 0
        total_errors = 0

        for unit_id, tokens in tokens_by_unit.items():
            contacts = get_unit_contacts(unit_id)
            if not contacts:
                continue

            # Match tokens med kontakter
            results = send_assessment_batch(contacts, tokens, assessment_name, sender_name)
            total_sent += results['emails_sent'] + results['sms_sent']
            total_errors += results['errors']

        # Marker som sendt
        mark_assessment_sent(assessment_id)

        total_tokens = sum(len(t) for t in tokens_by_unit.values())
        logger.info("Assessment sent successfully", extra={'extra_data': {
            'assessment_id': assessment_id,
            'total_tokens': total_tokens,
            'total_sent': total_sent,
            'total_errors': total_errors
        }})

        return True

    except Exception as e:
        logger.error("Error sending assessment", exc_info=True, extra={'extra_data': {
            'assessment_id': assessment_id
        }})
        mark_assessment_error(assessment_id, str(e))
        return False


def mark_assessment_sent(assessment_id: str):
    """Marker en assessment som sendt"""
    try:
        conn = get_db_connection()
        conn.execute("""
            UPDATE assessments
            SET status = 'sent', sent_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), assessment_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error marking assessment sent", exc_info=True, extra={'extra_data': {
            'assessment_id': assessment_id
        }})


def mark_assessment_error(assessment_id: str, error_message: str):
    """Marker en assessment som fejlet"""
    try:
        conn = get_db_connection()
        # Gem error i en ny kolonne eller bare hold den som scheduled
        # For nu, lad den være scheduled så den kan prøves igen
        logger.error("Assessment failed", extra={'extra_data': {
            'assessment_id': assessment_id,
            'error_message': error_message
        }})
        conn.close()
    except Exception as e:
        logger.error("Error marking assessment error", exc_info=True, extra={'extra_data': {
            'assessment_id': assessment_id
        }})


def run_daily_cleanup():
    """Run data retention cleanup job (GDPR compliance)"""
    global _last_cleanup_date

    try:
        from data_retention import run_all_cleanups

        logger.info("Running daily data retention cleanup")
        results = run_all_cleanups()

        _last_cleanup_date = datetime.now().date()

        logger.info("Cleanup complete", extra={'extra_data': {
            'total_deleted': results['total_deleted']
        }})
        return results

    except Exception as e:
        logger.error("Error running cleanup", exc_info=True)
        return None


def should_run_cleanup() -> bool:
    """Check if cleanup should run today"""
    global _last_cleanup_date

    today = datetime.now().date()

    # Run if never run, or if last run was not today
    if _last_cleanup_date is None or _last_cleanup_date < today:
        return True

    return False


def scheduler_loop():
    """Hovedloop for scheduler - tjekker hvert minut"""
    global _scheduler_running

    logger.info("Scheduler started")

    # Variables for cleanup scheduling
    cleanup_hour = 3  # Run cleanup at 3 AM
    cleanup_checked_today = False

    while _scheduler_running:
        try:
            current_time = datetime.now()

            # Check for scheduled assessments
            pending = get_pending_scheduled_assessments()

            if pending:
                logger.info("Found scheduled assessments to send", extra={'extra_data': {
                    'count': len(pending)
                }})

                for assessment in pending:
                    send_scheduled_assessment(assessment)

            # Check if it's time to run cleanup (once per day at cleanup_hour)
            if current_time.hour == cleanup_hour and should_run_cleanup():
                if not cleanup_checked_today:
                    run_daily_cleanup()
                    cleanup_checked_today = True
            elif current_time.hour != cleanup_hour:
                # Reset flag when we're past the cleanup hour
                cleanup_checked_today = False

        except Exception as e:
            logger.error("Error in scheduler loop", exc_info=True)

        # Vent 60 sekunder før næste check
        for _ in range(60):
            if not _scheduler_running:
                break
            time.sleep(1)

    logger.info("Scheduler stopped")


def start_scheduler():
    """Start scheduler i baggrunden"""
    global _scheduler_thread, _scheduler_running

    if _scheduler_running:
        logger.info("Scheduler already running")
        return

    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Scheduler background thread started")


def stop_scheduler():
    """Stop scheduler"""
    global _scheduler_running
    _scheduler_running = False
    logger.info("Scheduler stop requested")


def get_scheduled_assessments() -> List[Dict]:
    """Hent alle scheduled (ikke endnu sendte) assessments"""
    try:
        conn = get_db_connection()

        assessments = conn.execute("""
            SELECT c.*, ou.name as unit_name, ou.full_path
            FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.status = 'scheduled'
            ORDER BY c.scheduled_at ASC
        """).fetchall()

        conn.close()
        return [dict(c) for c in assessments]
    except Exception as e:
        logger.error("Error getting scheduled assessments", exc_info=True)
        return []


def cancel_scheduled_assessment(assessment_id: str) -> bool:
    """Annuller en scheduled assessment"""
    try:
        conn = get_db_connection()

        # Tjek at den er scheduled (ikke allerede sendt)
        assessment = conn.execute("""
            SELECT status FROM assessments WHERE id = ?
        """, (assessment_id,)).fetchone()

        if not assessment or assessment['status'] != 'scheduled':
            conn.close()
            return False

        conn.execute("""
            UPDATE assessments SET status = 'cancelled'
            WHERE id = ? AND status = 'scheduled'
        """, (assessment_id,))
        conn.commit()
        conn.close()

        logger.info("Assessment cancelled", extra={'extra_data': {
            'assessment_id': assessment_id
        }})
        return True

    except Exception as e:
        logger.error("Error cancelling assessment", exc_info=True, extra={'extra_data': {
            'assessment_id': assessment_id
        }})
        return False


def reschedule_assessment(assessment_id: str, new_scheduled_at: datetime) -> bool:
    """Ændr tidspunkt for en scheduled assessment"""
    try:
        conn = get_db_connection()

        # Tjek at den er scheduled
        assessment = conn.execute("""
            SELECT status FROM assessments WHERE id = ?
        """, (assessment_id,)).fetchone()

        if not assessment or assessment['status'] != 'scheduled':
            conn.close()
            return False

        conn.execute("""
            UPDATE assessments SET scheduled_at = ?
            WHERE id = ? AND status = 'scheduled'
        """, (new_scheduled_at.isoformat(), assessment_id))
        conn.commit()
        conn.close()

        logger.info("Assessment rescheduled", extra={'extra_data': {
            'assessment_id': assessment_id,
            'new_scheduled_at': new_scheduled_at.isoformat()
        }})
        return True

    except Exception as e:
        logger.error("Error rescheduling assessment", exc_info=True, extra={'extra_data': {
            'assessment_id': assessment_id
        }})
        return False


if __name__ == "__main__":
    # Test scheduler
    print("Testing scheduler...")

    pending = get_pending_scheduled_assessments()
    print(f"Pending assessments: {len(pending)}")

    scheduled = get_scheduled_assessments()
    print(f"Scheduled assessments: {len(scheduled)}")
    for c in scheduled:
        print(f"  - {c['name']} @ {c['scheduled_at']}")

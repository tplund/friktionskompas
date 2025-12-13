"""
Scheduler for Friktionskompasset
Kører planlagte målinger automatisk
"""
import threading
import time
import sqlite3
import os
from datetime import datetime
from typing import List, Dict

# Database path (same logic as db_hierarchical.py)
RENDER_DISK_PATH = "/var/data"
if os.path.exists(RENDER_DISK_PATH):
    DB_PATH = os.path.join(RENDER_DISK_PATH, "friktionskompas_v3.db")
else:
    DB_PATH = "friktionskompas_v3.db"

# Global scheduler state
_scheduler_thread = None
_scheduler_running = False


def get_db_connection():
    """Get database connection with foreign keys enabled"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
        print(f"[Scheduler] Error getting pending assessments: {e}")
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

    print(f"[Scheduler] Sending scheduled assessment: {assessment_name} (ID: {assessment_id})")

    try:
        # Generer tokens
        tokens_by_unit = generate_tokens_for_assessment(assessment_id)

        if not tokens_by_unit:
            print(f"[Scheduler] No tokens generated for assessment {assessment_id}")
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
        print(f"[Scheduler] Assessment {assessment_id} sent: {total_tokens} tokens, {total_sent} emails, {total_errors} errors")

        return True

    except Exception as e:
        print(f"[Scheduler] Error sending assessment {assessment_id}: {e}")
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
        print(f"[Scheduler] Error marking assessment sent: {e}")


def mark_assessment_error(assessment_id: str, error_message: str):
    """Marker en assessment som fejlet"""
    try:
        conn = get_db_connection()
        # Gem error i en ny kolonne eller bare hold den som scheduled
        # For nu, lad den være scheduled så den kan prøves igen
        print(f"[Scheduler] Assessment {assessment_id} failed: {error_message}")
        conn.close()
    except Exception as e:
        print(f"[Scheduler] Error marking assessment error: {e}")


def scheduler_loop():
    """Hovedloop for scheduler - tjekker hvert minut"""
    global _scheduler_running

    print("[Scheduler] Started")

    while _scheduler_running:
        try:
            # Hent pending assessments
            pending = get_pending_scheduled_assessments()

            if pending:
                print(f"[Scheduler] Found {len(pending)} scheduled assessments to send")

                for assessment in pending:
                    send_scheduled_assessment(assessment)

        except Exception as e:
            print(f"[Scheduler] Error in loop: {e}")

        # Vent 60 sekunder før næste check
        for _ in range(60):
            if not _scheduler_running:
                break
            time.sleep(1)

    print("[Scheduler] Stopped")


def start_scheduler():
    """Start scheduler i baggrunden"""
    global _scheduler_thread, _scheduler_running

    if _scheduler_running:
        print("[Scheduler] Already running")
        return

    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    _scheduler_thread.start()
    print("[Scheduler] Background thread started")


def stop_scheduler():
    """Stop scheduler"""
    global _scheduler_running
    _scheduler_running = False
    print("[Scheduler] Stop requested")


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
        print(f"[Scheduler] Error getting scheduled assessments: {e}")
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

        print(f"[Scheduler] Assessment {assessment_id} cancelled")
        return True

    except Exception as e:
        print(f"[Scheduler] Error cancelling assessment: {e}")
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

        print(f"[Scheduler] Assessment {assessment_id} rescheduled to {new_scheduled_at}")
        return True

    except Exception as e:
        print(f"[Scheduler] Error rescheduling assessment: {e}")
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

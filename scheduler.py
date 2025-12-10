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


def get_pending_scheduled_campaigns() -> List[Dict]:
    """Hent alle scheduled campaigns der er klar til at blive sendt"""
    try:
        conn = get_db_connection()
        now = datetime.now().isoformat()

        campaigns = conn.execute("""
            SELECT c.*, ou.name as unit_name
            FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.status = 'scheduled'
            AND c.scheduled_at <= ?
            ORDER BY c.scheduled_at ASC
        """, (now,)).fetchall()

        conn.close()
        return [dict(c) for c in campaigns]
    except Exception as e:
        print(f"[Scheduler] Error getting pending campaigns: {e}")
        return []


def send_scheduled_campaign(campaign: Dict) -> bool:
    """Send en scheduled campaign"""
    from db_hierarchical import (
        get_db, generate_tokens_for_campaign,
        get_unit_contacts
    )
    from mailjet_integration import send_campaign_batch

    campaign_id = campaign['id']
    campaign_name = campaign['name']
    sender_name = campaign.get('sender_name', 'HR')

    print(f"[Scheduler] Sending scheduled campaign: {campaign_name} (ID: {campaign_id})")

    try:
        # Generer tokens
        tokens_by_unit = generate_tokens_for_campaign(campaign_id)

        if not tokens_by_unit:
            print(f"[Scheduler] No tokens generated for campaign {campaign_id}")
            mark_campaign_sent(campaign_id)
            return True

        # Send til hver unit
        total_sent = 0
        total_errors = 0

        for unit_id, tokens in tokens_by_unit.items():
            contacts = get_unit_contacts(unit_id)
            if not contacts:
                continue

            # Match tokens med kontakter
            results = send_campaign_batch(contacts, tokens, campaign_name, sender_name)
            total_sent += results['emails_sent'] + results['sms_sent']
            total_errors += results['errors']

        # Marker som sendt
        mark_campaign_sent(campaign_id)

        total_tokens = sum(len(t) for t in tokens_by_unit.values())
        print(f"[Scheduler] Campaign {campaign_id} sent: {total_tokens} tokens, {total_sent} emails, {total_errors} errors")

        return True

    except Exception as e:
        print(f"[Scheduler] Error sending campaign {campaign_id}: {e}")
        mark_campaign_error(campaign_id, str(e))
        return False


def mark_campaign_sent(campaign_id: str):
    """Marker en campaign som sendt"""
    try:
        conn = get_db_connection()
        conn.execute("""
            UPDATE campaigns
            SET status = 'sent', sent_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), campaign_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Scheduler] Error marking campaign sent: {e}")


def mark_campaign_error(campaign_id: str, error_message: str):
    """Marker en campaign som fejlet"""
    try:
        conn = get_db_connection()
        # Gem error i en ny kolonne eller bare hold den som scheduled
        # For nu, lad den være scheduled så den kan prøves igen
        print(f"[Scheduler] Campaign {campaign_id} failed: {error_message}")
        conn.close()
    except Exception as e:
        print(f"[Scheduler] Error marking campaign error: {e}")


def scheduler_loop():
    """Hovedloop for scheduler - tjekker hvert minut"""
    global _scheduler_running

    print("[Scheduler] Started")

    while _scheduler_running:
        try:
            # Hent pending campaigns
            pending = get_pending_scheduled_campaigns()

            if pending:
                print(f"[Scheduler] Found {len(pending)} scheduled campaigns to send")

                for campaign in pending:
                    send_scheduled_campaign(campaign)

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


def get_scheduled_campaigns() -> List[Dict]:
    """Hent alle scheduled (ikke endnu sendte) campaigns"""
    try:
        conn = get_db_connection()

        campaigns = conn.execute("""
            SELECT c.*, ou.name as unit_name, ou.full_path
            FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            WHERE c.status = 'scheduled'
            ORDER BY c.scheduled_at ASC
        """).fetchall()

        conn.close()
        return [dict(c) for c in campaigns]
    except Exception as e:
        print(f"[Scheduler] Error getting scheduled campaigns: {e}")
        return []


def cancel_scheduled_campaign(campaign_id: str) -> bool:
    """Annuller en scheduled campaign"""
    try:
        conn = get_db_connection()

        # Tjek at den er scheduled (ikke allerede sendt)
        campaign = conn.execute("""
            SELECT status FROM campaigns WHERE id = ?
        """, (campaign_id,)).fetchone()

        if not campaign or campaign['status'] != 'scheduled':
            conn.close()
            return False

        conn.execute("""
            UPDATE campaigns SET status = 'cancelled'
            WHERE id = ? AND status = 'scheduled'
        """, (campaign_id,))
        conn.commit()
        conn.close()

        print(f"[Scheduler] Campaign {campaign_id} cancelled")
        return True

    except Exception as e:
        print(f"[Scheduler] Error cancelling campaign: {e}")
        return False


def reschedule_campaign(campaign_id: str, new_scheduled_at: datetime) -> bool:
    """Ændr tidspunkt for en scheduled campaign"""
    try:
        conn = get_db_connection()

        # Tjek at den er scheduled
        campaign = conn.execute("""
            SELECT status FROM campaigns WHERE id = ?
        """, (campaign_id,)).fetchone()

        if not campaign or campaign['status'] != 'scheduled':
            conn.close()
            return False

        conn.execute("""
            UPDATE campaigns SET scheduled_at = ?
            WHERE id = ? AND status = 'scheduled'
        """, (new_scheduled_at.isoformat(), campaign_id))
        conn.commit()
        conn.close()

        print(f"[Scheduler] Campaign {campaign_id} rescheduled to {new_scheduled_at}")
        return True

    except Exception as e:
        print(f"[Scheduler] Error rescheduling campaign: {e}")
        return False


if __name__ == "__main__":
    # Test scheduler
    print("Testing scheduler...")

    pending = get_pending_scheduled_campaigns()
    print(f"Pending campaigns: {len(pending)}")

    scheduled = get_scheduled_campaigns()
    print(f"Scheduled campaigns: {len(scheduled)}")
    for c in scheduled:
        print(f"  - {c['name']} @ {c['scheduled_at']}")

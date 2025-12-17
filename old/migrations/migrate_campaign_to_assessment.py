"""
Migration: Rename 'campaign' to 'assessment' in entire database

This migration:
1. Renames campaigns table to assessments
2. Renames campaign_modes table to assessment_modes
3. Renames campaign_id columns to assessment_id in all related tables
4. Updates indexes

IMPORTANT: Take backup before running!
"""
import sqlite3
import os
import shutil
from datetime import datetime

# Database path
RENDER_DISK_PATH = "/var/data"
if os.path.exists(RENDER_DISK_PATH):
    DB_PATH = os.path.join(RENDER_DISK_PATH, "friktionskompas_v3.db")
else:
    DB_PATH = "friktionskompas_v3.db"


def backup_database():
    """Create backup before migration"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def migrate_campaign_to_assessment():
    """Execute migration from campaign to assessment"""

    # Backup first
    backup_path = backup_database()

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        # Disable foreign keys temporarily
        conn.execute("PRAGMA foreign_keys=OFF")

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

        print("Step 1: Renaming campaigns table to assessments...")
        conn.execute("ALTER TABLE campaigns RENAME TO assessments")

        print("Step 2: Renaming campaign_modes table to assessment_modes...")
        conn.execute("ALTER TABLE campaign_modes RENAME TO assessment_modes")

        print("Step 3: Renaming campaign_id columns in tokens...")
        conn.execute("""
            CREATE TABLE tokens_new (
                token TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                respondent_type TEXT DEFAULT 'employee',
                respondent_name TEXT,
                is_used INTEGER DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            INSERT INTO tokens_new (token, assessment_id, unit_id, respondent_type, respondent_name, is_used, used_at, created_at)
            SELECT token, campaign_id, unit_id, respondent_type, respondent_name, is_used, used_at, created_at
            FROM tokens
        """)
        conn.execute("DROP TABLE tokens")
        conn.execute("ALTER TABLE tokens_new RENAME TO tokens")

        print("Step 4: Renaming campaign_id columns in responses...")
        conn.execute("""
            CREATE TABLE responses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                comment TEXT,
                category_comment TEXT,
                respondent_type TEXT DEFAULT 'employee',
                respondent_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)
        conn.execute("""
            INSERT INTO responses_new (id, assessment_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at)
            SELECT id, campaign_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at
            FROM responses
        """)
        conn.execute("DROP TABLE responses")
        conn.execute("ALTER TABLE responses_new RENAME TO responses")

        print("Step 5: Renaming campaign_id columns in substitution_patterns...")
        conn.execute("""
            CREATE TABLE substitution_patterns_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                respondent_type TEXT NOT NULL,
                reported_field TEXT NOT NULL,
                likely_actual_field TEXT NOT NULL,
                confidence REAL,
                reasoning TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            INSERT INTO substitution_patterns_new (id, assessment_id, unit_id, respondent_type, reported_field, likely_actual_field, confidence, reasoning, detected_at)
            SELECT id, campaign_id, unit_id, respondent_type, reported_field, likely_actual_field, confidence, reasoning, detected_at
            FROM substitution_patterns
        """)
        conn.execute("DROP TABLE substitution_patterns")
        conn.execute("ALTER TABLE substitution_patterns_new RENAME TO substitution_patterns")

        print("Step 6: Renaming campaign_id columns in data_consent...")
        conn.execute("""
            CREATE TABLE data_consent_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id TEXT NOT NULL,
                respondent_name TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                consent_given INTEGER DEFAULT 1,
                consent_given_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                withdrawn INTEGER DEFAULT 0,
                withdrawn_at TIMESTAMP,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
                UNIQUE(assessment_id, respondent_name)
            )
        """)
        conn.execute("""
            INSERT INTO data_consent_new (id, assessment_id, respondent_name, unit_id, consent_given, consent_given_at, withdrawn, withdrawn_at)
            SELECT id, campaign_id, respondent_name, unit_id, consent_given, consent_given_at, withdrawn, withdrawn_at
            FROM data_consent
        """)
        conn.execute("DROP TABLE data_consent")
        conn.execute("ALTER TABLE data_consent_new RENAME TO data_consent")

        print("Step 7: Renaming campaign_id columns in email_logs...")
        conn.execute("""
            CREATE TABLE email_logs_new (
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            INSERT INTO email_logs_new (id, message_id, to_email, subject, email_type, status, assessment_id, token, error_message, delivered_at, opened_at, clicked_at, bounced_at, created_at)
            SELECT id, message_id, to_email, subject, email_type, status, campaign_id, token, error_message, delivered_at, opened_at, clicked_at, bounced_at, created_at
            FROM email_logs
        """)
        conn.execute("DROP TABLE email_logs")
        conn.execute("ALTER TABLE email_logs_new RENAME TO email_logs")

        print("Step 8: Recreating indexes...")
        # Drop old indexes (if they exist)
        for idx in ['idx_tokens_campaign_unit', 'idx_responses_campaign_unit',
                    'idx_substitution_patterns_campaign', 'idx_consent_campaign',
                    'idx_campaigns_target_unit', 'idx_campaigns_created_at', 'idx_campaigns_status']:
            try:
                conn.execute(f"DROP INDEX IF EXISTS {idx}")
            except:
                pass

        # Create new indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_assessment_unit ON tokens(assessment_id, unit_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_respondent_type ON tokens(respondent_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_assessment_unit ON responses(assessment_id, unit_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_respondent_type ON responses(respondent_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_substitution_patterns_assessment ON substitution_patterns(assessment_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_consent_assessment ON data_consent(assessment_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assessments_target_unit ON assessments(target_unit_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assessments_created_at ON assessments(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status)")

        # Commit transaction
        conn.execute("COMMIT")

        # Re-enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

        print("\nMigration completed successfully!")
        print(f"  Backup saved: {backup_path}")

        # Verify
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        print("\nTables after migration:")
        for t in tables:
            print(f"  - {t['name']}")

    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"\nMigration failed: {e}")
        print(f"  Database unchanged. Backup: {backup_path}")
        raise
    finally:
        conn.close()


def verify_migration():
    """Verify migration is correct"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    print("\nVerification of migration:")

    # Check that assessments table exists
    assessments = conn.execute("SELECT COUNT(*) as cnt FROM assessments").fetchone()
    print(f"  assessments table: {assessments['cnt']} rows")

    # Check that responses has assessment_id
    responses = conn.execute("SELECT COUNT(*) as cnt FROM responses").fetchone()
    print(f"  responses table: {responses['cnt']} rows")

    # Check that tokens has assessment_id
    tokens = conn.execute("SELECT COUNT(*) as cnt FROM tokens").fetchone()
    print(f"  tokens table: {tokens['cnt']} rows")

    # Check column names
    print("\n  responses columns:", [c[1] for c in conn.execute('PRAGMA table_info(responses)').fetchall()])
    print("  tokens columns:", [c[1] for c in conn.execute('PRAGMA table_info(tokens)').fetchall()])

    # Check that old tables are gone
    old_tables = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('campaigns', 'campaign_modes')
    """).fetchall()

    if old_tables:
        print(f"\n  WARNING: Old tables still exist: {[t['name'] for t in old_tables]}")
    else:
        print("\n  All old tables removed")

    conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_migration()
    elif len(sys.argv) > 1 and sys.argv[1] == "--yes":
        migrate_campaign_to_assessment()
        verify_migration()
    else:
        print("=" * 60)
        print("Migration: campaign -> assessment")
        print("=" * 60)
        print(f"\nDatabase: {DB_PATH}")
        print("\nThis migration renames:")
        print("  - campaigns -> assessments")
        print("  - campaign_modes -> assessment_modes")
        print("  - campaign_id -> assessment_id (in all tables)")
        print("\nRun with --yes to execute migration")
        print("Run with --verify to check migration status")

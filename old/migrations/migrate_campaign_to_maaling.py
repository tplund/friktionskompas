"""
Migration: Omdøb 'campaign' til 'maaling' i hele databasen

Denne migration:
1. Opretter nye tabeller med 'maaling' navngivning
2. Kopierer data fra gamle tabeller
3. Sletter gamle tabeller
4. Opdaterer indexes

VIGTIGT: Tag backup før kørsel!
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
    """Opret backup før migration"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup oprettet: {backup_path}")
    return backup_path


def migrate_campaign_to_maaling():
    """Udfør migration fra campaign til maaling"""

    # Backup først
    backup_path = backup_database()

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        # Disable foreign keys midlertidigt
        conn.execute("PRAGMA foreign_keys=OFF")

        # Start transaction
        conn.execute("BEGIN TRANSACTION")

        print("Step 1: Omdøber campaigns tabel til maalinger...")
        conn.execute("ALTER TABLE campaigns RENAME TO maalinger")

        print("Step 2: Omdøber campaign_modes tabel til maaling_modes...")
        conn.execute("ALTER TABLE campaign_modes RENAME TO maaling_modes")

        print("Step 3: Omdøber campaign_id kolonner i tokens...")
        # SQLite kan ikke rename kolonner direkte, så vi skal genskabe tabellen
        conn.execute("""
            CREATE TABLE tokens_new (
                token TEXT PRIMARY KEY,
                maaling_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                respondent_type TEXT DEFAULT 'employee',
                respondent_name TEXT,
                is_used INTEGER DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (maaling_id) REFERENCES maalinger(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            INSERT INTO tokens_new (token, maaling_id, unit_id, respondent_type, respondent_name, is_used, used_at, created_at)
            SELECT token, campaign_id, unit_id, respondent_type, respondent_name, is_used, used_at, created_at
            FROM tokens
        """)
        conn.execute("DROP TABLE tokens")
        conn.execute("ALTER TABLE tokens_new RENAME TO tokens")

        print("Step 4: Omdøber campaign_id kolonner i responses...")
        conn.execute("""
            CREATE TABLE responses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                maaling_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                comment TEXT,
                category_comment TEXT,
                respondent_type TEXT DEFAULT 'employee',
                respondent_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (maaling_id) REFERENCES maalinger(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)
        conn.execute("""
            INSERT INTO responses_new (id, maaling_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at)
            SELECT id, campaign_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at
            FROM responses
        """)
        conn.execute("DROP TABLE responses")
        conn.execute("ALTER TABLE responses_new RENAME TO responses")

        print("Step 5: Omdøber campaign_id kolonner i substitution_patterns...")
        conn.execute("""
            CREATE TABLE substitution_patterns_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                maaling_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                respondent_type TEXT NOT NULL,
                reported_field TEXT NOT NULL,
                likely_actual_field TEXT NOT NULL,
                confidence REAL,
                reasoning TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (maaling_id) REFERENCES maalinger(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            INSERT INTO substitution_patterns_new (id, maaling_id, unit_id, respondent_type, reported_field, likely_actual_field, confidence, reasoning, detected_at)
            SELECT id, campaign_id, unit_id, respondent_type, reported_field, likely_actual_field, confidence, reasoning, detected_at
            FROM substitution_patterns
        """)
        conn.execute("DROP TABLE substitution_patterns")
        conn.execute("ALTER TABLE substitution_patterns_new RENAME TO substitution_patterns")

        print("Step 6: Omdøber campaign_id kolonner i data_consent...")
        conn.execute("""
            CREATE TABLE data_consent_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                maaling_id TEXT NOT NULL,
                respondent_name TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                consent_given INTEGER DEFAULT 1,
                consent_given_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                withdrawn INTEGER DEFAULT 0,
                withdrawn_at TIMESTAMP,
                FOREIGN KEY (maaling_id) REFERENCES maalinger(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
                UNIQUE(maaling_id, respondent_name)
            )
        """)
        conn.execute("""
            INSERT INTO data_consent_new (id, maaling_id, respondent_name, unit_id, consent_given, consent_given_at, withdrawn, withdrawn_at)
            SELECT id, campaign_id, respondent_name, unit_id, consent_given, consent_given_at, withdrawn, withdrawn_at
            FROM data_consent
        """)
        conn.execute("DROP TABLE data_consent")
        conn.execute("ALTER TABLE data_consent_new RENAME TO data_consent")

        print("Step 7: Omdøber campaign_id kolonner i email_logs...")
        conn.execute("""
            CREATE TABLE email_logs_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                to_email TEXT NOT NULL,
                subject TEXT,
                email_type TEXT DEFAULT 'invitation',
                status TEXT DEFAULT 'sent',
                maaling_id TEXT,
                token TEXT,
                error_message TEXT,
                delivered_at TIMESTAMP,
                opened_at TIMESTAMP,
                clicked_at TIMESTAMP,
                bounced_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (maaling_id) REFERENCES maalinger(id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            INSERT INTO email_logs_new (id, message_id, to_email, subject, email_type, status, maaling_id, token, error_message, delivered_at, opened_at, clicked_at, bounced_at, created_at)
            SELECT id, message_id, to_email, subject, email_type, status, campaign_id, token, error_message, delivered_at, opened_at, clicked_at, bounced_at, created_at
            FROM email_logs
        """)
        conn.execute("DROP TABLE email_logs")
        conn.execute("ALTER TABLE email_logs_new RENAME TO email_logs")

        print("Step 8: Genskaber indexes...")
        # Drop gamle indexes (hvis de eksisterer)
        for idx in ['idx_tokens_campaign_unit', 'idx_responses_campaign_unit',
                    'idx_substitution_patterns_campaign', 'idx_consent_campaign',
                    'idx_campaigns_target_unit', 'idx_campaigns_created_at', 'idx_campaigns_status']:
            try:
                conn.execute(f"DROP INDEX IF EXISTS {idx}")
            except:
                pass

        # Opret nye indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_maaling_unit ON tokens(maaling_id, unit_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_respondent_type ON tokens(respondent_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_maaling_unit ON responses(maaling_id, unit_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_respondent_type ON responses(respondent_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_substitution_patterns_maaling ON substitution_patterns(maaling_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_consent_maaling ON data_consent(maaling_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_maalinger_target_unit ON maalinger(target_unit_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_maalinger_created_at ON maalinger(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_maalinger_status ON maalinger(status)")

        # Commit transaction
        conn.execute("COMMIT")

        # Re-enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

        print("\n✓ Migration gennemført!")
        print(f"  Backup gemt: {backup_path}")

        # Verificer
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        print("\nTabeller efter migration:")
        for t in tables:
            print(f"  - {t['name']}")

    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"\n✗ Migration fejlede: {e}")
        print(f"  Database uændret. Backup: {backup_path}")
        raise
    finally:
        conn.close()


def verify_migration():
    """Verificer at migration er korrekt"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    print("\nVerificering af migration:")

    # Tjek at maalinger tabel eksisterer
    maalinger = conn.execute("SELECT COUNT(*) as cnt FROM maalinger").fetchone()
    print(f"  maalinger tabel: {maalinger['cnt']} rækker")

    # Tjek at responses har maaling_id
    responses = conn.execute("SELECT COUNT(*) as cnt FROM responses").fetchone()
    print(f"  responses tabel: {responses['cnt']} rækker")

    # Tjek at tokens har maaling_id
    tokens = conn.execute("SELECT COUNT(*) as cnt FROM tokens").fetchone()
    print(f"  tokens tabel: {tokens['cnt']} rækker")

    # Tjek at gamle tabeller er væk
    old_tables = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('campaigns', 'campaign_modes')
    """).fetchall()

    if old_tables:
        print(f"\n  ⚠ Gamle tabeller findes stadig: {[t['name'] for t in old_tables]}")
    else:
        print("\n  ✓ Alle gamle tabeller fjernet")

    conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_migration()
    else:
        print("=" * 60)
        print("Migration: campaign -> maaling")
        print("=" * 60)
        print(f"\nDatabase: {DB_PATH}")
        print("\nDenne migration omdøber:")
        print("  - campaigns -> maalinger")
        print("  - campaign_modes -> maaling_modes")
        print("  - campaign_id -> maaling_id (i alle tabeller)")
        print("\nEr du sikker? (ja/nej)")

        answer = input().strip().lower()
        if answer == "ja":
            migrate_campaign_to_maaling()
            verify_migration()
        else:
            print("Migration afbrudt.")

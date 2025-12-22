"""
Migration: Convert all 1-5 Likert scale responses to 1-7 scale.

This migration:
1. Backs up the database
2. Converts existing scores using: new = round(1 + (old - 1) * 1.5)
   Mapping: 1->1, 2->3, 3->4, 4->6, 5->7
3. Updates CHECK constraints from BETWEEN 1 AND 5 to BETWEEN 1 AND 7

Run with: python migrations/migrate_to_7point.py
"""
import sqlite3
import shutil
import os
from datetime import datetime

# Get database path
DB_PATH = os.environ.get('DB_PATH', 'friktionskompas_v3.db')


def migrate_score(old_score):
    """Convert 1-5 score to 1-7 scale."""
    if old_score is None:
        return None
    # Formula: new = 1 + (old - 1) * 1.5
    # 1->1, 2->2.5->3, 3->4, 4->5.5->6, 5->7
    new_raw = 1 + (old_score - 1) * 1.5
    return round(new_raw)


def backup_database():
    """Create timestamped backup of the database."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{DB_PATH}.backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def get_table_info(conn, table_name):
    """Get column definitions for a table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def migrate_responses_table(conn):
    """Migrate the main responses table (gruppe-maaling)."""
    print("\nMigrating 'responses' table...")

    # Check current row count
    count_before = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    print(f"  Rows before: {count_before}")

    # Get min/max scores before migration
    stats = conn.execute("""
        SELECT MIN(score), MAX(score), AVG(score)
        FROM responses WHERE score IS NOT NULL
    """).fetchone()
    print(f"  Score stats before: min={stats[0]}, max={stats[1]}, avg={stats[2]:.2f}" if stats[0] else "  No scores to migrate")

    if stats[0] is None:
        print("  Skipping - no data")
        return

    # Step 1: Create new table with 1-7 constraint
    conn.execute("""
        CREATE TABLE responses_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id TEXT NOT NULL,
            unit_id TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 7),
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

    # Step 2: Copy data with converted scores
    conn.execute("""
        INSERT INTO responses_new (id, assessment_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at)
        SELECT id, assessment_id, unit_id, question_id,
               CASE
                   WHEN score = 1 THEN 1
                   WHEN score = 2 THEN 3
                   WHEN score = 3 THEN 4
                   WHEN score = 4 THEN 6
                   WHEN score = 5 THEN 7
                   ELSE score
               END,
               comment, category_comment, respondent_type, respondent_name, created_at
        FROM responses
    """)

    # Step 3: Drop old table and rename new
    conn.execute("DROP TABLE responses")
    conn.execute("ALTER TABLE responses_new RENAME TO responses")

    # Step 4: Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_assessment ON responses(assessment_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_unit ON responses(unit_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_question ON responses(question_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at)")

    # Verify
    count_after = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    stats_after = conn.execute("""
        SELECT MIN(score), MAX(score), AVG(score)
        FROM responses WHERE score IS NOT NULL
    """).fetchone()

    print(f"  Rows after: {count_after}")
    print(f"  Score stats after: min={stats_after[0]}, max={stats_after[1]}, avg={stats_after[2]:.2f}")

    if count_before != count_after:
        raise Exception(f"Row count mismatch! Before: {count_before}, After: {count_after}")


def migrate_profil_responses_table(conn):
    """Migrate the profil_responses table (legacy profil)."""
    print("\nMigrating 'profil_responses' table...")

    # Check if table exists
    table_exists = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='profil_responses'
    """).fetchone()

    if not table_exists:
        print("  Table does not exist - skipping")
        return

    count_before = conn.execute("SELECT COUNT(*) FROM profil_responses").fetchone()[0]
    print(f"  Rows before: {count_before}")

    if count_before == 0:
        # Just update the constraint
        print("  No data - updating constraint only")
        conn.execute("""
            CREATE TABLE profil_responses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 7),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES profil_sessions(id) ON DELETE CASCADE
            )
        """)
        conn.execute("DROP TABLE profil_responses")
        conn.execute("ALTER TABLE profil_responses_new RENAME TO profil_responses")
        return

    stats = conn.execute("""
        SELECT MIN(score), MAX(score), AVG(score)
        FROM profil_responses WHERE score IS NOT NULL
    """).fetchone()
    print(f"  Score stats before: min={stats[0]}, max={stats[1]}, avg={stats[2]:.2f}")

    # Create new table
    conn.execute("""
        CREATE TABLE profil_responses_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question_id INTEGER NOT NULL,
            score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 7),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES profil_sessions(id) ON DELETE CASCADE
        )
    """)

    # Copy with conversion
    conn.execute("""
        INSERT INTO profil_responses_new (id, session_id, question_id, score, created_at)
        SELECT id, session_id, question_id,
               CASE
                   WHEN score = 1 THEN 1
                   WHEN score = 2 THEN 3
                   WHEN score = 3 THEN 4
                   WHEN score = 4 THEN 6
                   WHEN score = 5 THEN 7
                   ELSE score
               END,
               created_at
        FROM profil_responses
    """)

    conn.execute("DROP TABLE profil_responses")
    conn.execute("ALTER TABLE profil_responses_new RENAME TO profil_responses")

    count_after = conn.execute("SELECT COUNT(*) FROM profil_responses").fetchone()[0]
    stats_after = conn.execute("""
        SELECT MIN(score), MAX(score), AVG(score)
        FROM profil_responses WHERE score IS NOT NULL
    """).fetchone()

    print(f"  Rows after: {count_after}")
    print(f"  Score stats after: min={stats_after[0]}, max={stats_after[1]}, avg={stats_after[2]:.2f}")


def migrate_situation_responses_table(conn):
    """Migrate the situation_responses table."""
    print("\nMigrating 'situation_responses' table...")

    table_exists = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='situation_responses'
    """).fetchone()

    if not table_exists:
        print("  Table does not exist - skipping")
        return

    count_before = conn.execute("SELECT COUNT(*) FROM situation_responses").fetchone()[0]
    print(f"  Rows before: {count_before}")

    if count_before == 0:
        print("  No data - updating constraint only")
        conn.execute("""
            CREATE TABLE situation_responses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL,
                action_id TEXT NOT NULL,
                field TEXT NOT NULL,
                score INTEGER CHECK(score BETWEEN 1 AND 7),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (token) REFERENCES situation_tokens(token) ON DELETE CASCADE,
                FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
            )
        """)
        conn.execute("DROP TABLE situation_responses")
        conn.execute("ALTER TABLE situation_responses_new RENAME TO situation_responses")
        return

    stats = conn.execute("""
        SELECT MIN(score), MAX(score), AVG(score)
        FROM situation_responses WHERE score IS NOT NULL
    """).fetchone()
    print(f"  Score stats before: min={stats[0]}, max={stats[1]}, avg={stats[2]:.2f}" if stats[0] else "  No scores")

    conn.execute("""
        CREATE TABLE situation_responses_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            action_id TEXT NOT NULL,
            field TEXT NOT NULL,
            score INTEGER CHECK(score BETWEEN 1 AND 7),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (token) REFERENCES situation_tokens(token) ON DELETE CASCADE,
            FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        INSERT INTO situation_responses_new (id, token, action_id, field, score, created_at)
        SELECT id, token, action_id, field,
               CASE
                   WHEN score = 1 THEN 1
                   WHEN score = 2 THEN 3
                   WHEN score = 3 THEN 4
                   WHEN score = 4 THEN 6
                   WHEN score = 5 THEN 7
                   ELSE score
               END,
               created_at
        FROM situation_responses
    """)

    conn.execute("DROP TABLE situation_responses")
    conn.execute("ALTER TABLE situation_responses_new RENAME TO situation_responses")

    count_after = conn.execute("SELECT COUNT(*) FROM situation_responses").fetchone()[0]
    print(f"  Rows after: {count_after}")


def verify_migration(conn):
    """Verify that all scores are now in 1-7 range."""
    print("\n=== Verification ===")

    tables = ['responses', 'profil_responses', 'situation_responses']
    all_ok = True

    for table in tables:
        exists = conn.execute(f"""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='{table}'
        """).fetchone()

        if not exists:
            continue

        # Check for out-of-range scores
        out_of_range = conn.execute(f"""
            SELECT COUNT(*) FROM {table}
            WHERE score IS NOT NULL AND (score < 1 OR score > 7)
        """).fetchone()[0]

        if out_of_range > 0:
            print(f"  ERROR: {table} has {out_of_range} scores outside 1-7 range!")
            all_ok = False
        else:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: OK ({count} rows, all in 1-7 range)")

    return all_ok


def run_migration():
    """Run the full migration."""
    print("=" * 60)
    print("7-Point Likert Scale Migration")
    print("=" * 60)
    print(f"\nDatabase: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return False

    # Step 1: Backup
    print("\n[Step 1] Creating backup...")
    backup_path = backup_database()

    # Step 2: Migrate
    print("\n[Step 2] Migrating tables...")
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        # Disable foreign keys during migration
        conn.execute("PRAGMA foreign_keys=OFF")

        migrate_responses_table(conn)
        migrate_profil_responses_table(conn)
        migrate_situation_responses_table(conn)

        # Re-enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

        # Commit all changes
        conn.commit()

        # Verify
        print("\n[Step 3] Verifying migration...")
        if verify_migration(conn):
            print("\n" + "=" * 60)
            print("MIGRATION SUCCESSFUL")
            print("=" * 60)
            print(f"\nBackup available at: {backup_path}")
            print("If you need to rollback, run: python migrations/rollback_from_7point.py")
            return True
        else:
            print("\nMIGRATION VERIFICATION FAILED - Please check the data")
            return False

    except Exception as e:
        conn.rollback()
        print(f"\nERROR during migration: {e}")
        print(f"Database unchanged. Backup at: {backup_path}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    success = run_migration()
    sys.exit(0 if success else 1)

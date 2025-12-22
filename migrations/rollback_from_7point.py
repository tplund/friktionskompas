"""
Rollback: Convert all 1-7 Likert scale responses back to 1-5 scale.

This rollback:
1. Converts existing scores using: old = round((new - 1) / 1.5 + 1)
   Mapping: 1->1, 2->2, 3->2, 4->3, 5->3, 6->4, 7->5
2. Updates CHECK constraints from BETWEEN 1 AND 7 to BETWEEN 1 AND 5

Run with: python migrations/rollback_from_7point.py
"""
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', 'friktionskompas_v3.db')


def rollback_score(new_score):
    """Convert 1-7 score back to 1-5 scale."""
    if new_score is None:
        return None
    # Reverse of: new = 1 + (old - 1) * 1.5
    # old = (new - 1) / 1.5 + 1
    old_raw = (new_score - 1) / 1.5 + 1
    return round(old_raw)


def backup_database():
    """Create timestamped backup of the database."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{DB_PATH}.rollback_backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def rollback_responses_table(conn):
    """Rollback the main responses table."""
    print("\nRolling back 'responses' table...")

    count_before = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    print(f"  Rows: {count_before}")

    if count_before == 0:
        print("  No data - updating constraint only")

    # Create new table with 1-5 constraint
    conn.execute("""
        CREATE TABLE responses_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (token_id) REFERENCES tokens(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id)
        )
    """)

    # Copy with conversion: 1->1, 2-3->2, 4->3, 5-6->4, 7->5
    conn.execute("""
        INSERT INTO responses_new (id, token_id, question_id, score, created_at)
        SELECT id, token_id, question_id,
               CASE
                   WHEN score = 1 THEN 1
                   WHEN score IN (2, 3) THEN 2
                   WHEN score = 4 THEN 3
                   WHEN score IN (5, 6) THEN 4
                   WHEN score = 7 THEN 5
                   ELSE 3  -- Default to middle if something weird
               END,
               created_at
        FROM responses
    """)

    conn.execute("DROP TABLE responses")
    conn.execute("ALTER TABLE responses_new RENAME TO responses")

    # Recreate indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_token ON responses(token_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_question ON responses(question_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_created_at ON responses(created_at)")

    print("  Done")


def rollback_profil_responses_table(conn):
    """Rollback the profil_responses table."""
    print("\nRolling back 'profil_responses' table...")

    table_exists = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='profil_responses'
    """).fetchone()

    if not table_exists:
        print("  Table does not exist - skipping")
        return

    conn.execute("""
        CREATE TABLE profil_responses_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES profil_sessions(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        INSERT INTO profil_responses_new (id, session_id, question_id, score, created_at)
        SELECT id, session_id, question_id,
               CASE
                   WHEN score = 1 THEN 1
                   WHEN score IN (2, 3) THEN 2
                   WHEN score = 4 THEN 3
                   WHEN score IN (5, 6) THEN 4
                   WHEN score = 7 THEN 5
                   ELSE 3
               END,
               created_at
        FROM profil_responses
    """)

    conn.execute("DROP TABLE profil_responses")
    conn.execute("ALTER TABLE profil_responses_new RENAME TO profil_responses")

    print("  Done")


def rollback_situation_responses_table(conn):
    """Rollback the situation_responses table."""
    print("\nRolling back 'situation_responses' table...")

    table_exists = conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='situation_responses'
    """).fetchone()

    if not table_exists:
        print("  Table does not exist - skipping")
        return

    conn.execute("""
        CREATE TABLE situation_responses_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            field TEXT NOT NULL,
            score INTEGER CHECK(score BETWEEN 1 AND 5),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (token_id) REFERENCES situation_tokens(id) ON DELETE CASCADE,
            FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        INSERT INTO situation_responses_new (id, token_id, action_id, field, score, created_at)
        SELECT id, token_id, action_id, field,
               CASE
                   WHEN score = 1 THEN 1
                   WHEN score IN (2, 3) THEN 2
                   WHEN score = 4 THEN 3
                   WHEN score IN (5, 6) THEN 4
                   WHEN score = 7 THEN 5
                   ELSE 3
               END,
               created_at
        FROM situation_responses
    """)

    conn.execute("DROP TABLE situation_responses")
    conn.execute("ALTER TABLE situation_responses_new RENAME TO situation_responses")

    print("  Done")


def run_rollback():
    """Run the full rollback."""
    print("=" * 60)
    print("7-Point Likert Scale ROLLBACK")
    print("=" * 60)
    print(f"\nDatabase: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return False

    # Backup first
    print("\n[Step 1] Creating backup before rollback...")
    backup_path = backup_database()

    # Rollback
    print("\n[Step 2] Rolling back tables...")
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys=OFF")

        rollback_responses_table(conn)
        rollback_profil_responses_table(conn)
        rollback_situation_responses_table(conn)

        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()

        print("\n" + "=" * 60)
        print("ROLLBACK COMPLETE")
        print("=" * 60)
        print(f"\nBackup at: {backup_path}")
        return True

    except Exception as e:
        conn.rollback()
        print(f"\nERROR during rollback: {e}")
        print(f"Database may be in inconsistent state. Restore from: {backup_path}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    import sys
    success = run_rollback()
    sys.exit(0 if success else 1)

"""
Migration runner for Friktionskompasset
Kører database migrationer og holder styr på hvilke der er kørt
"""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = "friktionskompas_v3.db"
MIGRATIONS_DIR = "migrations"

@contextmanager
def get_db():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_migration_tracking():
    """Opret schema_migrations tabel hvis den ikke findes"""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def get_applied_migrations():
    """Hent liste af allerede anvendte migrationer"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT migration_name FROM schema_migrations ORDER BY id"
        ).fetchall()
        return [row['migration_name'] for row in rows]


def get_pending_migrations():
    """Find migrationer der ikke er kørt endnu"""
    applied = set(get_applied_migrations())

    # Find alle .sql filer i migrations directory
    if not os.path.exists(MIGRATIONS_DIR):
        print(f"[ERROR] Migrations directory '{MIGRATIONS_DIR}' ikke fundet")
        return []

    all_migrations = sorted([
        f for f in os.listdir(MIGRATIONS_DIR)
        if f.endswith('.sql')
    ])

    pending = [m for m in all_migrations if m not in applied]
    return pending


def run_migration(migration_file):
    """Kør en specifik migration"""
    filepath = os.path.join(MIGRATIONS_DIR, migration_file)

    print(f"[*] Koerer migration: {migration_file}")

    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()

    # SQLite kræver at vi kører uden explicit transactions når vi bruger BEGIN/COMMIT
    # så vi bruger executescript
    conn = sqlite3.connect(DB_PATH)
    try:
        # Remove BEGIN and COMMIT from SQL since executescript handles transactions
        # Actually, let's keep them - executescript can handle it
        conn.executescript(sql)
        conn.commit()
        print(f"[OK] Migration {migration_file} koert succesfuldt")
        return True
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Fejl i migration {migration_file}: {e}")
        return False
    finally:
        conn.close()


def run_all_pending():
    """Kør alle pending migrationer"""
    init_migration_tracking()

    pending = get_pending_migrations()

    if not pending:
        print("[OK] Ingen pending migrationer. Database er up-to-date!")
        return True

    print(f"\n[INFO] Fandt {len(pending)} pending migration(er):")
    for m in pending:
        print(f"  - {m}")
    print()

    for migration in pending:
        success = run_migration(migration)
        if not success:
            print(f"\n[ERROR] Migration fejlede. Stopper her.")
            return False

    print(f"\n[OK] Alle {len(pending)} migration(er) koert succesfuldt!")
    return True


def show_status():
    """Vis status for migrationer"""
    init_migration_tracking()

    applied = get_applied_migrations()
    pending = get_pending_migrations()

    print("\n" + "="*60)
    print("MIGRATION STATUS")
    print("="*60)

    print(f"\n[APPLIED] Anvendte migrationer ({len(applied)}):")
    if applied:
        for m in applied:
            print(f"  - {m}")
    else:
        print("  (ingen)")

    print(f"\n[PENDING] Pending migrationer ({len(pending)}):")
    if pending:
        for m in pending:
            print(f"  - {m}")
    else:
        print("  (ingen)")

    print("\n" + "="*60)


def verify_migration_001():
    """Verificer at migration 001 er kørt korrekt"""
    print("\n[VERIFY] Verificerer migration 001...")

    with get_db() as conn:
        # Check new tables exist
        tables_to_check = [
            'respondent_types',
            'campaign_modes',
            'kcc_mapping',
            'substitution_patterns',
            'data_consent'
        ]

        for table in tables_to_check:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()

            if result:
                count = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()['cnt']
                print(f"  [OK] {table} (rows: {count})")
            else:
                print(f"  [ERROR] {table} MANGLER!")
                return False

        # Check new columns in campaigns
        campaigns_cols = conn.execute("PRAGMA table_info(campaigns)").fetchall()
        campaigns_col_names = [col['name'] for col in campaigns_cols]

        required_cols = ['mode', 'include_leader_assessment', 'include_leader_self', 'min_responses']
        for col in required_cols:
            if col in campaigns_col_names:
                print(f"  [OK] campaigns.{col}")
            else:
                print(f"  [ERROR] campaigns.{col} MANGLER!")
                return False

        # Check new columns in tokens
        tokens_cols = conn.execute("PRAGMA table_info(tokens)").fetchall()
        tokens_col_names = [col['name'] for col in tokens_cols]

        if 'respondent_type' in tokens_col_names:
            print(f"  [OK] tokens.respondent_type")
        else:
            print(f"  [ERROR] tokens.respondent_type MANGLER!")
            return False

        # Check new columns in responses
        responses_cols = conn.execute("PRAGMA table_info(responses)").fetchall()
        responses_col_names = [col['name'] for col in responses_cols]

        if 'respondent_type' in responses_col_names:
            print(f"  [OK] responses.respondent_type")
        else:
            print(f"  [ERROR] responses.respondent_type MANGLER!")
            return False

    print("\n[OK] Migration 001 verificeret succesfuldt!")
    return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        show_status()
    elif len(sys.argv) > 1 and sys.argv[1] == 'verify':
        verify_migration_001()
    else:
        print("\n" + "="*60)
        print("FRIKTIONSKOMPASSET - DATABASE MIGRATION")
        print("="*60)

        success = run_all_pending()

        if success:
            # Verificer at alt er korrekt
            verify_migration_001()

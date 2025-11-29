"""Kør migration 003"""
from db_hierarchical import get_db

with get_db() as conn:
    # Læs migration
    with open('migrations/003_update_to_v1_0.sql', 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    # Kør migration
    conn.executescript(migration_sql)

    # Marker som kørt
    conn.execute("INSERT OR IGNORE INTO schema_migrations (migration_name) VALUES ('003_update_to_v1_0.sql')")

    print("[OK] Migration 003 komplet - 25 nye spoergsmaal")

    # Verificer
    count = conn.execute("SELECT COUNT(*) as cnt FROM questions WHERE is_default = 1").fetchone()['cnt']
    print(f"[OK] Total antal default spoergsmaal: {count}")

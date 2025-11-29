"""Kør migration 006 til V1.4"""
from db_hierarchical import get_db

with get_db() as conn:
    # Læs migration
    with open('migrations/006_update_to_v1_4.sql', 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    # Kør migration
    conn.executescript(migration_sql)

    # Marker som kørt
    conn.execute("INSERT OR IGNORE INTO schema_migrations (migration_name) VALUES ('006_update_to_v1_4.sql')")

    print("[OK] Migration 006 komplet - V1.4 med 24 spoergsmaal (stealth substitution)")

    # Verificer
    count = conn.execute("SELECT COUNT(*) as cnt FROM questions WHERE is_default = 1").fetchone()['cnt']
    print(f"[OK] Total antal default spoergsmaal: {count}")

    # Vis fordeling
    fields = conn.execute("""
        SELECT field, COUNT(*) as cnt
        FROM questions WHERE is_default = 1
        GROUP BY field
        ORDER BY MIN(sequence)
    """).fetchall()

    print("\n[OK] Fordeling:")
    for field_row in fields:
        print(f"  {field_row['field']}: {field_row['cnt']} spoergsmaal")

    # Vis reverse-scored
    reverse = conn.execute("""
        SELECT sequence FROM questions
        WHERE is_default = 1 AND reverse_scored = 1
        ORDER BY sequence
    """).fetchall()

    print(f"\n[OK] Reverse-scored: {', '.join([str(r['sequence']) for r in reverse])}")

    # Vis stealth-S items
    stealth_s = [5, 10, 17, 18, 23]
    print(f"[OK] Stealth-S items: {', '.join([str(s) for s in stealth_s])}")

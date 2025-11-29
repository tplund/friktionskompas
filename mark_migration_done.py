from db_hierarchical import get_db

with get_db() as conn:
    conn.execute("INSERT OR IGNORE INTO schema_migrations (migration_name) VALUES ('001_add_respondent_modes.sql')")
    print('[OK] Migration 001 markeret som koert')

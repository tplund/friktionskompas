from db_hierarchical import get_db

with get_db() as conn:
    conn.execute('DELETE FROM campaigns WHERE name LIKE "Test Campaign%"')
    conn.execute('DELETE FROM organizational_units WHERE name LIKE "Test%"')
    print('[OK] Testdata slettet')

"""Check database contents"""
from db_hierarchical import get_db

with get_db() as conn:
    campaigns = conn.execute('SELECT COUNT(*) as c FROM campaigns').fetchone()['c']
    responses = conn.execute('SELECT COUNT(*) as c FROM responses').fetchone()['c']
    units = conn.execute('SELECT COUNT(*) as c FROM organizational_units').fetchone()['c']

    print(f"Database status:")
    print(f"  Units: {units}")
    print(f"  Campaigns: {campaigns}")
    print(f"  Responses: {responses}")

    if campaigns > 0:
        print("\nSample campaigns:")
        sample = conn.execute('SELECT id, name, target_unit_id FROM campaigns LIMIT 3').fetchall()
        for c in sample:
            print(f"  - {c['name']} (ID: {c['id'][:15]}...)")

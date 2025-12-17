"""Fix Trivselsmåling -> Friktionsmåling"""
from db_hierarchical import get_db

with get_db() as conn:
    # Update campaign names
    result = conn.execute('''
        UPDATE campaigns
        SET name = REPLACE(name, "Trivselmåling", "Friktionsmåling")
        WHERE name LIKE "%Trivsel%"
    ''')

    affected = result.rowcount
    print(f"[OK] Updated {affected} campaign names: Trivselmåling -> Friktionsmåling")

print("[OK] Database terminology fixed!")

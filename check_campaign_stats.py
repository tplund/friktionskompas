"""Check campaign statistics"""
from db_hierarchical import get_db

with get_db() as conn:
    # Get first campaign
    campaign = conn.execute('SELECT id, name FROM campaigns LIMIT 1').fetchone()

    if campaign:
        print(f"Campaign: {campaign['name']}")
        print(f"ID: {campaign['id']}")

        # Check tokens
        tokens = conn.execute('''
            SELECT COUNT(*) as total, SUM(is_used) as used
            FROM tokens
            WHERE campaign_id = ?
        ''', (campaign['id'],)).fetchone()

        print(f"\nTokens:")
        print(f"  Total sent: {tokens['total']}")
        print(f"  Used (responded): {tokens['used']}")

        # Check responses
        responses = conn.execute('''
            SELECT COUNT(DISTINCT id) as cnt
            FROM responses
            WHERE campaign_id = ?
        ''', (campaign['id'],)).fetchone()

        print(f"\nResponses: {responses['cnt']}")

        if tokens['total'] > 0:
            percent = (tokens['used'] / tokens['total']) * 100
            print(f"Response rate: {percent:.1f}%")

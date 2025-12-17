"""Check assessment statistics"""
from db_hierarchical import get_db

with get_db() as conn:
    # Get first assessment
    assessment = conn.execute('SELECT id, name FROM assessments LIMIT 1').fetchone()

    if assessment:
        print(f"Assessment: {assessment['name']}")
        print(f"ID: {assessment['id']}")

        # Check tokens
        tokens = conn.execute('''
            SELECT COUNT(*) as total, SUM(is_used) as used
            FROM tokens
            WHERE assessment_id = ?
        ''', (assessment['id'],)).fetchone()

        print(f"\nTokens:")
        print(f"  Total sent: {tokens['total']}")
        print(f"  Used (responded): {tokens['used']}")

        # Check responses
        responses = conn.execute('''
            SELECT COUNT(DISTINCT id) as cnt
            FROM responses
            WHERE assessment_id = ?
        ''', (assessment['id'],)).fetchone()

        print(f"\nResponses: {responses['cnt']}")

        if tokens['total'] > 0:
            percent = (tokens['used'] / tokens['total']) * 100
            print(f"Response rate: {percent:.1f}%")

"""
Skift MULIGHED til KAN i database
"""
from db_hierarchical import get_db

with get_db() as conn:
    # Update questions table
    result1 = conn.execute('''
        UPDATE questions
        SET field = 'KAN'
        WHERE field = 'MULIGHED'
    ''')

    print(f"[OK] Updated {result1.rowcount} questions: MULIGHED -> KAN")

    # Check current fields
    fields = conn.execute('''
        SELECT DISTINCT field FROM questions ORDER BY field
    ''').fetchall()

    print(f"[OK] Current fields in database: {[f['field'] for f in fields]}")

print("[OK] Database updated successfully!")

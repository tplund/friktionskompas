"""Verificer at nye spørgsmål er tilføjet korrekt"""
import sqlite3

conn = sqlite3.connect('friktionskompas_v3.db')
conn.row_factory = sqlite3.Row

print("="*60)
print("SPØRGSMÅLSFORDELING")
print("="*60)

# Count per field
rows = conn.execute("""
    SELECT field, COUNT(*) as cnt
    FROM questions
    WHERE is_default = 1
    GROUP BY field
    ORDER BY field
""").fetchall()

for row in rows:
    print(f"{row['field']:12} {row['cnt']} spørgsmål")

# Total
total = conn.execute("SELECT COUNT(*) as cnt FROM questions WHERE is_default = 1").fetchone()['cnt']
print(f"\n{'Total:':12} {total} spørgsmål")

print("\n" + "="*60)
print("ALLE SPØRGSMÅL")
print("="*60)

all_questions = conn.execute("""
    SELECT field, sequence, text_da, reverse_scored
    FROM questions
    WHERE is_default = 1
    ORDER BY sequence
""").fetchall()

current_field = None
for q in all_questions:
    if q['field'] != current_field:
        print(f"\n### {q['field']}")
        current_field = q['field']

    reverse_mark = " (R)" if q['reverse_scored'] else ""
    print(f"{q['sequence']:2}. {q['text_da']}{reverse_mark}")

conn.close()

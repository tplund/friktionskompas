#!/usr/bin/env python3
"""
Eksporter lokal database til SQL fil der kan importeres på Render
"""
import sqlite3
import json

def export_to_sql():
    conn = sqlite3.connect('friktionskompas_v3.db')
    conn.row_factory = sqlite3.Row

    # Eksporter som Python data struktur til import
    data = {
        'organizational_units': [],
        'campaigns': [],
        'responses': [],
        'questions': []
    }

    # Units
    for row in conn.execute('SELECT * FROM organizational_units').fetchall():
        data['organizational_units'].append(dict(row))

    # Campaigns
    for row in conn.execute('SELECT * FROM campaigns').fetchall():
        data['campaigns'].append(dict(row))

    # Responses
    for row in conn.execute('SELECT * FROM responses').fetchall():
        data['responses'].append(dict(row))

    # Questions
    for row in conn.execute('SELECT * FROM questions').fetchall():
        data['questions'].append(dict(row))

    conn.close()

    # Gem som JSON
    with open('local_data_export.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Eksporteret:")
    print(f"  - {len(data['organizational_units'])} units")
    print(f"  - {len(data['campaigns'])} campaigns")
    print(f"  - {len(data['responses'])} responses")
    print(f"  - {len(data['questions'])} questions")
    print(f"\nGemt til: local_data_export.json")

if __name__ == '__main__':
    export_to_sql()

#!/usr/bin/env python3
"""
Importer lokal data fra JSON fil til Render database
Kør via /admin/import-local-data endpoint
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_hierarchical import init_db, get_db
from db_multitenant import init_multitenant_db, get_all_customers

def import_local_data(customer_id=None):
    """Importer data fra local_data_export.json"""

    # Læs JSON fil
    json_path = os.path.join(os.path.dirname(__file__), 'local_data_export.json')
    if not os.path.exists(json_path):
        return {'success': False, 'error': 'local_data_export.json ikke fundet'}

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Initialiser database
    init_db()
    init_multitenant_db()

    stats = {
        'units_imported': 0,
        'campaigns_imported': 0,
        'responses_imported': 0,
        'questions_imported': 0,
        'skipped': 0
    }

    with get_db() as conn:
        # Slet eksisterende demo-data først
        conn.execute("DELETE FROM responses WHERE campaign_id LIKE 'camp-test-%'")
        conn.execute("DELETE FROM campaigns WHERE id LIKE 'camp-test-%'")
        conn.execute("DELETE FROM organizational_units WHERE full_path LIKE 'Demo Virksomhed%'")

        # Import questions først
        for q in data.get('questions', []):
            try:
                existing = conn.execute('SELECT id FROM questions WHERE id = ?', (q['id'],)).fetchone()
                if not existing:
                    conn.execute('''
                        INSERT INTO questions (id, field, question_text, category, dimension, layer)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (q['id'], q.get('field'), q.get('question_text'),
                          q.get('category'), q.get('dimension'), q.get('layer')))
                    stats['questions_imported'] += 1
            except Exception as e:
                stats['skipped'] += 1

        # Import units
        for unit in data.get('organizational_units', []):
            try:
                existing = conn.execute('SELECT id FROM organizational_units WHERE id = ?', (unit['id'],)).fetchone()
                if not existing:
                    conn.execute('''
                        INSERT INTO organizational_units (id, name, full_path, parent_id, customer_id)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (unit['id'], unit['name'], unit['full_path'],
                          unit.get('parent_id'), customer_id))
                    stats['units_imported'] += 1
            except Exception as e:
                stats['skipped'] += 1

        # Import campaigns
        for camp in data.get('campaigns', []):
            try:
                existing = conn.execute('SELECT id FROM campaigns WHERE id = ?', (camp['id'],)).fetchone()
                if not existing:
                    conn.execute('''
                        INSERT INTO campaigns (id, name, target_unit_id, period, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (camp['id'], camp['name'], camp['target_unit_id'],
                          camp.get('period', 'Q1 2025'), camp.get('created_at')))
                    stats['campaigns_imported'] += 1
            except Exception as e:
                stats['skipped'] += 1

        # Import responses
        for resp in data.get('responses', []):
            try:
                conn.execute('''
                    INSERT INTO responses (campaign_id, unit_id, question_id, score, respondent_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (resp['campaign_id'], resp['unit_id'], resp['question_id'],
                      resp['score'], resp.get('respondent_type', 'employee'), resp.get('created_at')))
                stats['responses_imported'] += 1
            except Exception as e:
                stats['skipped'] += 1

        conn.commit()

    stats['success'] = True
    return stats


if __name__ == '__main__':
    print("Importerer lokal data...")
    result = import_local_data()
    print(f"\nResultat:")
    print(f"  Units: {result.get('units_imported', 0)}")
    print(f"  Campaigns: {result.get('campaigns_imported', 0)}")
    print(f"  Responses: {result.get('responses_imported', 0)}")
    print(f"  Questions: {result.get('questions_imported', 0)}")
    print(f"  Skipped: {result.get('skipped', 0)}")

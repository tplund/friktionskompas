#!/usr/bin/env python3
"""
Seed Esbjerg Kommune som kanonisk testkunde.

VIGTIGT: Dette script opretter STABIL testdata der bruges til at fange bugs.
         Ændr ALDRIG dette script uden at opdatere ESBJERG_TESTDATA.md!

Usage:
    python seed_esbjerg_canonical.py

Se ESBJERG_TESTDATA.md for komplet dokumentation af testdata-design.
"""

import sqlite3
import secrets
from datetime import datetime, timedelta
import random

# Import centralized database functions
from db import get_db_connection as get_db, DB_PATH

# Esbjerg customer ID (eksisterende)
ESBJERG_CUSTOMER_ID = 'cust-SHKIi10cOe8'

# Questions by field (from database)
QUESTIONS = {
    'TRYGHED': [95, 96, 97, 98, 99],  # 95, 99 are reverse
    'MENING': [90, 91, 92, 93, 94],   # 90, 94 are reverse
    'KAN': [100, 101, 102, 103, 104, 105, 106, 107],  # 101, 106, 107 are reverse
    'BESVÆR': [108, 109, 110, 111, 112, 113],  # 108, 112 are reverse
}

REVERSE_SCORED = {95, 99, 90, 94, 101, 106, 107, 108, 112}

def generate_id(prefix=''):
    return f"{prefix}{secrets.token_urlsafe(8)}"

def generate_responses(assessment_id, unit_id, target_scores, respondent_type, num_respondents=1):
    """
    Generate responses for a given target score profile.

    Args:
        assessment_id: Assessment ID
        unit_id: Unit ID
        target_scores: Dict with field -> target score (1-7)
        respondent_type: 'employee' or 'leader_assess'
        num_respondents: Number of respondents to generate

    Returns:
        List of response dicts
    """
    responses = []

    for respondent_num in range(num_respondents):
        for field, questions in QUESTIONS.items():
            target = target_scores.get(field, 4.0)

            for q_id in questions:
                # For reverse scored questions, we need to invert the target
                if q_id in REVERSE_SCORED:
                    # If we want high adjusted score, we need LOW raw score
                    raw_target = 8 - target
                else:
                    raw_target = target

                # Add small variation
                score = raw_target + random.uniform(-0.4, 0.4)
                score = max(1, min(7, score))  # Clamp to 1-7
                score = round(score, 1)

                responses.append({
                    'assessment_id': assessment_id,
                    'unit_id': unit_id,
                    'question_id': q_id,
                    'score': score,
                    'respondent_type': respondent_type,
                    'respondent_name': f'{respondent_type}_{respondent_num}',
                    'created_at': datetime.now().isoformat()
                })

    return responses

def clear_esbjerg_data(conn):
    """Clear existing Esbjerg data (but keep the customer and structure)"""
    cur = conn.cursor()

    # Get all Esbjerg units
    cur.execute('''
        SELECT id FROM organizational_units WHERE customer_id = ?
    ''', [ESBJERG_CUSTOMER_ID])
    unit_ids = [r['id'] for r in cur.fetchall()]

    # Delete responses for these units
    for unit_id in unit_ids:
        cur.execute('DELETE FROM responses WHERE unit_id = ?', [unit_id])

    # Delete assessments for these units
    for unit_id in unit_ids:
        cur.execute('DELETE FROM assessments WHERE target_unit_id = ?', [unit_id])

    # Delete tokens for these units (if any)
    for unit_id in unit_ids:
        cur.execute('DELETE FROM tokens WHERE unit_id = ?', [unit_id])

    # Delete all units
    cur.execute('DELETE FROM organizational_units WHERE customer_id = ?', [ESBJERG_CUSTOMER_ID])

    conn.commit()
    print(f"Cleared {len(unit_ids)} units and their data")

def create_unit(conn, name, parent_id=None, level=0):
    """Create an organizational unit"""
    unit_id = generate_id('unit-')
    full_path = name  # Simplified for now

    conn.execute('''
        INSERT INTO organizational_units (id, name, customer_id, parent_id, level, full_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', [unit_id, name, ESBJERG_CUSTOMER_ID, parent_id, level, full_path, datetime.now().isoformat()])

    return unit_id

def create_assessment(conn, unit_id, name, assessment_type='gruppe_friktion', period=None):
    """Create an assessment"""
    assessment_id = generate_id('assess-')

    conn.execute('''
        INSERT INTO assessments (id, name, target_unit_id, assessment_type_id, period, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'completed', ?)
    ''', [assessment_id, name, unit_id, assessment_type, period, datetime.now().isoformat()])

    return assessment_id

def insert_responses(conn, responses):
    """Insert responses into database"""
    for r in responses:
        conn.execute('''
            INSERT INTO responses (assessment_id, unit_id, question_id, score, respondent_type, respondent_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [r['assessment_id'], r['unit_id'], r['question_id'],
              r['score'], r['respondent_type'], r['respondent_name'], r['created_at']])

def seed_esbjerg():
    """Main seeding function"""
    conn = get_db()

    print("=" * 60)
    print("SEEDING ESBJERG KOMMUNE - KANONISK TESTDATA")
    print("=" * 60)

    # Clear existing data
    print("\n1. Clearing existing Esbjerg data...")
    clear_esbjerg_data(conn)

    # Create structure
    print("\n2. Creating organizational structure...")

    # Level 0: Top units
    social_sundhed_id = create_unit(conn, "Social- og Sundhedsforvaltningen", None, 0)
    boern_kultur_id = create_unit(conn, "Børn og Kultur", None, 0)
    teknisk_id = create_unit(conn, "Teknisk Forvaltning", None, 0)

    # Level 1: Departments
    aeldreplejen_id = create_unit(conn, "Ældreplejen", social_sundhed_id, 1)
    handicap_id = create_unit(conn, "Handicapområdet", social_sundhed_id, 1)  # Empty unit!
    substitution_parent_id = create_unit(conn, "Driftsafdelingen", teknisk_id, 1)

    # Level 2: Teams/Units
    birkebo_id = create_unit(conn, "Birkebo", aeldreplejen_id, 2)
    skovbrynet_id = create_unit(conn, "Skovbrynet", aeldreplejen_id, 2)
    solhjem_id = create_unit(conn, "Solhjem", aeldreplejen_id, 2)
    strandparken_id = create_unit(conn, "Strandparken", aeldreplejen_id, 2)

    individuel_id = create_unit(conn, "Individuel Profil Test", boern_kultur_id, 1)
    minimal_id = create_unit(conn, "Minimal Data Test", boern_kultur_id, 1)

    substitution_id = create_unit(conn, "Substitution Test", substitution_parent_id, 2)

    conn.commit()
    print(f"  Created structure with 11 units")

    # Create assessments and responses
    print("\n3. Creating assessments and responses...")

    all_responses = []

    # 1. Birkebo - Normal case (average scores ~4.8 on 7-point scale)
    print("  - Birkebo: Normal case")
    assess_id = create_assessment(conn, birkebo_id, "Birkebo Q4 2024", period="Q4 2024")
    target = {'TRYGHED': 4.8, 'MENING': 4.6, 'KAN': 4.9, 'BESVÆR': 4.5}
    all_responses.extend(generate_responses(assess_id, birkebo_id, target, 'employee', 9))
    leader_target = {'TRYGHED': 4.9, 'MENING': 4.8, 'KAN': 4.8, 'BESVÆR': 4.6}
    all_responses.extend(generate_responses(assess_id, birkebo_id, leader_target, 'leader_assess', 1))
    all_responses.extend(generate_responses(assess_id, birkebo_id, leader_target, 'leader_self', 1))

    # 2. Skovbrynet - Success case (high scores ~6.2 on 7-point scale)
    print("  - Skovbrynet: Success case")
    assess_id = create_assessment(conn, skovbrynet_id, "Skovbrynet Q4 2024", period="Q4 2024")
    target = {'TRYGHED': 6.3, 'MENING': 6.4, 'KAN': 6.1, 'BESVÆR': 6.0}
    all_responses.extend(generate_responses(assess_id, skovbrynet_id, target, 'employee', 9))
    leader_target = {'TRYGHED': 6.1, 'MENING': 6.3, 'KAN': 6.3, 'BESVÆR': 6.1}
    all_responses.extend(generate_responses(assess_id, skovbrynet_id, leader_target, 'leader_assess', 1))
    all_responses.extend(generate_responses(assess_id, skovbrynet_id, leader_target, 'leader_self', 1))

    # 3. Solhjem - Crisis case (low scores ~2.5 on 7-point scale)
    print("  - Solhjem: Crisis case")
    assess_id = create_assessment(conn, solhjem_id, "Solhjem Q4 2024", period="Q4 2024")
    target = {'TRYGHED': 2.2, 'MENING': 2.4, 'KAN': 2.5, 'BESVÆR': 2.1}
    all_responses.extend(generate_responses(assess_id, solhjem_id, target, 'employee', 9))
    leader_target = {'TRYGHED': 2.5, 'MENING': 2.7, 'KAN': 2.8, 'BESVÆR': 2.4}
    all_responses.extend(generate_responses(assess_id, solhjem_id, leader_target, 'leader_assess', 1))
    all_responses.extend(generate_responses(assess_id, solhjem_id, leader_target, 'leader_self', 1))

    # 4. Strandparken - Leader gap case (low employee, high leader)
    print("  - Strandparken: Leader gap case")
    assess_id = create_assessment(conn, strandparken_id, "Strandparken Q4 2024", period="Q4 2024")
    target = {'TRYGHED': 3.3, 'MENING': 3.4, 'KAN': 3.1, 'BESVÆR': 3.3}
    all_responses.extend(generate_responses(assess_id, strandparken_id, target, 'employee', 9))
    leader_target = {'TRYGHED': 6.3, 'MENING': 6.1, 'KAN': 6.4, 'BESVÆR': 6.3}
    all_responses.extend(generate_responses(assess_id, strandparken_id, leader_target, 'leader_assess', 1))
    all_responses.extend(generate_responses(assess_id, strandparken_id, leader_target, 'leader_self', 1))

    # 5. Handicapområdet - Empty unit (NO ASSESSMENT!)
    print("  - Handicapområdet: Empty unit (no assessment)")
    # No assessment created!

    # 6. Individuel Profil Test - B2C with 1 respondent
    print("  - Individuel Profil Test: B2C single respondent")
    assess_id = create_assessment(conn, individuel_id, "Individuel Test", 'profil_fuld', period="2024")
    target = {'TRYGHED': 4.0, 'MENING': 5.5, 'KAN': 3.3, 'BESVÆR': 4.8}
    all_responses.extend(generate_responses(assess_id, individuel_id, target, 'employee', 1))

    # 7. Minimal Data Test - B2C with identical scores
    print("  - Minimal Data Test: B2C identical scores")
    assess_id = create_assessment(conn, minimal_id, "Minimal Test", 'profil_fuld', period="2024")
    target = {'TRYGHED': 4.0, 'MENING': 4.0, 'KAN': 4.0, 'BESVÆR': 4.0}
    # Generate with NO variation
    for field, questions in QUESTIONS.items():
        for q_id in questions:
            if q_id in REVERSE_SCORED:
                score = 4.0  # 8-4=4 for reverse on 7-point scale
            else:
                score = 4.0
            all_responses.append({
                'assessment_id': assess_id,
                'unit_id': minimal_id,
                'question_id': q_id,
                'score': score,
                'respondent_type': 'employee',
                'respondent_name': 'employee_0',
                'created_at': datetime.now().isoformat()
            })

    # 8. Substitution Test - Kahneman pattern
    print("  - Substitution Test: Kahneman substitution pattern")
    assess_id = create_assessment(conn, substitution_id, "Substitution Analyse", period="Q4 2024")
    # High TRYGHED and KAN, low MENING and BESVÆR -> substitution!
    target = {'TRYGHED': 5.5, 'MENING': 2.5, 'KAN': 5.5, 'BESVÆR': 2.5}
    all_responses.extend(generate_responses(assess_id, substitution_id, target, 'employee', 9))
    all_responses.extend(generate_responses(assess_id, substitution_id, target, 'leader_assess', 1))
    all_responses.extend(generate_responses(assess_id, substitution_id, target, 'leader_self', 1))

    # Insert all responses
    print(f"\n4. Inserting {len(all_responses)} responses...")
    insert_responses(conn, all_responses)
    conn.commit()

    # Summary
    print("\n" + "=" * 60)
    print("ESBJERG SEEDING COMPLETE")
    print("=" * 60)

    cur = conn.cursor()
    cur.execute('''
        SELECT COUNT(DISTINCT ou.id) as units,
               COUNT(DISTINCT a.id) as assessments,
               COUNT(DISTINCT r.id) as responses
        FROM organizational_units ou
        LEFT JOIN assessments a ON a.target_unit_id = ou.id
        LEFT JOIN responses r ON r.assessment_id = a.id
        WHERE ou.customer_id = ?
    ''', [ESBJERG_CUSTOMER_ID])
    stats = cur.fetchone()

    print(f"Units: {stats['units']}")
    print(f"Assessments: {stats['assessments']}")
    print(f"Responses: {stats['responses']}")
    print()
    print("Se ESBJERG_TESTDATA.md for dokumentation")

    conn.close()

if __name__ == '__main__':
    seed_esbjerg()

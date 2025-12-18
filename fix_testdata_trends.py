"""
Fix testdata trends:
1. Delete duplicate November measurements for Birk Skole and Aktivitetscentret Midt
2. Add Q1-Q4 measurements for Åparken and Gødstrup
3. Add more realistic variation to scores over time
"""
import sqlite3
import uuid
import random
from datetime import datetime

def get_db():
    conn = sqlite3.connect('friktionskompas_v3.db')
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def delete_duplicate_november_assessments():
    """Delete the extra November assessments that have wrong period"""
    conn = get_db()

    # Find assessments to delete
    duplicates = conn.execute("""
        SELECT a.id, a.name, ou.name as unit_name
        FROM assessments a
        JOIN organizational_units ou ON a.target_unit_id = ou.id
        WHERE a.name LIKE 'Friktionsmåling %'
        AND a.created_at LIKE '2025-11-%'
        AND ou.name IN ('Birk Skole', 'Aktivitetscentret Midt')
    """).fetchall()

    print(f"Sletter {len(duplicates)} duplikerede målinger:")
    for d in duplicates:
        print(f"  - {d['name']} ({d['unit_name']})")
        # Delete responses first (cascade should handle but be explicit)
        conn.execute("DELETE FROM responses WHERE assessment_id = ?", [d['id']])
        conn.execute("DELETE FROM tokens WHERE assessment_id = ?", [d['id']])
        conn.execute("DELETE FROM assessments WHERE id = ?", [d['id']])

    conn.commit()
    conn.close()
    print("Done!")

def create_quarterly_assessments(unit_name, profiles):
    """
    Create Q1-Q4 assessments for a unit with realistic score variation.

    profiles: dict with quarterly profiles, e.g.:
    {
        'Q1': {'TRYGHED': 3.2, 'MENING': 3.8, 'KAN': 3.5, 'BESVÆR': 3.3},
        'Q2': {'TRYGHED': 3.4, 'MENING': 3.9, 'KAN': 3.3, 'BESVÆR': 3.5},
        ...
    }
    """
    conn = get_db()

    # Get unit and questions
    unit = conn.execute("""
        SELECT id FROM organizational_units WHERE name = ?
    """, [unit_name]).fetchone()

    if not unit:
        print(f"Unit not found: {unit_name}")
        return

    questions = conn.execute("""
        SELECT id, field, reverse_scored FROM questions WHERE is_default = 1
    """).fetchall()

    quarters = [
        ('Q1 2025', '2025-01-15'),
        ('Q2 2025', '2025-04-15'),
        ('Q3 2025', '2025-07-15'),
        ('Q4 2025', '2025-10-15'),
    ]

    print(f"\nOpretter Q1-Q4 for {unit_name}:")

    for period, date in quarters:
        quarter_key = period.split()[0]  # 'Q1', 'Q2', etc.
        target_scores = profiles.get(quarter_key, {})

        if not target_scores:
            print(f"  Springer {period} over - ingen profil")
            continue

        # Check if assessment already exists
        existing = conn.execute("""
            SELECT id FROM assessments
            WHERE target_unit_id = ? AND period = ?
        """, [unit['id'], period]).fetchone()

        if existing:
            print(f"  {period} findes allerede - springer over")
            continue

        # Create assessment
        assessment_id = f"assess-{uuid.uuid4().hex[:12]}"
        assessment_name = f"{unit_name} - {period}"

        conn.execute("""
            INSERT INTO assessments (id, target_unit_id, name, period,
                                     assessment_type_id, status, created_at)
            VALUES (?, ?, ?, ?, 'gruppe_friktion', 'completed', ?)
        """, [assessment_id, unit['id'], assessment_name, period, date])

        # Create respondents (8 employees, 2 leader_assess, 1 leader_self)
        respondent_configs = [
            ('employee', 8),
            ('leader_assess', 2),
            ('leader_self', 1),
        ]

        response_count = 0
        for resp_type, count in respondent_configs:
            for i in range(count):
                token = f"tok-{uuid.uuid4().hex[:16]}"
                conn.execute("""
                    INSERT INTO tokens (token, assessment_id, unit_id, respondent_type, is_used, used_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                """, [token, assessment_id, unit['id'], resp_type, date])

                # Create responses for each question
                for q in questions:
                    target = target_scores.get(q['field'], 3.5)

                    # Add variation: +/- 0.8 with some extreme values
                    variation = random.gauss(0, 0.5)
                    if random.random() < 0.1:  # 10% chance of more extreme
                        variation = random.gauss(0, 1.0)

                    score = target + variation

                    # For reverse scored, we need low raw score to get high adjusted
                    if q['reverse_scored']:
                        score = 6 - score

                    # Clamp to 1-5
                    score = max(1, min(5, round(score)))

                    conn.execute("""
                        INSERT INTO responses (assessment_id, unit_id, question_id,
                                              respondent_type, score, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, [assessment_id, unit['id'], q['id'], resp_type, score, date])
                    response_count += 1

        print(f"  {period}: {response_count} responses")

    conn.commit()
    conn.close()

def update_existing_variation(unit_name, profiles):
    """Update existing Q1-Q4 assessments with more variation"""
    conn = get_db()

    # Get unit
    unit = conn.execute("""
        SELECT id FROM organizational_units WHERE name = ?
    """, [unit_name]).fetchone()

    if not unit:
        print(f"Unit not found: {unit_name}")
        return

    questions = conn.execute("""
        SELECT id, field, reverse_scored FROM questions WHERE is_default = 1
    """).fetchall()

    quarters = ['Q1 2025', 'Q2 2025', 'Q3 2025', 'Q4 2025']

    print(f"\nOpdaterer variation for {unit_name}:")

    for period in quarters:
        quarter_key = period.split()[0]
        target_scores = profiles.get(quarter_key, {})

        if not target_scores:
            continue

        # Get assessment
        assessment = conn.execute("""
            SELECT id FROM assessments
            WHERE target_unit_id = ? AND period = ?
        """, [unit['id'], period]).fetchone()

        if not assessment:
            print(f"  {period} ikke fundet")
            continue

        # Update responses
        responses = conn.execute("""
            SELECT r.id, r.question_id, r.respondent_type, q.field, q.reverse_scored
            FROM responses r
            JOIN questions q ON r.question_id = q.id
            WHERE r.assessment_id = ?
        """, [assessment['id']]).fetchall()

        updated = 0
        for r in responses:
            target = target_scores.get(r['field'], 3.5)

            # Add variation
            variation = random.gauss(0, 0.5)
            if random.random() < 0.1:
                variation = random.gauss(0, 1.0)

            score = target + variation

            if r['reverse_scored']:
                score = 6 - score

            score = max(1, min(5, round(score)))

            conn.execute("UPDATE responses SET score = ? WHERE id = ?", [score, r['id']])
            updated += 1

        print(f"  {period}: {updated} responses opdateret")

    conn.commit()
    conn.close()

def main():
    print("=== Fixing testdata trends ===\n")

    # Step 1: Delete duplicates
    print("1. Sletter duplikerede november-målinger...")
    delete_duplicate_november_assessments()

    # Step 2: Create Q1-Q4 for units that only have 1 measurement
    # Åparken: Starter godt, dykker i Q2-Q3 (sommerferie stress), kommer tilbage Q4
    aaparken_profiles = {
        'Q1': {'TRYGHED': 4.0, 'MENING': 4.3, 'KAN': 3.5, 'BESVÆR': 3.8},
        'Q2': {'TRYGHED': 3.6, 'MENING': 4.1, 'KAN': 3.2, 'BESVÆR': 3.4},  # Dyk
        'Q3': {'TRYGHED': 3.4, 'MENING': 3.9, 'KAN': 3.0, 'BESVÆR': 3.2},  # Lavest
        'Q4': {'TRYGHED': 3.8, 'MENING': 4.2, 'KAN': 3.4, 'BESVÆR': 3.6},  # Bedring
    }

    # Gødstrup: Starter lavt, forbedrer sig støt gennem året (intervention virker)
    godstrup_profiles = {
        'Q1': {'TRYGHED': 2.5, 'MENING': 2.3, 'KAN': 2.8, 'BESVÆR': 2.6},
        'Q2': {'TRYGHED': 2.9, 'MENING': 2.7, 'KAN': 3.1, 'BESVÆR': 2.9},
        'Q3': {'TRYGHED': 3.3, 'MENING': 3.2, 'KAN': 3.4, 'BESVÆR': 3.2},
        'Q4': {'TRYGHED': 3.6, 'MENING': 3.5, 'KAN': 3.7, 'BESVÆR': 3.5},
    }

    print("\n2. Opretter Q1-Q4 for enheder med kun 1 måling...")
    create_quarterly_assessments('Bofællesskabet Åparken', aaparken_profiles)
    create_quarterly_assessments('Gødstrup Skole', godstrup_profiles)

    # Step 3: Add more variation to existing units
    # Birk Skole: Stabilt god, men MENING dykker i Q3 (lederskift?)
    birk_profiles = {
        'Q1': {'TRYGHED': 3.9, 'MENING': 4.2, 'KAN': 3.8, 'BESVÆR': 3.7},
        'Q2': {'TRYGHED': 4.0, 'MENING': 4.1, 'KAN': 3.9, 'BESVÆR': 3.8},
        'Q3': {'TRYGHED': 3.8, 'MENING': 3.4, 'KAN': 3.7, 'BESVÆR': 3.5},  # MENING dyk
        'Q4': {'TRYGHED': 3.9, 'MENING': 3.7, 'KAN': 3.8, 'BESVÆR': 3.7},  # Bedring
    }

    # Aktivitetscentret: KAN starter lavt men forbedres markant
    aktivitet_profiles = {
        'Q1': {'TRYGHED': 3.3, 'MENING': 4.0, 'KAN': 2.2, 'BESVÆR': 3.2},
        'Q2': {'TRYGHED': 3.4, 'MENING': 3.9, 'KAN': 2.8, 'BESVÆR': 3.3},  # KAN bedres
        'Q3': {'TRYGHED': 3.5, 'MENING': 3.8, 'KAN': 3.3, 'BESVÆR': 3.4},  # KAN bedres mere
        'Q4': {'TRYGHED': 3.6, 'MENING': 3.9, 'KAN': 3.6, 'BESVÆR': 3.5},  # KAN meget bedre
    }

    print("\n3. Opdaterer variation for eksisterende enheder...")
    update_existing_variation('Birk Skole', birk_profiles)
    update_existing_variation('Aktivitetscentret Midt', aktivitet_profiles)

    print("\n=== Done! ===")

if __name__ == '__main__':
    main()

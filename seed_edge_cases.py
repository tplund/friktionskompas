"""
Seed edge-case testdata for Herning Kommune.

Tilføjer målinger med:
1. Stort gap mellem medarbejder og leder (~1.5 point)
2. Meget lave scores (<2.0 = kritisk)
3. Meget høje scores (>4.0 = alt er fint)
4. Høj spredning i svar (std_dev > 1.2)

Formål: Test at alle advarsels-scenarier i analysen fungerer.
"""
import sqlite3
import random
import os
from datetime import datetime
from secrets import token_urlsafe

# Herning Kommune ID
HERNING_CUSTOMER_ID = 'cust-0nlG8ldxSYU'

# Database path
DB_PATH = os.environ.get('DATABASE_PATH', '/var/data/friktionskompas_v3.db')
if not os.path.exists(DB_PATH):
    DB_PATH = 'friktionskompas_v3.db'


def generate_id(prefix: str) -> str:
    return f"{prefix}-{token_urlsafe(8)}"


def get_questions(conn) -> list:
    return conn.execute("""
        SELECT id, field, reverse_scored
        FROM questions
        WHERE is_default = 1 AND field IS NOT NULL
        ORDER BY sequence
    """).fetchall()


def get_or_create_edge_case_unit(conn, name: str, parent_name: str = None) -> str:
    """Find eller opret unit til edge-case tests"""

    # Find parent først
    if parent_name:
        parent = conn.execute("""
            SELECT id FROM organizational_units
            WHERE customer_id = ? AND name = ?
        """, [HERNING_CUSTOMER_ID, parent_name]).fetchone()
        parent_id = parent[0] if parent else None
    else:
        parent_id = None

    # Tjek om unit eksisterer
    if parent_id:
        existing = conn.execute("""
            SELECT id FROM organizational_units
            WHERE customer_id = ? AND name = ? AND parent_id = ?
        """, [HERNING_CUSTOMER_ID, name, parent_id]).fetchone()
    else:
        existing = conn.execute("""
            SELECT id FROM organizational_units
            WHERE customer_id = ? AND name = ? AND parent_id IS NULL
        """, [HERNING_CUSTOMER_ID, name]).fetchone()

    if existing:
        return existing[0]

    # Opret ny unit
    unit_id = generate_id('unit')
    level = 1 if parent_id else 0
    full_path = f"{parent_name}//{name}" if parent_name else name

    conn.execute("""
        INSERT INTO organizational_units (id, name, parent_id, customer_id, full_path, level)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [unit_id, name, parent_id, HERNING_CUSTOMER_ID, full_path, level])

    print(f"  Oprettet unit: {name}")
    return unit_id


def create_assessment_with_responses(conn, unit_id: str, name: str, questions: list,
                                      employee_scores: dict, leader_scores: dict = None,
                                      response_count: int = 30, leader_count: int = 3,
                                      score_variance: float = 0.5):
    """
    Opretter en måling med specificerede score-profiler.

    Args:
        employee_scores: {field: target_score} for medarbejdere
        leader_scores: {field: target_score} for leader_assess (hvis None, bruges employee_scores)
        score_variance: Hvor meget scores varierer omkring target
    """

    # Tjek om måling allerede eksisterer
    existing = conn.execute("""
        SELECT id FROM assessments WHERE target_unit_id = ? AND name = ?
    """, [unit_id, name]).fetchone()

    if existing:
        print(f"    Måling '{name}' eksisterer allerede")
        return existing[0]

    assessment_id = generate_id('assess')

    conn.execute("""
        INSERT INTO assessments (id, name, target_unit_id, created_at, period, include_leader_assessment)
        VALUES (?, ?, ?, ?, 'Edge Case Test', ?)
    """, [assessment_id, name, unit_id, datetime.now().strftime('%Y-%m-%d'),
          1 if leader_scores else 0])

    # Generer medarbejder-responses
    for _ in range(response_count):
        for q_id, field, is_reverse in questions:
            target = employee_scores.get(field, 4.0)
            # Tilføj varians
            score = target + random.uniform(-score_variance, score_variance)
            score = max(1, min(7, round(score)))

            conn.execute("""
                INSERT INTO responses (assessment_id, unit_id, question_id, score, created_at, respondent_type)
                VALUES (?, ?, ?, ?, ?, 'employee')
            """, [assessment_id, unit_id, q_id, score, datetime.now().isoformat()])

    # Generer leder-responses (leader_assess)
    if leader_scores:
        for _ in range(leader_count):
            for q_id, field, is_reverse in questions:
                target = leader_scores.get(field, 4.0)
                score = target + random.uniform(-score_variance, score_variance)
                score = max(1, min(7, round(score)))

                conn.execute("""
                    INSERT INTO responses (assessment_id, unit_id, question_id, score, created_at, respondent_type)
                    VALUES (?, ?, ?, ?, ?, 'leader_assess')
                """, [assessment_id, unit_id, q_id, score, datetime.now().isoformat()])

        # Også leader_self
        for _ in range(leader_count):
            for q_id, field, is_reverse in questions:
                target = leader_scores.get(field, 4.0) + 0.7  # Ledere scorer ofte sig selv højere
                score = target + random.uniform(-score_variance, score_variance)
                score = max(1, min(7, round(score)))

                conn.execute("""
                    INSERT INTO responses (assessment_id, unit_id, question_id, score, created_at, respondent_type)
                    VALUES (?, ?, ?, ?, ?, 'leader_self')
                """, [assessment_id, unit_id, q_id, score, datetime.now().isoformat()])

    print(f"    Oprettet: {name} ({response_count} emp + {leader_count if leader_scores else 0} leaders)")
    return assessment_id


def main():
    print("=" * 60)
    print("EDGE-CASE TESTDATA FOR HERNING KOMMUNE")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        questions = get_questions(conn)
        print(f"\nFandt {len(questions)} spørgsmål")

        # Opret "Test Cases" parent unit
        print("\n1. OPRETTER TEST-UNITS")
        print("-" * 40)

        test_parent_id = get_or_create_edge_case_unit(conn, "Edge Case Tests")

        # === EDGE CASE 1: Stort gap (medarbejdere ~3.2, ledere ~5.8 på 7-point skala) ===
        print("\n2. STORT GAP (medarbejder vs. leder)")
        print("-" * 40)

        gap_unit_id = get_or_create_edge_case_unit(conn, "Afd. med Stort Gap", "Edge Case Tests")
        create_assessment_with_responses(
            conn, gap_unit_id, "Gap Test - Kritisk Forskel",
            questions,
            employee_scores={'MENING': 3.0, 'TRYGHED': 3.3, 'KAN': 2.8, 'BESVÆR': 3.7},
            leader_scores={'MENING': 5.5, 'TRYGHED': 5.8, 'KAN': 5.2, 'BESVÆR': 6.3},
            response_count=25,
            leader_count=3,
            score_variance=0.4
        )

        # === EDGE CASE 2: Meget lave scores (kritisk) ===
        print("\n3. KRITISK LAVE SCORES")
        print("-" * 40)

        low_unit_id = get_or_create_edge_case_unit(conn, "Afd. i Krise", "Edge Case Tests")
        create_assessment_with_responses(
            conn, low_unit_id, "Krise Test - Alt er Galt",
            questions,
            employee_scores={'MENING': 1.8, 'TRYGHED': 1.5, 'KAN': 2.2, 'BESVÆR': 1.6},
            leader_scores={'MENING': 2.5, 'TRYGHED': 2.2, 'KAN': 2.8, 'BESVÆR': 2.4},
            response_count=20,
            leader_count=2,
            score_variance=0.5
        )

        # === EDGE CASE 3: Meget høje scores (alt er fint) ===
        print("\n4. HØJE SCORES (ALT ER FINT)")
        print("-" * 40)

        high_unit_id = get_or_create_edge_case_unit(conn, "Dream Team", "Edge Case Tests")
        create_assessment_with_responses(
            conn, high_unit_id, "Succes Test - Høj Trivsel",
            questions,
            employee_scores={'MENING': 6.3, 'TRYGHED': 6.6, 'KAN': 6.0, 'BESVÆR': 6.4},
            leader_scores={'MENING': 6.4, 'TRYGHED': 6.7, 'KAN': 6.1, 'BESVÆR': 6.6},
            response_count=30,
            leader_count=4,
            score_variance=0.4
        )

        # === EDGE CASE 4: Høj spredning (uenige medarbejdere) ===
        print("\n5. HØJ SPREDNING (UENIGHED)")
        print("-" * 40)

        spread_unit_id = get_or_create_edge_case_unit(conn, "Delt Afdeling", "Edge Case Tests")

        # Her bruger vi manuelt høj varians
        create_assessment_with_responses(
            conn, spread_unit_id, "Spredning Test - Stor Uenighed",
            questions,
            employee_scores={'MENING': 4.0, 'TRYGHED': 4.0, 'KAN': 4.0, 'BESVÆR': 4.0},
            leader_scores={'MENING': 4.8, 'TRYGHED': 4.8, 'KAN': 4.8, 'BESVÆR': 4.8},
            response_count=40,
            leader_count=3,
            score_variance=2.0  # Høj varians = stor spredning (øget for 7-point skala)
        )

        # === EDGE CASE 5: Kun TRYGHED er lav (test prioritering) ===
        print("\n6. KUN TRYGHED ER LAV (PRIORITERINGSTEST)")
        print("-" * 40)

        tryghed_unit_id = get_or_create_edge_case_unit(conn, "Utryg Afdeling", "Edge Case Tests")
        create_assessment_with_responses(
            conn, tryghed_unit_id, "Tryghed Test - Kun Psykologisk Sikkerhed",
            questions,
            employee_scores={'MENING': 5.5, 'TRYGHED': 2.5, 'KAN': 5.8, 'BESVÆR': 5.2},
            leader_scores={'MENING': 5.8, 'TRYGHED': 5.2, 'KAN': 5.5, 'BESVÆR': 5.5},
            response_count=25,
            leader_count=3,
            score_variance=0.5
        )

        conn.commit()

        # Vis resultater
        print("\n" + "=" * 60)
        print("EDGE-CASE DATA TILFØJET")
        print("=" * 60)

        edge_assessments = conn.execute("""
            SELECT c.name, COUNT(r.id) as responses
            FROM assessments c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            LEFT JOIN responses r ON r.assessment_id = c.id
            WHERE ou.customer_id = ? AND ou.full_path LIKE '%Edge Case%'
            GROUP BY c.id
            ORDER BY c.name
        """, [HERNING_CUSTOMER_ID]).fetchall()

        print("\nNye målinger:")
        for name, count in edge_assessments:
            print(f"  - {name}: {count} responses")

    finally:
        conn.close()

    print("\nFærdig!")


if __name__ == '__main__':
    main()

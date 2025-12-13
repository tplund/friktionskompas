"""
Seed komplet testdata for Herning Kommune (kanonisk test-kunde).

Dette script:
1. Tilføjer "Borgere" afdeling til B2C test
2. Genererer trend-data (kampagner over flere måneder)
3. Sikrer at alle rapport-sider har data

Brug: python seed_herning_testdata.py
"""

import sqlite3
import random
from datetime import datetime, timedelta
from secrets import token_urlsafe

# Herning Kommune ID
HERNING_CUSTOMER_ID = 'cust-0nlG8ldxSYU'

# Database path
DB_PATH = 'friktionskompas_v3.db'

# Friktionsfelter
FRICTION_FIELDS = ['MENING', 'TRYGHED', 'MULIGHED', 'KAN', 'BESVÆR']


def generate_id(prefix: str) -> str:
    """Genererer unikt ID med prefix"""
    return f"{prefix}-{token_urlsafe(8)}"


def get_questions(conn) -> list:
    """Hent alle aktive friktionsspørgsmål"""
    return conn.execute("""
        SELECT id, field, reverse_scored
        FROM questions
        WHERE is_default = 1 AND field IS NOT NULL
        ORDER BY sequence
    """).fetchall()


def generate_score(base_score: float, variance: float = 0.5) -> int:
    """Genererer plausibel score (1-5) med varians"""
    score = base_score + random.uniform(-variance, variance)
    return max(1, min(5, round(score)))


def create_borgere_unit(conn) -> str:
    """Opret 'Borgere' afdeling for B2C testdata"""

    # Tjek om den allerede eksisterer
    existing = conn.execute("""
        SELECT id FROM organizational_units
        WHERE customer_id = ? AND name = 'Borgere'
    """, [HERNING_CUSTOMER_ID]).fetchone()

    if existing:
        print(f"  'Borgere' afdeling eksisterer allerede: {existing[0]}")
        return existing[0]

    # Opret ny toplevel unit
    borgere_id = generate_id('unit')
    conn.execute("""
        INSERT INTO organizational_units (id, name, parent_id, customer_id, full_path, level)
        VALUES (?, 'Borgere', NULL, ?, 'Borgere', 0)
    """, [borgere_id, HERNING_CUSTOMER_ID])

    print(f"  Oprettet 'Borgere' afdeling: {borgere_id}")
    return borgere_id


def create_borgere_sub_units(conn, borgere_id: str) -> list:
    """Opret sub-units under Borgere for varieret B2C data"""

    sub_units = [
        ('Individuel Screening', 1),
        ('Par-profiler', 1),
        ('Karrierevejledning', 1),
    ]

    created = []
    for name, level in sub_units:
        # Tjek om den allerede eksisterer
        existing = conn.execute("""
            SELECT id FROM organizational_units
            WHERE customer_id = ? AND name = ? AND parent_id = ?
        """, [HERNING_CUSTOMER_ID, name, borgere_id]).fetchone()

        if existing:
            print(f"    '{name}' eksisterer allerede")
            created.append(existing[0])
            continue

        unit_id = generate_id('unit')
        full_path = f"Borgere // {name}"
        conn.execute("""
            INSERT INTO organizational_units (id, name, parent_id, customer_id, full_path, level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [unit_id, name, borgere_id, HERNING_CUSTOMER_ID, full_path, level])

        print(f"    Oprettet '{name}': {unit_id}")
        created.append(unit_id)

    return created


def generate_trend_campaigns(conn, questions):
    """Genererer kampagner over tid for trend-analyse (B2B med medarbejdere + ledere)"""

    # Hent eksisterende units (level 2 - de faktiske enheder, IKKE Borgere)
    units = conn.execute("""
        SELECT id, name FROM organizational_units
        WHERE customer_id = ? AND level = 2 AND name NOT LIKE '%Screening%' AND name NOT LIKE '%Par-%' AND name NOT LIKE '%Karriere%'
        ORDER BY name
        LIMIT 4
    """, [HERNING_CUSTOMER_ID]).fetchall()

    if not units:
        print("  Ingen B2B enheder fundet på level 2")
        return

    # Generer kampagner for Q1, Q2, Q3, Q4 2025 for udvalgte enheder
    periods = [
        ('2025-01-15', 'Q1 2025'),
        ('2025-04-15', 'Q2 2025'),
        ('2025-07-15', 'Q3 2025'),
        ('2025-10-15', 'Q4 2025'),
    ]

    for unit_id, unit_name in units[:2]:  # Kun de 2 første for at holde datasættet håndterbart
        print(f"  Genererer trend-data for: {unit_name}")

        # Base scores der ændrer sig over tid (simulerer forbedring)
        base_scores = {
            'MENING': 3.0,
            'TRYGHED': 2.5,
            'MULIGHED': 3.2,
            'KAN': 2.8,
            'BESVÆR': 2.3,
        }

        for i, (date_str, period_name) in enumerate(periods):
            # Tjek om kampagne allerede eksisterer
            existing = conn.execute("""
                SELECT id FROM campaigns
                WHERE target_unit_id = ? AND name LIKE ?
            """, [unit_id, f"%{period_name}%"]).fetchone()

            if existing:
                print(f"    {period_name} eksisterer allerede")
                continue

            # Skab gradvis forbedring over tid
            improvement = i * 0.15  # 0.15 point forbedring per kvartal

            campaign_id = generate_id('camp')
            campaign_name = f"{unit_name} - {period_name}"

            conn.execute("""
                INSERT INTO campaigns (id, name, target_unit_id, status, created_at, period, include_leader_assessment)
                VALUES (?, ?, ?, 'completed', ?, ?, 1)
            """, [campaign_id, campaign_name, unit_id, date_str, period_name])

            # Generer 25-35 responses per kampagne (medarbejdere + ledere)
            response_count = random.randint(25, 35)
            leader_count = random.randint(2, 4)  # 2-4 ledere per måling

            for r in range(response_count):
                response_time = datetime.strptime(date_str, '%Y-%m-%d') + timedelta(days=random.randint(0, 14))
                respondent_type = 'leader' if r < leader_count else 'employee'

                for q in questions:
                    q_id, field, is_reverse = q

                    # Beregn score med forbedring over tid
                    # Ledere har tendens til at score lidt højere
                    base = base_scores.get(field, 3.0) + improvement
                    if respondent_type == 'leader':
                        base += 0.3  # Ledere ser ofte tingene lidt mere positivt

                    score = generate_score(base, variance=0.8)

                    conn.execute("""
                        INSERT INTO responses (campaign_id, unit_id, question_id, score, created_at, respondent_type)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, [campaign_id, unit_id, q_id, score, response_time.isoformat(), respondent_type])

            print(f"    {period_name}: {response_count} responses ({leader_count} ledere)")


def generate_borgere_data(conn, borgere_unit_ids, questions):
    """Genererer B2C test-data for Borgere afdelinger (individuelle tests, par-profiler, etc.)"""

    for unit_id in borgere_unit_ids:
        unit_name = conn.execute("SELECT name FROM organizational_units WHERE id = ?", [unit_id]).fetchone()[0]

        # Tjek om der allerede er kampagner
        existing = conn.execute("""
            SELECT COUNT(*) FROM campaigns WHERE target_unit_id = ?
        """, [unit_id]).fetchone()[0]

        if existing > 0:
            print(f"    {unit_name}: har allerede {existing} kampagner")
            continue

        print(f"  Genererer data for: {unit_name}")

        # Opret én kampagne per B2C afdeling
        campaign_id = generate_id('camp')
        campaign_name = f"B2C - {unit_name}"

        # B2C kampagner: ingen leder-vurdering, individuel mode
        conn.execute("""
            INSERT INTO campaigns (id, name, target_unit_id, status, created_at, period, include_leader_assessment, mode)
            VALUES (?, ?, ?, 'completed', ?, 'December 2025', 0, 'anonymous')
        """, [campaign_id, campaign_name, unit_id, datetime.now().strftime('%Y-%m-%d')])

        # Generer 50-100 individuelle screenings
        response_count = random.randint(50, 100)

        for r in range(response_count):
            # B2C har mere spredning i scores (folk kommer fra meget forskellige situationer)
            for q in questions:
                q_id, field, is_reverse = q
                base = random.uniform(2.0, 4.0)  # Mere variation i B2C
                score = generate_score(base, variance=1.0)

                conn.execute("""
                    INSERT INTO responses (campaign_id, unit_id, question_id, score, created_at, respondent_type)
                    VALUES (?, ?, ?, ?, ?, 'employee')
                """, [campaign_id, unit_id, q_id, score, datetime.now().isoformat()])

        print(f"    Oprettet: {response_count} individuelle screenings")


def main():
    print("=" * 60)
    print("HERNING KOMMUNE - KOMPLET TESTDATA")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        # Hent spørgsmål
        questions = get_questions(conn)
        print(f"\nFandt {len(questions)} aktive spørgsmål")

        # 1. Opret Borgere afdeling
        print("\n1. BORGERE AFDELING (B2C)")
        print("-" * 40)
        borgere_id = create_borgere_unit(conn)
        borgere_sub_ids = create_borgere_sub_units(conn, borgere_id)

        # 2. Generer trend-data
        print("\n2. TREND-DATA (kampagner over tid)")
        print("-" * 40)
        generate_trend_campaigns(conn, questions)

        # 3. Generer B2C data
        print("\n3. B2C DATA")
        print("-" * 40)
        generate_borgere_data(conn, borgere_sub_ids, questions)

        conn.commit()

        # Vis resultater
        print("\n" + "=" * 60)
        print("RESULTAT")
        print("=" * 60)

        stats = {
            'units': conn.execute("SELECT COUNT(*) FROM organizational_units WHERE customer_id = ?",
                                  [HERNING_CUSTOMER_ID]).fetchone()[0],
            'campaigns': conn.execute("""
                SELECT COUNT(*) FROM campaigns c
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [HERNING_CUSTOMER_ID]).fetchone()[0],
            'responses': conn.execute("""
                SELECT COUNT(*) FROM responses r
                JOIN campaigns c ON r.campaign_id = c.id
                JOIN organizational_units ou ON c.target_unit_id = ou.id
                WHERE ou.customer_id = ?
            """, [HERNING_CUSTOMER_ID]).fetchone()[0],
        }

        print(f"Herning Kommune nu:")
        print(f"  Units: {stats['units']}")
        print(f"  Kampagner: {stats['campaigns']}")
        print(f"  Responses: {stats['responses']}")

    finally:
        conn.close()

    print("\nFærdig!")


if __name__ == '__main__':
    main()

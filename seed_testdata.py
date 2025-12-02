#!/usr/bin/env python3
"""
Seed script til at generere testdata på Render eller lokalt
Kør med: python seed_testdata.py
"""
import os
import sys
import random
from datetime import datetime, timedelta

# Tilføj projekt-root til path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_hierarchical import init_db, get_db, create_unit_from_path, create_campaign, generate_tokens_for_campaign
from db_multitenant import init_multitenant_db, create_customer, create_user
from db_profil import init_profil_tables, generate_test_profiles, get_db as get_profil_db

def seed_customers_and_users():
    """Opret test-kunder og brugere"""
    print("Opretter kunder og brugere...")

    # Opret kunder
    customers = [
        ("Demo Virksomhed A/S", "demo"),
        ("Test Organisation", "test"),
    ]

    customer_ids = []
    for name, slug in customers:
        try:
            cid = create_customer(name)
            customer_ids.append(cid)
            print(f"  Oprettet kunde: {name} (id={cid})")
        except Exception as e:
            print(f"  Kunde {name} eksisterer måske allerede: {e}")

    # Opret admin bruger (hvis ikke eksisterer)
    try:
        create_user("admin@friktionskompas.dk", "admin123", "Administrator", "admin", None)
        print("  Oprettet admin bruger: admin@friktionskompas.dk / admin123")
    except:
        print("  Admin bruger eksisterer allerede")

    # Opret manager brugere per kunde
    for i, cid in enumerate(customer_ids):
        try:
            email = f"manager{i+1}@test.dk"
            create_user(email, "test123", f"Manager {i+1}", "manager", cid)
            print(f"  Oprettet manager: {email} / test123")
        except:
            pass

    return customer_ids


def seed_organizations(customer_id):
    """Opret organisationsstruktur med units"""
    print(f"Opretter organisationsstruktur for kunde {customer_id}...")

    # Hierarkisk struktur
    units = [
        "Demo Virksomhed",
        "Demo Virksomhed//Salg",
        "Demo Virksomhed//Salg//Team Nord",
        "Demo Virksomhed//Salg//Team Syd",
        "Demo Virksomhed//IT",
        "Demo Virksomhed//IT//Udvikling",
        "Demo Virksomhed//IT//Support",
        "Demo Virksomhed//HR",
    ]

    created = []
    for path in units:
        try:
            unit_id = create_unit_from_path(path, customer_id)
            created.append((path, unit_id))
            print(f"  Oprettet: {path}")
        except Exception as e:
            print(f"  {path} eksisterer måske: {e}")

    return created


def seed_campaign_with_responses(customer_id, unit_path="Demo Virksomhed"):
    """Opret kampagne med test-responses"""
    print(f"Opretter kampagne for {unit_path}...")

    with get_db() as conn:
        # Find unit - prøv først med customer_id, ellers uden
        unit = conn.execute(
            "SELECT id FROM organizational_units WHERE full_path = ? AND customer_id = ?",
            (unit_path, customer_id)
        ).fetchone()

        if not unit:
            # Prøv uden customer_id filter (for eksisterende data)
            unit = conn.execute(
                "SELECT id FROM organizational_units WHERE full_path = ?",
                (unit_path,)
            ).fetchone()

        if not unit:
            print(f"  Unit ikke fundet: {unit_path}")
            return

        unit_id = unit['id']

        # Opret kampagne
        campaign_id = f"camp-test-{random.randint(1000, 9999)}"
        campaign_name = f"Test Kampagne {datetime.now().strftime('%d/%m')}"

        conn.execute("""
            INSERT INTO campaigns (id, name, target_unit_id, period, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (campaign_id, campaign_name, unit_id, "2024-Q4"))

        print(f"  Oprettet kampagne: {campaign_name}")

        # Hent alle leaf units under denne unit
        leaf_units = conn.execute("""
            WITH RECURSIVE descendants AS (
                SELECT id, full_path FROM organizational_units WHERE id = ?
                UNION ALL
                SELECT u.id, u.full_path FROM organizational_units u
                JOIN descendants d ON u.parent_id = d.id
            )
            SELECT id, full_path FROM descendants
            WHERE id NOT IN (SELECT DISTINCT parent_id FROM organizational_units WHERE parent_id IS NOT NULL)
        """, (unit_id,)).fetchall()

        # Hent spørgsmål
        questions = conn.execute("SELECT id, field FROM questions").fetchall()

        # Generer responses for hver leaf unit
        total_responses = 0
        for leaf in leaf_units:
            # 5-15 respondenter per unit
            num_respondents = random.randint(5, 15)

            for i in range(num_respondents):
                token = f"token-{leaf['id'][:8]}-{i}"
                respondent_type = random.choice(['employee', 'employee', 'employee', 'leader'])

                # Opret token
                conn.execute("""
                    INSERT OR IGNORE INTO tokens (token, campaign_id, unit_id, respondent_type, is_used, created_at)
                    VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (token, campaign_id, leaf['id'], respondent_type))

                # Generer svar for alle spørgsmål
                for q in questions:
                    # Realistisk score distribution
                    if respondent_type == 'leader':
                        # Ledere scorer typisk lidt lavere (mindre friktion)
                        score = random.choices([1, 2, 3, 4, 5], weights=[15, 30, 30, 20, 5])[0]
                    else:
                        # Medarbejdere har bredere variation
                        score = random.choices([1, 2, 3, 4, 5], weights=[10, 20, 35, 25, 10])[0]

                    conn.execute("""
                        INSERT INTO responses (token, campaign_id, unit_id, question_id, score, respondent_type, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (token, campaign_id, leaf['id'], q['id'], score, respondent_type))

                total_responses += len(questions)

        print(f"  Genereret {total_responses} responses for {len(leaf_units)} units")

        return campaign_id


def seed_profil_sessions():
    """Opret test profil-sessions"""
    print("Opretter profil test-data...")

    try:
        sessions = generate_test_profiles()
        print(f"  Oprettet {len(sessions)} test-profiler")
        for s in sessions:
            print(f"    - {s['name']}")
    except Exception as e:
        print(f"  Fejl ved profil-generering: {e}")


def main():
    print("=" * 60)
    print("  FRIKTIONSKOMPASSET - SEED TESTDATA")
    print("=" * 60)

    # Initialiser databaser
    print("\nInitialiserer databaser...")
    init_db()
    init_multitenant_db()
    init_profil_tables()

    # Seed data
    customer_ids = seed_customers_and_users()

    if customer_ids:
        cid = customer_ids[0]
        seed_organizations(cid)
        seed_campaign_with_responses(cid, "Demo Virksomhed")
        seed_campaign_with_responses(cid, "Demo Virksomhed//Salg")
        seed_campaign_with_responses(cid, "Demo Virksomhed//IT")

    seed_profil_sessions()

    # Vis statistik
    print("\n" + "=" * 60)
    print("  STATISTIK")
    print("=" * 60)

    with get_db() as conn:
        customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        units = conn.execute("SELECT COUNT(*) FROM organizational_units").fetchone()[0]
        campaigns = conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
        responses = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]

        print(f"  Kunder:     {customers}")
        print(f"  Brugere:    {users}")
        print(f"  Units:      {units}")
        print(f"  Kampagner:  {campaigns}")
        print(f"  Responses:  {responses}")

    with get_profil_db() as conn:
        sessions = conn.execute("SELECT COUNT(*) FROM profil_sessions").fetchone()[0]
        print(f"  Profiler:   {sessions}")

    print("\n  FÆRDIG!")
    print("\n  Login: admin@friktionskompas.dk / admin123")
    print("=" * 60)


if __name__ == "__main__":
    main()

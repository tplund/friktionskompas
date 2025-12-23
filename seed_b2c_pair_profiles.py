"""
Seed B2C customer with 10 sample pair profiles.
Creates varied response patterns to demonstrate different comparison scenarios.
"""
import secrets
from datetime import datetime, timedelta
from db import get_db
from db_profil import get_questions_by_field

# B2C Customer ID
B2C_CUSTOMER_ID = 'cust-B2C-profiles'

# 10 Par-profiler med forskellige scenarier
PAIR_PROFILES = [
    {
        'name': 'Par 1: Harmonisk par',
        'person_a': {'name': 'Anna', 'email': 'anna@example.com'},
        'person_b': {'name': 'Bo', 'email': 'bo@example.com'},
        'pattern': 'similar_high',  # Begge scorer hojt
        'description': 'Begge parter har hoj trivsel og lignende profiler'
    },
    {
        'name': 'Par 2: Stor forskel',
        'person_a': {'name': 'Clara', 'email': 'clara@example.com'},
        'person_b': {'name': 'David', 'email': 'david@example.com'},
        'pattern': 'opposite',  # A hoj, B lav
        'description': 'Stor kontrast - en trives, en kaemper'
    },
    {
        'name': 'Par 3: Kommunikationsfokus',
        'person_a': {'name': 'Eva', 'email': 'eva@example.com'},
        'person_b': {'name': 'Frank', 'email': 'frank@example.com'},
        'pattern': 'mening_gap',  # Stor forskel i MENING
        'description': 'Forskellige syn pa mening og formaal'
    },
    {
        'name': 'Par 4: Trygheds-udfordring',
        'person_a': {'name': 'Gitte', 'email': 'gitte@example.com'},
        'person_b': {'name': 'Hans', 'email': 'hans@example.com'},
        'pattern': 'tryghed_gap',  # Stor forskel i TRYGHED
        'description': 'En foler sig mere utryg end den anden'
    },
    {
        'name': 'Par 5: Kompetence-mismatch',
        'person_a': {'name': 'Ida', 'email': 'ida@example.com'},
        'person_b': {'name': 'Jakob', 'email': 'jakob@example.com'},
        'pattern': 'kan_gap',  # Stor forskel i KAN
        'description': 'Forskellig oplevelse af egne evner'
    },
    {
        'name': 'Par 6: Lavt gennemsnit',
        'person_a': {'name': 'Karen', 'email': 'karen@example.com'},
        'person_b': {'name': 'Lars', 'email': 'lars@example.com'},
        'pattern': 'similar_low',  # Begge scorer lavt
        'description': 'Begge parter kaemper - behov for stotte'
    },
    {
        'name': 'Par 7: Mellem-terren',
        'person_a': {'name': 'Mette', 'email': 'mette@example.com'},
        'person_b': {'name': 'Niels', 'email': 'niels@example.com'},
        'pattern': 'similar_medium',  # Begge midt i
        'description': 'Gennemsnitlige profiler med potentiale'
    },
    {
        'name': 'Par 8: Besvaer-fokus',
        'person_a': {'name': 'Olivia', 'email': 'olivia@example.com'},
        'person_b': {'name': 'Peter', 'email': 'peter@example.com'},
        'pattern': 'besvaer_gap',  # Stor forskel i BESVAER
        'description': 'Forskellig oplevelse af hverdagens besvaer'
    },
    {
        'name': 'Par 9: Positiv udvikling',
        'person_a': {'name': 'Rikke', 'email': 'rikke@example.com'},
        'person_b': {'name': 'Soren', 'email': 'soren@example.com'},
        'pattern': 'a_growth',  # A medium, B hoj
        'description': 'Den ene trakker opad'
    },
    {
        'name': 'Par 10: Komplementaere',
        'person_a': {'name': 'Tina', 'email': 'tina@example.com'},
        'person_b': {'name': 'Ulrik', 'email': 'ulrik@example.com'},
        'pattern': 'complementary',  # Forskellige styrker
        'description': 'Forskellige styrker der kompletterer hinanden'
    },
]


def generate_score(pattern: str, field: str, is_person_b: bool = False) -> int:
    """Generate a score based on pattern and field."""
    import random

    if pattern == 'similar_high':
        # Begge scorer 5-7
        return random.randint(5, 7)

    elif pattern == 'similar_low':
        # Begge scorer 1-3
        return random.randint(1, 3)

    elif pattern == 'similar_medium':
        # Begge scorer 3-5
        return random.randint(3, 5)

    elif pattern == 'opposite':
        # A: 5-7, B: 1-3
        if is_person_b:
            return random.randint(1, 3)
        return random.randint(5, 7)

    elif pattern == 'mening_gap':
        # Stor forskel kun i MENING
        if field.upper() == 'MENING':
            if is_person_b:
                return random.randint(1, 2)
            return random.randint(6, 7)
        return random.randint(4, 5)

    elif pattern == 'tryghed_gap':
        # Stor forskel kun i TRYGHED
        if field.upper() == 'TRYGHED':
            if is_person_b:
                return random.randint(2, 3)
            return random.randint(6, 7)
        return random.randint(4, 5)

    elif pattern == 'kan_gap':
        # Stor forskel kun i KAN
        if field.upper() == 'KAN':
            if is_person_b:
                return random.randint(2, 3)
            return random.randint(6, 7)
        return random.randint(4, 5)

    elif pattern == 'besvaer_gap':
        # Stor forskel kun i BESVAER
        if field.upper() == 'BESVÆR' or field.upper() == 'BESVAER':
            if is_person_b:
                return random.randint(2, 3)
            return random.randint(5, 6)
        return random.randint(4, 5)

    elif pattern == 'a_growth':
        # A medium, B hoj
        if is_person_b:
            return random.randint(5, 7)
        return random.randint(3, 5)

    elif pattern == 'complementary':
        # Forskellige styrker
        if field.upper() in ['TRYGHED', 'KAN']:
            if is_person_b:
                return random.randint(2, 4)
            return random.randint(5, 7)
        else:  # MENING, BESVAER
            if is_person_b:
                return random.randint(5, 7)
            return random.randint(2, 4)

    # Default
    return random.randint(3, 5)


def seed_b2c_customer():
    """Create B2C customer if not exists."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM customers WHERE id = ?",
            (B2C_CUSTOMER_ID,)
        ).fetchone()

        if existing:
            print(f"B2C customer already exists: {B2C_CUSTOMER_ID}")
            return

        conn.execute("""
            INSERT INTO customers (id, name, is_active, created_at)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
        """, (B2C_CUSTOMER_ID, 'B2C Profiles'))

        print(f"Created B2C customer: {B2C_CUSTOMER_ID}")


def seed_pair_profiles():
    """Create 10 pair profiles with varied response patterns."""
    questions = get_questions_by_field()
    all_questions = []
    for field, qs in questions.items():
        for q in qs:
            q['field'] = field
        all_questions.extend(qs)

    print(f"Found {len(all_questions)} questions across {len(questions)} fields")

    with get_db() as conn:
        for i, pair_config in enumerate(PAIR_PROFILES, 1):
            print(f"\nCreating {pair_config['name']}...")

            # Generate unique IDs
            pair_id = f"pair-b2c-{i:02d}"
            pair_code = f"B2C{i:03d}"
            session_a_id = f"profil-b2c-{i:02d}-a"
            session_b_id = f"profil-b2c-{i:02d}-b"

            # Check if already exists
            existing = conn.execute(
                "SELECT id FROM pair_sessions WHERE id = ?",
                (pair_id,)
            ).fetchone()

            if existing:
                print(f"  -> Already exists, skipping")
                continue

            # Create profil sessions for both persons
            created_at = datetime.now() - timedelta(days=30-i)  # Spread over last month

            conn.execute("""
                INSERT INTO profil_sessions
                (id, person_name, person_email, context, customer_id, is_complete, created_at, completed_at)
                VALUES (?, ?, ?, 'pair', ?, 1, ?, ?)
            """, (
                session_a_id,
                pair_config['person_a']['name'],
                pair_config['person_a']['email'],
                B2C_CUSTOMER_ID,
                created_at,
                created_at
            ))

            conn.execute("""
                INSERT INTO profil_sessions
                (id, person_name, person_email, context, customer_id, is_complete, created_at, completed_at)
                VALUES (?, ?, ?, 'pair', ?, 1, ?, ?)
            """, (
                session_b_id,
                pair_config['person_b']['name'],
                pair_config['person_b']['email'],
                B2C_CUSTOMER_ID,
                created_at + timedelta(hours=2),
                created_at + timedelta(hours=2)
            ))

            # Create pair session
            conn.execute("""
                INSERT INTO pair_sessions
                (id, pair_code, person_a_name, person_a_email, person_a_session_id,
                 person_b_name, person_b_email, person_b_session_id,
                 status, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'complete', ?, ?)
            """, (
                pair_id,
                pair_code,
                pair_config['person_a']['name'],
                pair_config['person_a']['email'],
                session_a_id,
                pair_config['person_b']['name'],
                pair_config['person_b']['email'],
                session_b_id,
                created_at,
                created_at + timedelta(hours=3)
            ))

            # Generate responses for person A
            for q in all_questions:
                score = generate_score(pair_config['pattern'], q['field'], is_person_b=False)
                conn.execute("""
                    INSERT INTO profil_responses (session_id, question_id, score)
                    VALUES (?, ?, ?)
                """, (session_a_id, q['id'], score))

            # Generate responses for person B
            for q in all_questions:
                score = generate_score(pair_config['pattern'], q['field'], is_person_b=True)
                conn.execute("""
                    INSERT INTO profil_responses (session_id, question_id, score)
                    VALUES (?, ?, ?)
                """, (session_b_id, q['id'], score))

            print(f"  -> Created: {pair_config['description']}")


def main():
    """Main seed function."""
    print("=" * 60)
    print("Seeding B2C Customer with Pair Profiles")
    print("=" * 60)

    # Initialize tables
    from db_profil import init_profil_tables
    init_profil_tables()

    # Create B2C customer
    seed_b2c_customer()

    # Create pair profiles
    seed_pair_profiles()

    print("\n" + "=" * 60)
    print("Done! Created 10 pair profiles for B2C customer.")
    print("View them in admin at /admin/pair-sessions")
    print("=" * 60)


if __name__ == '__main__':
    main()

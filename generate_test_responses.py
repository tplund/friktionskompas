"""
Generer test-responses for eksisterende kampagne
"""
from db_hierarchical import get_db
import random

def generate_test_responses():
    """Generer test-responses for test-kampagnen"""

    # Find test-kampagnen
    with get_db() as conn:
        campaign = conn.execute("""
            SELECT id, target_unit_id
            FROM campaigns
            WHERE name LIKE '%Test%' OR name LIKE '%Nye Sp%'
            ORDER BY created_at DESC
            LIMIT 1
        """).fetchone()

        if not campaign:
            print("[ERROR] Ingen test-kampagne fundet")
            return

        campaign_id = campaign['id']
        unit_id = campaign['target_unit_id']

        print(f"[OK] Genererer test-responses for kampagne: {campaign_id}")
        print(f"[OK] Unit: {unit_id}")

        # Hent alle spørgsmål
        questions = conn.execute("""
            SELECT id, field FROM questions WHERE is_default = 1 ORDER BY sequence
        """).fetchall()

        print(f"[OK] Fandt {len(questions)} spørgsmål")

        # Generer svar for 7 medarbejdere (over anonymitetsgrænsen på 5)
        for i in range(7):
            respondent_name = f"TestMedarbejder{i+1}"

            for question in questions:
                q_id = question['id']
                field = question['field']

                # Generer realistiske scores baseret på felt
                # MENING og TRYGHED: middel til høj (3-5)
                # MULIGHED: middel (2-4)
                # BESVÆR: lav til middel (2-4)
                if field == 'MENING':
                    score = random.choice([3, 3, 4, 4, 5])
                elif field == 'TRYGHED':
                    score = random.choice([3, 3, 4, 4, 4, 5])
                elif field == 'MULIGHED':
                    score = random.choice([2, 3, 3, 4, 4])
                else:  # BESVÆR
                    score = random.choice([2, 2, 3, 3, 4])

                # Første medarbejder får fritekst
                comment = None
                if i == 0 and q_id == questions[0]['id']:
                    comment = "Generelt fungerer tingene godt, men der er plads til forbedring i værktøjssupporten."

                conn.execute("""
                    INSERT INTO responses
                    (campaign_id, unit_id, question_id, score, respondent_type, respondent_name, comment)
                    VALUES (?, ?, ?, ?, 'employee', ?, ?)
                """, (campaign_id, unit_id, q_id, score, respondent_name, comment))

        print(f"[OK] Genereret {7 * len(questions)} test-responses")

        # Generer 1 leder-vurdering
        for question in questions:
            q_id = question['id']
            field = question['field']

            # Ledere vurderer typisk lidt højere end medarbejdere
            if field == 'MENING':
                score = random.choice([4, 4, 5, 5])
            elif field == 'TRYGHED':
                score = random.choice([4, 4, 5, 5])
            elif field == 'MULIGHED':
                score = random.choice([3, 4, 4, 5])
            else:  # BESVÆR
                score = random.choice([3, 3, 4, 4])

            conn.execute("""
                INSERT INTO responses
                (campaign_id, unit_id, question_id, score, respondent_type, respondent_name)
                VALUES (?, ?, ?, ?, 'leader_assess', 'TestLeder')
            """, (campaign_id, unit_id, q_id, score))

        print(f"[OK] Genereret leder-vurdering")

        # Generer 1 leder-self
        for question in questions:
            q_id = question['id']
            field = question['field']

            # Leder selv: realistisk profil
            if field == 'MENING':
                score = random.choice([4, 5, 5])
            elif field == 'TRYGHED':
                score = random.choice([2, 3, 3, 4])  # Lav tryghed!
            elif field == 'MULIGHED':
                score = random.choice([3, 3, 4])
            else:  # BESVÆR
                score = random.choice([3, 4, 4])

            conn.execute("""
                INSERT INTO responses
                (campaign_id, unit_id, question_id, score, respondent_type, respondent_name)
                VALUES (?, ?, ?, ?, 'leader_self', 'TestLeder')
            """, (campaign_id, unit_id, q_id, score))

        print(f"[OK] Genereret leder-self")

        # Verificer resultater
        total = conn.execute("""
            SELECT COUNT(*) as cnt FROM responses WHERE campaign_id = ?
        """, (campaign_id,)).fetchone()['cnt']

        print(f"\n[OK] KOMPLET! Total responses i databasen: {total}")
        print(f"[OK] Du kan nu se data i dashboardet")

if __name__ == '__main__':
    generate_test_responses()

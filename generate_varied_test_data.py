"""
Generer varierede test-responses med forskellige friktionsprofiler
- Høje friktioner (problematiske teams)
- Lave friktioner (velfungerende teams)
- Gennemsnitlige (normale teams)
- Ubalancerede profiler
- Varierende spredning (enighed vs uenighed)
"""
from db_hierarchical import get_db
import random
import math

# Definér forskellige friktionsprofiler
PROFILES = {
    'excellent': {
        'name': 'Fremragende team',
        'base_scores': {'MENING': 4.5, 'TRYGHED': 4.5, 'KAN': 4.3, 'BESVÆR': 4.2},
        'spread': 0.3,  # Lav spredning - meget enige
        'leader_gap': 0.2,  # Lille gap
    },
    'good': {
        'name': 'Godt fungerende team',
        'base_scores': {'MENING': 3.8, 'TRYGHED': 3.9, 'KAN': 3.7, 'BESVÆR': 3.6},
        'spread': 0.5,
        'leader_gap': 0.3,
    },
    'average': {
        'name': 'Gennemsnitligt team',
        'base_scores': {'MENING': 3.2, 'TRYGHED': 3.3, 'KAN': 3.0, 'BESVÆR': 3.1},
        'spread': 0.6,
        'leader_gap': 0.4,
    },
    'struggling': {
        'name': 'Udfordret team',
        'base_scores': {'MENING': 2.5, 'TRYGHED': 2.3, 'KAN': 2.8, 'BESVÆR': 2.4},
        'spread': 0.9,  # Høj spredning - meget uenige
        'leader_gap': 0.8,  # Stort gap mellem leder og medarbejdere
    },
    'critical': {
        'name': 'Kritisk team',
        'base_scores': {'MENING': 1.8, 'TRYGHED': 1.9, 'KAN': 2.0, 'BESVÆR': 1.7},
        'spread': 1.2,  # Meget høj spredning
        'leader_gap': 1.5,  # Meget stort gap
    },
    'substitution': {
        'name': 'Substitution-team',
        'base_scores': {'MENING': 2.2, 'TRYGHED': 2.3, 'KAN': 2.4, 'BESVÆR': 4.5},  # Paradoks: høj BESVÆR
        'spread': 0.7,
        'leader_gap': 1.0,
    },
    'unbalanced_meaning': {
        'name': 'Mangler mening',
        'base_scores': {'MENING': 1.9, 'TRYGHED': 3.8, 'KAN': 3.6, 'BESVÆR': 3.4},
        'spread': 0.8,
        'leader_gap': 0.9,
    },
    'unbalanced_safety': {
        'name': 'Mangler tryghed',
        'base_scores': {'MENING': 3.7, 'TRYGHED': 2.0, 'KAN': 3.5, 'BESVÆR': 3.2},
        'spread': 1.0,
        'leader_gap': 1.2,
    },
    'blocked_leader': {
        'name': 'Blokeret leder',
        'base_scores': {'MENING': 2.3, 'TRYGHED': 2.1, 'KAN': 2.2, 'BESVÆR': 2.0},
        'spread': 0.6,
        'leader_gap': 0.3,  # Lille gap - leder er også ramt
        'leader_self_low': True,  # Leder har også lave scores
    },
    'harmonious_low': {
        'name': 'Harmonisk men lavt',
        'base_scores': {'MENING': 2.6, 'TRYGHED': 2.5, 'KAN': 2.7, 'BESVÆR': 2.6},
        'spread': 0.3,  # Meget enige, bare enige om at det er dårligt
        'leader_gap': 0.2,
    },
    'polarized': {
        'name': 'Polariseret team',
        'base_scores': {'MENING': 3.0, 'TRYGHED': 3.2, 'KAN': 3.1, 'BESVÆR': 2.9},
        'spread': 1.5,  # Ekstremt høj spredning - meget uenige
        'leader_gap': 0.5,
    },
}


def clip_score(score):
    """Clip score til 1-5 range"""
    return max(1, min(5, round(score)))


def generate_scores_with_spread(base_score, spread, num_responses):
    """Generer scores med specifik spredning omkring en base score"""
    scores = [random.gauss(base_score, spread) for _ in range(num_responses)]
    return [clip_score(s) for s in scores]


def generate_campaign_responses(campaign_id, unit_id, profile_key, num_employees=8):
    """Generer responses for en kampagne med specifik profil"""

    profile = PROFILES[profile_key]

    with get_db() as conn:
        # Hent alle spørgsmål
        questions = conn.execute("""
            SELECT id, field FROM questions WHERE is_default = 1 ORDER BY sequence
        """).fetchall()

        # Gruppér spørgsmål efter felt
        questions_by_field = {}
        for q in questions:
            field = q['field']
            if field not in questions_by_field:
                questions_by_field[field] = []
            questions_by_field[field].append(q['id'])

        print(f"\n=== Genererer: {profile['name']} ({profile_key}) ===")
        print(f"    Antal medarbejdere: {num_employees}")

        # Generer medarbejder-responses
        for field, base_score in profile['base_scores'].items():
            # Generer scores med variation
            scores = generate_scores_with_spread(
                base_score,
                profile['spread'],
                num_employees
            )

            # Fordel scores på spørgsmål i dette felt
            field_questions = questions_by_field.get(field, [])

            for emp_idx in range(num_employees):
                respondent_name = f"Medarbejder_{profile_key}_{emp_idx+1}"

                for q_id in field_questions:
                    score = scores[emp_idx]

                    conn.execute("""
                        INSERT INTO responses
                        (campaign_id, unit_id, question_id, score, respondent_type, respondent_name)
                        VALUES (?, ?, ?, ?, 'employee', ?)
                    """, (campaign_id, unit_id, q_id, score, respondent_name))

            print(f"    {field}: {base_score:.1f} (σ={profile['spread']:.1f}) → scores: {sorted(scores)}")

        # Generer leder vurdering (leader_assess)
        # Leder vurderer typisk lidt højere end virkeligheden
        for field, base_score in profile['base_scores'].items():
            leader_score = base_score + profile.get('leader_gap', 0.5)
            leader_score = clip_score(leader_score)

            field_questions = questions_by_field.get(field, [])
            for q_id in field_questions:
                # Tilføj lidt variation til lederens vurdering
                score = clip_score(leader_score + random.uniform(-0.3, 0.3))

                conn.execute("""
                    INSERT INTO responses
                    (campaign_id, unit_id, question_id, score, respondent_type, respondent_name)
                    VALUES (?, ?, ?, ?, 'leader_assess', ?)
                """, (campaign_id, unit_id, q_id, score, f"Leder_{profile_key}"))

        # Generer leder self-assessment
        if profile.get('leader_self_low'):
            # Leder har også problemer (blokeret leder)
            leader_self_scores = {
                field: clip_score(score + random.uniform(-0.2, 0.2))
                for field, score in profile['base_scores'].items()
            }
        else:
            # Leder har det selv fint
            leader_self_scores = {
                'MENING': clip_score(4.0 + random.uniform(-0.3, 0.5)),
                'TRYGHED': clip_score(3.8 + random.uniform(-0.5, 0.5)),
                'KAN': clip_score(3.9 + random.uniform(-0.3, 0.4)),
                'BESVÆR': clip_score(3.7 + random.uniform(-0.3, 0.4)),
            }

        for field, score in leader_self_scores.items():
            field_questions = questions_by_field.get(field, [])
            for q_id in field_questions:
                actual_score = clip_score(score + random.uniform(-0.2, 0.2))

                conn.execute("""
                    INSERT INTO responses
                    (campaign_id, unit_id, question_id, score, respondent_type, respondent_name)
                    VALUES (?, ?, ?, ?, 'leader_self', ?)
                """, (campaign_id, unit_id, q_id, actual_score, f"Leder_{profile_key}"))

        print(f"    ✓ Færdig")


def main():
    """Generer varierede test-data for alle kampagner"""

    with get_db() as conn:
        # Find alle kampagner
        campaigns = conn.execute("""
            SELECT c.id, c.name, c.target_unit_id, ou.name as unit_name
            FROM campaigns c
            JOIN organizational_units ou ON c.target_unit_id = ou.id
            ORDER BY c.created_at DESC
        """).fetchall()

        if not campaigns:
            print("[ERROR] Ingen kampagner fundet")
            return

        print(f"[OK] Fandt {len(campaigns)} kampagner")

        # Assign different profiles to different campaigns
        profile_keys = list(PROFILES.keys())

        for idx, campaign in enumerate(campaigns):
            # Slet eksisterende responses for denne kampagne
            conn.execute("DELETE FROM responses WHERE campaign_id = ?", (campaign['id'],))

            # Vælg profil (roter gennem profilerne)
            profile_key = profile_keys[idx % len(profile_keys)]

            # Variér antallet af medarbejdere
            num_employees = random.choice([6, 7, 8, 9, 10, 12])

            print(f"\nKampagne: {campaign['name']} ({campaign['unit_name']})")
            generate_campaign_responses(
                campaign['id'],
                campaign['target_unit_id'],
                profile_key,
                num_employees
            )

        # Verificer resultater
        total = conn.execute("SELECT COUNT(*) as cnt FROM responses").fetchone()['cnt']
        print(f"\n{'='*60}")
        print(f"[OK] KOMPLET! Total responses i databasen: {total}")
        print(f"[OK] Du kan nu se varierede data i dashboardet")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()

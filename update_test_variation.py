"""
Script til at skabe mere variation i testdata
Forskellige organisationer får forskellige profiler
"""
import random
from db_hierarchical import get_db

# Definér profiler for forskellige organisationstyper
ORGANIZATION_PROFILES = {
    # Skoler - generelt god trivsel, men udfordringer med KAN (ressourcer)
    'Birk Skole': {
        'MENING': (3.8, 4.5),      # Høj mening - lærere føler formål
        'TRYGHED': (3.5, 4.2),     # God tryghed
        'KAN': (2.2, 3.0),         # Lav - mangler ressourcer/tid
        'BESVÆR': (3.0, 3.8),      # Moderat besvær
    },
    'Gødstrup Skole': {
        'MENING': (2.0, 2.8),      # Lav mening - demotiveret personale
        'TRYGHED': (2.5, 3.2),     # Moderat tryghed
        'KAN': (2.8, 3.5),         # OK ressourcer
        'BESVÆR': (2.0, 2.8),      # Højt besvær - tunge processer
    },
    'Hammerum Skole': {
        'MENING': (4.0, 4.8),      # Meget høj mening
        'TRYGHED': (4.2, 4.8),     # Meget høj tryghed - godt miljø
        'KAN': (3.5, 4.2),         # Gode ressourcer
        'BESVÆR': (3.8, 4.5),      # Lavt besvær - effektive processer
    },
    'Snejbjerg Skole': {
        'MENING': (3.0, 3.8),      # Moderat mening
        'TRYGHED': (2.0, 2.8),     # Lav tryghed - konflikter
        'KAN': (3.2, 4.0),         # OK ressourcer
        'BESVÆR': (3.0, 3.8),      # Moderat besvær
    },

    # Plejecentre - ofte højt besvær og lav KAN
    'Aktivitetscentret Midt': {
        'MENING': (3.5, 4.2),      # God mening - meningsfuldt arbejde
        'TRYGHED': (3.0, 3.8),     # Moderat tryghed
        'KAN': (1.8, 2.5),         # Meget lav - underbemandet
        'BESVÆR': (1.5, 2.3),      # Meget højt besvær - dokumentation
    },
    'Bofællesskabet Åparken': {
        'MENING': (4.2, 4.8),      # Meget høj mening
        'TRYGHED': (3.8, 4.5),     # Høj tryghed
        'KAN': (3.0, 3.8),         # OK ressourcer
        'BESVÆR': (2.5, 3.2),      # Noget besvær
    },

    # Administration - ofte høj KAN men varierende mening
    'Støttecentret Vestergade': {
        'MENING': (2.2, 3.0),      # Lav mening - rutinearbejde
        'TRYGHED': (3.5, 4.2),     # God tryghed
        'KAN': (4.0, 4.8),         # Høj KAN - gode systemer
        'BESVÆR': (3.5, 4.2),      # Lavt besvær
    },
}

# Default profil for units uden specifik profil
DEFAULT_PROFILE = {
    'MENING': (2.8, 3.8),
    'TRYGHED': (2.8, 3.8),
    'KAN': (2.8, 3.8),
    'BESVÆR': (2.8, 3.8),
}

def get_score_for_field(profile, field):
    """Generer en score baseret på profil med normal distribution"""
    low, high = profile.get(field, DEFAULT_PROFILE[field])
    # Brug triangular distribution for mere realistisk spredning
    mid = (low + high) / 2
    score = random.triangular(low, high, mid)
    # Clamp til 1-5
    return max(1, min(5, round(score)))

def update_responses():
    """Opdater alle responses med mere varierede scores"""

    with get_db() as conn:
        # Hent alle responses med unit og question info
        responses = conn.execute("""
            SELECT r.id, r.assessment_id, r.unit_id, r.question_id, r.respondent_type,
                   ou.name as unit_name, q.field
            FROM responses r
            JOIN organizational_units ou ON r.unit_id = ou.id
            JOIN questions q ON r.question_id = q.id
            WHERE r.respondent_type = 'employee'
        """).fetchall()

        print(f"Opdaterer {len(responses)} employee responses...")

        # Gruppér efter unit for at holde styr på hvilken profil
        updates = []
        for r in responses:
            unit_name = r['unit_name']
            field = r['field']

            # Find profil for denne unit
            profile = None
            for key in ORGANIZATION_PROFILES:
                if key in unit_name:
                    profile = ORGANIZATION_PROFILES[key]
                    break

            if profile is None:
                profile = DEFAULT_PROFILE

            new_score = get_score_for_field(profile, field)
            updates.append((new_score, r['id']))

        # Batch update
        conn.executemany("UPDATE responses SET score = ? WHERE id = ?", updates)
        print(f"Opdateret {len(updates)} responses")

        # Opdater også leader_assess (leders vurdering af team)
        # Ledere ser ofte tingene lidt mere positivt
        leader_responses = conn.execute("""
            SELECT r.id, r.unit_id, ou.name as unit_name, q.field
            FROM responses r
            JOIN organizational_units ou ON r.unit_id = ou.id
            JOIN questions q ON r.question_id = q.id
            WHERE r.respondent_type = 'leader_assess'
        """).fetchall()

        print(f"Opdaterer {len(leader_responses)} leader_assess responses...")

        leader_updates = []
        for r in leader_responses:
            unit_name = r['unit_name']
            field = r['field']

            profile = None
            for key in ORGANIZATION_PROFILES:
                if key in unit_name:
                    profile = ORGANIZATION_PROFILES[key]
                    break

            if profile is None:
                profile = DEFAULT_PROFILE

            # Ledere scorer typisk 0.5-1.0 højere end medarbejdere
            low, high = profile.get(field, DEFAULT_PROFILE[field])
            leader_low = min(5, low + 0.5)
            leader_high = min(5, high + 0.8)
            leader_profile = {field: (leader_low, leader_high)}

            new_score = get_score_for_field(leader_profile, field)
            leader_updates.append((new_score, r['id']))

        conn.executemany("UPDATE responses SET score = ? WHERE id = ?", leader_updates)
        print(f"Opdateret {len(leader_updates)} leader_assess responses")

        # Leader_self (lederens selvvurdering) - varierer mere
        leader_self = conn.execute("""
            SELECT r.id, r.unit_id, ou.name as unit_name, q.field
            FROM responses r
            JOIN organizational_units ou ON r.unit_id = ou.id
            JOIN questions q ON r.question_id = q.id
            WHERE r.respondent_type = 'leader_self'
        """).fetchall()

        print(f"Opdaterer {len(leader_self)} leader_self responses...")

        self_updates = []
        for r in leader_self:
            # Leader self varierer mere - nogle ledere er selvkritiske, andre optimistiske
            new_score = random.choice([2, 3, 3, 4, 4, 4, 5])
            self_updates.append((new_score, r['id']))

        conn.executemany("UPDATE responses SET score = ? WHERE id = ?", self_updates)
        print(f"Opdateret {len(self_updates)} leader_self responses")

        # Vis resultat
        print("\n--- Ny fordeling per organisation ---")
        stats = conn.execute("""
            SELECT ou.name,
                   ROUND(AVG(CASE WHEN q.field = 'MENING' THEN r.score END), 1) as mening,
                   ROUND(AVG(CASE WHEN q.field = 'TRYGHED' THEN r.score END), 1) as tryghed,
                   ROUND(AVG(CASE WHEN q.field = 'KAN' THEN r.score END), 1) as kan,
                   ROUND(AVG(CASE WHEN q.field = 'BESVÆR' THEN r.score END), 1) as besvaer,
                   COUNT(DISTINCT r.id) as responses
            FROM responses r
            JOIN organizational_units ou ON r.unit_id = ou.id
            JOIN questions q ON r.question_id = q.id
            WHERE r.respondent_type = 'employee'
            GROUP BY ou.id
            ORDER BY ou.name
        """).fetchall()

        for s in stats:
            print(f"{s['name']}: M={s['mening']} T={s['tryghed']} K={s['kan']} B={s['besvaer']} ({s['responses']} svar)")

if __name__ == '__main__':
    random.seed(42)  # For reproducerbarhed
    update_responses()

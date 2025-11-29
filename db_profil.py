"""
Database setup for Friktionsprofil - Individuel friktionsmåling
Måler hvordan pres bevæger sig gennem en persons reguleringsarkitektur
"""
import sqlite3
import secrets
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = "friktionskompas_v3.db"

@contextmanager
def get_db():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_profil_tables():
    """Initialize profil-specific tables"""
    with get_db() as conn:
        # Friktionsprofil spørgsmål
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profil_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field TEXT NOT NULL,
                layer TEXT NOT NULL,
                text_da TEXT NOT NULL,
                reverse_scored INTEGER DEFAULT 0,
                sequence INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Friktionsprofil sessioner
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profil_sessions (
                id TEXT PRIMARY KEY,
                person_name TEXT,
                person_email TEXT,
                context TEXT DEFAULT 'general',

                -- Valgfri kobling til organisation
                customer_id TEXT,
                unit_id TEXT,

                -- Metadata
                is_complete INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,

                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id)
            )
        """)

        # Friktionsprofil svar
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profil_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (session_id) REFERENCES profil_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES profil_questions(id)
            )
        """)

        # Profil-sammenligning
        conn.execute("""
            CREATE TABLE IF NOT EXISTS profil_comparisons (
                id TEXT PRIMARY KEY,
                session_id_1 TEXT NOT NULL,
                session_id_2 TEXT NOT NULL,
                context TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (session_id_1) REFERENCES profil_sessions(id),
                FOREIGN KEY (session_id_2) REFERENCES profil_sessions(id)
            )
        """)

        # Indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_profil_responses_session
            ON profil_responses(session_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_profil_sessions_customer
            ON profil_sessions(customer_id)
        """)

        # Indsæt default spørgsmål hvis tom
        count = conn.execute("SELECT COUNT(*) as cnt FROM profil_questions").fetchone()['cnt']

        if count == 0:
            _insert_default_questions(conn)


def _insert_default_questions(conn):
    """Indsæt de 16 standard friktionsprofil-spørgsmål"""
    questions = [
        # TRYGHED - 4 spørgsmål
        ("TRYGHED", "BIOLOGI", "Jeg reagerer hurtigt fysisk, når noget virker uforudsigeligt", 0, 1),
        ("TRYGHED", "EMOTION", "Jeg opfanger små signaler eller stemninger meget tydeligt", 0, 2),
        ("TRYGHED", "INDRE", "Jeg bliver urolig, hvis min oplevelse af virkeligheden bliver udfordret", 0, 3),
        ("TRYGHED", "KOGNITION", "Jeg falder til ro, når jeg forstår, hvad der foregår", 1, 4),  # Omvendt

        # MENING - 4 spørgsmål
        ("MENING", "BIOLOGI", "Når noget ikke giver mening, føles det fysisk forkert", 0, 5),
        ("MENING", "EMOTION", "Jeg mærker stærkt, hvad der er vigtigt for mig", 0, 6),
        ("MENING", "INDRE", "Jeg får hurtigt retning, når jeg tænker over noget", 1, 7),  # Omvendt
        ("MENING", "KOGNITION", "Jeg kan holde meget pres ud, hvis meningen er klar", 1, 8),  # Omvendt

        # KAN - 4 spørgsmål
        ("KAN", "BIOLOGI", "Jeg mærker energifald hurtigt i kroppen", 0, 9),
        ("KAN", "EMOTION", "Jeg bliver let overvældet, hvis der er mange ting på én gang", 0, 10),
        ("KAN", "INDRE", "Jeg regulerer mig selv bedst ved at forstå, hvad jeg skal", 1, 11),  # Omvendt
        ("KAN", "KOGNITION", "Jeg kan tænke klart, selv når jeg er presset", 1, 12),  # Omvendt

        # BESVÆR - 4 spørgsmål
        ("BESVÆR", "BIOLOGI", "Små ting kan føles tunge, når jeg er træt", 0, 13),
        ("BESVÆR", "EMOTION", "Jeg undgår ting, der føles som bøvl eller kompleksitet", 0, 14),
        ("BESVÆR", "INDRE", "Jeg gør ting lettere ved at forstå processen", 1, 15),  # Omvendt
        ("BESVÆR", "KOGNITION", "Jeg mister overblik i opgaver med mange små elementer", 0, 16),
    ]

    for field, layer, text, reverse, seq in questions:
        conn.execute(
            """INSERT INTO profil_questions
               (field, layer, text_da, reverse_scored, sequence)
               VALUES (?, ?, ?, ?, ?)""",
            (field, layer, text, reverse, seq)
        )


# ========================================
# SESSION FUNCTIONS
# ========================================

def create_session(
    person_name: Optional[str] = None,
    person_email: Optional[str] = None,
    context: str = 'general',
    customer_id: Optional[str] = None,
    unit_id: Optional[str] = None
) -> str:
    """Opret ny profil-session"""
    session_id = f"profil-{secrets.token_urlsafe(12)}"

    with get_db() as conn:
        conn.execute(
            """INSERT INTO profil_sessions
               (id, person_name, person_email, context, customer_id, unit_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, person_name, person_email, context, customer_id, unit_id)
        )

    return session_id


def get_session(session_id: str) -> Optional[Dict]:
    """Hent session med metadata"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM profil_sessions WHERE id = ?",
            (session_id,)
        ).fetchone()

        if row:
            return dict(row)
    return None


def complete_session(session_id: str):
    """Marker session som færdig"""
    with get_db() as conn:
        conn.execute(
            """UPDATE profil_sessions
               SET is_complete = 1, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (session_id,)
        )


def list_sessions(
    customer_id: Optional[str] = None,
    include_incomplete: bool = False
) -> List[Dict]:
    """List alle sessioner, valgfrit filtreret på kunde"""
    with get_db() as conn:
        query = "SELECT * FROM profil_sessions WHERE 1=1"
        params = []

        if customer_id:
            query += " AND customer_id = ?"
            params.append(customer_id)

        if not include_incomplete:
            query += " AND is_complete = 1"

        query += " ORDER BY created_at DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# ========================================
# QUESTION FUNCTIONS
# ========================================

def get_all_questions() -> List[Dict]:
    """Hent alle profil-spørgsmål i rækkefølge"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM profil_questions
               ORDER BY sequence"""
        ).fetchall()
        return [dict(row) for row in rows]


def get_questions_by_field() -> Dict[str, List[Dict]]:
    """Hent spørgsmål grupperet efter felt"""
    questions = get_all_questions()
    grouped = {}

    for q in questions:
        field = q['field']
        if field not in grouped:
            grouped[field] = []
        grouped[field].append(q)

    return grouped


# ========================================
# RESPONSE FUNCTIONS
# ========================================

def save_responses(session_id: str, responses: Dict[int, int]):
    """
    Gem svar for en session
    responses: {question_id: score}
    """
    with get_db() as conn:
        for question_id, score in responses.items():
            conn.execute(
                """INSERT INTO profil_responses
                   (session_id, question_id, score)
                   VALUES (?, ?, ?)""",
                (session_id, question_id, score)
            )


def get_responses(session_id: str) -> List[Dict]:
    """Hent alle svar for en session med spørgsmålsinfo"""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT pr.*, pq.field, pq.layer, pq.text_da, pq.reverse_scored
               FROM profil_responses pr
               JOIN profil_questions pq ON pr.question_id = pq.id
               WHERE pr.session_id = ?
               ORDER BY pq.sequence""",
            (session_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_response_matrix(session_id: str) -> Dict[str, Dict[str, float]]:
    """
    Hent svar som 4x4 matrix: {felt: {lag: score}}
    Håndterer reverse scoring
    """
    responses = get_responses(session_id)

    matrix = {
        'TRYGHED': {},
        'MENING': {},
        'KAN': {},
        'BESVÆR': {}
    }

    for r in responses:
        field = r['field']
        layer = r['layer']
        score = r['score']

        # Håndter omvendt scoring
        if r['reverse_scored']:
            score = 6 - score

        matrix[field][layer] = score

    return matrix


# ========================================
# COMPARISON FUNCTIONS
# ========================================

def create_comparison(
    session_id_1: str,
    session_id_2: str,
    context: Optional[str] = None
) -> str:
    """Opret sammenligning mellem to profiler"""
    comparison_id = f"comp-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        conn.execute(
            """INSERT INTO profil_comparisons
               (id, session_id_1, session_id_2, context)
               VALUES (?, ?, ?, ?)""",
            (comparison_id, session_id_1, session_id_2, context)
        )

    return comparison_id


def get_comparison(comparison_id: str) -> Optional[Dict]:
    """Hent sammenligning med begge sessioners data"""
    with get_db() as conn:
        row = conn.execute(
            """SELECT pc.*,
                      s1.person_name as person1_name,
                      s2.person_name as person2_name
               FROM profil_comparisons pc
               JOIN profil_sessions s1 ON pc.session_id_1 = s1.id
               JOIN profil_sessions s2 ON pc.session_id_2 = s2.id
               WHERE pc.id = ?""",
            (comparison_id,)
        ).fetchone()

        if row:
            return dict(row)
    return None


# ========================================
# DELETE FUNCTIONS
# ========================================

def delete_session(session_id: str) -> bool:
    """Slet en profil-session og alle tilhørende svar"""
    with get_db() as conn:
        # Slet svar først (foreign key)
        conn.execute(
            "DELETE FROM profil_responses WHERE session_id = ?",
            (session_id,)
        )
        # Slet session
        cursor = conn.execute(
            "DELETE FROM profil_sessions WHERE id = ?",
            (session_id,)
        )
        return cursor.rowcount > 0


def delete_sessions(session_ids: list) -> int:
    """Slet flere profil-sessions og returnér antal slettede"""
    deleted = 0
    for session_id in session_ids:
        if delete_session(session_id):
            deleted += 1
    return deleted


# ========================================
# TEST DATA GENERATION
# ========================================

def generate_test_profiles():
    """
    Generer testdata for forskellige profil-typer
    Baseret på teoretiske forventninger til friktionsmønstre
    """
    profiles = [
        {
            'name': 'Anna (ADHD-profil)',
            'context': 'test',
            'description': 'Lav båndbredde Bio→Kogn, høj KAN/BESVÆR-følsomhed',
            'scores': {
                # TRYGHED: Moderat følsom, hurtig biologisk reaktion
                ('TRYGHED', 'BIOLOGI'): 4,
                ('TRYGHED', 'EMOTION'): 4,
                ('TRYGHED', 'INDRE'): 3,
                ('TRYGHED', 'KOGNITION'): 2,  # Svært at falde til ro via forståelse

                # MENING: Stærk emotionel, men svingende retning
                ('MENING', 'BIOLOGI'): 3,
                ('MENING', 'EMOTION'): 5,  # Mærker stærkt hvad der er vigtigt
                ('MENING', 'INDRE'): 2,    # Får ikke hurtigt retning
                ('MENING', 'KOGNITION'): 2,  # Svært at holde pres ud

                # KAN: Høj følsomhed, lav tærskel
                ('KAN', 'BIOLOGI'): 5,     # Mærker energifald meget
                ('KAN', 'EMOTION'): 5,     # Let overvældet
                ('KAN', 'INDRE'): 2,       # Regulerer ikke via forståelse
                ('KAN', 'KOGNITION'): 1,   # Kan ikke tænke klart under pres

                # BESVÆR: Meget høj følsomhed
                ('BESVÆR', 'BIOLOGI'): 5,  # Alt føles tungt
                ('BESVÆR', 'EMOTION'): 5,  # Undgår bøvl
                ('BESVÆR', 'INDRE'): 2,    # Svært at lette via proces
                ('BESVÆR', 'KOGNITION'): 5,  # Mister overblik
            }
        },
        {
            'name': 'Bo (Autisme-profil)',
            'context': 'test',
            'description': 'Høj sensorisk følsomhed, stærk kognition, lav båndbredde ned',
            'scores': {
                # TRYGHED: Meget høj sensorisk, stærk kognition
                ('TRYGHED', 'BIOLOGI'): 5,  # Reagerer fysisk på uforudsigelighed
                ('TRYGHED', 'EMOTION'): 5,  # Opfanger signaler meget tydeligt
                ('TRYGHED', 'INDRE'): 5,    # Urolig hvis virkelighed udfordres
                ('TRYGHED', 'KOGNITION'): 5,  # Falder til ro når forstår (omvendt=lav score)

                # MENING: Stærk indre retning
                ('MENING', 'BIOLOGI'): 4,
                ('MENING', 'EMOTION'): 3,
                ('MENING', 'INDRE'): 5,     # Får hurtigt retning (omvendt)
                ('MENING', 'KOGNITION'): 5,  # Kan holde pres ud hvis mening klar (omvendt)

                # KAN: Svingende - god kognition, men overvældes let
                ('KAN', 'BIOLOGI'): 3,
                ('KAN', 'EMOTION'): 5,      # Overvældes af mange ting
                ('KAN', 'INDRE'): 5,        # Regulerer via forståelse (omvendt)
                ('KAN', 'KOGNITION'): 4,    # Kan tænke under pres (omvendt)

                # BESVÆR: Moderat
                ('BESVÆR', 'BIOLOGI'): 3,
                ('BESVÆR', 'EMOTION'): 4,
                ('BESVÆR', 'INDRE'): 5,     # Gør ting lettere via proces (omvendt)
                ('BESVÆR', 'KOGNITION'): 3,
            }
        },
        {
            'name': 'Clara (Borderline-træk)',
            'context': 'test',
            'description': 'Ustabil tryghed, lav tærskel i indre lag, hurtige skift',
            'scores': {
                # TRYGHED: Meget høj følsomhed i alle lag
                ('TRYGHED', 'BIOLOGI'): 5,
                ('TRYGHED', 'EMOTION'): 5,
                ('TRYGHED', 'INDRE'): 5,    # Indre ustabilitet
                ('TRYGHED', 'KOGNITION'): 2,

                # MENING: Stærk emotionel, ustabil indre
                ('MENING', 'BIOLOGI'): 4,
                ('MENING', 'EMOTION'): 5,
                ('MENING', 'INDRE'): 2,
                ('MENING', 'KOGNITION'): 2,

                # KAN: Svingende
                ('KAN', 'BIOLOGI'): 4,
                ('KAN', 'EMOTION'): 5,
                ('KAN', 'INDRE'): 2,
                ('KAN', 'KOGNITION'): 3,

                # BESVÆR: Moderat til høj
                ('BESVÆR', 'BIOLOGI'): 4,
                ('BESVÆR', 'EMOTION'): 4,
                ('BESVÆR', 'INDRE'): 3,
                ('BESVÆR', 'KOGNITION'): 4,
            }
        },
        {
            'name': 'David (Introvert)',
            'context': 'test',
            'description': 'Højere baseline i besvær (social energi), stærkere indre/kogn',
            'scores': {
                # TRYGHED: Moderat, lidt forsigtig
                ('TRYGHED', 'BIOLOGI'): 3,
                ('TRYGHED', 'EMOTION'): 4,  # Opfanger stemninger
                ('TRYGHED', 'INDRE'): 3,
                ('TRYGHED', 'KOGNITION'): 4,  # Rolig når forstår

                # MENING: Stærk indre retning
                ('MENING', 'BIOLOGI'): 2,
                ('MENING', 'EMOTION'): 3,
                ('MENING', 'INDRE'): 4,
                ('MENING', 'KOGNITION'): 4,

                # KAN: God selvregulering
                ('KAN', 'BIOLOGI'): 3,
                ('KAN', 'EMOTION'): 3,
                ('KAN', 'INDRE'): 4,
                ('KAN', 'KOGNITION'): 4,

                # BESVÆR: Højere - sociale ting koster energi
                ('BESVÆR', 'BIOLOGI'): 4,  # Træt lettere
                ('BESVÆR', 'EMOTION'): 4,  # Undgår kompleksitet
                ('BESVÆR', 'INDRE'): 4,
                ('BESVÆR', 'KOGNITION'): 2,  # God overblik
            }
        },
        {
            'name': 'Eva (Ekstrovert)',
            'context': 'test',
            'description': 'Lavt besvær socialt, følsom på mening/forbundethed',
            'scores': {
                # TRYGHED: Lav - føler sig generelt tryg
                ('TRYGHED', 'BIOLOGI'): 2,
                ('TRYGHED', 'EMOTION'): 3,
                ('TRYGHED', 'INDRE'): 2,
                ('TRYGHED', 'KOGNITION'): 3,

                # MENING: Høj følsomhed - forbundethed vigtigt
                ('MENING', 'BIOLOGI'): 3,
                ('MENING', 'EMOTION'): 5,  # Mærker stærkt hvad der er vigtigt
                ('MENING', 'INDRE'): 4,
                ('MENING', 'KOGNITION'): 3,

                # KAN: God energi
                ('KAN', 'BIOLOGI'): 2,
                ('KAN', 'EMOTION'): 2,
                ('KAN', 'INDRE'): 3,
                ('KAN', 'KOGNITION'): 3,

                # BESVÆR: Lavt
                ('BESVÆR', 'BIOLOGI'): 2,
                ('BESVÆR', 'EMOTION'): 2,
                ('BESVÆR', 'INDRE'): 3,
                ('BESVÆR', 'KOGNITION'): 3,
            }
        },
        {
            'name': 'Frederik (Robust profil)',
            'context': 'test',
            'description': 'Grøn i de fleste celler, høj båndbredde',
            'scores': {
                # TRYGHED: Lav følsomhed
                ('TRYGHED', 'BIOLOGI'): 2,
                ('TRYGHED', 'EMOTION'): 2,
                ('TRYGHED', 'INDRE'): 2,
                ('TRYGHED', 'KOGNITION'): 4,

                # MENING: Stabil
                ('MENING', 'BIOLOGI'): 2,
                ('MENING', 'EMOTION'): 3,
                ('MENING', 'INDRE'): 4,
                ('MENING', 'KOGNITION'): 4,

                # KAN: God kapacitet
                ('KAN', 'BIOLOGI'): 2,
                ('KAN', 'EMOTION'): 2,
                ('KAN', 'INDRE'): 4,
                ('KAN', 'KOGNITION'): 5,

                # BESVÆR: Lavt
                ('BESVÆR', 'BIOLOGI'): 2,
                ('BESVÆR', 'EMOTION'): 2,
                ('BESVÆR', 'INDRE'): 4,
                ('BESVÆR', 'KOGNITION'): 2,
            }
        },
        {
            'name': 'Gitte (Presset/udbrændt)',
            'context': 'test',
            'description': 'Orange i flere søjler, lav båndbredde',
            'scores': {
                # TRYGHED: Høj
                ('TRYGHED', 'BIOLOGI'): 4,
                ('TRYGHED', 'EMOTION'): 4,
                ('TRYGHED', 'INDRE'): 4,
                ('TRYGHED', 'KOGNITION'): 2,

                # MENING: Lav - mistet retning
                ('MENING', 'BIOLOGI'): 4,
                ('MENING', 'EMOTION'): 3,
                ('MENING', 'INDRE'): 2,
                ('MENING', 'KOGNITION'): 2,

                # KAN: Meget lav kapacitet
                ('KAN', 'BIOLOGI'): 5,
                ('KAN', 'EMOTION'): 5,
                ('KAN', 'INDRE'): 2,
                ('KAN', 'KOGNITION'): 2,

                # BESVÆR: Alt føles tungt
                ('BESVÆR', 'BIOLOGI'): 5,
                ('BESVÆR', 'EMOTION'): 5,
                ('BESVÆR', 'INDRE'): 2,
                ('BESVÆR', 'KOGNITION'): 4,
            }
        },
    ]

    created_sessions = []

    with get_db() as conn:
        questions = conn.execute(
            "SELECT id, field, layer FROM profil_questions"
        ).fetchall()

        # Map (field, layer) -> question_id
        q_map = {(q['field'], q['layer']): q['id'] for q in questions}

        for profile in profiles:
            # Opret session
            session_id = f"profil-test-{secrets.token_urlsafe(8)}"

            conn.execute(
                """INSERT INTO profil_sessions
                   (id, person_name, context, is_complete, completed_at)
                   VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)""",
                (session_id, profile['name'], profile['context'])
            )

            # Indsæt svar
            for (field, layer), score in profile['scores'].items():
                question_id = q_map.get((field, layer))
                if question_id:
                    conn.execute(
                        """INSERT INTO profil_responses
                           (session_id, question_id, score)
                           VALUES (?, ?, ?)""",
                        (session_id, question_id, score)
                    )

            created_sessions.append({
                'session_id': session_id,
                'name': profile['name'],
                'description': profile['description']
            })

    return created_sessions


if __name__ == "__main__":
    print("Initialiserer friktionsprofil-tabeller...")
    init_profil_tables()
    print("Done!")

    print("\nGenererer testprofiler...")
    sessions = generate_test_profiles()
    print(f"Oprettet {len(sessions)} testprofiler:")
    for s in sessions:
        print(f"  - {s['name']}: {s['session_id']}")

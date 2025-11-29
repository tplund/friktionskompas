"""
Database setup og queries for Friktionskompas
"""
import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

DB_PATH = "friktionskompas.db"

@contextmanager
def get_db():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize database with schema"""
    with get_db() as conn:
        # Spørgsmål (gemmes i database, klar til editor)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field TEXT NOT NULL,
                text_da TEXT NOT NULL,
                reverse_scored INTEGER NOT NULL DEFAULT 0,
                sequence INTEGER NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 1,
                organization_id TEXT
            )
        """)
        
        # Svar (anonyme, aggregerbare)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                period TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)
        
        # Tjek om vi allerede har spørgsmål
        count = conn.execute("SELECT COUNT(*) as cnt FROM questions").fetchone()['cnt']
        
        if count == 0:
            # Indsæt de 12 standard-spørgsmål
            questions = [
                # MENING (oplevelse af meningsløshed)
                ("MENING", "Der er opgaver i mit arbejde, som føles som spild af tid", 1, 1),
                ("MENING", "Jeg forstår, hvordan det jeg laver hjælper borgeren/kunden", 0, 2),
                ("MENING", "Hvis jeg kunne vælge, er der ting jeg ville lade være med at gøre - fordi de ikke giver værdi", 1, 3),
                
                # TRYGHED (det usagte)
                ("TRYGHED", "Der er ting på min arbejdsplads jeg gerne vil sige, men som jeg holder for mig selv", 1, 4),
                ("TRYGHED", "Jeg kan indrømme fejl uden at bekymre mig om konsekvenser", 0, 5),
                ("TRYGHED", "Hvis jeg rejser kritik af hvordan ting fungerer, bliver det taget seriøst", 0, 6),
                
                # MULIGHED (manglende evne man ikke kan sige)
                ("MULIGHED", "Jeg har de værktøjer og informationer jeg skal bruge for at gøre mit arbejde ordentligt", 0, 7),
                ("MULIGHED", "Der er opgaver, hvor jeg ikke helt ved hvordan jeg skal gøre det rigtigt - men jeg tør ikke spørge", 1, 8),
                ("MULIGHED", "Når jeg står fast, ved jeg hvor jeg kan få hjælp", 0, 9),
                
                # BESVÆR (workarounds og regelomgåelse) - IKKE reverse scored!
                ("BESVÆR", "For at få tingene til at fungere, må jeg nogle gange gøre det anderledes end procedurerne beskriver", 0, 10),
                ("BESVÆR", "Hvis jeg fulgte alle regler og procedurer, ville jeg ikke nå mit arbejde", 0, 11),
                ("BESVÆR", "Jeg bruger tid på dobbeltarbejde eller unødige registreringer", 0, 12),
            ]
            
            conn.executemany(
                "INSERT INTO questions (field, text_da, reverse_scored, sequence) VALUES (?, ?, ?, ?)",
                questions
            )


def get_questions() -> List[Dict[str, Any]]:
    """Hent alle spørgsmål (sorteret)"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, field, text_da, reverse_scored, sequence
            FROM questions
            WHERE is_default = 1
            ORDER BY sequence
        """).fetchall()
        return [dict(row) for row in rows]


def save_response(team_id: str, period: str, question_id: int, score: int, comment: Optional[str] = None):
    """Gem et enkelt svar"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO responses (team_id, period, question_id, score, comment) VALUES (?, ?, ?, ?, ?)",
            (team_id, period, question_id, score, comment)
        )


def get_response_count(team_id: str, period: str) -> int:
    """Tæl antal unikke besvarelser (respondenter)"""
    with get_db() as conn:
        # Tæl hvor mange komplette besvarelser vi har (12 spørgsmål hver)
        result = conn.execute("""
            SELECT COUNT(*) / 12 as cnt
            FROM responses
            WHERE team_id = ? AND period = ?
        """, (team_id, period)).fetchone()
        return int(result['cnt']) if result else 0


def get_field_stats(team_id: str, period: str) -> List[Dict[str, Any]]:
    """
    Beregn statistik pr. felt
    
    Returnerer i FAST rækkefølge: Mening, Tryghed, Mulighed, Besvær
    (ikke sorteret efter score)
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                q.field,
                AVG(CASE 
                    WHEN q.reverse_scored = 1 THEN 6 - r.score 
                    ELSE r.score 
                END) as avg_score,
                COUNT(r.id) as response_count,
                GROUP_CONCAT(r.comment, '|||') as all_comments
            FROM questions q
            LEFT JOIN responses r ON q.id = r.question_id 
                AND r.team_id = ? AND r.period = ?
            WHERE q.is_default = 1
            GROUP BY q.field
        """, (team_id, period)).fetchall()
        
        # Konverter til dict for nem opslag
        data_by_field = {}
        for row in rows:
            comments = row['all_comments'] if row['all_comments'] else ""
            top_words = extract_top_words(comments)
            
            data_by_field[row['field']] = {
                'field': row['field'],
                'avg_score': round(row['avg_score'], 1) if row['avg_score'] else 0,
                'response_count': row['response_count'],
                'top_words': top_words
            }
        
        # Returner i FAST rækkefølge
        field_order = ['MENING', 'TRYGHED', 'MULIGHED', 'BESVÆR']
        results = [data_by_field[field] for field in field_order if field in data_by_field]
        
        return results


def extract_top_words(text: str, top_n: int = 3) -> List[str]:
    """Simpel ord-frekvens analyse (ingen AI)"""
    if not text:
        return []
    
    # Stopord (danske)
    stopwords = {
        'og', 'i', 'er', 'det', 'den', 'en', 'at', 'til', 'på', 'med', 'som', 'for',
        'af', 'der', 'har', 'ikke', 'jeg', 'de', 'kan', 'vi', 'om', 'blev', 'var',
        'så', 'men', 'også', 'være', 'eller', 'når', 'bare', 'meget', 'godt', 'mere'
    }
    
    # Split og clean
    words = text.lower().replace('|||', ' ').split()
    words = [w.strip('.,!?;:') for w in words if len(w) > 3 and w.lower() not in stopwords]
    
    # Tæl frekvens
    from collections import Counter
    word_counts = Counter(words)
    
    return [word for word, _ in word_counts.most_common(top_n)]


def clear_all_responses():
    """Slet alle svar (kun til demo)"""
    with get_db() as conn:
        conn.execute("DELETE FROM responses")

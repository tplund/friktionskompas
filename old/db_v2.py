"""
Database setup for Friktionskompas v2 - Organization level
Med support for organisationer, afdelinger, kampagner og magic links
"""
import sqlite3
import secrets
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = "friktionskompas_v2.db"

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
    """Initialize database with full organization structure"""
    with get_db() as conn:
        # Organisationer (kommuner, virksomheder)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                contact_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Afdelinger
        conn.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                name TEXT NOT NULL,
                leader_name TEXT,
                leader_email TEXT,
                employee_count INTEGER DEFAULT 0,
                sick_leave_percent REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES organizations(id)
            )
        """)
        
        # Kampagner (målinger sendt til flere afdelinger)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                name TEXT NOT NULL,
                period TEXT NOT NULL,
                sent_from TEXT DEFAULT 'admin',
                sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES organizations(id)
            )
        """)
        
        # Kampagne-afdelinger (mange-til-mange)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS campaign_departments (
                campaign_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                tokens_sent INTEGER DEFAULT 0,
                tokens_used INTEGER DEFAULT 0,
                PRIMARY KEY (campaign_id, department_id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        """)
        
        # Tokens (magic links - anonyme)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                contact_method TEXT,
                is_used INTEGER DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        """)
        
        # Kontakter (telefon/email per afdeling)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            )
        """)
        
        # Spørgsmål (som før)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field TEXT NOT NULL,
                text_da TEXT NOT NULL,
                reverse_scored INTEGER NOT NULL DEFAULT 0,
                sequence INTEGER NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 1,
                org_id TEXT,
                FOREIGN KEY (org_id) REFERENCES organizations(id)
            )
        """)
        
        # Svar (nu med department_id i stedet for team_id)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL,
                department_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                comment TEXT,
                category_comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
                FOREIGN KEY (department_id) REFERENCES departments(id),
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)
        
        # Indsæt default spørgsmål hvis tom database
        count = conn.execute("SELECT COUNT(*) as cnt FROM questions").fetchone()['cnt']
        
        if count == 0:
            questions = [
                # MENING
                ("MENING", "Der er opgaver i mit arbejde, som føles som spild af tid", 1, 1),
                ("MENING", "Jeg forstår, hvordan det jeg laver hjælper borgeren/kunden", 0, 2),
                ("MENING", "Hvis jeg kunne vælge, er der ting jeg ville lade være med at gøre - fordi de ikke giver værdi", 1, 3),
                
                # TRYGHED
                ("TRYGHED", "Der er ting på min arbejdsplads jeg gerne vil sige, men som jeg holder for mig selv", 1, 4),
                ("TRYGHED", "Jeg kan indrømme fejl uden at bekymre mig om konsekvenser", 0, 5),
                ("TRYGHED", "Hvis jeg rejser kritik af hvordan ting fungerer, bliver det taget seriøst", 0, 6),
                
                # KAN/MULIGHED
                ("MULIGHED", "Jeg har de værktøjer og informationer jeg skal bruge for at gøre mit arbejde ordentligt", 0, 7),
                ("MULIGHED", "Der er opgaver, hvor jeg ikke helt ved hvordan jeg skal gøre det rigtigt - men jeg tør ikke spørge", 1, 8),
                ("MULIGHED", "Når jeg står fast, ved jeg hvor jeg kan få hjælp", 0, 9),
                
                # BESVÆR - IKKE reverse scored!
                ("BESVÆR", "For at få tingene til at fungere, må jeg nogle gange gøre det anderledes end procedurerne beskriver", 0, 10),
                ("BESVÆR", "Hvis jeg fulgte alle regler og procedurer, ville jeg ikke nå mit arbejde", 0, 11),
                ("BESVÆR", "Jeg bruger tid på dobbeltarbejde eller unødige registreringer", 0, 12),
            ]
            
            for field, text, reverse, seq in questions:
                conn.execute(
                    "INSERT INTO questions (field, text_da, reverse_scored, sequence, is_default) VALUES (?, ?, ?, ?, 1)",
                    (field, text, reverse, seq)
                )


# ========================================
# ORGANISATION FUNCTIONS
# ========================================

def create_organization(name: str, contact_email: str = None) -> str:
    """Opret ny organisation"""
    org_id = f"org-{secrets.token_urlsafe(8)}"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO organizations (id, name, contact_email) VALUES (?, ?, ?)",
            (org_id, name, contact_email)
        )
    return org_id


def create_department(org_id: str, name: str, leader_name: str = None, 
                     leader_email: str = None, employee_count: int = 0) -> str:
    """Opret ny afdeling"""
    dept_id = f"dept-{secrets.token_urlsafe(8)}"
    with get_db() as conn:
        conn.execute("""
            INSERT INTO departments (id, org_id, name, leader_name, leader_email, employee_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (dept_id, org_id, name, leader_name, leader_email, employee_count))
    return dept_id


def update_sick_leave(dept_id: str, sick_leave_percent: float):
    """Opdater sygefravær for afdeling"""
    with get_db() as conn:
        conn.execute(
            "UPDATE departments SET sick_leave_percent = ? WHERE id = ?",
            (sick_leave_percent, dept_id)
        )


# ========================================
# CAMPAIGN FUNCTIONS
# ========================================

def create_campaign(org_id: str, name: str, period: str, 
                   department_ids: List[str], sent_from: str = 'admin') -> str:
    """Opret ny kampagne"""
    campaign_id = f"camp-{secrets.token_urlsafe(8)}"
    
    with get_db() as conn:
        # Opret kampagne
        conn.execute("""
            INSERT INTO campaigns (id, org_id, name, period, sent_from)
            VALUES (?, ?, ?, ?, ?)
        """, (campaign_id, org_id, name, period, sent_from))
        
        # Tilknyt afdelinger
        for dept_id in department_ids:
            conn.execute("""
                INSERT INTO campaign_departments (campaign_id, department_id)
                VALUES (?, ?)
            """, (campaign_id, dept_id))
    
    return campaign_id


def generate_tokens_for_department(campaign_id: str, department_id: str, count: int) -> List[str]:
    """Generer magic link tokens for en afdeling"""
    tokens = []
    
    with get_db() as conn:
        for _ in range(count):
            token = secrets.token_urlsafe(16)
            tokens.append(token)
            
            conn.execute("""
                INSERT INTO tokens (token, campaign_id, department_id)
                VALUES (?, ?, ?)
            """, (token, campaign_id, department_id))
        
        # Opdater antal sendte tokens
        conn.execute("""
            UPDATE campaign_departments 
            SET tokens_sent = tokens_sent + ?
            WHERE campaign_id = ? AND department_id = ?
        """, (count, campaign_id, department_id))
    
    return tokens


def validate_and_use_token(token: str) -> Optional[Dict[str, str]]:
    """Valider token og marker som brugt. Returner campaign og department hvis valid."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT token, campaign_id, department_id, is_used
            FROM tokens
            WHERE token = ?
        """, (token,)).fetchone()
        
        if not row:
            return None
        
        if row['is_used']:
            return None  # Allerede brugt
        
        # Marker som brugt
        conn.execute("""
            UPDATE tokens
            SET is_used = 1, used_at = CURRENT_TIMESTAMP
            WHERE token = ?
        """, (token,))
        
        # Opdater tokens_used counter
        conn.execute("""
            UPDATE campaign_departments
            SET tokens_used = tokens_used + 1
            WHERE campaign_id = ? AND department_id = ?
        """, (row['campaign_id'], row['department_id']))
        
        return {
            'campaign_id': row['campaign_id'],
            'department_id': row['department_id']
        }


# ========================================
# RESPONSES
# ========================================

def save_response_v2(campaign_id: str, department_id: str, question_id: int, 
                     score: int, comment: str = None):
    """Gem svar (ny version med campaign/department)"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO responses (campaign_id, department_id, question_id, score, comment)
            VALUES (?, ?, ?, ?, ?)
        """, (campaign_id, department_id, question_id, score, comment))


# ========================================
# STATS & REPORTING
# ========================================

def get_department_stats(department_id: str, campaign_id: str) -> List[Dict]:
    """Hent statistik for en afdeling i en kampagne"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                q.field,
                AVG(CASE 
                    WHEN q.reverse_scored = 1 THEN 6 - r.score 
                    ELSE r.score 
                END) as avg_score,
                COUNT(r.id) as response_count
            FROM questions q
            LEFT JOIN responses r ON q.id = r.question_id 
                AND r.department_id = ? AND r.campaign_id = ?
            WHERE q.is_default = 1
            GROUP BY q.field
        """, (department_id, campaign_id)).fetchall()
        
        # Returner i fast rækkefølge
        field_order = ['MENING', 'TRYGHED', 'MULIGHED', 'BESVÆR']
        data_by_field = {row['field']: row for row in rows}
        
        return [
            {
                'field': field,
                'avg_score': round(data_by_field[field]['avg_score'], 1) if field in data_by_field and data_by_field[field]['avg_score'] else 0,
                'response_count': data_by_field[field]['response_count'] if field in data_by_field else 0
            }
            for field in field_order
        ]


def get_organization_overview(org_id: str, campaign_id: str) -> List[Dict]:
    """Hent overview for alle afdelinger i en organisation"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT 
                d.id,
                d.name,
                d.sick_leave_percent,
                cd.tokens_sent,
                cd.tokens_used,
                ROUND(AVG(CASE 
                    WHEN q.field = 'BESVÆR' AND q.reverse_scored = 0 THEN r.score
                    WHEN q.field = 'BESVÆR' AND q.reverse_scored = 1 THEN 6 - r.score
                    ELSE NULL 
                END), 1) as besvær_score
            FROM departments d
            JOIN campaign_departments cd ON d.id = cd.department_id
            LEFT JOIN responses r ON d.id = r.department_id AND r.campaign_id = ?
            LEFT JOIN questions q ON r.question_id = q.id
            WHERE d.org_id = ? AND cd.campaign_id = ?
            GROUP BY d.id, d.name, d.sick_leave_percent, cd.tokens_sent, cd.tokens_used
        """, (campaign_id, org_id, campaign_id)).fetchall()
        
        return [dict(row) for row in rows]


def get_questions():
    """Hent alle default spørgsmål"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, field, text_da, reverse_scored, sequence
            FROM questions
            WHERE is_default = 1
            ORDER BY sequence
        """).fetchall()
        return [dict(row) for row in rows]


# ========================================
# CONTACTS
# ========================================

def add_contacts_from_csv(department_id: str, contacts: List[Dict[str, str]]):
    """Tilføj kontakter fra CSV"""
    with get_db() as conn:
        for contact in contacts:
            conn.execute("""
                INSERT INTO contacts (department_id, email, phone)
                VALUES (?, ?, ?)
            """, (department_id, contact.get('email'), contact.get('phone')))


def get_department_contacts(department_id: str) -> List[Dict]:
    """Hent alle kontakter for en afdeling"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT email, phone
            FROM contacts
            WHERE department_id = ?
        """, (department_id,)).fetchall()
        return [dict(row) for row in rows]


# Initialize on import
init_db()

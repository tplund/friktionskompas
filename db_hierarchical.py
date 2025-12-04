"""
Database setup for Friktionskompas v3 - Hierarchical Structure
Alle organisatoriske enheder er 'units' i et træ med parent_id
"""
import sqlite3
import secrets
import os
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime

# Use persistent disk on Render, local file otherwise
RENDER_DISK_PATH = "/var/data"
if os.path.exists(RENDER_DISK_PATH):
    DB_PATH = os.path.join(RENDER_DISK_PATH, "friktionskompas_v3.db")
else:
    DB_PATH = "friktionskompas_v3.db"

@contextmanager
def get_db():
    """Context manager for database connection"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize database with hierarchical structure"""
    with get_db() as conn:
        # Organizational Units - træstruktur for ALT
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizational_units (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                name TEXT NOT NULL,
                full_path TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 0,
                
                -- Leder info (kan være på alle niveauer)
                leader_name TEXT,
                leader_email TEXT,
                
                -- Metrics (typisk på leaf nodes, men kan være alle steder)
                employee_count INTEGER DEFAULT 0,
                sick_leave_percent REAL DEFAULT 0,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (parent_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        
        # Index for hurtig parent lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_units_parent 
            ON organizational_units(parent_id)
        """)
        
        # Kampagner (sendes til en unit, rammer alle children)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                target_unit_id TEXT NOT NULL,
                name TEXT NOT NULL,
                period TEXT NOT NULL,
                sent_from TEXT DEFAULT 'admin',
                sent_at TIMESTAMP,
                min_responses INTEGER DEFAULT 5,
                mode TEXT DEFAULT 'anonymous',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (target_unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)

        # Tilføj kolonner hvis de mangler (migration)
        try:
            conn.execute("ALTER TABLE campaigns ADD COLUMN min_responses INTEGER DEFAULT 5")
        except:
            pass
        try:
            conn.execute("ALTER TABLE campaigns ADD COLUMN mode TEXT DEFAULT 'anonymous'")
        except:
            pass
        
        # Tokens (genereres per leaf-unit)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                respondent_type TEXT DEFAULT 'employee',
                respondent_name TEXT,
                is_used INTEGER DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        
        # Index for hurtig token validation
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tokens_campaign_unit 
            ON tokens(campaign_id, unit_id)
        """)
        
        # Kontakter (kan være på alle unit-niveauer)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        
        # Spørgsmål (globale eller per top-level organization)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field TEXT NOT NULL,
                text_da TEXT NOT NULL,
                reverse_scored INTEGER NOT NULL DEFAULT 0,
                sequence INTEGER NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 1,
                org_unit_id TEXT,
                FOREIGN KEY (org_unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        
        # Svar (gemmes på den unit tokenet kom fra)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                comment TEXT,
                category_comment TEXT,
                respondent_type TEXT DEFAULT 'employee',
                respondent_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)
        
        # Index for aggregering
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_responses_campaign_unit
            ON responses(campaign_id, unit_id)
        """)

        # Email logs for delivery tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                to_email TEXT NOT NULL,
                subject TEXT,
                email_type TEXT DEFAULT 'invitation',
                status TEXT DEFAULT 'sent',
                campaign_id TEXT,
                token TEXT,
                error_message TEXT,
                delivered_at TIMESTAMP,
                opened_at TIMESTAMP,
                clicked_at TIMESTAMP,
                bounced_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL
            )
        """)

        # Email templates per customer
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                template_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                html_content TEXT NOT NULL,
                text_content TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
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
                
                # BESVÆR
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
# ORGANIZATIONAL UNIT FUNCTIONS
# ========================================

def create_unit(name: str, parent_id: Optional[str] = None,
                leader_name: str = None, leader_email: str = None,
                employee_count: int = 0, sick_leave_percent: float = 0,
                customer_id: Optional[str] = None) -> str:
    """
    Opret ny organizational unit
    Kan være top-level (parent_id=None) eller child
    """
    unit_id = f"unit-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        # Find level og byg full_path
        if parent_id is None:
            level = 0
            full_path = name
        else:
            parent = conn.execute(
                "SELECT level, full_path, customer_id FROM organizational_units WHERE id = ?",
                (parent_id,)
            ).fetchone()

            if not parent:
                raise ValueError(f"Parent unit {parent_id} ikke fundet")

            # Arv customer_id fra parent hvis ikke specificeret
            if customer_id is None:
                customer_id = parent['customer_id']

            level = parent['level'] + 1
            full_path = f"{parent['full_path']}//{name}"

        # Indsæt unit
        conn.execute("""
            INSERT INTO organizational_units
            (id, parent_id, name, full_path, level, leader_name, leader_email,
             employee_count, sick_leave_percent, customer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (unit_id, parent_id, name, full_path, level, leader_name,
              leader_email, employee_count, sick_leave_percent, customer_id))

    return unit_id


def create_unit_from_path(path: str, leader_name: str = None,
                         leader_email: str = None, employee_count: int = 0,
                         sick_leave_percent: float = 0, customer_id: Optional[str] = None) -> str:
    """
    Opret unit fra sti som "Virksomhed A//HR//Team Nord"
    Opretter automatisk manglende parent units
    Returnerer ID for leaf unit
    """
    parts = [p.strip() for p in path.split('//')]

    with get_db() as conn:
        parent_id = None
        current_path = ""

        for i, part in enumerate(parts):
            if i == 0:
                current_path = part
            else:
                current_path = f"{current_path}//{part}"

            # Check om unit allerede findes (med customer_id filter)
            if customer_id:
                existing = conn.execute(
                    "SELECT id FROM organizational_units WHERE full_path = ? AND customer_id = ?",
                    (current_path, customer_id)
                ).fetchone()
            else:
                existing = conn.execute(
                    "SELECT id FROM organizational_units WHERE full_path = ? AND customer_id IS NULL",
                    (current_path,)
                ).fetchone()

            if existing:
                parent_id = existing['id']
            else:
                # Opret unit
                is_leaf = (i == len(parts) - 1)

                unit_id = create_unit(
                    name=part,
                    parent_id=parent_id,
                    leader_name=leader_name if is_leaf else None,
                    leader_email=leader_email if is_leaf else None,
                    employee_count=employee_count if is_leaf else 0,
                    sick_leave_percent=sick_leave_percent if is_leaf else 0,
                    customer_id=customer_id
                )
                parent_id = unit_id

        return parent_id


def get_unit_children(unit_id: str, recursive: bool = False) -> List[Dict]:
    """
    Hent children af en unit
    recursive=True: Hent alle descendants (hele subtræet)
    """
    with get_db() as conn:
        if recursive:
            # Recursive CTE for at få hele subtræet
            rows = conn.execute("""
                WITH RECURSIVE subtree AS (
                    SELECT * FROM organizational_units WHERE parent_id = ?
                    UNION ALL
                    SELECT ou.* FROM organizational_units ou
                    JOIN subtree st ON ou.parent_id = st.id
                )
                SELECT * FROM subtree
                ORDER BY level, name
            """, (unit_id,)).fetchall()
        else:
            # Kun direkte children
            rows = conn.execute("""
                SELECT * FROM organizational_units 
                WHERE parent_id = ?
                ORDER BY name
            """, (unit_id,)).fetchall()
        
        return [dict(row) for row in rows]


def get_leaf_units(parent_unit_id: Optional[str] = None) -> List[Dict]:
    """
    Hent alle leaf units (units uden children)
    Hvis parent_unit_id angives, kun under den
    """
    with get_db() as conn:
        if parent_unit_id:
            # Leaf units under specifik parent
            rows = conn.execute("""
                WITH RECURSIVE subtree AS (
                    SELECT * FROM organizational_units WHERE id = ?
                    UNION ALL
                    SELECT ou.* FROM organizational_units ou
                    JOIN subtree st ON ou.parent_id = st.id
                )
                SELECT st.* FROM subtree st
                LEFT JOIN organizational_units children ON st.id = children.parent_id
                WHERE children.id IS NULL
                ORDER BY st.full_path
            """, (parent_unit_id,)).fetchall()
        else:
            # Alle leaf units
            rows = conn.execute("""
                SELECT ou.* FROM organizational_units ou
                LEFT JOIN organizational_units children ON ou.id = children.parent_id
                WHERE children.id IS NULL
                ORDER BY ou.full_path
            """).fetchall()
        
        return [dict(row) for row in rows]


def get_unit_path(unit_id: str) -> List[Dict]:
    """Hent path fra root til unit (breadcrumbs)"""
    with get_db() as conn:
        # Recursive CTE backwards til root
        rows = conn.execute("""
            WITH RECURSIVE ancestors AS (
                SELECT * FROM organizational_units WHERE id = ?
                UNION ALL
                SELECT ou.* FROM organizational_units ou
                JOIN ancestors a ON ou.id = a.parent_id
            )
            SELECT * FROM ancestors
            ORDER BY level
        """, (unit_id,)).fetchall()
        
        return [dict(row) for row in rows]


# ========================================
# CAMPAIGN FUNCTIONS
# ========================================

def create_campaign(target_unit_id: str, name: str, period: str, 
                   sent_from: str = 'admin') -> str:
    """
    Opret kampagne rettet mod en unit
    Kampagnen rammer alle leaf units under target_unit_id
    """
    campaign_id = f"camp-{secrets.token_urlsafe(8)}"
    
    with get_db() as conn:
        # Valider at target unit eksisterer
        unit = conn.execute(
            "SELECT id FROM organizational_units WHERE id = ?",
            (target_unit_id,)
        ).fetchone()
        
        if not unit:
            raise ValueError(f"Unit {target_unit_id} ikke fundet")
        
        # Opret kampagne
        conn.execute("""
            INSERT INTO campaigns (id, target_unit_id, name, period, sent_from)
            VALUES (?, ?, ?, ?, ?)
        """, (campaign_id, target_unit_id, name, period, sent_from))
    
    return campaign_id


def generate_tokens_for_campaign(campaign_id: str) -> Dict[str, List[str]]:
    """
    Generer tokens for alle leaf units under kampagnens target
    Returnerer dict: {unit_id: [tokens]}
    """
    with get_db() as conn:
        # Find target unit
        campaign = conn.execute(
            "SELECT target_unit_id FROM campaigns WHERE id = ?",
            (campaign_id,)
        ).fetchone()
        
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} ikke fundet")
        
        target_unit_id = campaign['target_unit_id']
        
        # Find alle leaf units under target
        leaf_units = get_leaf_units(target_unit_id)
        
        tokens_by_unit = {}
        
        for unit in leaf_units:
            unit_id = unit['id']
            count = unit['employee_count']
            
            if count <= 0:
                continue
            
            tokens = []
            for _ in range(count):
                token = secrets.token_urlsafe(16)
                tokens.append(token)
                
                conn.execute("""
                    INSERT INTO tokens (token, campaign_id, unit_id)
                    VALUES (?, ?, ?)
                """, (token, campaign_id, unit_id))
            
            tokens_by_unit[unit_id] = tokens
        
        # Opdater sent_at
        conn.execute("""
            UPDATE campaigns
            SET sent_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (campaign_id,))
    
    return tokens_by_unit


def validate_and_use_token(token: str) -> Optional[Dict[str, str]]:
    """Valider token og marker som brugt"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT token, campaign_id, unit_id, is_used
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
        
        return {
            'campaign_id': row['campaign_id'],
            'unit_id': row['unit_id']
        }


# ========================================
# RESPONSES
# ========================================

def save_response(campaign_id: str, unit_id: str, question_id: int, 
                 score: int, comment: str = None, category_comment: str = None):
    """Gem svar"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO responses (campaign_id, unit_id, question_id, score, comment, category_comment)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (campaign_id, unit_id, question_id, score, comment, category_comment))


def get_unit_stats(unit_id: str, campaign_id: str, include_children: bool = True) -> List[Dict]:
    """
    Hent statistik for en unit i en kampagne
    include_children: Aggreger data fra alle child units
    """
    with get_db() as conn:
        if include_children:
            # Aggregate fra hele subtræet
            rows = conn.execute("""
                WITH RECURSIVE subtree AS (
                    SELECT id FROM organizational_units WHERE id = ?
                    UNION ALL
                    SELECT ou.id FROM organizational_units ou
                    JOIN subtree st ON ou.parent_id = st.id
                )
                SELECT 
                    q.field,
                    AVG(CASE 
                        WHEN q.reverse_scored = 1 THEN 6 - r.score 
                        ELSE r.score 
                    END) as avg_score,
                    COUNT(r.id) as response_count
                FROM questions q
                LEFT JOIN responses r ON q.id = r.question_id 
                    AND r.unit_id IN (SELECT id FROM subtree)
                    AND r.campaign_id = ?
                WHERE q.is_default = 1
                GROUP BY q.field
            """, (unit_id, campaign_id)).fetchall()
        else:
            # Kun denne unit
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
                    AND r.unit_id = ? AND r.campaign_id = ?
                WHERE q.is_default = 1
                GROUP BY q.field
            """, (unit_id, campaign_id)).fetchall()
        
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


def get_campaign_overview(campaign_id: str) -> List[Dict]:
    """Hent overview for alle leaf units i en kampagne"""
    with get_db() as conn:
        # Find target unit for campaign
        campaign = conn.execute(
            "SELECT target_unit_id FROM campaigns WHERE id = ?",
            (campaign_id,)
        ).fetchone()
        
        if not campaign:
            return []
        
        # Find alle leaf units under target
        leaf_units = get_leaf_units(campaign['target_unit_id'])
        
        # Hent stats for hver
        overview = []
        for unit in leaf_units:
            unit_id = unit['id']
            
            # Count tokens sent/used
            token_stats = conn.execute("""
                SELECT 
                    COUNT(*) as tokens_sent,
                    SUM(CASE WHEN is_used = 1 THEN 1 ELSE 0 END) as tokens_used
                FROM tokens
                WHERE campaign_id = ? AND unit_id = ?
            """, (campaign_id, unit_id)).fetchone()
            
            # Besvær score
            besvær = conn.execute("""
                SELECT 
                    ROUND(AVG(CASE 
                        WHEN q.field = 'BESVÆR' AND q.reverse_scored = 0 THEN r.score
                        WHEN q.field = 'BESVÆR' AND q.reverse_scored = 1 THEN 6 - r.score
                        ELSE NULL 
                    END), 1) as besvær_score
                FROM responses r
                JOIN questions q ON r.question_id = q.id
                WHERE r.campaign_id = ? AND r.unit_id = ? AND q.field = 'BESVÆR'
            """, (campaign_id, unit_id)).fetchone()
            
            overview.append({
                'id': unit_id,
                'name': unit['name'],
                'full_path': unit['full_path'],
                'sick_leave_percent': unit['sick_leave_percent'],
                'tokens_sent': token_stats['tokens_sent'] or 0,
                'tokens_used': token_stats['tokens_used'] or 0,
                'besvær_score': besvær['besvær_score']
            })
        
        return overview


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

def add_contacts_bulk(unit_id: str, contacts: List[Dict[str, str]], conn=None):
    """Tilføj kontakter fra liste

    Args:
        unit_id: ID for unit
        contacts: Liste af kontakter med email/phone
        conn: Eksisterende database connection (valgfri - opretter ny hvis None)
    """
    if conn is None:
        with get_db() as conn:
            for contact in contacts:
                conn.execute("""
                    INSERT INTO contacts (unit_id, email, phone)
                    VALUES (?, ?, ?)
                """, (unit_id, contact.get('email'), contact.get('phone')))
    else:
        for contact in contacts:
            conn.execute("""
                INSERT INTO contacts (unit_id, email, phone)
                VALUES (?, ?, ?)
            """, (unit_id, contact.get('email'), contact.get('phone')))


def get_unit_contacts(unit_id: str) -> List[Dict]:
    """Hent alle kontakter for en unit"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT email, phone
            FROM contacts
            WHERE unit_id = ?
        """, (unit_id,)).fetchall()
        return [dict(row) for row in rows]


def get_all_leaf_units_under(parent_unit_id: str) -> List[Dict]:
    """
    Hent alle leaf units under en parent (inkl. parent selv hvis det er en leaf)

    Returns:
        Liste af dicts med unit info inkl. employee_count
    """
    with get_db() as conn:
        # Recursive CTE til at finde alle descendants
        rows = conn.execute("""
            WITH RECURSIVE subtree AS (
                SELECT * FROM organizational_units WHERE id = ?
                UNION ALL
                SELECT ou.* FROM organizational_units ou
                JOIN subtree st ON ou.parent_id = st.id
            )
            SELECT st.* FROM subtree st
            LEFT JOIN organizational_units children ON st.id = children.parent_id
            WHERE children.id IS NULL
            ORDER BY st.full_path
        """, (parent_unit_id,)).fetchall()

        return [dict(row) for row in rows]


# ========================================
# CAMPAIGN V2 WITH MODES AND RESPONDENT TYPES
# ========================================

def create_campaign_with_modes(
    target_unit_id: str,
    name: str,
    period: str,
    mode: str = 'anonymous',
    include_leader_assessment: bool = False,
    include_leader_self: bool = False,
    min_responses: int = 5,
    sent_from: str = 'admin'
) -> str:
    """
    Opret kampagne med support for modes og leder-perspektiv

    Args:
        target_unit_id: ID for target unit
        name: Kampagne navn
        period: Periode (f.eks. "2025 Q1")
        mode: 'anonymous' eller 'identified'
        include_leader_assessment: Skal lederen vurdere teamet?
        include_leader_self: Skal lederen svare om egne friktioner?
        min_responses: Minimum antal svar før data vises (kun anonymous)
        sent_from: Afsender

    Returns:
        campaign_id
    """
    campaign_id = f"camp-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        # Valider at target unit eksisterer
        unit = conn.execute(
            "SELECT id FROM organizational_units WHERE id = ?",
            (target_unit_id,)
        ).fetchone()

        if not unit:
            raise ValueError(f"Unit {target_unit_id} ikke fundet")

        # Valider mode
        if mode not in ['anonymous', 'identified']:
            raise ValueError(f"Ugyldig mode: {mode}. Skal være 'anonymous' eller 'identified'")

        # Opret kampagne
        conn.execute("""
            INSERT INTO campaigns (
                id, target_unit_id, name, period, sent_from,
                mode, include_leader_assessment, include_leader_self, min_responses
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            campaign_id, target_unit_id, name, period, sent_from,
            mode, 1 if include_leader_assessment else 0,
            1 if include_leader_self else 0, min_responses
        ))

    return campaign_id


def generate_tokens_with_respondent_types(
    campaign_id: str,
    respondent_names: Optional[Dict[str, List[str]]] = None
) -> Dict[str, Dict[str, List[str]]]:
    """
    Generer tokens med support for respondent types

    Args:
        campaign_id: Campaign ID
        respondent_names: For identified mode: {unit_id: [navne]}

    Returns:
        {
            unit_id: {
                'employee': [tokens] eller [(token, name), ...] for identified,
                'leader_assess': [tokens] (hvis enabled),
                'leader_self': [tokens] (hvis enabled)
            }
        }
    """
    with get_db() as conn:
        # Hent campaign info
        campaign = conn.execute("""
            SELECT * FROM campaigns WHERE id = ?
        """, (campaign_id,)).fetchone()

        if not campaign:
            raise ValueError(f"Campaign {campaign_id} ikke fundet")

        target_unit_id = campaign['target_unit_id']
        mode = campaign['mode']
        include_leader_assessment = campaign['include_leader_assessment']
        include_leader_self = campaign['include_leader_self']

        # Find alle leaf units under target
        leaf_units = get_all_leaf_units_under(target_unit_id)

        tokens_by_unit = {}

        for unit in leaf_units:
            unit_id = unit['id']
            employee_count = unit['employee_count']

            unit_tokens = {}

            # ===== EMPLOYEE TOKENS =====
            if mode == 'identified':
                # Identified mode: Brug navne fra respondent_names
                if not respondent_names or unit_id not in respondent_names:
                    # Ingen navne angivet for denne unit - skip
                    continue

                names = respondent_names[unit_id]
                employee_tokens = []

                for name in names:
                    token = secrets.token_urlsafe(16)
                    employee_tokens.append((token, name))

                    conn.execute("""
                        INSERT INTO tokens (token, campaign_id, unit_id, respondent_type, respondent_name)
                        VALUES (?, ?, ?, 'employee', ?)
                    """, (token, campaign_id, unit_id, name))

                unit_tokens['employee'] = employee_tokens
            else:
                # Anonymous mode: Generer tokens baseret på employee_count
                if employee_count <= 0:
                    continue

                employee_tokens = []
                for _ in range(employee_count):
                    token = secrets.token_urlsafe(16)
                    employee_tokens.append(token)

                    conn.execute("""
                        INSERT INTO tokens (token, campaign_id, unit_id, respondent_type)
                        VALUES (?, ?, ?, 'employee')
                    """, (token, campaign_id, unit_id))

                unit_tokens['employee'] = employee_tokens

            # ===== LEADER ASSESSMENT TOKEN =====
            if include_leader_assessment:
                token = secrets.token_urlsafe(16)
                conn.execute("""
                    INSERT INTO tokens (token, campaign_id, unit_id, respondent_type, respondent_name)
                    VALUES (?, ?, ?, 'leader_assess', ?)
                """, (token, campaign_id, unit_id, unit.get('leader_name')))

                unit_tokens['leader_assess'] = [token]

            # ===== LEADER SELF TOKEN =====
            if include_leader_self:
                token = secrets.token_urlsafe(16)
                conn.execute("""
                    INSERT INTO tokens (token, campaign_id, unit_id, respondent_type, respondent_name)
                    VALUES (?, ?, ?, 'leader_self', ?)
                """, (token, campaign_id, unit_id, unit.get('leader_name')))

                unit_tokens['leader_self'] = [token]

            tokens_by_unit[unit_id] = unit_tokens

        # Opdater sent_at
        conn.execute("""
            UPDATE campaigns
            SET sent_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (campaign_id,))

    return tokens_by_unit


# ========================================
# HELPER FUNCTIONS FOR RESPONDENT TYPES
# ========================================

def get_campaign_info(campaign_id: str) -> Optional[Dict]:
    """Hent campaign info inkl. mode og flags"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT * FROM campaigns WHERE id = ?
        """, (campaign_id,)).fetchone()

        return dict(row) if row else None


def get_respondent_types() -> List[Dict]:
    """Hent alle respondent types"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM respondent_types ORDER BY id
        """).fetchall()

        return [dict(row) for row in rows]


def get_campaign_modes() -> List[Dict]:
    """Hent alle campaign modes"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM campaign_modes ORDER BY id
        """).fetchall()

        return [dict(row) for row in rows]


# Initialize on import
init_db()

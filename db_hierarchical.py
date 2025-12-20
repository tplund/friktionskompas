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

# Use DB_PATH from environment, or persistent disk on Render, or local file
def _get_db_path():
    """Determine database path, respecting environment variable."""
    if 'DB_PATH' in os.environ:
        return os.environ['DB_PATH']
    RENDER_DISK_PATH = "/var/data"
    if os.path.exists(RENDER_DISK_PATH):
        return os.path.join(RENDER_DISK_PATH, "friktionskompas_v3.db")
    return "friktionskompas_v3.db"

DB_PATH = _get_db_path()

@contextmanager
def get_db():
    """Context manager for database connection"""
    # Check environment at runtime for test support
    db_path = os.environ.get('DB_PATH', DB_PATH)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys for CASCADE DELETE to work
    conn.execute("PRAGMA foreign_keys=ON")
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def migrate_campaign_to_assessment():
    """Migrate from 'campaign' to 'assessment' terminology in database.
    This runs automatically before init_db() and is safe to run multiple times."""
    with get_db() as conn:
        # Disable foreign keys during migration to avoid constraint errors
        conn.execute("PRAGMA foreign_keys=OFF")

        # Check if migration is needed by looking for old table names
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]

        # Check if tokens table has campaign_id column (need to migrate)
        needs_column_migration = False
        if 'tokens' in tables:
            columns = [r[1] for r in conn.execute("PRAGMA table_info(tokens)").fetchall()]
            if 'campaign_id' in columns:
                needs_column_migration = True
                print("Found tokens.campaign_id - need to migrate columns")

        if 'campaigns' in tables and 'assessments' not in tables:
            print("Migrating database: campaign -> assessment...")

            # 1. Rename campaigns table to assessments
            conn.execute("ALTER TABLE campaigns RENAME TO assessments")
            print("  Renamed campaigns -> assessments")

            # 2. Check if campaign_modes exists and rename it
            if 'campaign_modes' in tables:
                conn.execute("ALTER TABLE campaign_modes RENAME TO assessment_modes")
                print("  Renamed campaign_modes -> assessment_modes")

            # 3. Rename campaign_id columns in related tables
            # SQLite doesn't support ALTER COLUMN, so we need to recreate tables

            # 3a. Tokens table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens_new (
                    token TEXT PRIMARY KEY,
                    assessment_id TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    respondent_type TEXT DEFAULT 'employee',
                    respondent_name TEXT,
                    is_used INTEGER DEFAULT 0,
                    used_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                INSERT INTO tokens_new (token, assessment_id, unit_id, respondent_type, respondent_name, is_used, used_at, created_at)
                SELECT token, campaign_id, unit_id, respondent_type, respondent_name, is_used, used_at, created_at
                FROM tokens
            """)
            conn.execute("DROP TABLE tokens")
            conn.execute("ALTER TABLE tokens_new RENAME TO tokens")
            print("  Migrated tokens.campaign_id -> assessment_id")

            # 3b. Responses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS responses_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    question_id INTEGER NOT NULL,
                    score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                    comment TEXT,
                    category_comment TEXT,
                    respondent_type TEXT DEFAULT 'employee',
                    respondent_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
                    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                INSERT INTO responses_new (id, assessment_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at)
                SELECT id, campaign_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at
                FROM responses
            """)
            conn.execute("DROP TABLE responses")
            conn.execute("ALTER TABLE responses_new RENAME TO responses")
            print("  Migrated responses.campaign_id -> assessment_id")

            # 3c. Scheduled_assessments table (if exists)
            if 'scheduled_campaigns' in tables:
                conn.execute("ALTER TABLE scheduled_campaigns RENAME TO scheduled_assessments")
                # Rename column
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS scheduled_assessments_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assessment_id TEXT NOT NULL,
                        scheduled_date DATE NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
                    )
                """)
                conn.execute("""
                    INSERT INTO scheduled_assessments_new (id, assessment_id, scheduled_date, status, created_at)
                    SELECT id, campaign_id, scheduled_date, status, created_at
                    FROM scheduled_assessments
                """)
                conn.execute("DROP TABLE scheduled_assessments")
                conn.execute("ALTER TABLE scheduled_assessments_new RENAME TO scheduled_assessments")
                print("  Migrated scheduled_campaigns -> scheduled_assessments")

            # Recreate indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_assessment_unit ON tokens(assessment_id, unit_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_assessment ON responses(assessment_id)")

            print("Migration complete!")
        elif needs_column_migration:
            # Table was renamed but columns weren't migrated (partial migration)
            print("Completing partial migration: migrating columns...")

            # Migrate tokens table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens_new (
                    token TEXT PRIMARY KEY,
                    assessment_id TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    respondent_type TEXT DEFAULT 'employee',
                    respondent_name TEXT,
                    is_used INTEGER DEFAULT 0,
                    used_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                INSERT INTO tokens_new (token, assessment_id, unit_id, respondent_type, respondent_name, is_used, used_at, created_at)
                SELECT token, campaign_id, unit_id, respondent_type, respondent_name, is_used, used_at, created_at
                FROM tokens
            """)
            conn.execute("DROP TABLE tokens")
            conn.execute("ALTER TABLE tokens_new RENAME TO tokens")
            print("  Migrated tokens.campaign_id -> assessment_id")

            # Migrate responses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS responses_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    question_id INTEGER NOT NULL,
                    score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                    comment TEXT,
                    category_comment TEXT,
                    respondent_type TEXT DEFAULT 'employee',
                    respondent_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                    FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
                    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                INSERT INTO responses_new (id, assessment_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at)
                SELECT id, campaign_id, unit_id, question_id, score, comment, category_comment, respondent_type, respondent_name, created_at
                FROM responses
            """)
            conn.execute("DROP TABLE responses")
            conn.execute("ALTER TABLE responses_new RENAME TO responses")
            print("  Migrated responses.campaign_id -> assessment_id")

            # Recreate indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_assessment_unit ON tokens(assessment_id, unit_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_assessment ON responses(assessment_id)")

            print("Partial migration complete!")
        elif 'assessments' in tables:
            print("Database already migrated to 'assessment' terminology")
        else:
            print("Fresh database - no migration needed")


def init_db():
    """Initialize database with hierarchical structure"""
    # Run migration first (safe to run multiple times)
    migrate_campaign_to_assessment()

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
            CREATE TABLE IF NOT EXISTS assessments (
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
            conn.execute("ALTER TABLE assessments ADD COLUMN min_responses INTEGER DEFAULT 5")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE assessments ADD COLUMN mode TEXT DEFAULT 'anonymous'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE assessments ADD COLUMN include_leader_assessment INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE assessments ADD COLUMN include_leader_self INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE assessments ADD COLUMN scheduled_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE assessments ADD COLUMN status TEXT DEFAULT 'sent'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE assessments ADD COLUMN sender_name TEXT DEFAULT 'HR'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE assessments ADD COLUMN assessment_type_id TEXT DEFAULT 'gruppe_friktion'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Tokens (genereres per leaf-unit)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                respondent_type TEXT DEFAULT 'employee',
                respondent_name TEXT,
                is_used INTEGER DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE
            )
        """)
        
        # Index for hurtig token validation
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tokens_assessment_unit 
            ON tokens(assessment_id, unit_id)
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
                assessment_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
                comment TEXT,
                category_comment TEXT,
                respondent_type TEXT DEFAULT 'employee',
                respondent_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
        """)
        
        # Index for aggregering
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_responses_assessment_unit
            ON responses(assessment_id, unit_id)
        """)

        # Composite index for N+1 query optimization (audit 2025-12-20)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_responses_unit_assess_type
            ON responses(unit_id, assessment_id, respondent_type)
        """)

        # Index for respondent_type filtering
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_responses_respondent_type
            ON responses(respondent_type)
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
                assessment_id TEXT,
                token TEXT,
                error_message TEXT,
                delivered_at TIMESTAMP,
                opened_at TIMESTAMP,
                clicked_at TIMESTAMP,
                bounced_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE SET NULL
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

        # ========================================
        # SITUATIONSMÅLING TABELLER
        # ========================================

        # Opgaver (tasks) - knyttet til customer og evt. unit
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                unit_id TEXT,
                name TEXT NOT NULL,
                description TEXT,
                situation TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE SET NULL
            )
        """)

        # Migration: Tilføj situation kolonne hvis den mangler
        try:
            conn.execute("SELECT situation FROM tasks LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE tasks ADD COLUMN situation TEXT")

        # Handlinger (actions) - 2-5 per opgave
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                sequence INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)

        # Situationsmålinger (assessments for tasks)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS situation_assessments (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                unit_id TEXT,
                name TEXT,
                period TEXT,
                sent_from TEXT,
                sender_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES organizational_units(id) ON DELETE SET NULL
            )
        """)

        # Tokens til situationsmålinger
        conn.execute("""
            CREATE TABLE IF NOT EXISTS situation_tokens (
                token TEXT PRIMARY KEY,
                situation_assessment_id TEXT NOT NULL,
                recipient_email TEXT,
                recipient_name TEXT,
                is_used INTEGER DEFAULT 0,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (situation_assessment_id) REFERENCES situation_assessments(id) ON DELETE CASCADE
            )
        """)

        # Svar per handling per felt
        conn.execute("""
            CREATE TABLE IF NOT EXISTS situation_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL,
                action_id TEXT NOT NULL,
                field TEXT NOT NULL,
                score INTEGER CHECK(score BETWEEN 1 AND 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (token) REFERENCES situation_tokens(token) ON DELETE CASCADE,
                FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
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


def get_toplevel_units(customer_id: str = None) -> List[Dict]:
    """
    Hent top-level units (uden parent_id).
    Hvis customer_id angives, kun for den kunde.
    """
    with get_db() as conn:
        if customer_id:
            rows = conn.execute("""
                SELECT ou.*, c.name as customer_name
                FROM organizational_units ou
                LEFT JOIN customers c ON ou.customer_id = c.id
                WHERE ou.parent_id IS NULL AND ou.customer_id = ?
                ORDER BY ou.name
            """, (customer_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT ou.*, c.name as customer_name
                FROM organizational_units ou
                LEFT JOIN customers c ON ou.customer_id = c.id
                WHERE ou.parent_id IS NULL
                ORDER BY c.name, ou.name
            """).fetchall()
        return [dict(row) for row in rows]


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

def create_assessment(target_unit_id: str, name: str, period: str,
                   sent_from: str = 'admin',
                   assessment_type_id: str = 'gruppe_friktion') -> str:
    """
    Opret kampagne rettet mod en unit
    Kampagnen rammer alle leaf units under target_unit_id
    """
    assessment_id = f"assess-{secrets.token_urlsafe(8)}"

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
            INSERT INTO assessments (id, target_unit_id, name, period, sent_from, assessment_type_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (assessment_id, target_unit_id, name, period, sent_from, assessment_type_id))

    return assessment_id


def create_individual_assessment(
    name: str,
    period: str,
    target_email: str,
    target_name: str = None,
    sent_from: str = 'admin',
    sender_name: str = 'HR',
    assessment_type_id: str = 'profil_fuld',
    scheduled_at: str = None
) -> str:
    """
    Opret individuel måling - sendes til en enkelt person via email.
    """
    from mailjet_integration import send_single_invitation
    assessment_id = f"assess-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        # Opret assessment med target_email i stedet for target_unit_id
        conn.execute("""
            INSERT INTO assessments (id, name, period, sent_from, sender_name,
                                    assessment_type_id, scheduled_at, status,
                                    target_unit_id, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (assessment_id, name, period, sent_from, sender_name,
              assessment_type_id, scheduled_at,
              'scheduled' if scheduled_at else 'sent',
              None,  # No target_unit for individual
              'individual'))  # Mark as individual

        # Generer én token til personen
        token = secrets.token_urlsafe(16)
        conn.execute("""
            INSERT INTO tokens (token, assessment_id, unit_id, respondent_type, respondent_name)
            VALUES (?, ?, ?, ?, ?)
        """, (token, assessment_id, None, 'individual', target_name or target_email))

    # Send email med det samme (medmindre scheduled)
    if not scheduled_at:
        # Send invitation
        send_single_invitation(
            email=target_email,
            name=target_name,
            token=token,
            assessment_name=name,
            sender_name=sender_name
        )

    return assessment_id


def generate_tokens_for_assessment(assessment_id: str) -> Dict[str, List[str]]:
    """
    Generer tokens for alle leaf units under kampagnens target
    Returnerer dict: {unit_id: [tokens]}
    """
    with get_db() as conn:
        # Find target unit
        assessment = conn.execute(
            "SELECT target_unit_id FROM assessments WHERE id = ?",
            (assessment_id,)
        ).fetchone()
        
        if not assessment:
            raise ValueError(f"Assessment {assessment_id} ikke fundet")
        
        target_unit_id = assessment['target_unit_id']
        
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
                    INSERT INTO tokens (token, assessment_id, unit_id)
                    VALUES (?, ?, ?)
                """, (token, assessment_id, unit_id))
            
            tokens_by_unit[unit_id] = tokens
        
        # Opdater sent_at
        conn.execute("""
            UPDATE assessments
            SET sent_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (assessment_id,))
    
    return tokens_by_unit


def validate_and_use_token(token: str) -> Optional[Dict[str, str]]:
    """Valider token og marker som brugt"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT token, assessment_id, unit_id, is_used
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
            'assessment_id': row['assessment_id'],
            'unit_id': row['unit_id']
        }


# ========================================
# RESPONSES
# ========================================

def save_response(assessment_id: str, unit_id: str, question_id: int,
                 score: int, comment: str = None, category_comment: str = None):
    """Gem svar"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO responses (assessment_id, unit_id, question_id, score, comment, category_comment)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (assessment_id, unit_id, question_id, score, comment, category_comment))


def get_unit_stats(unit_id: str, assessment_id: str, include_children: bool = True) -> List[Dict]:
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
                    AND r.assessment_id = ?
                WHERE q.is_default = 1
                GROUP BY q.field
            """, (unit_id, assessment_id)).fetchall()
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
                    AND r.unit_id = ? AND r.assessment_id = ?
                WHERE q.is_default = 1
                GROUP BY q.field
            """, (unit_id, assessment_id)).fetchall()
        
        # Returner i fast rækkefølge
        field_order = ['TRYGHED', 'MENING', 'KAN', 'BESVÆR']
        data_by_field = {row['field']: row for row in rows}
        
        return [
            {
                'field': field,
                'avg_score': round(data_by_field[field]['avg_score'], 1) if field in data_by_field and data_by_field[field]['avg_score'] else 0,
                'response_count': data_by_field[field]['response_count'] if field in data_by_field else 0
            }
            for field in field_order
        ]


def get_assessment_overview(assessment_id: str) -> List[Dict]:
    """Hent overview for alle leaf units i en kampagne"""
    with get_db() as conn:
        # Find target unit for assessment
        assessment = conn.execute(
            "SELECT target_unit_id FROM assessments WHERE id = ?",
            (assessment_id,)
        ).fetchone()
        
        if not assessment:
            return []
        
        # Find alle leaf units under target
        leaf_units = get_leaf_units(assessment['target_unit_id'])
        
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
                WHERE assessment_id = ? AND unit_id = ?
            """, (assessment_id, unit_id)).fetchone()
            
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
                WHERE r.assessment_id = ? AND r.unit_id = ? AND q.field = 'BESVÆR'
            """, (assessment_id, unit_id)).fetchone()
            
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

def create_assessment_with_modes(
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
        assessment_id
    """
    assessment_id = f"assess-{secrets.token_urlsafe(8)}"

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
            INSERT INTO assessments (
                id, target_unit_id, name, period, sent_from,
                mode, include_leader_assessment, include_leader_self, min_responses
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            assessment_id, target_unit_id, name, period, sent_from,
            mode, 1 if include_leader_assessment else 0,
            1 if include_leader_self else 0, min_responses
        ))

    return assessment_id


def generate_tokens_with_respondent_types(
    assessment_id: str,
    respondent_names: Optional[Dict[str, List[str]]] = None
) -> Dict[str, Dict[str, List[str]]]:
    """
    Generer tokens med support for respondent types

    Args:
        assessment_id: Assessment ID
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
        # Hent assessment info
        assessment = conn.execute("""
            SELECT * FROM assessments WHERE id = ?
        """, (assessment_id,)).fetchone()

        if not assessment:
            raise ValueError(f"Assessment {assessment_id} ikke fundet")

        target_unit_id = assessment['target_unit_id']
        mode = assessment['mode']
        include_leader_assessment = assessment['include_leader_assessment']
        include_leader_self = assessment['include_leader_self']

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
                        INSERT INTO tokens (token, assessment_id, unit_id, respondent_type, respondent_name)
                        VALUES (?, ?, ?, 'employee', ?)
                    """, (token, assessment_id, unit_id, name))

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
                        INSERT INTO tokens (token, assessment_id, unit_id, respondent_type)
                        VALUES (?, ?, ?, 'employee')
                    """, (token, assessment_id, unit_id))

                unit_tokens['employee'] = employee_tokens

            # ===== LEADER ASSESSMENT TOKEN =====
            if include_leader_assessment:
                token = secrets.token_urlsafe(16)
                conn.execute("""
                    INSERT INTO tokens (token, assessment_id, unit_id, respondent_type, respondent_name)
                    VALUES (?, ?, ?, 'leader_assess', ?)
                """, (token, assessment_id, unit_id, unit.get('leader_name')))

                unit_tokens['leader_assess'] = [token]

            # ===== LEADER SELF TOKEN =====
            if include_leader_self:
                token = secrets.token_urlsafe(16)
                conn.execute("""
                    INSERT INTO tokens (token, assessment_id, unit_id, respondent_type, respondent_name)
                    VALUES (?, ?, ?, 'leader_self', ?)
                """, (token, assessment_id, unit_id, unit.get('leader_name')))

                unit_tokens['leader_self'] = [token]

            tokens_by_unit[unit_id] = unit_tokens

        # Opdater sent_at
        conn.execute("""
            UPDATE assessments
            SET sent_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (assessment_id,))

    return tokens_by_unit


# ========================================
# HELPER FUNCTIONS FOR RESPONDENT TYPES
# ========================================

def get_assessment_info(assessment_id: str) -> Optional[Dict]:
    """Hent assessment info inkl. mode og flags"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT * FROM assessments WHERE id = ?
        """, (assessment_id,)).fetchone()

        return dict(row) if row else None


def get_respondent_types() -> List[Dict]:
    """Hent alle respondent types"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM respondent_types ORDER BY id
        """).fetchall()

        return [dict(row) for row in rows]


def get_assessment_modes() -> List[Dict]:
    """Hent alle assessment modes"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM assessment_modes ORDER BY id
        """).fetchall()

        return [dict(row) for row in rows]


def move_unit(unit_id: str, new_parent_id: Optional[str]) -> bool:
    """
    Flyt en unit til en ny parent.
    Opdaterer full_path og level for unit og alle descendants.

    Args:
        unit_id: ID for unit der skal flyttes
        new_parent_id: ID for ny parent (None for toplevel)

    Returns:
        True hvis flytning lykkedes
    """
    with get_db() as conn:
        # Hent unit der skal flyttes
        unit = conn.execute(
            "SELECT * FROM organizational_units WHERE id = ?",
            (unit_id,)
        ).fetchone()

        if not unit:
            raise ValueError(f"Unit {unit_id} ikke fundet")

        old_full_path = unit['full_path']
        unit_name = unit['name']

        # Tjek at vi ikke flytter til sig selv eller descendant
        if new_parent_id:
            # Find alle descendants af unit
            descendants = conn.execute("""
                WITH RECURSIVE subtree AS (
                    SELECT id FROM organizational_units WHERE id = ?
                    UNION ALL
                    SELECT ou.id FROM organizational_units ou
                    JOIN subtree st ON ou.parent_id = st.id
                )
                SELECT id FROM subtree
            """, (unit_id,)).fetchall()

            descendant_ids = {row['id'] for row in descendants}
            if new_parent_id in descendant_ids:
                raise ValueError("Kan ikke flytte unit til sin egen descendant")

            # Hent ny parent info
            new_parent = conn.execute(
                "SELECT level, full_path, customer_id FROM organizational_units WHERE id = ?",
                (new_parent_id,)
            ).fetchone()

            if not new_parent:
                raise ValueError(f"Ny parent {new_parent_id} ikke fundet")

            new_level = new_parent['level'] + 1
            new_full_path = f"{new_parent['full_path']}//{unit_name}"
            new_customer_id = new_parent['customer_id']
        else:
            # Toplevel
            new_level = 0
            new_full_path = unit_name
            new_customer_id = unit['customer_id']  # Behold customer_id

        # Beregn level-diff og path-prefix ændring
        old_level = unit['level']
        level_diff = new_level - old_level

        # Opdater unit selv
        conn.execute("""
            UPDATE organizational_units
            SET parent_id = ?, level = ?, full_path = ?, customer_id = ?
            WHERE id = ?
        """, (new_parent_id, new_level, new_full_path, new_customer_id, unit_id))

        # Opdater alle descendants rekursivt
        # Hent alle descendants med deres nuværende path
        descendants = conn.execute("""
            WITH RECURSIVE subtree AS (
                SELECT id, full_path, level FROM organizational_units WHERE parent_id = ?
                UNION ALL
                SELECT ou.id, ou.full_path, ou.level FROM organizational_units ou
                JOIN subtree st ON ou.parent_id = st.id
            )
            SELECT * FROM subtree
        """, (unit_id,)).fetchall()

        for desc in descendants:
            # Erstat den gamle path-prefix med den nye
            desc_new_path = desc['full_path'].replace(old_full_path, new_full_path, 1)
            desc_new_level = desc['level'] + level_diff

            conn.execute("""
                UPDATE organizational_units
                SET full_path = ?, level = ?, customer_id = ?
                WHERE id = ?
            """, (desc_new_path, desc_new_level, new_customer_id, desc['id']))

        return True


# ========================================
# SITUATIONSMÅLING FUNCTIONS
# ========================================

def create_task(customer_id: str, name: str, description: str = None,
                situation: str = None, unit_id: str = None, created_by: str = None) -> str:
    """Opret ny opgave (task) for situationsmåling"""
    task_id = f"task-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        conn.execute("""
            INSERT INTO tasks (id, customer_id, unit_id, name, description, situation, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, customer_id, unit_id, name, description, situation, created_by))

    return task_id


def get_tasks(customer_id: str = None) -> List[Dict]:
    """Hent alle opgaver, evt. filtreret på customer"""
    with get_db() as conn:
        if customer_id:
            rows = conn.execute("""
                SELECT t.*, ou.name as unit_name,
                       (SELECT COUNT(*) FROM actions WHERE task_id = t.id) as action_count,
                       (SELECT COUNT(*) FROM situation_assessments WHERE task_id = t.id) as assessment_count
                FROM tasks t
                LEFT JOIN organizational_units ou ON t.unit_id = ou.id
                WHERE t.customer_id = ?
                ORDER BY t.created_at DESC
            """, (customer_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT t.*, ou.name as unit_name,
                       (SELECT COUNT(*) FROM actions WHERE task_id = t.id) as action_count,
                       (SELECT COUNT(*) FROM situation_assessments WHERE task_id = t.id) as assessment_count
                FROM tasks t
                LEFT JOIN organizational_units ou ON t.unit_id = ou.id
                ORDER BY t.created_at DESC
            """).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: str) -> Optional[Dict]:
    """Hent en opgave med dens handlinger"""
    with get_db() as conn:
        task = conn.execute("""
            SELECT t.*, ou.name as unit_name, c.name as customer_name
            FROM tasks t
            LEFT JOIN organizational_units ou ON t.unit_id = ou.id
            LEFT JOIN customers c ON t.customer_id = c.id
            WHERE t.id = ?
        """, (task_id,)).fetchone()

        if not task:
            return None

        result = dict(task)

        # Hent handlinger
        actions = conn.execute("""
            SELECT * FROM actions WHERE task_id = ? ORDER BY sequence
        """, (task_id,)).fetchall()
        result['actions'] = [dict(a) for a in actions]

        # Hent situationsmålinger
        assessments = conn.execute("""
            SELECT sa.*, ou.name as unit_name,
                   (SELECT COUNT(*) FROM situation_tokens WHERE situation_assessment_id = sa.id) as token_count,
                   (SELECT COUNT(*) FROM situation_tokens WHERE situation_assessment_id = sa.id AND is_used = 1) as response_count
            FROM situation_assessments sa
            LEFT JOIN organizational_units ou ON sa.unit_id = ou.id
            WHERE sa.task_id = ?
            ORDER BY sa.created_at DESC
        """, (task_id,)).fetchall()
        result['assessments'] = [dict(a) for a in assessments]

        return result


def update_task(task_id: str, name: str = None, description: str = None, unit_id: str = None) -> bool:
    """Opdater opgave"""
    with get_db() as conn:
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if unit_id is not None:
            updates.append("unit_id = ?")
            params.append(unit_id)

        if not updates:
            return False

        params.append(task_id)
        conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
        return True


def delete_task(task_id: str) -> bool:
    """Slet opgave (cascade sletter handlinger og målinger)"""
    with get_db() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return True


def add_action(task_id: str, name: str, description: str = None) -> str:
    """Tilføj handling til opgave"""
    action_id = f"action-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        # Find højeste sequence
        max_seq = conn.execute(
            "SELECT COALESCE(MAX(sequence), -1) as max_seq FROM actions WHERE task_id = ?",
            (task_id,)
        ).fetchone()['max_seq']

        conn.execute("""
            INSERT INTO actions (id, task_id, name, description, sequence)
            VALUES (?, ?, ?, ?, ?)
        """, (action_id, task_id, name, description, max_seq + 1))

    return action_id


def update_action(action_id: str, name: str = None, description: str = None, sequence: int = None) -> bool:
    """Opdater handling"""
    with get_db() as conn:
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if sequence is not None:
            updates.append("sequence = ?")
            params.append(sequence)

        if not updates:
            return False

        params.append(action_id)
        conn.execute(f"UPDATE actions SET {', '.join(updates)} WHERE id = ?", params)
        return True


def delete_action(action_id: str) -> bool:
    """Slet handling"""
    with get_db() as conn:
        conn.execute("DELETE FROM actions WHERE id = ?", (action_id,))
        return True


def create_situation_assessment(task_id: str, name: str = None, period: str = None,
                                 unit_id: str = None, sent_from: str = None,
                                 sender_name: str = None) -> str:
    """Opret situationsmåling for en opgave"""
    assessment_id = f"sitass-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        conn.execute("""
            INSERT INTO situation_assessments (id, task_id, unit_id, name, period, sent_from, sender_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (assessment_id, task_id, unit_id, name, period, sent_from, sender_name))

    return assessment_id


def get_situation_assessment(assessment_id: str) -> Optional[Dict]:
    """Hent situationsmåling med detaljer"""
    with get_db() as conn:
        assessment = conn.execute("""
            SELECT sa.*, t.name as task_name, t.description as task_description,
                   ou.name as unit_name, c.name as customer_name
            FROM situation_assessments sa
            JOIN tasks t ON sa.task_id = t.id
            LEFT JOIN organizational_units ou ON sa.unit_id = ou.id
            LEFT JOIN customers c ON t.customer_id = c.id
            WHERE sa.id = ?
        """, (assessment_id,)).fetchone()

        if not assessment:
            return None

        result = dict(assessment)

        # Hent handlinger
        actions = conn.execute("""
            SELECT * FROM actions WHERE task_id = ? ORDER BY sequence
        """, (result['task_id'],)).fetchall()
        result['actions'] = [dict(a) for a in actions]

        # Hent tokens
        tokens = conn.execute("""
            SELECT * FROM situation_tokens WHERE situation_assessment_id = ?
        """, (assessment_id,)).fetchall()
        result['tokens'] = [dict(t) for t in tokens]
        result['token_count'] = len(tokens)
        result['response_count'] = sum(1 for t in tokens if t['is_used'])

        return result


def generate_situation_tokens(assessment_id: str, recipients: List[Dict]) -> List[str]:
    """Generer tokens for situationsmåling

    recipients: [{'email': '...', 'name': '...'}, ...]
    """
    tokens = []

    with get_db() as conn:
        for recipient in recipients:
            token = secrets.token_urlsafe(16)
            conn.execute("""
                INSERT INTO situation_tokens (token, situation_assessment_id, recipient_email, recipient_name)
                VALUES (?, ?, ?, ?)
            """, (token, assessment_id, recipient.get('email'), recipient.get('name')))
            tokens.append(token)

    return tokens


def validate_situation_token(token: str) -> Optional[Dict]:
    """Valider og hent token data for situationsmåling"""
    with get_db() as conn:
        token_data = conn.execute("""
            SELECT st.*, sa.task_id, sa.name as assessment_name,
                   t.name as task_name, t.description as task_description,
                   t.situation as task_situation
            FROM situation_tokens st
            JOIN situation_assessments sa ON st.situation_assessment_id = sa.id
            JOIN tasks t ON sa.task_id = t.id
            WHERE st.token = ? AND st.is_used = 0
        """, (token,)).fetchone()

        if not token_data:
            return None

        result = dict(token_data)

        # Hent handlinger
        actions = conn.execute("""
            SELECT * FROM actions WHERE task_id = ? ORDER BY sequence
        """, (result['task_id'],)).fetchall()
        result['actions'] = [dict(a) for a in actions]

        return result


def save_situation_responses(token: str, responses: List[Dict]) -> int:
    """Gem svar for situationsmåling

    responses: [{'action_id': '...', 'field': 'TRYGHED', 'score': 3}, ...]
    """
    with get_db() as conn:
        for resp in responses:
            conn.execute("""
                INSERT INTO situation_responses (token, action_id, field, score)
                VALUES (?, ?, ?, ?)
            """, (token, resp['action_id'], resp['field'], resp['score']))

        # Marker token som brugt
        conn.execute("""
            UPDATE situation_tokens SET is_used = 1, used_at = CURRENT_TIMESTAMP
            WHERE token = ?
        """, (token,))

    return len(responses)


def get_situation_results(assessment_id: str) -> Dict:
    """Hent aggregerede resultater for situationsmåling"""
    with get_db() as conn:
        # Hent assessment info
        assessment = get_situation_assessment(assessment_id)
        if not assessment:
            return None

        # Hent alle svar
        responses = conn.execute("""
            SELECT sr.action_id, sr.field, sr.score, a.name as action_name, a.sequence
            FROM situation_responses sr
            JOIN situation_tokens st ON sr.token = st.token
            JOIN actions a ON sr.action_id = a.id
            WHERE st.situation_assessment_id = ?
        """, (assessment_id,)).fetchall()

        if not responses:
            return {
                'assessment': assessment,
                'actions': [],
                'summary': None,
                'response_count': 0
            }

        # Aggreger per handling per felt
        from collections import defaultdict
        scores_by_action = defaultdict(lambda: defaultdict(list))
        action_names = {}
        action_sequences = {}

        for r in responses:
            action_id = r['action_id']
            scores_by_action[action_id][r['field']].append(r['score'])
            action_names[action_id] = r['action_name']
            action_sequences[action_id] = r['sequence']

        # Beregn gennemsnit
        from friction_engine import score_to_percent, get_severity, adjust_score

        action_results = []
        for action_id, fields in scores_by_action.items():
            field_scores = {}
            for field, scores in fields.items():
                avg = sum(scores) / len(scores)
                # Note: reverse_scored håndteres i spørgsmålsdefinitionen
                pct = score_to_percent(avg)
                severity = get_severity(avg)
                field_scores[field] = {
                    'score': round(avg, 2),
                    'percent': round(pct, 0),
                    'severity': severity.value,
                    'response_count': len(scores)
                }

            # Find primær friktion (laveste score)
            min_field = min(field_scores.keys(), key=lambda f: field_scores[f]['score'])

            action_results.append({
                'id': action_id,
                'name': action_names[action_id],
                'sequence': action_sequences[action_id],
                'scores': field_scores,
                'primary_friction': min_field
            })

        # Sorter efter sequence
        action_results.sort(key=lambda a: a['sequence'])

        # Find højeste friktion overall
        worst_action = min(action_results, key=lambda a: min(a['scores'][f]['score'] for f in a['scores']))
        worst_field = worst_action['primary_friction']

        return {
            'assessment': assessment,
            'actions': action_results,
            'summary': {
                'highest_friction_action': worst_action['name'],
                'highest_friction_field': worst_field,
                'recommendation': f"Start med at adressere {worst_field} i \"{worst_action['name']}\""
            },
            'response_count': assessment['response_count']
        }


# Initialize on import
init_db()

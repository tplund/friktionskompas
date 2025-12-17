"""
Multi-tenant extension for Friktionskompas v3
Tilføjer customer isolation og user authentication
"""
import sqlite3
import secrets
import os
import bcrypt
from contextlib import contextmanager
from typing import Optional, Dict
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys for CASCADE DELETE to work
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_multitenant_db():
    """Tilføj multi-tenant tabeller til eksisterende database"""
    with get_db() as conn:
        # Customers tabel
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                contact_email TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Users tabel med authentication
        # Roles: superadmin (global), admin (kunde-admin), manager (enheds-leder), user (B2C bruger)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'manager', 'user')),
                customer_id TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
            )
        """)

        # Index for hurtig username lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_username
            ON users(username)
        """)

        # Translations tabel for i18n
        conn.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                language TEXT NOT NULL,
                value TEXT NOT NULL,
                context TEXT,
                UNIQUE(key, language)
            )
        """)

        # Index for hurtig translation lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_translations_key_lang
            ON translations(key, language)
        """)

        # Domains tabel for multi-domain support
        conn.execute("""
            CREATE TABLE IF NOT EXISTS domains (
                id TEXT PRIMARY KEY,
                domain TEXT UNIQUE NOT NULL,
                customer_id TEXT,
                default_language TEXT DEFAULT 'da',
                branding_logo_url TEXT,
                branding_primary_color TEXT,
                branding_company_name TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
            )
        """)

        # Index for hurtig domain lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_domains_domain
            ON domains(domain)
        """)

        # OAuth links tabel - linker users til OAuth providers
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_oauth_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_user_id TEXT NOT NULL,
                provider_email TEXT,
                access_token TEXT,
                refresh_token TEXT,
                token_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(provider, provider_user_id)
            )
        """)

        # Index for OAuth lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_oauth_provider_user
            ON user_oauth_links(provider, provider_user_id)
        """)

        # Email verification codes tabel - for passwordless login og password reset
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                code_type TEXT NOT NULL CHECK(code_type IN ('login', 'register', 'reset')),
                expires_at TIMESTAMP NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for email code lookup
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_email_codes_email
            ON email_codes(email, code_type, used)
        """)

        # Tilføj auth_providers kolonne til customers hvis den ikke findes
        customer_columns = conn.execute("PRAGMA table_info(customers)").fetchall()
        customer_column_names = [col['name'] for col in customer_columns]

        if 'auth_providers' not in customer_column_names:
            conn.execute("""
                ALTER TABLE customers ADD COLUMN auth_providers TEXT DEFAULT '{"email_password": true}'
            """)

        # Tilføj email afsender kolonner til customers hvis de ikke findes
        if 'email_from_address' not in customer_column_names:
            conn.execute("""
                ALTER TABLE customers ADD COLUMN email_from_address TEXT
            """)

        if 'email_from_name' not in customer_column_names:
            conn.execute("""
                ALTER TABLE customers ADD COLUMN email_from_name TEXT
            """)

        # Tilføj allow_profile_edit til customers (default true for bagudkompatibilitet)
        if 'allow_profile_edit' not in customer_column_names:
            conn.execute("""
                ALTER TABLE customers ADD COLUMN allow_profile_edit INTEGER DEFAULT 1
            """)

        # Tilføj auth_providers kolonne til domains hvis den ikke findes
        domain_columns = conn.execute("PRAGMA table_info(domains)").fetchall()
        domain_column_names = [col['name'] for col in domain_columns]

        if 'auth_providers' not in domain_column_names:
            conn.execute("""
                ALTER TABLE domains ADD COLUMN auth_providers TEXT
            """)

        # Tilføj language kolonne til users hvis den ikke findes
        user_columns = conn.execute("PRAGMA table_info(users)").fetchall()
        user_column_names = [col['name'] for col in user_columns]

        if 'language' not in user_column_names:
            conn.execute("""
                ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'da'
            """)

        # Tilføj recovery_email til users hvis den ikke findes
        if 'recovery_email' not in user_column_names:
            conn.execute("""
                ALTER TABLE users ADD COLUMN recovery_email TEXT
            """)

        # Tilføj text_en kolonne til questions hvis den ikke findes
        questions_columns = conn.execute("PRAGMA table_info(questions)").fetchall()
        questions_column_names = [col['name'] for col in questions_columns]

        if 'text_en' not in questions_column_names:
            conn.execute("""
                ALTER TABLE questions ADD COLUMN text_en TEXT
            """)

        # Tilføj text_en og state_text_en kolonner til profil_questions hvis de ikke findes
        profil_q_columns = conn.execute("PRAGMA table_info(profil_questions)").fetchall()
        profil_q_column_names = [col['name'] for col in profil_q_columns]

        if 'text_en' not in profil_q_column_names:
            conn.execute("""
                ALTER TABLE profil_questions ADD COLUMN text_en TEXT
            """)

        if 'state_text_en' not in profil_q_column_names:
            conn.execute("""
                ALTER TABLE profil_questions ADD COLUMN state_text_en TEXT
            """)

        # Tilføj customer_id til organizational_units hvis den ikke findes
        # Check hvis kolonnen eksisterer
        columns = conn.execute("PRAGMA table_info(organizational_units)").fetchall()
        column_names = [col['name'] for col in columns]

        if 'customer_id' not in column_names:
            conn.execute("""
                ALTER TABLE organizational_units
                ADD COLUMN customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE
            """)

            # Index for customer filtering
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_units_customer
                ON organizational_units(customer_id)
            """)

        # Migration: Opdater users tabel til at understøtte 'superadmin' rolle
        # SQLite tillader ikke ændring af CHECK constraints, så vi skal migrere tabellen
        try:
            # Test om superadmin er tilladt ved at prøve en dummy INSERT
            conn.execute("INSERT INTO users (id, username, password_hash, name, role) VALUES ('__test__', '__test__', '__test__', '__test__', 'superadmin')")
            conn.execute("DELETE FROM users WHERE id = '__test__'")
        except Exception as e:
            if 'CHECK constraint failed' in str(e):
                print("[Migration] Migrerer users tabel til at understøtte superadmin rolle...")
                # Opret ny tabel med korrekt CHECK constraint
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users_new (
                        id TEXT PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        name TEXT NOT NULL,
                        email TEXT,
                        role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin', 'manager', 'user')),
                        customer_id TEXT,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        language TEXT DEFAULT 'da',
                        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
                    )
                """)
                # Kopier data fra gammel tabel
                conn.execute("""
                    INSERT INTO users_new (id, username, password_hash, name, email, role, customer_id, is_active, created_at, last_login)
                    SELECT id, username, password_hash, name, email, role, customer_id, is_active, created_at, last_login
                    FROM users
                """)
                # Drop gammel tabel og omdøb ny
                conn.execute("DROP TABLE users")
                conn.execute("ALTER TABLE users_new RENAME TO users")
                # Genskab index
                conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
                print("[Migration] Users tabel migreret!")

        # Migration: Opdater eksisterende 'admin' brugere uden customer_id til 'superadmin'
        conn.execute("""
            UPDATE users SET role = 'superadmin'
            WHERE role = 'admin' AND customer_id IS NULL
        """)

        # Opret default superadmin user hvis ingen users findes
        user_count = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()['cnt']

        if user_count == 0:
            # Hash password: "admin123"
            password_hash = hash_password("admin123")
            admin_id = f"user-{secrets.token_urlsafe(8)}"

            conn.execute("""
                INSERT INTO users (id, username, password_hash, name, email, role, customer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (admin_id, "admin", password_hash, "System Administrator", "admin@friktionskompas.dk", "superadmin", None))

            print("Default superadmin user oprettet:")
            print("   Username: admin")
            print("   Password: admin123")
            print("   ADVARSEL: SKIFT PASSWORD I PRODUKTION!")

        # ========================================
        # ASSESSMENT TYPES TABLES
        # ========================================

        # Assessment types - definerer hvilke målingstyper der findes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assessment_types (
                id TEXT PRIMARY KEY,
                name_da TEXT NOT NULL,
                name_en TEXT NOT NULL,
                description_da TEXT,
                description_en TEXT,
                question_count INTEGER,
                duration_minutes INTEGER,
                is_individual INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                sequence INTEGER DEFAULT 0,
                icon TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Customer assessment types - hvilke typer er tilgængelige per kunde
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_assessment_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                assessment_type_id TEXT NOT NULL,
                is_enabled INTEGER DEFAULT 1,
                custom_name_da TEXT,
                custom_name_en TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                FOREIGN KEY (assessment_type_id) REFERENCES assessment_types(id) ON DELETE CASCADE,
                UNIQUE(customer_id, assessment_type_id)
            )
        """)

        # Domain assessment types - override per domæne
        conn.execute("""
            CREATE TABLE IF NOT EXISTS domain_assessment_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id TEXT NOT NULL,
                assessment_type_id TEXT NOT NULL,
                is_enabled INTEGER DEFAULT 1,
                FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
                FOREIGN KEY (assessment_type_id) REFERENCES assessment_types(id) ON DELETE CASCADE,
                UNIQUE(domain_id, assessment_type_id)
            )
        """)

        # Assessment presets - foruddefinerede kombinationer
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assessment_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                is_default INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Preset assessment types - hvilke typer er i hvert preset
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preset_assessment_types (
                preset_id INTEGER NOT NULL,
                assessment_type_id TEXT NOT NULL,
                FOREIGN KEY (preset_id) REFERENCES assessment_presets(id) ON DELETE CASCADE,
                FOREIGN KEY (assessment_type_id) REFERENCES assessment_types(id) ON DELETE CASCADE,
                PRIMARY KEY(preset_id, assessment_type_id)
            )
        """)

        # Indexes for assessment tables
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_customer_assessment_types
            ON customer_assessment_types(customer_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_domain_assessment_types
            ON domain_assessment_types(domain_id)
        """)


def hash_password(password: str) -> str:
    """Hash password med bcrypt (sikker og langsom)"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verificer password mod bcrypt hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except (ValueError, AttributeError):
        # Håndter forkert format gracefully
        return False


# ========================================
# CUSTOMER FUNCTIONS
# ========================================

def create_customer(name: str, contact_email: str = None) -> str:
    """Opret ny customer"""
    customer_id = f"cust-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        conn.execute("""
            INSERT INTO customers (id, name, contact_email)
            VALUES (?, ?, ?)
        """, (customer_id, name, contact_email))

    return customer_id


def get_customer(customer_id: str) -> Optional[Dict]:
    """Hent customer info"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?",
            (customer_id,)
        ).fetchone()

        return dict(row) if row else None


def update_customer(customer_id: str, **kwargs) -> bool:
    """Opdater customer felter"""
    allowed_fields = ['name', 'contact_email', 'email_from_address', 'email_from_name', 'auth_providers', 'is_active']
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return False

    with get_db() as conn:
        set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [customer_id]

        conn.execute(f"""
            UPDATE customers SET {set_clause} WHERE id = ?
        """, values)

    return True


def get_customer_email_config(customer_id: str) -> Dict:
    """
    Hent email-afsender konfiguration for en kunde.
    Returnerer default værdier hvis ikke sat.
    """
    import os
    default_from_email = os.getenv('FROM_EMAIL', 'info@friktionskompasset.dk')
    default_from_name = os.getenv('FROM_NAME', 'Friktionskompasset')

    if not customer_id:
        return {
            'from_address': default_from_email,
            'from_name': default_from_name
        }

    with get_db() as conn:
        row = conn.execute("""
            SELECT email_from_address, email_from_name
            FROM customers WHERE id = ?
        """, (customer_id,)).fetchone()

        if row and row['email_from_address']:
            return {
                'from_address': row['email_from_address'],
                'from_name': row['email_from_name'] or default_from_name
            }

    return {
        'from_address': default_from_email,
        'from_name': default_from_name
    }


def list_customers() -> list:
    """List alle customers (kun for admin)"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT c.*, COUNT(DISTINCT ou.id) as unit_count
            FROM customers c
            LEFT JOIN organizational_units ou ON c.id = ou.customer_id
            GROUP BY c.id
            ORDER BY c.name
        """).fetchall()

        return [dict(row) for row in rows]


# ========================================
# DOMAIN FUNCTIONS
# ========================================

def create_domain(domain: str, customer_id: Optional[str] = None,
                  default_language: str = 'da', branding: Optional[Dict] = None) -> str:
    """Opret nyt domain mapping"""
    domain_id = f"dom-{secrets.token_urlsafe(8)}"

    with get_db() as conn:
        conn.execute("""
            INSERT INTO domains (id, domain, customer_id, default_language,
                                branding_logo_url, branding_primary_color, branding_company_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            domain_id,
            domain.lower(),
            customer_id,
            default_language,
            branding.get('logo_url') if branding else None,
            branding.get('primary_color') if branding else None,
            branding.get('company_name') if branding else None
        ))

    return domain_id


def get_domain_config(domain: str) -> Optional[Dict]:
    """Hent domain konfiguration baseret på hostname"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT d.*, c.name as customer_name
            FROM domains d
            LEFT JOIN customers c ON d.customer_id = c.id
            WHERE d.domain = ? AND d.is_active = 1
        """, (domain.lower(),)).fetchone()

        if row:
            return dict(row)
        return None


def list_domains() -> list:
    """List alle domains med customer info"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT d.*, c.name as customer_name
            FROM domains d
            LEFT JOIN customers c ON d.customer_id = c.id
            ORDER BY d.domain
        """).fetchall()

        return [dict(row) for row in rows]


def update_domain(domain_id: str, **kwargs) -> bool:
    """Opdater domain settings"""
    allowed_fields = ['customer_id', 'default_language', 'branding_logo_url',
                      'branding_primary_color', 'branding_company_name', 'is_active']

    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return False

    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values()) + [domain_id]

    with get_db() as conn:
        conn.execute(f"""
            UPDATE domains SET {set_clause} WHERE id = ?
        """, values)

    return True


def delete_domain(domain_id: str) -> bool:
    """Slet domain"""
    with get_db() as conn:
        conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
    return True


# ========================================
# USER FUNCTIONS
# ========================================

def create_user(username: str, password: str, name: str, email: str,
                role: str, customer_id: Optional[str] = None) -> str:
    """
    Opret ny user

    Roles:
    - 'superadmin': Global admin, kan se alt (customer_id = None)
    - 'admin': Kunde-admin, styrer én kunde (customer_id påkrævet)
    - 'manager': Enheds-leder, kan se resultater (customer_id påkrævet)
    - 'user': B2C bruger, kan tage tests (customer_id påkrævet)
    """
    if role == 'manager' and not customer_id:
        raise ValueError("Manager skal have en customer_id")

    if role == 'admin' and not customer_id:
        raise ValueError("Admin skal have en customer_id (brug superadmin for global adgang)")

    if role == 'superadmin' and customer_id:
        raise ValueError("Superadmin kan ikke have en customer_id (har adgang til alt)")

    if role == 'user' and not customer_id:
        raise ValueError("User skal have en customer_id")

    user_id = f"user-{secrets.token_urlsafe(8)}"
    password_hash = hash_password(password)

    with get_db() as conn:
        try:
            conn.execute("""
                INSERT INTO users (id, username, password_hash, name, email, role, customer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, password_hash, name, email, role, customer_id))
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' er allerede i brug")

    return user_id


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Autentificer bruger og returner user info
    Returnerer None hvis login fejler
    """
    with get_db() as conn:
        user = conn.execute("""
            SELECT u.*, c.name as customer_name
            FROM users u
            LEFT JOIN customers c ON u.customer_id = c.id
            WHERE u.username = ? AND u.is_active = 1
        """, (username,)).fetchone()

        if not user:
            return None

        if not verify_password(password, user['password_hash']):
            return None

        # Opdater last_login
        conn.execute("""
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user['id'],))

        return {
            'id': user['id'],
            'username': user['username'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'customer_id': user['customer_id'],
            'customer_name': user['customer_name']
        }


def get_user(user_id: str) -> Optional[Dict]:
    """Hent user info"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT u.*, c.name as customer_name
            FROM users u
            LEFT JOIN customers c ON u.customer_id = c.id
            WHERE u.id = ?
        """, (user_id,)).fetchone()

        return dict(row) if row else None


def list_users(customer_id: Optional[str] = None) -> list:
    """
    List users
    customer_id: None = alle users (admin), specifik = kun den customer
    """
    with get_db() as conn:
        if customer_id:
            rows = conn.execute("""
                SELECT u.*, c.name as customer_name
                FROM users u
                LEFT JOIN customers c ON u.customer_id = c.id
                WHERE u.customer_id = ?
                ORDER BY u.name
            """, (customer_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT u.*, c.name as customer_name
                FROM users u
                LEFT JOIN customers c ON u.customer_id = c.id
                ORDER BY u.name
            """).fetchall()

        return [dict(row) for row in rows]


def change_password(user_id: str, new_password: str):
    """Skift password for user"""
    password_hash = hash_password(new_password)

    with get_db() as conn:
        conn.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
        """, (password_hash, user_id))


# ========================================
# CUSTOMER ISOLATION HELPERS
# ========================================

def get_customer_filter(user_role: str, customer_id: Optional[str], session_filter: Optional[int] = None) -> tuple:
    """
    Returner SQL WHERE clause og params for customer filtering

    Returns:
        (where_clause, params)

    Roles:
        - superadmin: Kan se alt, eller filtreret hvis session_filter er sat
        - admin: Kan se alt, eller filtreret hvis session_filter er sat
        - manager: Kun egen kunde (customer_id påkrævet)

    Args:
        user_role: Brugerens rolle
        customer_id: Brugerens faste customer_id (for managers)
        session_filter: Optional customer_filter fra session (for admin/superadmin)

    Eksempel:
        where, params = get_customer_filter('manager', 'cust-123')
        # Returns: ("ou.customer_id = ?", ['cust-123'])

        # For superadmin med valgt kunde:
        where, params = get_customer_filter('superadmin', None, session.get('customer_filter'))
        # Returns: ("ou.customer_id = ?", [123]) hvis filter sat

        sql = f"SELECT * FROM organizational_units WHERE {where}"
        conn.execute(sql, params)
    """
    # For managers, always use their customer_id
    if customer_id:
        return ("ou.customer_id = ?", [customer_id])

    # For admin/superadmin, check session filter
    if session_filter:
        return ("ou.customer_id = ?", [session_filter])

    # Admin/superadmin without filter can see all
    return ("1=1", [])


# ========================================
# EMAIL CODE FUNCTIONS (Passwordless login)
# ========================================

def generate_email_code(email: str, code_type: str = 'login', expires_minutes: int = 15) -> str:
    """
    Generer 6-cifret kode til email-verifikation.

    Args:
        email: Brugerens email
        code_type: 'login', 'register', eller 'reset'
        expires_minutes: Koden udløber efter X minutter

    Returns:
        Den genererede kode
    """
    import random
    from datetime import datetime, timedelta

    # Generer 6-cifret kode
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    expires_at = datetime.now() + timedelta(minutes=expires_minutes)

    with get_db() as conn:
        # Invalider tidligere ubrugte koder for denne email og type
        conn.execute("""
            UPDATE email_codes
            SET used = 1
            WHERE email = ? AND code_type = ? AND used = 0
        """, (email.lower(), code_type))

        # Indsæt ny kode
        conn.execute("""
            INSERT INTO email_codes (email, code, code_type, expires_at)
            VALUES (?, ?, ?, ?)
        """, (email.lower(), code, code_type, expires_at))

    return code


def verify_email_code(email: str, code: str, code_type: str = 'login') -> bool:
    """
    Verificer email-kode.

    Returns:
        True hvis koden er gyldig og ikke udløbet
    """
    from datetime import datetime

    with get_db() as conn:
        row = conn.execute("""
            SELECT id, expires_at FROM email_codes
            WHERE email = ? AND code = ? AND code_type = ? AND used = 0
            ORDER BY created_at DESC
            LIMIT 1
        """, (email.lower(), code, code_type)).fetchone()

        if not row:
            return False

        # Check om koden er udløbet
        expires_at = datetime.fromisoformat(row['expires_at'])
        if datetime.now() > expires_at:
            return False

        # Marker koden som brugt
        conn.execute("UPDATE email_codes SET used = 1 WHERE id = ?", (row['id'],))

        return True


def find_user_by_email(email: str) -> Optional[Dict]:
    """Find bruger via email"""
    with get_db() as conn:
        row = conn.execute("""
            SELECT u.*, c.name as customer_name
            FROM users u
            LEFT JOIN customers c ON u.customer_id = c.id
            WHERE LOWER(u.email) = ? AND u.is_active = 1
        """, (email.lower(),)).fetchone()

        return dict(row) if row else None


def create_b2c_user(email: str, name: str, customer_id: str) -> str:
    """
    Opret B2C bruger (user rolle) uden password.
    Brugeren logger ind via email-kode eller OAuth.

    Returns:
        user_id
    """
    user_id = f"user-{secrets.token_urlsafe(8)}"
    # OAuth/passwordless brugere får et random "password" de aldrig bruger
    dummy_password_hash = f"b2c-{secrets.token_urlsafe(32)}"

    with get_db() as conn:
        conn.execute("""
            INSERT INTO users (id, username, password_hash, name, email, role, customer_id)
            VALUES (?, ?, ?, ?, ?, 'user', ?)
        """, (user_id, email.lower(), dummy_password_hash, name, email.lower(), customer_id))

    return user_id


def get_or_create_b2c_customer() -> str:
    """
    Hent eller opret B2C kunden til selvregistrerede brugere.

    Returns:
        customer_id for B2C kunden
    """
    B2C_CUSTOMER_NAME = "B2C Brugere"

    with get_db() as conn:
        # Tjek om B2C kunde allerede eksisterer
        row = conn.execute("""
            SELECT id FROM customers WHERE name = ?
        """, (B2C_CUSTOMER_NAME,)).fetchone()

        if row:
            return row['id']

        # Opret B2C kunde
        customer_id = f"cust-b2c-{secrets.token_urlsafe(4)}"
        auth_providers = {
            "email_password": False,  # Ingen password login
            "email_code": True,  # Passwordless med email-kode
            "microsoft": {"enabled": True},
            "google": {"enabled": True}
        }

        conn.execute("""
            INSERT INTO customers (id, name, contact_email, auth_providers)
            VALUES (?, ?, ?, ?)
        """, (customer_id, B2C_CUSTOMER_NAME, "b2c@friktionskompas.dk",
              __import__('json').dumps(auth_providers)))

        return customer_id


def authenticate_by_email_code(email: str, code: str) -> Optional[Dict]:
    """
    Autentificer bruger via email-kode.

    Returns:
        User dict for session, eller None ved fejl
    """
    if not verify_email_code(email, code, 'login'):
        return None

    user = find_user_by_email(email)
    if not user:
        return None

    # Opdater last_login
    with get_db() as conn:
        conn.execute("""
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
        """, (user['id'],))

    return {
        'id': user['id'],
        'username': user['username'],
        'name': user['name'],
        'email': user['email'],
        'role': user['role'],
        'customer_id': user['customer_id'],
        'customer_name': user.get('customer_name')
    }


def reset_password_with_code(email: str, code: str, new_password: str) -> bool:
    """
    Nulstil password med email-kode.

    Returns:
        True ved succes
    """
    if not verify_email_code(email, code, 'reset'):
        return False

    user = find_user_by_email(email)
    if not user:
        return False

    # Opdater password
    password_hash = hash_password(new_password)

    with get_db() as conn:
        conn.execute("""
            UPDATE users SET password_hash = ? WHERE id = ?
        """, (password_hash, user['id']))

    return True


# ========================================
# ASSESSMENT TYPES FUNCTIONS
# ========================================

# Initial assessment types data
INITIAL_ASSESSMENT_TYPES = [
    {
        'id': 'screening',
        'name_da': 'Hurtig Screening',
        'name_en': 'Quick Screening',
        'description_da': 'En hurtig screening med 6 spørgsmål for at få et overblik over friktionsniveauet.',
        'description_en': 'A quick screening with 6 questions to get an overview of friction levels.',
        'question_count': 6,
        'duration_minutes': 2,
        'is_individual': 1,
        'sequence': 1,
        'icon': '⚡'
    },
    {
        'id': 'profil_fuld',
        'name_da': 'Fuld Friktionsprofil',
        'name_en': 'Full Friction Profile',
        'description_da': 'En grundig individuel profil med 30+ spørgsmål der giver detaljeret indsigt.',
        'description_en': 'A thorough individual profile with 30+ questions providing detailed insights.',
        'question_count': 30,
        'duration_minutes': 15,
        'is_individual': 1,
        'sequence': 2,
        'icon': '🧠'
    },
    {
        'id': 'profil_situation',
        'name_da': 'Situations-profil',
        'name_en': 'Situation Profile',
        'description_da': 'Friktionsprofil i en specifik situation eller kontekst.',
        'description_en': 'Friction profile in a specific situation or context.',
        'question_count': 30,
        'duration_minutes': 15,
        'is_individual': 1,
        'sequence': 3,
        'icon': '🎯'
    },
    {
        'id': 'gruppe_friktion',
        'name_da': 'Gruppe-friktionsanalyse',
        'name_en': 'Team Friction Analysis',
        'description_da': 'Organisatorisk måling af friktion i teams og afdelinger.',
        'description_en': 'Organizational measurement of friction in teams and departments.',
        'question_count': 24,
        'duration_minutes': 10,
        'is_individual': 0,
        'sequence': 4,
        'icon': '👥'
    },
    {
        'id': 'gruppe_leder',
        'name_da': 'Leder-måling',
        'name_en': 'Leader Assessment',
        'description_da': 'Team-måling med ekstra fokus på ledelsesfriktion.',
        'description_en': 'Team measurement with extra focus on leadership friction.',
        'question_count': 28,
        'duration_minutes': 12,
        'is_individual': 0,
        'sequence': 5,
        'icon': '👔'
    },
    {
        'id': 'kapacitet',
        'name_da': 'Kapacitetsmåling',
        'name_en': 'Capacity Assessment',
        'description_da': 'Måler evnen til at "tage sig sammen" - den indre kapacitet.',
        'description_en': 'Measures the ability to "pull yourself together" - inner capacity.',
        'question_count': 8,
        'duration_minutes': 4,
        'is_individual': 1,
        'sequence': 6,
        'icon': '💪'
    },
    {
        'id': 'baandbredde',
        'name_da': 'Båndbredde-måling',
        'name_en': 'Bandwidth Assessment',
        'description_da': 'Måler evnen til at løfte pres opad i organisationen.',
        'description_en': 'Measures the ability to push pressure upward in the organization.',
        'question_count': 2,
        'duration_minutes': 1,
        'is_individual': 1,
        'sequence': 7,
        'icon': '📊'
    }
]

# Initial presets data
INITIAL_PRESETS = [
    {
        'name': 'B2C Individuel',
        'description': 'Standard for selvregistrerede individuelle brugere',
        'is_default': 0,
        'types': ['screening', 'profil_fuld']
    },
    {
        'name': 'B2B Standard',
        'description': 'Standard for business kunder med team-målinger',
        'is_default': 0,
        'types': ['screening', 'profil_fuld', 'gruppe_friktion']
    },
    {
        'name': 'Enterprise Full',
        'description': 'Alle målingstyper aktiveret',
        'is_default': 1,  # Nu default - alle 7 typer
        'types': ['screening', 'profil_fuld', 'profil_situation', 'gruppe_friktion', 'gruppe_leder', 'kapacitet', 'baandbredde']
    }
]


def seed_assessment_types():
    """Seed assessment types og presets til database"""
    with get_db() as conn:
        # Seed assessment types
        for at in INITIAL_ASSESSMENT_TYPES:
            # Check if exists
            existing = conn.execute(
                "SELECT id FROM assessment_types WHERE id = ?", (at['id'],)
            ).fetchone()

            if not existing:
                conn.execute("""
                    INSERT INTO assessment_types
                    (id, name_da, name_en, description_da, description_en,
                     question_count, duration_minutes, is_individual, sequence, icon)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (at['id'], at['name_da'], at['name_en'], at['description_da'],
                      at['description_en'], at['question_count'], at['duration_minutes'],
                      at['is_individual'], at['sequence'], at['icon']))
                print(f"  Tilføjet assessment type: {at['id']}")

        # Seed presets
        for preset in INITIAL_PRESETS:
            # Check if preset exists
            existing = conn.execute(
                "SELECT id FROM assessment_presets WHERE name = ?", (preset['name'],)
            ).fetchone()

            if not existing:
                conn.execute("""
                    INSERT INTO assessment_presets (name, description, is_default)
                    VALUES (?, ?, ?)
                """, (preset['name'], preset['description'], preset['is_default']))

                preset_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                # Add types to preset
                for type_id in preset['types']:
                    conn.execute("""
                        INSERT INTO preset_assessment_types (preset_id, assessment_type_id)
                        VALUES (?, ?)
                    """, (preset_id, type_id))

                print(f"  Tilføjet preset: {preset['name']} med {len(preset['types'])} typer")

    print("Assessment types og presets seedet!")


def get_available_assessments(customer_id: str = None, domain_id: str = None, lang: str = 'da') -> list:
    """
    Hent tilgængelige målingstyper for en given kunde/domæne.

    Prioritet:
    1. Domain-specific config
    2. Customer config
    3. Default preset
    4. All active types

    Args:
        customer_id: Kunde ID (optional)
        domain_id: Domæne ID (optional)
        lang: Sprog for navne ('da' eller 'en')

    Returns:
        List af assessment types med navn i det valgte sprog
    """
    name_col = 'name_da' if lang == 'da' else 'name_en'
    desc_col = 'description_da' if lang == 'da' else 'description_en'

    with get_db() as conn:
        # Check domain first
        if domain_id:
            domain_types = conn.execute(f'''
                SELECT at.id, at.{name_col} as name, at.{desc_col} as description,
                       at.question_count, at.duration_minutes, at.is_individual,
                       at.icon, at.sequence
                FROM assessment_types at
                JOIN domain_assessment_types dat ON at.id = dat.assessment_type_id
                WHERE dat.domain_id = ? AND dat.is_enabled = 1 AND at.is_active = 1
                ORDER BY at.sequence
            ''', (domain_id,)).fetchall()
            if domain_types:
                return [dict(row) for row in domain_types]

        # Check customer
        if customer_id:
            customer_types = conn.execute(f'''
                SELECT at.id,
                       COALESCE(cat.custom_name_da, at.{name_col}) as name,
                       at.{desc_col} as description,
                       at.question_count, at.duration_minutes, at.is_individual,
                       at.icon, at.sequence
                FROM assessment_types at
                JOIN customer_assessment_types cat ON at.id = cat.assessment_type_id
                WHERE cat.customer_id = ? AND cat.is_enabled = 1 AND at.is_active = 1
                ORDER BY at.sequence
            ''', (customer_id,)).fetchall()
            if customer_types:
                return [dict(row) for row in customer_types]

        # Default preset
        default_types = conn.execute(f'''
            SELECT at.id, at.{name_col} as name, at.{desc_col} as description,
                   at.question_count, at.duration_minutes, at.is_individual,
                   at.icon, at.sequence
            FROM assessment_types at
            JOIN preset_assessment_types pat ON at.id = pat.assessment_type_id
            JOIN assessment_presets ap ON pat.preset_id = ap.id
            WHERE ap.is_default = 1 AND at.is_active = 1
            ORDER BY at.sequence
        ''').fetchall()
        if default_types:
            return [dict(row) for row in default_types]

        # Fallback: all active types
        all_types = conn.execute(f'''
            SELECT id, {name_col} as name, {desc_col} as description,
                   question_count, duration_minutes, is_individual, icon, sequence
            FROM assessment_types WHERE is_active = 1
            ORDER BY sequence
        ''').fetchall()
        return [dict(row) for row in all_types]


def get_all_assessment_types(lang: str = 'da') -> list:
    """Hent alle assessment types (til admin UI)"""
    name_col = 'name_da' if lang == 'da' else 'name_en'
    desc_col = 'description_da' if lang == 'da' else 'description_en'

    with get_db() as conn:
        rows = conn.execute(f'''
            SELECT id, name_da, name_en, {name_col} as name,
                   description_da, description_en, {desc_col} as description,
                   question_count, duration_minutes, is_individual, is_active,
                   icon, sequence
            FROM assessment_types
            ORDER BY sequence
        ''').fetchall()
        return [dict(row) for row in rows]


def get_all_presets() -> list:
    """Hent alle presets med deres tilknyttede typer"""
    with get_db() as conn:
        presets = conn.execute('''
            SELECT id, name, description, is_default
            FROM assessment_presets
            ORDER BY is_default DESC, name
        ''').fetchall()

        result = []
        for preset in presets:
            preset_dict = dict(preset)
            # Hent tilknyttede typer
            types = conn.execute('''
                SELECT at.id, at.name_da, at.icon
                FROM assessment_types at
                JOIN preset_assessment_types pat ON at.id = pat.assessment_type_id
                WHERE pat.preset_id = ?
                ORDER BY at.sequence
            ''', (preset['id'],)).fetchall()
            preset_dict['types'] = [dict(t) for t in types]
            result.append(preset_dict)

        return result


def get_customer_assessment_config(customer_id: str) -> dict:
    """Hent kundens assessment type konfiguration"""
    with get_db() as conn:
        # Hent alle typer med kundens enabled status
        types = conn.execute('''
            SELECT at.id, at.name_da, at.name_en, at.icon, at.is_individual,
                   COALESCE(cat.is_enabled, 0) as is_enabled,
                   cat.custom_name_da, cat.custom_name_en
            FROM assessment_types at
            LEFT JOIN customer_assessment_types cat
                ON at.id = cat.assessment_type_id AND cat.customer_id = ?
            WHERE at.is_active = 1
            ORDER BY at.sequence
        ''', (customer_id,)).fetchall()

        return {
            'customer_id': customer_id,
            'types': [dict(t) for t in types],
            'has_custom_config': any(t['is_enabled'] for t in types)
        }


def set_customer_assessment_types(customer_id: str, enabled_types: list) -> bool:
    """Sæt hvilke assessment types der er aktiveret for en kunde"""
    with get_db() as conn:
        # Slet eksisterende config
        conn.execute(
            "DELETE FROM customer_assessment_types WHERE customer_id = ?",
            (customer_id,)
        )

        # Indsæt nye
        for type_id in enabled_types:
            conn.execute("""
                INSERT INTO customer_assessment_types (customer_id, assessment_type_id, is_enabled)
                VALUES (?, ?, 1)
            """, (customer_id, type_id))

    return True


# Initialize database
if __name__ == "__main__":
    print("Initialiserer multi-tenant database...")
    init_multitenant_db()
    print("Seeder assessment types...")
    seed_assessment_types()
    print("Database klar!")

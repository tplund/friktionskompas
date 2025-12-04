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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                role TEXT NOT NULL CHECK(role IN ('admin', 'manager')),
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

        # Opret default admin user hvis ingen users findes
        user_count = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()['cnt']

        if user_count == 0:
            # Hash password: "admin123"
            password_hash = hash_password("admin123")
            admin_id = f"user-{secrets.token_urlsafe(8)}"

            conn.execute("""
                INSERT INTO users (id, username, password_hash, name, email, role, customer_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (admin_id, "admin", password_hash, "System Administrator", "admin@friktionskompas.dk", "admin", None))

            print("Default admin user oprettet:")
            print("   Username: admin")
            print("   Password: admin123")
            print("   ADVARSEL: SKIFT PASSWORD I PRODUKTION!")


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
# USER FUNCTIONS
# ========================================

def create_user(username: str, password: str, name: str, email: str,
                role: str, customer_id: Optional[str] = None) -> str:
    """
    Opret ny user
    role: 'admin' eller 'manager'
    customer_id: None for admin, påkrævet for manager
    """
    if role == 'manager' and not customer_id:
        raise ValueError("Manager skal have en customer_id")

    if role == 'admin' and customer_id:
        raise ValueError("Admin kan ikke have en customer_id (kan se alle)")

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

def get_customer_filter(user_role: str, customer_id: Optional[str]) -> tuple:
    """
    Returner SQL WHERE clause og params for customer filtering

    Returns:
        (where_clause, params)

    Eksempel:
        where, params = get_customer_filter('manager', 'cust-123')
        # Returns: ("customer_id = ?", ['cust-123'])

        sql = f"SELECT * FROM organizational_units WHERE {where}"
        conn.execute(sql, params)
    """
    if customer_id:
        # Hvis customer_id er sat (manager ELLER admin der impersonates), filtrer på den
        return ("ou.customer_id = ?", [customer_id])
    else:
        # Admin uden customer_id kan se alt
        return ("1=1", [])


# Initialize database
if __name__ == "__main__":
    print("Initialiserer multi-tenant database...")
    init_multitenant_db()
    print("Database klar!")

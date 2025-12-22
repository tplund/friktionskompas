"""
Central Database Module for Friktionskompasset
Provides canonical get_db() function and database path resolution
"""
import sqlite3
import os
from contextlib import contextmanager


def _get_db_path():
    """
    Determine database path, respecting environment variable.

    Priority:
    1. DB_PATH environment variable (for tests and custom configs)
    2. Render persistent disk (/var/data) if it exists
    3. Local file (friktionskompas_v3.db)

    Returns:
        str: Path to the SQLite database file
    """
    if 'DB_PATH' in os.environ:
        return os.environ['DB_PATH']

    RENDER_DISK_PATH = "/var/data"
    if os.path.exists(RENDER_DISK_PATH):
        return os.path.join(RENDER_DISK_PATH, "friktionskompas_v3.db")

    return "friktionskompas_v3.db"


# Global DB_PATH constant - can be imported by other modules
DB_PATH = _get_db_path()


@contextmanager
def get_db():
    """
    Context manager for database connection.

    Features:
    - Enables foreign keys (for CASCADE DELETE)
    - Sets WAL mode (for better concurrent access)
    - Provides Row factory (for dict-like access)
    - Auto-commits on success, auto-closes connection
    - Respects DB_PATH environment variable at runtime (for tests)

    Usage:
        with get_db() as conn:
            cursor = conn.execute("SELECT * FROM users")
            rows = cursor.fetchall()

    Yields:
        sqlite3.Connection: Database connection with Row factory
    """
    # Check environment at runtime for test support
    db_path = os.environ.get('DB_PATH', DB_PATH)

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row

    # CRITICAL: Enable foreign keys for CASCADE DELETE to work
    # SQLite has foreign keys DISABLED by default!
    conn.execute("PRAGMA foreign_keys=ON")

    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_db_connection():
    """
    Get a database connection (non-context-manager version).

    NOTE: This is a legacy function for backward compatibility.
    Prefer using get_db() context manager when possible.

    IMPORTANT: Caller is responsible for closing the connection!

    Returns:
        sqlite3.Connection: Database connection with Row factory
    """
    db_path = os.environ.get('DB_PATH', DB_PATH)

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")

    return conn

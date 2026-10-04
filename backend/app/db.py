"""
SQLite database setup - deliberately stdlib-only (no SQLAlchemy/ORM) since
the schema here is small and simple enough not to need one.

On Azure App Service (or any container platform), this file lives inside
the container's writable filesystem. That means it resets on redeploy or
container restart unless you mount persistent storage - acceptable for a
demo, worth upgrading (Postgres, or a mounted volume) if this ever needs
to survive restarts reliably.
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "app_data.db")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_resets (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                label TEXT NOT NULL,
                ai_probability REAL NOT NULL,
                confidence TEXT NOT NULL,
                components TEXT NOT NULL,
                risk_flags TEXT NOT NULL,
                thumbnail TEXT,
                sentences TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        conn.commit()

        # Migration guard: a scans table created before the thumbnail column
        # existed won't get it from CREATE TABLE IF NOT EXISTS above (that
        # only applies to brand-new tables). This adds it to older databases
        # too, and is a no-op (caught, ignored) on databases that already
        # have it.
        for migration in (
            "ALTER TABLE scans ADD COLUMN thumbnail TEXT",
            "ALTER TABLE scans ADD COLUMN sentences TEXT",
        ):
            try:
                conn.execute(migration)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DB_PATH = DATA_DIR / "licenses.db"


def get_db_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DB_PATH


@contextmanager
def get_db():
    path = get_db_path()
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    try:
        ensure_schema(con)
        seed_admin_user_if_needed(con)
        yield con
        con.commit()
    finally:
        con.close()


def ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL COLLATE NOCASE,
            customer_name TEXT NOT NULL,
            instance_uuid TEXT COLLATE NOCASE DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            valid_until TEXT DEFAULT NULL,
            modules TEXT NOT NULL DEFAULT '{}',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_check_at TEXT DEFAULT NULL,
            last_check_ip TEXT DEFAULT NULL,
            last_check_version TEXT DEFAULT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_licenses_key ON licenses(license_key);
        CREATE INDEX IF NOT EXISTS idx_licenses_uuid ON licenses(instance_uuid);

        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            totp_secret TEXT NOT NULL,
            totp_enabled INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login_at TEXT DEFAULT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            license_key TEXT,
            instance_uuid TEXT,
            ip_address TEXT,
            details TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        """
    )


def seed_admin_user_if_needed(con: sqlite3.Connection) -> None:
    """Creates the initial admin user with email and password from environment if no user exists."""
    row = con.execute("SELECT COUNT(*) FROM admin_users").fetchone()
    if row and row[0] > 0:
        return

    from app.security import generate_totp_secret, hash_password

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@modernewolke.de").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "modernewolke2026!").strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    salt, pwd_hash = hash_password(admin_password)
    totp_secret = generate_totp_secret()

    con.execute(
        """
        INSERT INTO admin_users (email, password_hash, salt, totp_secret, totp_enabled, is_active, created_at)
        VALUES (?, ?, ?, ?, 0, 1, ?)
        """,
        (admin_email, pwd_hash, salt, totp_secret, now_iso),
    )

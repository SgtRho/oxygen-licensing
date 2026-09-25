import os
import sqlite3
from contextlib import contextmanager
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

"""SQLite storage for users, sessions, complaints, notifications, map reports, checks and workers."""
import os
import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user'
        CHECK (role IN ('user', 'admin', 'technician', 'technision')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    user_id INTEGER REFERENCES users(id),
    email TEXT
);

CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL,
    ward TEXT,
    category TEXT,
    confidence REAL,
    department TEXT,
    status TEXT DEFAULT 'Submitted',
    worker_id INTEGER REFERENCES workers(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    complaint_id INTEGER,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence REAL,
    department TEXT,
    city TEXT,
    area TEXT,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    worker_id INTEGER REFERENCES workers(id),
    embedding BLOB,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    kind TEXT NOT NULL,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (report_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_checks_report ON checks(report_id);
CREATE INDEX IF NOT EXISTS idx_complaints_user ON complaints(user_id);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_workers_category ON workers(category);
"""


def _columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        # Default DELETE = the normal SQLite mode. WAL is faster but can misbehave in synced folders (OneDrive),
        # so it is only used when you set the environment variable DB_JOURNAL_MODE=WAL.
        mode = os.environ.get("DB_JOURNAL_MODE", "DELETE").upper()
        if mode in ("DELETE", "WAL"):
            try:
                conn.execute(f"PRAGMA journal_mode = {mode}")
            except sqlite3.Error as ex:
                print(f"[db] journal mode not changed: {ex}", flush=True)
        conn.executescript(SCHEMA)

        # Safely update existing databases without deleting existing data.
        if "role" not in _columns(conn, "users"):
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        for table in ("complaints", "reports"):
            if "worker_id" not in _columns(conn, table):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN worker_id INTEGER REFERENCES workers(id)")
        worker_columns = _columns(conn, "workers")
        if "user_id" not in worker_columns:
            conn.execute("ALTER TABLE workers ADD COLUMN user_id INTEGER REFERENCES users(id)")
        if "email" not in worker_columns:
            conn.execute("ALTER TABLE workers ADD COLUMN email TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_complaints_worker ON complaints(worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_worker ON reports(worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workers_user ON workers(user_id)")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
"""On-disk SQLite for the rate limiter window.

WAL mode lets a reader work while a writer holds the lock. busy_timeout makes a
short lock conflict wait instead of failing.
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    id          TEXT PRIMARY KEY,
    tenant      TEXT NOT NULL,
    tokens      INTEGER NOT NULL,
    created_at  REAL NOT NULL,
    settled     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS usage_window ON usage (tenant, created_at);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread is off because the limiter runs the calls in a worker thread.
    # A lock in the limiter keeps the access to one caller at a time.
    connection = sqlite3.connect(
        database, isolation_level=None, timeout=10.0, check_same_thread=False
    )
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.executescript(SCHEMA)
    return connection

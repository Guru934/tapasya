"""Schema migrations. schema.sql creates version 1; later versions live here.

Never drop user data in a migration. Add new versions to MIGRATIONS only.
"""
from __future__ import annotations

MIGRATIONS: dict[int, str] = {
    2: """
    CREATE TABLE IF NOT EXISTS overrides (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        requested_ts INTEGER NOT NULL,
        activate_ts  INTEGER NOT NULL,
        expires_ts   INTEGER NOT NULL,
        cancelled    INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS lock_events (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        ts           INTEGER NOT NULL,
        action       TEXT NOT NULL,
        window_class TEXT,
        title        TEXT,
        dry_run      INTEGER NOT NULL DEFAULT 1,
        reason       TEXT
    );
    """,
}


def current_version(conn) -> int:
    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    return int(row[0]) if row else 1


def migrate(conn) -> int:
    """Apply pending migrations and return the resulting schema version."""
    version = current_version(conn)
    for target in sorted(MIGRATIONS):
        if target > version:
            conn.executescript(MIGRATIONS[target])
            conn.execute(
                "INSERT INTO meta(key,value) VALUES('schema_version',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(target),),
            )
            conn.commit()
            version = target
    return version

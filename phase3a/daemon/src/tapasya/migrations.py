"""Schema migrations. schema.sql creates version 1; everything after lives here.
Never drop user data in a migration. Add new versions to MIGRATIONS only."""
from __future__ import annotations

MIGRATIONS: dict[int, str] = {
    2: """
    CREATE TABLE IF NOT EXISTS overrides (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        requested_ts INTEGER NOT NULL,
        activate_ts  INTEGER NOT NULL,   -- lock is lifted from here...
        expires_ts   INTEGER NOT NULL,   -- ...until here
        cancelled    INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS lock_events (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        ts           INTEGER NOT NULL,
        action       TEXT NOT NULL,      -- warn | close | would_close | error
        window_class TEXT,
        title        TEXT,
        dry_run      INTEGER NOT NULL DEFAULT 1,
        reason       TEXT
    );
    """,
}


def current_version(conn) -> int:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(row[0]) if row else 1
    except Exception:
        return 1


def migrate(conn) -> int:
    """Apply any pending migrations. Safe to call on every start. Returns the version."""
    ver = current_version(conn)
    for v in sorted(MIGRATIONS):
        if v > ver:
            conn.executescript(MIGRATIONS[v])
            conn.execute(
                "INSERT INTO meta(key,value) VALUES('schema_version',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(v),))
            conn.commit()
            ver = v
    return ver

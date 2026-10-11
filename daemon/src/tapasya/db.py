"""SQLite helpers. Keep SQL here so other modules stay simple."""
from __future__ import annotations

import sqlite3
import time
from datetime import date
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(db_path: str) -> sqlite3.Connection:
    p = Path(db_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text())
    return conn


def today() -> str:
    return date.today().isoformat()


def add_sample(conn, app_class, title, domain, counted: bool) -> None:
    conn.execute(
        "INSERT INTO samples(ts, day, app_class, title, domain, counted) VALUES (?,?,?,?,?,?)",
        (int(time.time()), today(), app_class, title, domain, int(counted)),
    )
    conn.commit()


def studied_minutes(conn, day: str, sample_seconds: int) -> float:
    n = conn.execute(
        "SELECT COUNT(*) FROM samples WHERE day=? AND counted=1", (day,)
    ).fetchone()[0]
    return n * sample_seconds / 60.0


def set_goal(conn, day: str, minutes: int) -> None:
    conn.execute(
        "INSERT INTO goals(day, target_minutes) VALUES (?,?) "
        "ON CONFLICT(day) DO UPDATE SET target_minutes=excluded.target_minutes",
        (day, minutes),
    )
    conn.commit()


def get_goal(conn, day: str, default: int) -> int:
    row = conn.execute("SELECT target_minutes FROM goals WHERE day=?", (day,)).fetchone()
    return row[0] if row else default

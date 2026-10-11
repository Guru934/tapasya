"""SQL for lock mode (overrides + event log). Kept separate from db.py on purpose."""
from __future__ import annotations


def request_override(conn, now: int, delay_min: int, duration_min: int) -> dict:
    activate = now + delay_min * 60
    expires = activate + duration_min * 60
    conn.execute("INSERT INTO overrides(requested_ts, activate_ts, expires_ts) VALUES (?,?,?)",
                 (now, activate, expires))
    conn.commit()
    return {"activate_ts": activate, "expires_ts": expires}


def cancel_overrides(conn, now: int) -> int:
    cur = conn.execute("UPDATE overrides SET cancelled=1 WHERE cancelled=0 AND expires_ts>?", (now,))
    conn.commit()
    return cur.rowcount


def override_state(conn, now: int) -> dict | None:
    """Return {'state': 'active'|'pending', ...} or None. Active wins over pending."""
    rows = conn.execute(
        "SELECT activate_ts, expires_ts FROM overrides WHERE cancelled=0 AND expires_ts>? "
        "ORDER BY activate_ts", (now,)).fetchall()
    best = None
    for a, e in rows:
        if a <= now:
            return {"state": "active", "activate_ts": a, "expires_ts": e}
        best = best or {"state": "pending", "activate_ts": a, "expires_ts": e}
    return best


def override_active(conn, now: int) -> bool:
    s = override_state(conn, now)
    return bool(s and s["state"] == "active")


def log_event(conn, now: int, action: str, window_class: str = "", title: str = "",
              dry_run: bool = True, reason: str = "") -> None:
    conn.execute(
        "INSERT INTO lock_events(ts, action, window_class, title, dry_run, reason) VALUES (?,?,?,?,?,?)",
        (now, action, window_class, (title or "")[:200], int(dry_run), reason))
    conn.commit()


def recent_events(conn, limit: int = 20) -> list:
    return conn.execute(
        "SELECT ts, action, window_class, title, dry_run, reason FROM lock_events "
        "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

import time
from datetime import datetime

import pytest

from tapasya import db, lock, lock_store, migrations


def mkcfg(tmp_path, **lockopts):
    return {
        "goal": {"daily_minutes": 60},
        "tracking": {"sample_seconds": 5, "study_window_classes": ["brave-browser"],
                     "always_allowed_classes": ["kitty"]},
        "storage": {"db_path": str(tmp_path / "t.db")},
        "lock": {"enabled": True, "dry_run": False, "startup_grace_seconds": 0, "warn_seconds": 30,
                 "check_seconds": 15, "active_from": "00:00", "active_until": "23:59", **lockopts},
    }


def engine(cfg, clients, closed, notes):
    p = cfg["storage"]["db_path"]
    return lock.LockEngine(cfg, lambda: db.connect(p), clients_fn=lambda: clients(),
                           close_fn=closed.append, notify_fn=notes.append, mono=lambda: 0)


NOON = datetime(2026, 10, 12, 12, 0)
WIN = [{"class": "discord", "address": "0x1", "title": "chat", "mapped": True},
       {"class": "kitty", "address": "0x2", "title": "term", "mapped": True},
       {"class": "Brave-browser", "address": "0x3", "title": "b", "mapped": True},
       {"class": "", "address": "0x4", "mapped": True},
       {"class": "pinentry", "address": "0x5", "mapped": True}]


def test_decide_lock_matrix():
    d = lambda **k: lock.decide_lock(**{**dict(enabled=True, in_window=True, override_active=False,
                                              studied_min=10, goal_min=60), **k})
    assert d() == (True, "goal-unmet")
    assert d(enabled=False)[0] is False
    assert d(in_window=False)[0] is False
    assert d(override_active=True)[0] is False
    assert d(studied_min=60)[0] is False
    assert d(goal_min=0)[0] is False


def test_active_window():
    assert lock.in_active_window(datetime(2026, 1, 1, 12), "06:00", "23:00")
    assert not lock.in_active_window(datetime(2026, 1, 1, 23, 30), "06:00", "23:00")
    assert lock.in_active_window(datetime(2026, 1, 1, 1), "22:00", "05:00")   # overnight
    assert lock.in_active_window(datetime(2026, 1, 1, 12), "bad", "x") is False  # bad config fails open


def test_find_offenders():
    off = lock.find_offenders(WIN, {"kitty", "brave-browser"})
    assert [o["class"] for o in off] == ["discord"]   # allowed, empty class, safety list skipped


def test_warn_then_close(tmp_path):
    cfg, closed, notes = mkcfg(tmp_path), [], []
    e = engine(cfg, lambda: WIN, closed, notes)
    assert e.step(1000, 0, NOON) == "locked"          # first sight: warn only
    assert closed == [] and len(notes) == 1
    e.step(1010, 10, NOON)
    assert closed == []                                # still inside warn period
    e.step(1040, 40, NOON)
    assert closed == ["0x1"]                           # closed after warn_seconds, only discord


def test_dry_run_never_closes(tmp_path):
    cfg, closed, notes = mkcfg(tmp_path, dry_run=True), [], []
    e = engine(cfg, lambda: WIN, closed, notes)
    e.step(1000, 0, NOON); e.step(1040, 40, NOON); e.step(1080, 80, NOON)
    assert closed == [] and notes == []
    conn = db.connect(cfg["storage"]["db_path"])
    actions = [r[1] for r in lock_store.recent_events(conn, 10)]
    assert actions.count("would_close") == 1 and "warn" in actions


def test_goal_met_or_override_means_no_action(tmp_path):
    cfg, closed, notes = mkcfg(tmp_path), [], []
    e = engine(cfg, lambda: WIN, closed, notes)
    conn = db.connect(cfg["storage"]["db_path"])
    for _ in range(12 * 60):                           # 60 minutes of counted samples
        conn.execute("INSERT INTO samples(ts,day,app_class,title,domain,counted) VALUES (?,?,?,?,?,1)",
                     (1, db.today(), "brave-browser", "", None))
    conn.commit()
    assert e.step(1000, 0, NOON) == "goal-met"
    conn.execute("DELETE FROM samples"); conn.commit()
    lock_store.request_override(conn, 1000 - 700, 10, 60)   # activated 100s ago
    assert e.step(1000, 0, NOON) == "override-active"
    assert closed == []


def test_startup_grace_and_disabled(tmp_path):
    cfg = mkcfg(tmp_path, startup_grace_seconds=120)
    e = engine(cfg, lambda: WIN, [], [])
    assert e.step(1, 5, NOON) == "startup-grace"
    cfg2 = mkcfg(tmp_path, enabled=False)
    assert engine(cfg2, lambda: WIN, [], []).step(1, 999, NOON) == "disabled"


def test_fail_open_on_errors(tmp_path):
    cfg, closed = mkcfg(tmp_path), []
    def boom():
        raise RuntimeError("hyprctl exploded")
    e = engine(cfg, boom, closed, [])
    assert e.safe_step() == "error" and closed == []   # exception swallowed, nothing closed
    e2 = engine(cfg, lambda: None, closed, [])
    assert e2.step(1000, 0, NOON) == "no-clients"


def test_closes_capped_per_cycle(tmp_path):
    cfg, closed = mkcfg(tmp_path, max_closes_per_cycle=2), []
    many = [{"class": f"app{i}", "address": f"0x{i+10:x}", "mapped": True} for i in range(5)]
    e = engine(cfg, lambda: many, closed, [])
    e.step(1000, 0, NOON); e.step(1040, 40, NOON)
    assert len(closed) == 2


def test_override_lifecycle(tmp_path):
    conn = db.connect(str(tmp_path / "o.db"))
    assert lock_store.override_state(conn, 1000) is None
    lock_store.request_override(conn, 1000, 10, 60)
    assert lock_store.override_state(conn, 1100)["state"] == "pending"
    assert not lock_store.override_active(conn, 1100)
    assert lock_store.override_active(conn, 1000 + 601)
    assert lock_store.override_state(conn, 1000 + 601 + 3601) is None   # expired
    assert lock_store.cancel_overrides(conn, 1700) == 1
    assert not lock_store.override_active(conn, 1700)


def test_migration_idempotent(tmp_path):
    conn = db.connect(str(tmp_path / "m.db"))
    assert migrations.migrate(conn) == 2
    assert migrations.migrate(conn) == 2
    assert conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "2"
    conn.execute("SELECT * FROM overrides"); conn.execute("SELECT * FROM lock_events")

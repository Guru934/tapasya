from datetime import datetime

from tapasya import db, lock, lock_store, migrations


def mkcfg(tmp_path, **lockopts):
    return {
        "goal": {"daily_minutes": 60},
        "tracking": {
            "sample_seconds": 5,
            "study_window_classes": ["brave-browser"],
            "always_allowed_classes": ["kitty"],
        },
        "storage": {"db_path": str(tmp_path / "t.db")},
        "lock": {
            "enabled": True,
            "dry_run": False,
            "startup_grace_seconds": 0,
            "warn_seconds": 30,
            "check_seconds": 15,
            "active_from": "00:00",
            "active_until": "23:59",
            **lockopts,
        },
    }


def engine(cfg, clients, closed, notes):
    path = cfg["storage"]["db_path"]
    return lock.LockEngine(
        cfg,
        lambda: db.connect(path),
        clients_fn=lambda: clients(),
        close_fn=closed.append,
        notify_fn=notes.append,
        mono=lambda: 0,
    )


NOON = datetime(2026, 10, 12, 12, 0)
WINDOWS = [
    {"class": "discord", "address": "0x1", "title": "chat", "mapped": True},
    {"class": "kitty", "address": "0x2", "title": "term", "mapped": True},
    {"class": "Brave-browser", "address": "0x3", "title": "browser", "mapped": True},
    {"class": "", "address": "0x4", "mapped": True},
    {"class": "pinentry", "address": "0x5", "mapped": True},
]


def test_lock_defaults_to_disabled_dry_run():
    config = lock.load_lock_config({"tracking": {}})
    assert config.enabled is False
    assert config.dry_run is True


def test_decide_lock_matrix():
    decide = lambda **kwargs: lock.decide_lock(
        **{
            **dict(enabled=True, in_window=True, override_active=False, studied_min=10, goal_min=60),
            **kwargs,
        }
    )
    assert decide() == (True, "goal-unmet")
    assert decide(enabled=False)[0] is False
    assert decide(in_window=False)[0] is False
    assert decide(override_active=True)[0] is False
    assert decide(studied_min=60)[0] is False
    assert decide(goal_min=0)[0] is False


def test_active_window():
    assert lock.in_active_window(datetime(2026, 1, 1, 12), "06:00", "23:00")
    assert not lock.in_active_window(datetime(2026, 1, 1, 23, 30), "06:00", "23:00")
    assert lock.in_active_window(datetime(2026, 1, 1, 1), "22:00", "05:00")
    assert not lock.in_active_window(datetime(2026, 1, 1, 12), "bad", "x")


def test_find_offenders():
    offenders = lock.find_offenders(WINDOWS, {"kitty", "brave-browser"})
    assert [window["class"] for window in offenders] == ["discord"]


def test_find_offenders_never_returns_a_terminal():
    terminal = [{"class": "Alacritty", "address": "0x99", "mapped": True}]
    assert lock.find_offenders(terminal, set()) == []


def test_find_offenders_never_returns_auth_prompt_titles():
    prompts = [
        {"class": "unknown-dialog", "address": "0xa1", "title": "Authentication Required"},
        {"class": "unknown-dialog", "address": "0xa2", "title": "Enter your password"},
    ]
    assert lock.find_offenders(prompts, set()) == []


def test_find_offenders_skips_unmapped_windows():
    """Windows with missing or falsy 'mapped' field are skipped."""
    windows = [
        {"class": "discord", "address": "0x1", "title": "chat", "mapped": True},
        {"class": "discord", "address": "0x2", "title": "chat", "mapped": False},
        {"class": "discord", "address": "0x3", "title": "chat"},  # missing mapped
        {"class": "discord", "address": "0x4", "title": "chat", "mapped": None},
    ]
    offenders = lock.find_offenders(windows, set())
    # Only the first window (mapped: True) should be an offender
    assert [w["address"] for w in offenders] == ["0x1"]


def test_warn_then_close(tmp_path):
    cfg, closed, notes = mkcfg(tmp_path), [], []
    lock_engine = engine(cfg, lambda: WINDOWS, closed, notes)
    assert lock_engine.step(1000, 0, NOON) == "locked"
    assert closed == [] and len(notes) == 1
    lock_engine.step(1010, 10, NOON)
    assert closed == []
    lock_engine.step(1040, 40, NOON)
    assert closed == ["0x1"]


def test_failed_close_is_logged_as_error(tmp_path):
    cfg = mkcfg(tmp_path)
    lock_engine = lock.LockEngine(
        cfg,
        lambda: db.connect(cfg["storage"]["db_path"]),
        clients_fn=lambda: WINDOWS,
        close_fn=lambda _address: False,
        notify_fn=lambda _message: None,
        mono=lambda: 0,
    )
    lock_engine.step(1000, 0, NOON)
    lock_engine.step(1040, 40, NOON)
    conn = db.connect(cfg["storage"]["db_path"])
    events = lock_store.recent_events(conn, 10)
    assert events[0][1] == "error"
    assert events[0][5] == "close-failed"


def test_dry_run_never_closes(tmp_path):
    cfg, closed, notes = mkcfg(tmp_path, dry_run=True), [], []
    lock_engine = engine(cfg, lambda: WINDOWS, closed, notes)
    lock_engine.step(1000, 0, NOON)
    lock_engine.step(1040, 40, NOON)
    lock_engine.step(1080, 80, NOON)
    assert closed == [] and notes == []
    conn = db.connect(cfg["storage"]["db_path"])
    actions = [row[1] for row in lock_store.recent_events(conn, 10)]
    assert actions.count("would_close") == 1 and "warn" in actions


def test_goal_met_or_override_means_no_action(tmp_path):
    cfg, closed, notes = mkcfg(tmp_path), [], []
    lock_engine = engine(cfg, lambda: WINDOWS, closed, notes)
    conn = db.connect(cfg["storage"]["db_path"])
    for _ in range(12 * 60):
        conn.execute(
            "INSERT INTO samples(ts,day,app_class,title,domain,counted) VALUES (?,?,?,?,?,1)",
            (1, db.today(), "brave-browser", "", None),
        )
    conn.commit()
    assert lock_engine.step(1000, 0, NOON) == "goal-met"
    conn.execute("DELETE FROM samples")
    conn.commit()
    lock_store.request_override(conn, 300, 10, 60)
    assert lock_engine.step(1000, 0, NOON) == "override-active"
    assert closed == []


def test_startup_grace_and_disabled(tmp_path):
    cfg = mkcfg(tmp_path, startup_grace_seconds=120)
    assert engine(cfg, lambda: WINDOWS, [], []).step(1, 5, NOON) == "startup-grace"
    assert engine(mkcfg(tmp_path, enabled=False), lambda: WINDOWS, [], []).step(1, 999, NOON) == "disabled"


def test_fail_open_on_errors(tmp_path):
    cfg, closed = mkcfg(tmp_path), []

    def fail_clients():
        raise RuntimeError("hyprctl exploded")

    assert engine(cfg, fail_clients, closed, []).safe_step() == "error"
    assert closed == []
    assert engine(cfg, lambda: None, closed, []).step(1000, 0, NOON) == "no-clients"


def test_closes_capped_per_cycle(tmp_path):
    cfg, closed = mkcfg(tmp_path, max_closes_per_cycle=2), []
    windows = [{"class": f"app{i}", "address": f"0x{i + 10:x}", "mapped": True} for i in range(5)]
    lock_engine = engine(cfg, lambda: windows, closed, [])
    lock_engine.step(1000, 0, NOON)
    lock_engine.step(1040, 40, NOON)
    assert len(closed) == 2


def test_override_lifecycle(tmp_path):
    conn = db.connect(str(tmp_path / "o.db"))
    assert lock_store.override_state(conn, 1000) is None
    lock_store.request_override(conn, 1000, 10, 60)
    assert lock_store.override_state(conn, 1100)["state"] == "pending"
    assert not lock_store.override_active(conn, 1100)
    assert lock_store.override_active(conn, 1601)
    assert lock_store.override_state(conn, 5202) is None
    assert lock_store.cancel_overrides(conn, 1700) == 1
    assert not lock_store.override_active(conn, 1700)


def test_migration_idempotent(tmp_path):
    conn = db.connect(str(tmp_path / "m.db"))
    assert migrations.migrate(conn) == 2
    assert migrations.migrate(conn) == 2
    assert conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "2"
    conn.execute("SELECT * FROM overrides")
    conn.execute("SELECT * FROM lock_events")

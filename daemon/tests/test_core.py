import sqlite3

from tapasya import db
from tapasya.activity import ActivityMonitor, is_counted


def make_conn(tmp_path):
    return db.connect(str(tmp_path / "t.db"))


def test_minutes_counted_from_samples(tmp_path):
    conn = make_conn(tmp_path)
    for _ in range(12):                      # 12 counted samples x 5s = 1 minute
        db.add_sample(conn, "brave-browser", "x", None, True)
    for _ in range(30):                      # not counted
        db.add_sample(conn, "discord", "x", None, False)
    assert db.studied_minutes(conn, db.today(), 5) == 1.0


def test_goal_default_and_override(tmp_path):
    conn = make_conn(tmp_path)
    assert db.get_goal(conn, db.today(), 120) == 120
    db.set_goal(conn, db.today(), 90)
    assert db.get_goal(conn, db.today(), 120) == 90
    db.set_goal(conn, db.today(), 150)       # update, not duplicate
    assert db.get_goal(conn, db.today(), 120) == 150


def test_is_counted_rules():
    study = {"brave-browser"}
    assert is_counted("brave-browser", study, idle=False)
    assert not is_counted("brave-browser", study, idle=True)
    assert not is_counted("discord", study, idle=False)


def test_idle_after_no_change():
    m = ActivityMonitor(idle_seconds=60)
    assert m.update((1, 1), "brave", "a", now=0) is False
    assert m.update((1, 1), "brave", "a", now=30) is False
    assert m.update((1, 1), "brave", "a", now=60) is True


def test_activity_resets_idle():
    m = ActivityMonitor(idle_seconds=60)
    m.update((1, 1), "brave", "a", now=0)
    assert m.update((1, 1), "brave", "a", now=70) is True
    assert m.update((5, 5), "brave", "a", now=75) is False   # mouse moved
    assert m.update((5, 5), "brave", "b", now=80) is False   # title changed

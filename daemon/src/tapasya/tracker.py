"""Tracker: poll the focused Hyprland window and count study time.

A sample counts when: a study window is focused, the user is not idle, and (for browsers)
the active tab passes the site rules reported by the Brave extension.
If the extension is not running: falls back to "Brave focused = counts" unless
tracking.require_extension = true.
"""
from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import sys
import threading
import time

from . import api, db, rules
from .activity import ActivityMonitor, is_counted


def ensure_hypr_env() -> None:
    """Make hyprctl work from systemd/other shells by locating the running Hyprland instance."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    dirs = sorted(glob.glob(f"{runtime}/hypr/*/"), key=os.path.getmtime, reverse=True)
    if dirs:
        os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = os.path.basename(dirs[0].rstrip("/"))


def _hyprctl_json(*args: str) -> dict:
    try:
        out = subprocess.run(["hyprctl", *args, "-j"], capture_output=True, text=True, timeout=2)
        return json.loads(out.stdout or "{}")
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        return {}


def active_window() -> dict:
    data = _hyprctl_json("activewindow")
    return {"class": data.get("class", ""), "title": data.get("title", "")}


def cursor_pos() -> tuple | None:
    data = _hyprctl_json("cursorpos")
    if "x" in data and "y" in data:
        return (data["x"], data["y"])
    return None


def make_stop_handler(stop: threading.Event):
    """Return a SIGTERM/SIGINT handler that stops the tracker loop."""
    def handler(_signum, _frame) -> None:
        stop.set()
    return handler


def decide(cls: str, idle: bool, tab: dict | None, cfg: dict) -> tuple[bool, str | None]:
    """Pure decision function (testable). Returns (counted, domain)."""
    t = cfg["tracking"]
    study_classes = set(t["study_window_classes"])
    browsers = set(t.get("browser_classes", ["brave-browser", "Brave-browser"]))
    idle = idle and not bool(tab and tab.get("audible"))
    counted = is_counted(cls, study_classes, idle)
    if not counted or cls not in browsers:
        return counted, None
    if tab is None:
        return (not t.get("require_extension", False)), None
    ok, _reason = rules.classify(tab["domain"], tab["title"], tab["shorts"], cfg.get("study_sites", {}))
    return ok, tab["domain"] or None


def run(cfg: dict) -> None:
    ensure_hypr_env()
    db_path = cfg["storage"]["db_path"]
    conn = db.connect(db_path)
    step = cfg["tracking"]["sample_seconds"]
    monitor = ActivityMonitor(cfg["tracking"]["idle_seconds"])
    state = api.TabState(cfg["tracking"].get("tab_stale_seconds", 90))
    stop = threading.Event()
    signals = (signal.SIGTERM, signal.SIGINT)
    previous_handlers = {signum: signal.getsignal(signum) for signum in signals}
    for signum in signals:
        signal.signal(signum, make_stop_handler(stop))

    def status() -> dict:
        c = db.connect(db_path)  # own connection: this runs in the API thread
        try:
            day = db.today()
            return {"day": day,
                    "goal_minutes": db.get_goal(c, day, cfg["goal"]["daily_minutes"]),
                    "studied_minutes": round(db.studied_minutes(c, day, step), 1)}
        finally:
            c.close()

    host, port = cfg.get("api", {}).get("host", "127.0.0.1"), cfg.get("api", {}).get("port", 8765)
    server = None
    try:
        server = api.make_server(state, host, port, status)
        api.start_in_thread(server)
        print(f"[tapasya] API on http://{host}:{port}")
    except OSError as e:
        print(f"[tapasya] WARNING: API NOT STARTED ({e}). Brave extension will NOT work.", file=sys.stderr, flush=True)

    try:
        print(f"[tapasya] tracking every {step}s, idle after {cfg['tracking']['idle_seconds']}s.")
        while not stop.is_set():
            win = active_window()
            cls, title = win.get("class", ""), win.get("title", "")
            idle = monitor.update(cursor_pos(), cls, title, time.monotonic())
            counted, domain = decide(cls, idle, state.current(), cfg)
            db.add_sample(conn, cls, title, domain, counted)
            stop.wait(step)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        conn.close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

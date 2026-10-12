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


_HYPR_DISCOVERY_INTERVAL = 30.0  # seconds between Hyprland re-discovery attempts


def ensure_hypr_env(force: bool = False) -> bool:
    """Make hyprctl work by locating the running Hyprland instance.

    Returns True if a valid instance signature was found (or already set),
    False if Hyprland does not appear to be running.
    """
    if not force and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    dirs = sorted(glob.glob(f"{runtime}/hypr/*/"), key=os.path.getmtime, reverse=True)
    if dirs:
        os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = os.path.basename(dirs[0].rstrip("/"))
        return True
    # Clear any stale signature so we don't retry a dead instance
    os.environ.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
    return False


def _hyprctl_json(*args: str) -> tuple[dict, str | None]:
    """Run hyprctl and return (parsed_json, error_message).

    error_message is None on success, or a description of the failure.
    """
    try:
        out = subprocess.run(
            ["hyprctl", *args, "-j"], capture_output=True, text=True, timeout=2
        )
        if out.returncode != 0:
            err = (out.stderr or out.stdout or "hyprctl failed").strip()
            return {}, f"hyprctl exit {out.returncode}: {err}"
        return json.loads(out.stdout or "{}"), None
    except FileNotFoundError:
        return {}, "hyprctl not found in PATH"
    except subprocess.TimeoutExpired:
        return {}, "hyprctl timeout"
    except json.JSONDecodeError as e:
        return {}, f"hyprctl returned invalid JSON: {e}"
    except subprocess.SubprocessError as e:
        return {}, f"hyprctl subprocess error: {e}"


def active_window() -> tuple[dict, str | None]:
    data, err = _hyprctl_json("activewindow")
    if err:
        return {}, err
    return {"class": data.get("class", ""), "title": data.get("title", "")}, None


def cursor_pos() -> tuple[tuple[int, int] | None, str | None]:
    data, err = _hyprctl_json("cursorpos")
    if err:
        return None, err
    if "x" in data and "y" in data:
        return (data["x"], data["y"]), None
    return None, "cursorpos missing x/y"


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
        return (not t.get("require_extension", True)), None
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
    lock_thread = None
    try:
        server = api.make_server(state, host, port, status)
        api.start_in_thread(server)
        print(f"[tapasya] API on http://{host}:{port}")
    except OSError as e:
        print(f"[tapasya] WARNING: API NOT STARTED ({e}). Brave extension will NOT work.", file=sys.stderr, flush=True)

    try:
        from . import lock
        lock_thread = lock.start_engine(cfg, stop)
    except Exception as e:
        print(f"[tapasya] WARNING: lock engine not started (failing open): {e}", file=sys.stderr, flush=True)

    last_hypr_error_log = 0.0
    last_discovery_attempt = 0.0

    try:
        print(f"[tapasya] tracking every {step}s, idle after {cfg['tracking']['idle_seconds']}s.")
        while not stop.is_set():
            now = time.monotonic()
            win, win_err = active_window()
            cls, title = win.get("class", ""), win.get("title", "")

            # If window detection failed, try to re-discover Hyprland
            if win_err or not cls:
                if now - last_discovery_attempt >= _HYPR_DISCOVERY_INTERVAL:
                    if ensure_hypr_env(force=True):
                        print("[tapasya] Hyprland instance re-discovered", flush=True)
                    else:
                        print("[tapasya] WARNING: Hyprland not found; will retry", file=sys.stderr, flush=True)
                    last_discovery_attempt = now
                # Log the error at most once per 60 seconds to avoid journal spam
                if win_err and now - last_hypr_error_log >= 60.0:
                    print(f"[tapasya] hyprctl error: {win_err}", file=sys.stderr, flush=True)
                    last_hypr_error_log = now
                # Don't record a sample when we can't determine the window
                stop.wait(step)
                continue

            cursor, cursor_err = cursor_pos()
            idle = monitor.update(cursor, cls, title, now)
            counted, domain = decide(cls, idle, state.current(), cfg)
            db.add_sample(conn, cls, title, domain, counted)
            stop.wait(step)
    finally:
        stop.set()
        if lock_thread is not None:
            lock_thread.join(timeout=15)
        if server is not None:
            server.shutdown()
            server.server_close()
        conn.close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

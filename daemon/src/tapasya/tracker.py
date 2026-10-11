"""Tracker: poll the focused Hyprland window and count study time.

Counts a sample only when a study window is focused AND the user is not idle.
TODO (Phase 2): read current Brave domain/title from the extension and apply study_sites rules.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import time

from . import db
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
    """Return {'class': str, 'title': str} for the focused window ({} if none)."""
    data = _hyprctl_json("activewindow")
    return {"class": data.get("class", ""), "title": data.get("title", "")}


def cursor_pos() -> tuple | None:
    data = _hyprctl_json("cursorpos")
    if "x" in data and "y" in data:
        return (data["x"], data["y"])
    return None


def run(cfg: dict) -> None:
    ensure_hypr_env()
    conn = db.connect(cfg["storage"]["db_path"])
    step = cfg["tracking"]["sample_seconds"]
    study_classes = set(cfg["tracking"]["study_window_classes"])
    monitor = ActivityMonitor(cfg["tracking"]["idle_seconds"])
    print(f"[tapasya] tracking every {step}s, idle after {cfg['tracking']['idle_seconds']}s. Ctrl+C to stop.")
    while True:
        win = active_window()
        cls, title = win.get("class", ""), win.get("title", "")
        idle = monitor.update(cursor_pos(), cls, title, time.monotonic())
        db.add_sample(conn, cls, title, None, is_counted(cls, study_classes, idle))
        time.sleep(step)

"""Lock engine (Phase 3a). SAFE BY DEFAULT: disabled, and dry-run when enabled.

Rules (see docs/PRIVACY.md #9): fail open. Any error, missing data, or unknown state means
NOTHING is closed. Windows get a warning first; closing only happens after `warn_seconds`.
"""
from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from . import db, lock_store

# Never closed, whatever the config says (auth prompts, the shell itself).
SAFETY_ALLOW = {"quickshell", "caelestia-shell", "pinentry", "polkit-gnome-authentication-agent-1",
                "org.freedesktop.impl.portal.desktop.gtk", "xdg-desktop-portal-gtk"}


@dataclass
class LockConfig:
    enabled: bool = False
    dry_run: bool = True
    check_seconds: int = 15
    warn_seconds: int = 45
    startup_grace_seconds: int = 120
    max_closes_per_cycle: int = 2
    active_from: str = "06:00"
    active_until: str = "23:00"
    override_delay_minutes: int = 10
    override_minutes: int = 60
    extra_allowed_classes: list = field(default_factory=list)


def load_lock_config(cfg: dict) -> LockConfig:
    raw = cfg.get("lock", {}) or {}
    lc = LockConfig()
    for k in lc.__dataclass_fields__:
        if k in raw:
            setattr(lc, k, raw[k])
    lc.check_seconds = max(5, int(lc.check_seconds))
    lc.warn_seconds = max(10, int(lc.warn_seconds))
    lc.max_closes_per_cycle = max(1, int(lc.max_closes_per_cycle))
    return lc


def _parse_hhmm(s: str):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def in_active_window(dt: datetime, active_from: str, active_until: str) -> bool:
    try:
        a, b, now = _parse_hhmm(active_from), _parse_hhmm(active_until), dt.hour * 60 + dt.minute
    except (ValueError, TypeError):
        return False  # bad config -> fail open (no lock)
    return (a <= now < b) if a <= b else (now >= a or now < b)


def decide_lock(*, enabled: bool, in_window: bool, override_active: bool,
                studied_min: float, goal_min: float) -> tuple[bool, str]:
    if not enabled:
        return False, "disabled"
    if not in_window:
        return False, "outside-window"
    if override_active:
        return False, "override-active"
    if goal_min <= 0:
        return False, "no-goal"
    if studied_min >= goal_min:
        return False, "goal-met"
    return True, "goal-unmet"


def find_offenders(clients: list, allowed: set) -> list:
    allowed_l = {a.lower() for a in allowed} | {a.lower() for a in SAFETY_ALLOW}
    out = []
    for c in clients or []:
        cls = (c.get("class") or "")
        if not cls or not c.get("address") or c.get("mapped") is False:
            continue
        if cls.lower() in allowed_l:
            continue
        out.append(c)
    return out


# ---- Hyprland helpers (best effort, never raise) ----
def hypr_clients():
    try:
        import json
        r = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=3)
        data = json.loads(r.stdout or "null")
        return data if isinstance(data, list) else None
    except Exception:
        return None


def hypr_close(address: str) -> None:
    if re.fullmatch(r"0x[0-9a-fA-F]+", address or ""):
        subprocess.run(["hyprctl", "dispatch", "closewindow", f"address:{address}"],
                       capture_output=True, timeout=3)


def notify(msg: str) -> None:
    try:
        subprocess.run(["notify-send", "-u", "critical", "Tapasya", msg], timeout=3)
    except Exception:
        pass


class LockEngine:
    def __init__(self, cfg: dict, conn_factory, clients_fn=hypr_clients, close_fn=hypr_close,
                 notify_fn=notify, mono=time.monotonic):
        self.cfg, self.lc = cfg, load_lock_config(cfg)
        self.conn_factory, self.clients_fn = conn_factory, clients_fn
        self.close_fn, self.notify_fn = close_fn, notify_fn
        t = cfg["tracking"]
        self.allowed = (set(t.get("always_allowed_classes", [])) | set(t.get("study_window_classes", []))
                        | set(self.lc.extra_allowed_classes))
        self.sample_seconds = t["sample_seconds"]
        self._started = mono()
        self._first_seen: dict[str, float] = {}
        self._dry_done: set[str] = set()

    def step(self, wall: float, mono: float, dt: datetime) -> str:
        lc = self.lc
        if not lc.enabled:
            return "disabled"
        if mono - self._started < lc.startup_grace_seconds:
            return "startup-grace"
        conn = self.conn_factory()
        try:
            day = db.today()
            goal = db.get_goal(conn, day, self.cfg["goal"]["daily_minutes"])
            studied = db.studied_minutes(conn, day, self.sample_seconds)
            locked, reason = decide_lock(
                enabled=True, in_window=in_active_window(dt, lc.active_from, lc.active_until),
                override_active=lock_store.override_active(conn, int(wall)),
                studied_min=studied, goal_min=goal)
            if not locked:
                self._first_seen.clear(); self._dry_done.clear()
                return reason
            clients = self.clients_fn()
            if clients is None:
                return "no-clients"
            offenders = find_offenders(clients, self.allowed)
            live = {o["address"] for o in offenders}
            for a in list(self._first_seen):
                if a not in live:
                    del self._first_seen[a]
            self._dry_done &= live
            closed = 0
            for o in offenders:
                addr, cls, title = o["address"], o.get("class", ""), o.get("title", "")
                if addr not in self._first_seen:
                    self._first_seen[addr] = mono
                    lock_store.log_event(conn, int(wall), "warn", cls, title, lc.dry_run, "goal-unmet")
                    if not lc.dry_run:
                        self.notify_fn(f"Study first! '{cls}' closes in {lc.warn_seconds}s "
                                       f"({studied:.0f}/{goal} min done)")
                    continue
                if mono - self._first_seen[addr] < lc.warn_seconds or closed >= lc.max_closes_per_cycle:
                    continue
                if lc.dry_run:
                    if addr not in self._dry_done:
                        lock_store.log_event(conn, int(wall), "would_close", cls, title, True, "goal-unmet")
                        self._dry_done.add(addr)
                else:
                    lock_store.log_event(conn, int(wall), "close", cls, title, False, "goal-unmet")
                    self.close_fn(addr)
                    closed += 1
            return "locked"
        finally:
            conn.close()

    def safe_step(self) -> str:
        """Fail open: any exception means 'do nothing this cycle'."""
        try:
            return self.step(time.time(), time.monotonic(), datetime.now())
        except Exception as e:  # noqa: BLE001
            print(f"[tapasya] lock error (failing open): {e!r}", file=sys.stderr, flush=True)
            return "error"

    def run(self, stop: threading.Event) -> None:
        while not stop.wait(self.lc.check_seconds):
            self.safe_step()


def start_engine(cfg: dict, stop: threading.Event):
    """Start the lock engine thread. Returns the thread, or None if lock is disabled."""
    lc = load_lock_config(cfg)
    if not lc.enabled:
        print("[tapasya] lock: disabled", flush=True)
        return None
    db_path = cfg["storage"]["db_path"]
    engine = LockEngine(cfg, lambda: db.connect(db_path))
    t = threading.Thread(target=engine.run, args=(stop,), daemon=True, name="tapasya-lock")
    t.start()
    print(f"[tapasya] lock: ON ({'DRY-RUN' if lc.dry_run else 'REAL: windows will be closed'})", flush=True)
    return t

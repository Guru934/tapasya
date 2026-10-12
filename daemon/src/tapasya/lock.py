"""Phase 3a lock engine. Disabled by default and dry-run when enabled."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from . import db, lock_store

# Keep the shell, authentication prompts, and common terminals available for escape commands.
SAFETY_ALLOW = {
    "quickshell",
    "caelestia-shell",
    "pinentry",
    "polkit-gnome-authentication-agent-1",
    "org.freedesktop.impl.portal.desktop.gtk",
    "xdg-desktop-portal-gtk",
    "alacritty",
    "foot",
    "footclient",
    "gnome-terminal",
    "gnome-terminal-server",
    "kitty",
    "konsole",
    "wezterm",
    "org.wezfurlong.wezterm",
    "xterm",
}
SAFETY_TITLE_TERMS = ("authentication", "authenticate", "password", "passphrase", "credential")


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
    config = LockConfig()
    for name in config.__dataclass_fields__:
        if name in raw:
            setattr(config, name, raw[name])
    config.check_seconds = max(5, int(config.check_seconds))
    config.warn_seconds = max(10, int(config.warn_seconds))
    config.startup_grace_seconds = max(0, int(config.startup_grace_seconds))
    config.max_closes_per_cycle = max(1, int(config.max_closes_per_cycle))
    config.override_delay_minutes = max(0, int(config.override_delay_minutes))
    config.override_minutes = max(1, int(config.override_minutes))
    if not isinstance(config.extra_allowed_classes, list):
        raise ValueError("lock.extra_allowed_classes must be a list")
    return config


def _parse_hhmm(value: str) -> int:
    parts = str(value).split(":")
    if len(parts) != 2:
        raise ValueError("time must use HH:MM")
    hour, minute = (int(part) for part in parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("time is out of range")
    return hour * 60 + minute


def in_active_window(dt: datetime, active_from: str, active_until: str) -> bool:
    try:
        start, end = _parse_hhmm(active_from), _parse_hhmm(active_until)
    except (ValueError, TypeError):
        return False
    now = dt.hour * 60 + dt.minute
    return start <= now < end if start <= end else now >= start or now < end


def decide_lock(
    *, enabled: bool, in_window: bool, override_active: bool,
    studied_min: float, goal_min: float,
) -> tuple[bool, str]:
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
    allowed_classes = {item.lower() for item in allowed} | SAFETY_ALLOW
    offenders = []
    for client in clients or []:
        window_class = (client.get("class") or "").lower()
        title = (client.get("title") or "").lower()
        if not window_class or not client.get("address") or not client.get("mapped"):
            continue
        if window_class not in allowed_classes and not any(term in title for term in SAFETY_TITLE_TERMS):
            offenders.append(client)
    return offenders


def hypr_clients():
    try:
        result = subprocess.run(
            ["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=3
        )
        clients = json.loads(result.stdout or "null")
        return clients if isinstance(clients, list) else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def hypr_close(address: str) -> bool:
    if not re.fullmatch(r"0x[0-9a-fA-F]+", address or ""):
        return False
    try:
        result = subprocess.run(
            ["hyprctl", "dispatch", "closewindow", f"address:{address}"],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def notify(message: str) -> None:
    try:
        subprocess.run(
            ["notify-send", "-u", "critical", "Tapasya", message], timeout=3
        )
    except (OSError, subprocess.SubprocessError):
        pass


class LockEngine:
    def __init__(
        self,
        cfg: dict,
        conn_factory,
        clients_fn=hypr_clients,
        close_fn=hypr_close,
        notify_fn=notify,
        mono=time.monotonic,
    ):
        self.cfg, self.config = cfg, load_lock_config(cfg)
        self.conn_factory, self.clients_fn = conn_factory, clients_fn
        self.close_fn, self.notify_fn = close_fn, notify_fn
        tracking = cfg["tracking"]
        self.allowed = (
            set(tracking.get("always_allowed_classes", []))
            | set(tracking.get("study_window_classes", []))
            | set(self.config.extra_allowed_classes)
        )
        self.sample_seconds = tracking["sample_seconds"]
        self.started = mono()
        self.first_seen: dict[str, float] = {}
        self.dry_run_done: set[str] = set()
        self.stop: threading.Event | None = None

    def step(self, wall: float, monotonic: float, now: datetime) -> str:
        config = self.config
        if not config.enabled:
            return "disabled"
        if monotonic - self.started < config.startup_grace_seconds:
            return "startup-grace"

        conn = self.conn_factory()
        try:
            day = db.today()
            goal = db.get_goal(conn, day, self.cfg["goal"]["daily_minutes"])
            studied = db.studied_minutes(conn, day, self.sample_seconds)
            locked, reason = decide_lock(
                enabled=True,
                in_window=in_active_window(now, config.active_from, config.active_until),
                override_active=lock_store.override_active(conn, int(wall)),
                studied_min=studied,
                goal_min=goal,
            )
            if not locked:
                self.first_seen.clear()
                self.dry_run_done.clear()
                return reason

            clients = self.clients_fn()
            if clients is None:
                return "no-clients"
            offenders = find_offenders(clients, self.allowed)
            live_addresses = {client["address"] for client in offenders}
            self.first_seen = {
                address: first_seen
                for address, first_seen in self.first_seen.items()
                if address in live_addresses
            }
            self.dry_run_done.intersection_update(live_addresses)

            closed = 0
            for client in offenders:
                if self.stop is not None and self.stop.is_set():
                    return "stopping"
                address = client["address"]
                window_class = client.get("class", "")
                title = client.get("title", "")
                if address not in self.first_seen:
                    self.first_seen[address] = monotonic
                    lock_store.log_event(
                        conn, int(wall), "warn", window_class, title,
                        config.dry_run, "goal-unmet",
                    )
                    if not config.dry_run:
                        self.notify_fn(
                            f"Study first! '{window_class}' closes in {config.warn_seconds}s "
                            f"({studied:.0f}/{goal} min done)"
                        )
                    continue

                if monotonic - self.first_seen[address] < config.warn_seconds:
                    continue
                if closed >= config.max_closes_per_cycle:
                    continue
                if config.dry_run:
                    if address not in self.dry_run_done:
                        lock_store.log_event(
                            conn, int(wall), "would_close", window_class, title,
                            True, "goal-unmet",
                        )
                        self.dry_run_done.add(address)
                else:
                    did_close = self.close_fn(address)
                    lock_store.log_event(
                        conn, int(wall), "close" if did_close is not False else "error",
                        window_class, title, False,
                        "goal-unmet" if did_close is not False else "close-failed",
                    )
                    if did_close is not False:
                        closed += 1
            return "locked"
        finally:
            conn.close()

    def safe_step(self) -> str:
        try:
            return self.step(time.time(), time.monotonic(), datetime.now())
        except Exception as error:  # keep lock errors fail-open
            print(f"[tapasya] lock error (failing open): {error!r}", file=sys.stderr, flush=True)
            return "error"

    def run(self, stop: threading.Event) -> None:
        self.stop = stop
        while not stop.wait(self.config.check_seconds):
            self.safe_step()


def start_engine(cfg: dict, stop: threading.Event):
    config = load_lock_config(cfg)
    if not config.enabled:
        print("[tapasya] lock: disabled", flush=True)
        return None
    database_path = cfg["storage"]["db_path"]
    engine = LockEngine(cfg, lambda: db.connect(database_path))
    thread = threading.Thread(
        target=engine.run, args=(stop,), daemon=True, name="tapasya-lock"
    )
    thread.start()
    mode = "DRY-RUN" if config.dry_run else "REAL: windows will be closed"
    print(f"[tapasya] lock: ON ({mode})", flush=True)
    return thread

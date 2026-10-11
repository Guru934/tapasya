"""Idle detection (Phase 1b), dependency-free.

Hyprland has no built-in "seconds since last input" query, so we use a heuristic:
the user is ACTIVE if the cursor position OR the focused window OR its title changed
recently. If none changed for `idle_seconds`, the user is IDLE and time is not counted.

Known limitation: reading with keyboard only (no mouse, no title change) looks idle.
Mitigation: raise `idle_seconds` in config. Future upgrade: read real input events
(evdev / libinput) if the user joins the `input` group. See ROADMAP backlog.
"""
from __future__ import annotations


class ActivityMonitor:
    def __init__(self, idle_seconds: float) -> None:
        self.idle_seconds = idle_seconds
        self._last_state: tuple | None = None
        self._last_change: float | None = None

    def update(self, cursor: tuple | None, window_class: str, title: str, now: float) -> bool:
        """Feed the latest observation. Returns True if the user is considered idle."""
        state = (cursor, window_class, title)
        if self._last_state is None or state != self._last_state:
            self._last_state = state
            self._last_change = now
            return False
        return (now - self._last_change) >= self.idle_seconds


def is_counted(window_class: str, study_classes: set[str], idle: bool) -> bool:
    """Phase 1a/1b rule: a study window must be focused and the user must not be idle."""
    return (window_class in study_classes) and not idle

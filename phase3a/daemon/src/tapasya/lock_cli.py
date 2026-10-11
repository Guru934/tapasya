"""`tapasya-lock status | override | cancel | events` (works even if the overlay is broken)."""
from __future__ import annotations

import argparse
import time
from datetime import datetime

from . import db, lock_store
from .config import load_config
from .lock import load_lock_config


def _hm(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def main() -> None:
    ap = argparse.ArgumentParser(prog="tapasya-lock")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("override", help="request an emergency override (starts after a delay)")
    sub.add_parser("cancel", help="cancel pending/active override")
    ev = sub.add_parser("events")
    ev.add_argument("-n", type=int, default=20)
    args = ap.parse_args()

    cfg = load_config(args.config)
    lc = load_lock_config(cfg)
    conn = db.connect(cfg["storage"]["db_path"])
    now = int(time.time())

    if args.cmd == "status":
        day = db.today()
        goal = db.get_goal(conn, day, cfg["goal"]["daily_minutes"])
        done = db.studied_minutes(conn, day, cfg["tracking"]["sample_seconds"])
        mode = "OFF" if not lc.enabled else ("DRY-RUN" if lc.dry_run else "REAL")
        print(f"{day}: {done:.0f}/{goal} min | lock: {mode}")
        s = lock_store.override_state(conn, now)
        if s:
            print(f"override {s['state']}: {_hm(s['activate_ts'])} -> {_hm(s['expires_ts'])}")
    elif args.cmd == "override":
        r = lock_store.request_override(conn, now, lc.override_delay_minutes, lc.override_minutes)
        print(f"Override requested. Lock lifts at {_hm(r['activate_ts'])} until {_hm(r['expires_ts'])}. "
              f"Cancel with: tapasya-lock cancel")
    elif args.cmd == "cancel":
        print(f"Cancelled {lock_store.cancel_overrides(conn, now)} override(s).")
    elif args.cmd == "events":
        for ts, action, cls, title, dry, reason in lock_store.recent_events(conn, args.n):
            print(f"{datetime.fromtimestamp(ts):%m-%d %H:%M:%S} {action:<11} {cls:<20} {'(dry) ' if dry else ''}{title[:40]}")


if __name__ == "__main__":
    main()

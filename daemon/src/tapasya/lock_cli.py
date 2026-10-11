"""Command line controls for status, emergency overrides, and lock events."""
from __future__ import annotations

import argparse
import time
from datetime import datetime

from . import db, lock_store
from .config import load_config
from .lock import load_lock_config


def _clock(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%H:%M")


def main() -> None:
    parser = argparse.ArgumentParser(prog="tapasya-lock")
    parser.add_argument("--config")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("override", help="request an emergency override after a delay")
    commands.add_parser("cancel", help="cancel pending or active overrides")
    events = commands.add_parser("events")
    events.add_argument("-n", type=int, default=20)
    args = parser.parse_args()

    cfg = load_config(args.config)
    lock_config = load_lock_config(cfg)
    conn = db.connect(cfg["storage"]["db_path"])
    now = int(time.time())
    try:
        if args.command == "status":
            day = db.today()
            goal = db.get_goal(conn, day, cfg["goal"]["daily_minutes"])
            studied = db.studied_minutes(conn, day, cfg["tracking"]["sample_seconds"])
            mode = "OFF" if not lock_config.enabled else ("DRY-RUN" if lock_config.dry_run else "REAL")
            print(f"{day}: {studied:.0f}/{goal} min | lock: {mode}")
            state = lock_store.override_state(conn, now)
            if state:
                print(
                    f"override {state['state']}: {_clock(state['activate_ts'])} "
                    f"-> {_clock(state['expires_ts'])}"
                )
        elif args.command == "override":
            result = lock_store.request_override(
                conn, now, lock_config.override_delay_minutes, lock_config.override_minutes
            )
            print(
                f"Override requested. Lock lifts at {_clock(result['activate_ts'])} "
                f"until {_clock(result['expires_ts'])}. Cancel with: tapasya-lock cancel"
            )
        elif args.command == "cancel":
            cancelled = lock_store.cancel_overrides(conn, now)
            print(f"Cancelled {cancelled} override(s).")
        elif args.command == "events":
            for timestamp, action, window_class, title, dry_run, _reason in lock_store.recent_events(
                conn, max(0, args.n)
            ):
                dry_label = "(dry) " if dry_run else ""
                print(
                    f"{datetime.fromtimestamp(timestamp):%m-%d %H:%M:%S} "
                    f"{action:<11} {window_class:<20} {dry_label}{title[:40]}"
                )
    finally:
        conn.close()


if __name__ == "__main__":
    main()

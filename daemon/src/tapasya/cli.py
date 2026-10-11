"""CLI entry: `tapasya init | run | status | goal <minutes>`."""
from __future__ import annotations

import argparse

from . import db, tracker
from .config import load_config


def main() -> None:
    ap = argparse.ArgumentParser(prog="tapasya")
    ap.add_argument("--config", help="path to config toml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create the database")
    sub.add_parser("run", help="start the tracker loop")
    sub.add_parser("status", help="show today's progress")
    g = sub.add_parser("goal", help="set today's goal in minutes")
    g.add_argument("minutes", type=int)
    args = ap.parse_args()

    cfg = load_config(args.config)
    conn = db.connect(cfg["storage"]["db_path"])
    day = db.today()

    if args.cmd == "init":
        print(f"DB ready at {cfg['storage']['db_path']} (config: {cfg['_path']})")
    elif args.cmd == "run":
        tracker.run(cfg)
    elif args.cmd == "goal":
        db.set_goal(conn, day, args.minutes)
        print(f"Goal for {day}: {args.minutes} min")
    elif args.cmd == "status":
        step = cfg["tracking"]["sample_seconds"]
        goal = db.get_goal(conn, day, cfg["goal"]["daily_minutes"])
        done = db.studied_minutes(conn, day, step)
        print(f"{day}: {done:.0f}/{goal} min ({'GOAL MET' if done >= goal else 'keep going'})")


if __name__ == "__main__":
    main()

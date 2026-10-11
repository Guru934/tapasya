# Phase 3a integration (lock engine, dry-run first)

New files (copy into the repo, same paths):
- `daemon/src/tapasya/migrations.py`: schema v2 (`overrides`, `lock_events` tables)
- `daemon/src/tapasya/lock_store.py`: SQL for overrides and events
- `daemon/src/tapasya/lock.py`: the engine (fail-open, warn-first, dry-run default)
- `daemon/src/tapasya/lock_cli.py`: `tapasya-lock status | override | cancel | events`
- `daemon/tests/test_lock.py`: 11 tests (written against the original code; 20/20 pass there)
- `config/lock.example.toml`: the `[lock]` section to append to your configs

## 5 small edits to your existing files

1. **pyproject.toml**, under `[project.scripts]` add:
   `tapasya-lock = "tapasya.lock_cli:main"`
2. **db.py**, at the end of `connect()` just before `return conn` add:
   ```python
   from .migrations import migrate
   migrate(conn)
   ```
   (keep your existing `schema_version = 1` insert before it)
3. **tracker.py**, in `run()` after the API server starts, add:
   ```python
   from . import lock
   lock.start_engine(cfg, <your stop Event>)
   ```
   Use the same `threading.Event` your SIGTERM/SIGINT handler already sets.
4. Append `config/lock.example.toml` to `config/config.toml` and `config/config.example.toml`.
5. **AGENTS.md**: add "Lock SQL lives in lock_store.py; schema changes go in migrations.py".

Then: `pip install -e .`, `pytest -q`, `systemctl --user restart tapasya`.

### Prompt for opencode (edits 1-3)
> Make exactly these three edits and nothing else: (1) add the `tapasya-lock` script line to pyproject.toml, (2) call `migrate(conn)` from `tapasya.migrations` at the end of `db.connect()`, (3) in `tracker.run()` call `lock.start_engine(cfg, stop_event)` after the API starts, using the existing stop event. Then run pytest and show me the diff. Do not change behavior elsewhere.

## Test plan (do in this order)

1. **Dry-run:** in `config.toml` set `enabled = true`, `dry_run = true`. Restart. Set a high goal (`tapasya goal 600`). Open an app that is not allowed (a file manager, Discord, etc.) and wait about 3 minutes.
   Check: `tapasya-lock events` shows `warn` then `would_close` for that app, and nothing closes.
   Also check the journal for: `lock: ON (DRY-RUN)`.
2. **Allowed apps:** confirm kitty, your editor, and Brave never appear in events. If one does, add its class to `extra_allowed_classes`.
3. **Goal met:** `tapasya goal 1`, study a minute, and confirm events stop.
4. **Override:** `tapasya-lock override` then `tapasya-lock status` shows pending, then active after 10 min. `tapasya-lock cancel` removes it. Bind it to a key in Hyprland, e.g.
   `bind = SUPER SHIFT, F12, exec, kitty -e ~/tapasya/.venv/bin/tapasya-lock override`
5. **Real mode (only after 1-4 look right):** set `dry_run = false`, **save all work first**, and test with a harmless app. Windows are warned (notification) and then closed after `warn_seconds`.

## Emergency exits (know these before enabling real mode)
- `systemctl --user stop tapasya` stops the daemon, so the lock stops too (fail-open).
- `tapasya-lock override` (10 min delay) or set `enabled = false` and restart.
- If the screen is unusable: Ctrl+Alt+F3, log in, run `systemctl --user stop tapasya`.

## Limits of 3a (on purpose)
- Closes whole windows; it can't tell about unsaved work, so the warning comes first.
- Doesn't yet block distracting *sites inside Brave* (separate step: extension can close/redirect blocked tabs).
- No overlay/pill yet (3b) and no reward bank (3c).

# Phase 3a integration (lock engine, dry-run first)

The Phase 3a files are integrated at these paths:
- `daemon/src/tapasya/migrations.py`: schema v2 (`overrides`, `lock_events` tables)
- `daemon/src/tapasya/lock_store.py`: SQL for overrides and events
- `daemon/src/tapasya/lock.py`: the engine (fail-open, warn-first, dry-run default)
- `daemon/src/tapasya/lock_cli.py`: `tapasya-lock status | override | cancel | events`
- `daemon/tests/test_lock.py`: 15 lock-engine tests
- `config/lock.example.toml`: safe `[lock]` defaults

The repository has these files integrated. The live config keeps `[lock] enabled = false` and
`dry_run = true`; lock mode must not close windows until its dry-run checks and Phase 1a tracking
checks pass.

Pytest is configured to collect the canonical suite under `daemon/tests/`; the original package
copy under `phase3a/` is retained as reference input and is not collected twice.

The runner, migration, CLI script, and safe config defaults are already integrated. The full
automated suite currently has 29 tests. After changing source, use `.venv/bin/pip install -e .`,
run `pytest -q`, and restart the user service to load the new code.

## Test plan (do in this order)

1. **Dry-run:** in `config.toml` set `enabled = true`, `dry_run = true`. Restart. Set a high goal (`tapasya goal 600`). Open an app that is not allowed (a file manager, Discord, etc.) and wait about 3 minutes.
Check: `tapasya-lock events` shows `warn` then `would_close` for that app, and nothing closes.
   Also check the journal for: `lock: ON (DRY-RUN)`.
2. **Allowed apps:** confirm terminals, your editor, and Brave never appear in events. If another
   app must stay open, add its class to `extra_allowed_classes`.
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
- It protects common terminal classes and authentication/password prompt titles. Add other
  recovery-critical applications to `extra_allowed_classes` before enabling lock mode.
- Doesn't yet block distracting *sites inside Brave* (separate step: extension can close/redirect blocked tabs).
- No overlay/pill yet (3b) and no reward bank (3c).

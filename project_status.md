# Tapasya project status

Last updated: 2026-10-11

## Current state

Tapasya is a local, personal study tracker for CachyOS, Hyprland, and Brave. It samples the
focused window every five seconds and saves each result to SQLite. A group of rows with the same
`app_class`, `domain`, and `counted` values is normal: each row is one five-second sample.

Phase 3a lock mode is integrated and pushed to `main` in commit `359145d`. Locking remains disabled
in the live config.

## What has been built

### Phase 0: scaffold and basic tracker

- Python package and `tapasya` CLI.
- SQLite database for samples and daily goals.
- `init`, `goal`, `status`, and `run` commands.
- Hyprland focused-window polling.

### Phase 1: tracking reliability

- Idle heuristic based on cursor position, window class, and title.
- systemd user service and installer.
- Service finds the running Hyprland instance when launched by systemd.
- `PYTHONUNBUFFERED=1` is enabled so service output appears in `journalctl` immediately.

### Phase 2: Brave tab tracking

- Manifest V3 Brave extension sends the active tab's domain, title, Shorts state, and audible state
  to the local daemon at `127.0.0.1:8765`.
- The daemon accepts extension-origin requests, keeps the latest tab state, and exposes
  `GET /v1/status`.
- Site rules support allow, block, and mixed sites. YouTube counts only when its title contains a
  configured study keyword; Shorts never count.
- An allowed audible tab remains active when the idle heuristic would otherwise stop counting.
- The tracker warns clearly if its local API cannot bind to port 8765.

### Phase 3a: lock engine

- Database schema migration v2 adds `overrides` and `lock_events` without deleting existing data.
- Lock engine defaults to disabled and dry-run. It checks active hours, goal progress, delayed
  overrides, and window classes before warning or closing.
- Warning delay, startup grace, per-cycle close limit, terminal/authentication safety exclusions,
  event history, and `tapasya-lock status|override|cancel|events` are implemented.
- Lock thread shares the tracker stop event. Errors starting the lock engine leave tracking
  running and lock behavior fail-open.
- `tapasya-lock` is installed in the project virtual environment and reports lock mode OFF from
  the live user config.

## Verification performed

### Automated checks

- Full pytest suite: **10 passed** on 2026-10-11.
- Extension JavaScript syntax check passed with `node --check extension/background.js`.
- `git diff --check` passed before the Phase 2 commit.
- The API origin and tab-update behavior, site rules, idle logic, database calculations, and
  audible-tab regression are covered by the pytest tests.

### Real-machine checks

- `tapasya.service` was active and `GET /v1/status` responded.
- The running service received `PYTHONUNBUFFERED=1`.
- The API's reported 20.7 study minutes matched the database calculation of 248 counted samples
  at five seconds each.
- GitHub samples counted as study.
- Instagram samples did not count.
- A YouTube tab titled `lecture` counted; unrelated YouTube titles did not count because they did
  not contain configured study keywords.
- An audible Python tutorial produced 133 counted samples across 13 minutes without input, which
  verifies playback beyond the default 180-second idle timeout.
- The owner opened a YouTube Short and observed uncounted samples.

### Phase 3a checks

- Lock unit tests cover decision rules, active hours, offender filtering, warning delay, dry-run,
  goal completion, overrides, startup grace, fail-open errors, close limits, and migrations.
- Full pytest suite after integration: **29 passed** (2026-10-11).
- The live database was upgraded to schema version 2; both lock tables exist and the 2,515
  existing sample rows remained present at verification time.
- Restarted systemd service is active; journal shows the API started and `lock: disabled`.
- Real window closing remains disabled and must wait for Phase 1a stopwatch accuracy and reboot
  checks.

### Real Hyprland dry-run (2026-10-11)

- Enabled lock mode temporarily with `dry_run = true`, set the goal to 600, and restarted the
  user service. Journal confirmed `lock: ON (DRY-RUN)`; the service remained active.
- Opened Thunar after startup grace. The event log recorded `warn` followed by `would_close`; the
  Thunar window remained open. Brave and kitty did not appear in the test events.
- The first pass exposed the editor's real Hyprland class as `com.microsoft.VSCode`; the existing
  allow list only named `code`/`Code`, so the editor was initially logged as a dry-run offender.
  Added `com.microsoft.VSCode` to the example and local allow lists. It did not appear in the
  subsequent test run.
- Set the goal to 1 with 38 minutes already counted. Status showed `GOAL MET`, and no new lock
  events were recorded during the following check interval.
- Requested an override, confirmed its pending state, and canceled it successfully.
- Restored the live goal to 120 and lock mode to disabled (`dry_run = true`); restarted the
  service and confirmed it active with lock OFF. Real window closing was never enabled.

## Known limits and deferred cleanup

- Phase 1a still needs a full-session accuracy check against real study time and a reboot check.
- The tracker handles SIGTERM/SIGINT by stopping its loop and closing its API server and database
  connection. Samples are committed immediately, so stopping the service does not lose
  already-recorded samples.
- `config.py` currently assumes the installed repository layout. Add `TAPASYA_CONFIG` and
  `~/.config/tapasya/config.toml` lookup before Phase 5.
- Database initialization applies migrations through `meta.schema_version = 2`. Preserve user
  data during all future schema migrations.
- Extension behavior is tested only in the owner's current Brave/Hyprland setup.

## Next steps

1. Complete the Phase 1a stopwatch accuracy and reboot checks. Do not enable real window closing
   until tracking is within about 5% and both checks pass.
2. Continue with Phase 3b UI and Phase 3c rewards after Phase 1a fairness checks pass.

The emergency override is mandatory: lock mode must never trap the owner out of the PC.

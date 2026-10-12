# Tapasya project status

Last updated: 2026-10-12

## Current state

Tapasya is a local, personal study tracker for CachyOS, Hyprland, and Brave. It samples the
focused window every five seconds and saves each result to SQLite. A group of rows with the same
`app_class`, `domain`, and `counted` values is normal: each row is one five-second sample.

Phase 3a lock mode is integrated and pushed to `main` in commit `359145d`. Locking remains disabled
in the live config.

Phase 3a.1 reliability gate completed (2026-10-12): automated test suite expanded to 37 tests,
configuration lookup precedence implemented and tested, lock-engine safety defect fixed
(unmapped windows now skipped).

Phase 3a.2 Hyprland startup race fix (2026-10-12): fixed tracker to automatically recover when
Hyprland is unavailable at service startup. The tracker now re-discovers the Hyprland instance
signature on failure, logs diagnostics at a controlled rate, and does not record empty window
samples. Test suite expanded to 47 tests with 10 new regression tests.

Phase 3a.3 Brave extension hardening (2026-10-12): hardened Brave tracking to fail closed,
fixed intermittent empty-domain reports, and made heartbeat creation reliable. Test suite
expanded to 66 tests (52 Python + 14 JavaScript).

Phase 3a.4 Persistent domain loss fix (2026-10-12): fixed the daemon to ignore empty domain
reports from the extension (sent on focus loss), preserving the last valid domain until a new
valid one arrives or the state becomes stale. Extension no longer sends empty reports on
focus loss (WINDOW_ID_NONE). Test suite expanded to 68 tests (54 Python + 14 JavaScript).

Phase 3a.5 Explicit ineligible tab handling (2026-10-12): fixed the extension to explicitly
signal ineligible tabs (internal pages, new tabs) with `eligible: false`, allowing the daemon
to promptly invalidate study eligibility. Extension no longer sends empty reports for focus
loss (`WINDOW_ID_NONE`); internal pages send `eligible: false` which immediately clears the
tab state. Daemon `TabState.update()` treats `eligible: false` as explicit invalidation. Test
suite expanded to 71 tests (57 Python + 14 JavaScript).

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

- Full pytest suite: **57 passed** on 2026-10-12 (was 54 on 2026-10-12 evening, 52 on 2026-10-12 evening, 47 on 2026-10-12 morning, 37 on 2026-10-12 morning, 29 on 2026-10-11).
- Extension JavaScript tests: **14 passed** on 2026-10-12 (Node built-in test runner).
- Extension JavaScript syntax check passed with `node --check extension/background.js`.
- `git diff --check` passed.
- Configuration precedence (explicit arg > TAPASYA_CONFIG env > ~/.config/tapasya/config.toml > repo config > example fallback) tested with 7 new tests.
- Lock-engine safety defect fixed: `find_offenders()` now skips windows with missing or falsy `mapped` field; regression test added.
- Hyprland startup race fixed: tracker re-discovers Hyprland instance on failure, logs diagnostics at controlled rate (max once per 60s), skips empty window samples; 10 new regression tests cover Hyprland unavailable/recovery, malformed output, and empty-class handling.
- Brave extension hardening (Phase 3a.3):
  - `require_extension` default changed to `true` (fail closed) in config and code; 6 new regression tests for missing/valid/stale/blocked/unknown/empty domains.
  - Heartbeat alarm creation made reliable with `ensureHeartbeat()` helper; recovery from missing alarm tested.
  - Intermittent empty-domain reports fixed: version counter prevents race conditions, focused window tracking ignores unfocused window events, `WINDOW_ID_NONE` handled explicitly, internal pages return empty payload.
  - 14 JavaScript tests cover payload building, race prevention, focus tracking.
- Persistent domain loss fix (Phase 3a.4):
  - Daemon `TabState.update()` now ignores empty/whitespace domain reports, preserving last valid domain.
  - Extension no longer sends empty reports on focus loss (`WINDOW_ID_NONE`).
  - 2 new regression tests for TabState empty domain handling.
- Explicit ineligible tab handling (Phase 3a.5):
  - Extension sends `eligible: false` for internal pages/new tabs; daemon immediately clears tab state.
  - Focus loss (`WINDOW_ID_NONE`) no longer sends a report; last valid domain preserved.
  - 4 new regression tests for `eligible` flag handling and backward compatibility.
  - Test suite expanded to 71 tests (57 Python + 14 JavaScript).

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

### Phase 3a.3 Brave extension hardening verification (2026-10-12)

- Confirmed `require_extension = true` in both example and local config; daemon default also fails closed.
- Extension reloaded in Brave; `GET /v1/status` returns HTTP 200.
- Brave window on `https://docs.python.org/`: extension POSTs `domain: "docs.python.org"`, samples counted (`counted=1`).
- Brave window on `https://chatgpt.com/`: extension POSTs `domain: "chatgpt.com"`, samples uncounted (`counted=0`) per site rules (unknown domain).
- Brave new tab / internal page: extension POSTs empty domain, samples uncounted.
- Focus transitions between Brave and Kitty: no stale domains recorded; focused-window tracking works.
- Brave fully quit and reopened: heartbeat alarm persists (created by `ensureHeartbeat` on startup), reports resume automatically without daemon restart.
- Time-correlated SQLite records match extension POST payloads (domain, title, shorts, audible).
- No empty-domain samples recorded during controlled study-page test except when active page is genuinely ineligible (unknown domain, internal page).

### Phase 3a.4 Persistent domain loss fix verification (2026-10-12)

- Confirmed daemon `TabState.update()` ignores empty/whitespace domain reports, preserving last valid domain.
- Extension no longer sends empty reports on focus loss (`WINDOW_ID_NONE`).
- Service restarted; no empty-domain samples recorded in 10+ minutes of operation.
- Brave window on `https://docs.python.org/` remains counted; focus transitions to ChatGPT/internal pages correctly uncounted.
- No stale domains after focus transitions between Brave and Kitty.

### Phase 3a.5 Explicit ineligible tab handling verification (2026-10-12)

- Extension now sends `eligible: false` for internal pages (new tab, brave://, chrome://) and `eligible: true` for valid domains.
- Daemon `TabState.update()` treats `eligible: false` as explicit invalidation, immediately clearing tab state.
- Focus loss (`WINDOW_ID_NONE`) no longer sends a report; last valid domain preserved during transient focus loss.
- Real-desktop test: `docs.python.org` counted (`counted=1`); navigation to internal page immediately stops counting; return to study domain resumes counting.
- ChatGPT (`chatgpt.com`) correctly uncounted (unknown domain).
- No stale domains after focus transitions between Brave and Kitty.

### Phase 3a checks

- Lock unit tests cover decision rules, active hours, offender filtering, warning delay, dry-run,
  goal completion, overrides, startup grace, fail-open errors, close limits, and migrations.
- Full pytest suite after integration: **37 passed** (2026-10-12).
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
- Configuration lookup now supports `TAPASYA_CONFIG` and `~/.config/tapasya/config.toml` (implemented in Phase 3a.1).
- Database initialization applies migrations through `meta.schema_version = 2`. Preserve user
  data during all future schema migrations.
- Extension behavior is tested only in the owner's current Brave/Hyprland setup.
- Study-time calculation uses local date (`date.today()`); potential timezone edge case at midnight.
- Tracker shutdown waits up to `sample_seconds` (default 5s) for stop signal; lock thread join has 15s timeout.
- The Hyprland startup race fix has been verified for service restart after Hyprland is running.
  The cold-boot scenario (service starts before Hyprland at login) has not been tested because
  a safe reboot test was not performed. This should be verified on the next natural reboot.

## Next steps

1. Complete the Phase 1a stopwatch accuracy and reboot checks. Do not enable real window closing
   until tracking is within about 5% and both checks pass.
2. Continue with Phase 3b UI and Phase 3c rewards after Phase 1a fairness checks pass.

The emergency override is mandatory: lock mode must never trap the owner out of the PC.

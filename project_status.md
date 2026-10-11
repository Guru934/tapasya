# Tapasya project status

Last updated: 2026-10-11

## Current state

Tapasya is a local, personal study tracker for CachyOS, Hyprland, and Brave. It samples the
focused window every five seconds and saves each result to SQLite. A group of rows with the same
`app_class`, `domain`, and `counted` values is normal: each row is one five-second sample.

The implementation through Phase 2 is on `main` in commit `d57827e`
(`phase2: add Brave tab tracking`).

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
- The owner played a Python tutorial for three minutes and observed counted samples.
- The owner opened a YouTube Short and observed uncounted samples.

## Known limits and deferred cleanup

- Phase 1a still needs a full-session accuracy check against real study time and a reboot check.
- The tracker does not yet handle SIGTERM/SIGINT gracefully. Samples are committed immediately,
  so stopping the service does not lose already-recorded samples.
- `config.py` currently assumes the installed repository layout. Add `TAPASYA_CONFIG` and
  `~/.config/tapasya/config.toml` lookup before Phase 5.
- The database `meta` table has no `schema_version` entry yet. Add schema version `1` before
  Phase 5 and preserve user data during future migrations.
- Extension behavior is tested only in the owner's current Brave/Hyprland setup.

## Next phase: Phase 3 lock mode and rewards

Start with the first unchecked Phase 3 item in `ROADMAP.md`:

1. Decide whether the lock engine reads the existing local API or the database directly.
2. Add a lock engine that warns before closing non-allowed applications when the daily goal is unmet.
3. Build the Quickshell progress overlay and bar pill.
4. Add the reward bank and a delayed, logged emergency override.

The emergency override is mandatory: lock mode must never trap the owner out of the PC.

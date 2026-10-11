# Tapasya Roadmap

Source of truth for what to build and in what order. Update checkboxes as work completes.
Rule: finish and test one phase before starting the next. Keep each phase small and shippable.

## Architecture (target)
```
Brave ──(extension, JS)──► local daemon (Python, 127.0.0.1:8765) ◄── AI assistant / goose
                                │  SQLite (~/.local/share/tapasya/tapasya.db)
                                ├──► Quickshell overlay + bar pill (QML, via IPC/HTTP)
                                ├──► lock engine (hyprctl: close/block apps)
                                └──► sync worker ──► Supabase ──► Next.js PWA (viewer)
                                         (opt-in, consent-gated; see docs/PRIVACY.md)
```
Data flow: sampler writes `samples` every N seconds -> minutes studied = counted samples x N / 60
-> compared with today's goal -> status (`locked` / `unlocked`) exposed by API and overlay.

## Phase 0: Scaffold  (DONE)
- [x] Repo layout, pyproject, config example, SQLite schema
- [x] CLI: `init`, `run`, `status`, `goal`
- [x] Tracker counts time while the Brave window is focused

## Phase 1: Reliable tracking (PC only)
**1a**
- [ ] Verify Brave window class on the machine; set in `config.toml`
- [ ] Run `tapasya run` for a full session, confirm `status` matches real time
**1b**
- [x] Idle detection (heuristic: cursor/window/title unchanged for `idle_seconds`) in `activity.py`
      (untested on Hyprland; upgrade to real input events later if it undercounts)
- [x] Pytest tests for `db.py` and counting rules (`daemon/tests/test_core.py`)
**1c**
- [x] systemd **user** unit `scripts/tapasya.service` (written, untested on the real machine)
- [x] `scripts/install.sh` (venv, config copy, enable service; untested on the real machine)
- Done when: a full day of normal use gives study minutes within about 5% of reality, and survives reboot.

## Phase 2: Brave extension (know WHAT you study)
- [x] MV3 extension in `extension/` sends `{domain, title, shorts, audible}` to `POST /v1/tab` (partially verified in real Brave)
- [x] Daemon stores `domain`/`title` on each sample (`api.py`, `tracker.py`)
- [x] Rules engine (`rules.py`) from config: `allow` counts, `block` never counts, mixed sites (youtube.com)
      count only if the title matches `study_keywords`
- [x] Count only when the Brave window is focused AND the active tab is allowed (`tracker.decide`)
- Manual check on 2026-10-11: GitHub counted, Instagram did not, and a YouTube tab titled
  `lecture` counted; unrelated YouTube titles did not. Still verify that an audible lecture keeps
  counting after `idle_seconds`, and that a YouTube Short never counts.
- Done when: Instagram in Brave adds 0 minutes, docs.python.org adds minutes, a lecture on
  YouTube counts through the idle timeout, and Shorts do not.

## Phase 3: Lock mode and rewards
- [ ] Local API (Phase 3 needs it; see Phase 4 endpoints) or direct DB read for lock engine
- [ ] Lock engine: while goal not met, apps outside `always_allowed_classes` are closed with
      `hyprctl dispatch closewindow` (warn first with a notification and a countdown)
- [ ] Quickshell overlay: progress ring, minutes left, "goal met" unlock animation
- [ ] Bar pill widget showing `done/goal`
- [ ] Reward bank: `reward_ratio` minutes of free time per study minute; spending time pauses lock
- [ ] Emergency override with a 10-minute delay, logged in DB (`overrides` table)
- Done when: lock engages with an unmet goal, releases at goal, and override works without a reboot.

## Phase 4: Local API and AI assistant hooks
Endpoints (JSON, 127.0.0.1 only):
- `GET /v1/status` -> `{day, goal, studied_min, remaining_min, locked, streak}`
- `POST /v1/goal` `{minutes}`; `GET /v1/today` (domains breakdown); `POST /v1/tab`
- [ ] Implement with the stdlib `http.server` or FastAPI (decide, document in AGENTS.md)
- [ ] Assistant tool/skill for `ai-assistant` and goose: read status, nag by voice when behind,
      celebrate on goal met
- [ ] Streak logic: goal met = day counts; streak resets on a miss; weekly report
- Done when: asking the assistant "how much have I studied" returns the right number, and she
  proactively reminds when behind schedule.

## Phase 5: Online dashboard (viewer sees progress)
- [ ] Supabase project: tables `daily_stats`, `domains_daily`, `messages`, `settings`; Row Level
      Security so only the owner and the one invited viewer can read
- [ ] Sync worker in daemon pushes aggregated stats every few minutes (opt-in flag in config)
- [ ] `web/`: Next.js PWA (installable on phone): login + 2FA, today's progress, streak,
      domains, send message/voice note to the owner
- [ ] Owner's PC shows incoming messages as a popup
- Done when: the viewer opens the PWA on her phone, sees live-ish stats, and a message appears on the PC.

## Phase 6: Mutual accountability
- [ ] Viewer sets her own goals and shares only what she chooses (daily number or manual check-in)
- [ ] Owner sees her shared data in the overlay/dashboard
- [ ] Optional later: small Android app for automatic sharing (only with her explicit opt-in)

## Phase 7: Consent-gated camera and screen (hardest, last)
- [ ] Snapshot on request: owner PC shows a prompt/indicator, viewer gets one image
- [ ] Live view via WebRTC through Tailscale or a TURN server; always with on-screen indicator,
      kill switch, and an access log
- [ ] Follow every rule in `docs/PRIVACY.md`; add tests for the approval flow
- Done when: nothing can be viewed without approval/permission, and each access is visible and logged.

## Backlog / ideas
- Focus score, weekly PDF/MD report, pomodoro mode, per-subject goals, wallpaper change on
  streak milestones, voice-note motivation from the viewer.

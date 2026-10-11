# Tapasya (तपस्या)

> Study first. Everything else after.

Tapasya is a personal, study-first discipline system for a Linux desktop
(built for **CachyOS + Hyprland + Caelestia/Quickshell**). You set a daily study goal.
Tapasya measures real study time (focused Brave tab on study sites, not just "Brave is open"),
and until the goal is met it restricts distracting apps. Your AI assistant knows the status and
keeps you accountable. A consent-gated online dashboard lets one trusted person (your partner)
see your progress and send you motivation.

**Status:** Phases 0, 1b, 1c are written (tracker, idle detection, tests, autostart). Phase 1a needs a full-session accuracy and reboot check on the real machine. Phase 2 is verified in real Brave. Phase 3a lock engine is integrated, migrated to schema v2, and remains disabled by default; its real Hyprland dry-run checklist is still open.
**Personal use only.** Read `docs/PRIVACY.md` before building any remote feature.

## Features (planned, see ROADMAP.md)
- Daily goal, streaks, weekly report
- Study time from the focused window, then from Brave tab domain/title (extension)
- Lock mode: block/close distracting apps until goal met, reward bank, delayed emergency override
- Local HTTP API so the AI assistant / goose agent can read status and nag by voice
- Quickshell overlay and bar pill showing progress
- Online dashboard (PWA) for one trusted viewer: study minutes, domains, messages, opt-in snapshots

## Project tree
```
tapasya/
├── README.md              # this file
├── ROADMAP.md             # phases, tasks, acceptance criteria (source of truth)
├── INTEGRATION.md         # Phase 3a dry-run and real-mode test plan
├── project_status.md      # implementation, validation, known limits, and next steps
├── AGENTS.md              # instructions for any AI continuing the work
├── pyproject.toml         # Python package, `tapasya` command
├── .gitignore
├── config/
│   ├── config.example.toml   # copy to config.toml (git-ignored)
│   └── lock.example.toml     # safe Phase 3a lock defaults
├── docs/
│   └── PRIVACY.md         # consent + security rules (binding)
├── daemon/                # Python backend (runs on the PC)
│   ├── src/tapasya/
│   │   ├── __init__.py
│   │   ├── activity.py    # idle detection (heuristic)
│   │   ├── api.py         # local HTTP API (127.0.0.1)
│   │   ├── rules.py       # allow/block/mixed site rules
│   │   ├── cli.py         # init | run | status | goal
│   │   ├── config.py      # loads TOML config
│   │   ├── db.py          # core SQLite access and connection setup
│   │   ├── lock.py        # Phase 3a lock engine (off by default)
│   │   ├── lock_store.py  # override and event SQL
│   │   ├── lock_cli.py    # tapasya-lock emergency controls
│   │   ├── migrations.py  # schema migrations
│   │   ├── schema.sql     # DB schema v1
│   │   └── tracker.py     # focused-window sampler (Phase 1a)
│   └── tests/             # pytest tests
├── extension/             # Brave MV3 tab reporter (load unpacked)
├── overlay/               # Quickshell QML overlay + bar pill (Phase 3, planned)
├── web/                   # Next.js PWA dashboard for the viewer (Phase 5, planned)
└── scripts/               # install.sh + tapasya.service (autostart on login)
```

## Quick start (Phase 0)
Requirements: Python 3.11+, Hyprland (`hyprctl` on PATH).
```bash
cd tapasya
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp config/config.example.toml config/config.toml
tapasya init
tapasya goal 120        # today's goal: 120 minutes
tapasya run             # leave running; focus Brave to accumulate time
tapasya status          # in another terminal
```
Autostart on login instead: `bash scripts/install.sh`

Find your Brave window class with `hyprctl activewindow -j` and set it in `config.toml`
(`study_window_classes`) if it differs.

## Tech choices
- **Python 3.11+, SQLite** for the PC daemon (no heavy dependencies)
- **JavaScript (MV3)** for the Brave extension
- **QML (Quickshell)** for overlay/widgets
- **Supabase + Next.js PWA on Vercel** for the online dashboard (Phase 5)
- **Tailscale** as the safest option for live camera/screen (Phase 7)

## License
Private project. No license granted.

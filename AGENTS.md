# AGENTS.md: instructions for any AI working on Tapasya

Read this file, then `ROADMAP.md` and `docs/PRIVACY.md`, before changing anything.

## What this project is
Tapasya: a personal study-first discipline tool for one user's Linux desktop
(CachyOS, Hyprland, Caelestia on Quickshell). The owner is a student building skills toward AI
engineering and has limited coding experience, and he often works with free/small models.
Therefore: **small steps, simple code, plain explanations, no clever abstractions.**

## Current state
Phases 0, 1b, 1c are written (CLI, SQLite, sampler, idle heuristic, tests, systemd service + installer).
Owner must still verify on his real machine: Brave window class and a full-session accuracy check (Phase 1a).
Next task = the first unchecked item in `ROADMAP.md`, then Phase 2 (Brave extension).

## Rules
1. Work on ONE roadmap item at a time. Update the checkbox in `ROADMAP.md` when done.
2. Keep the daemon dependency-light (stdlib first). Add a dependency only with a stated reason.
3. All SQL lives in `daemon/src/tapasya/db.py`. Schema changes go in `schema.sql` with a
   migration note (add a `meta` key `schema_version`; never drop user data silently).
4. Config comes only from `config/config.toml` (git-ignored). Never hardcode secrets or paths.
5. Local API binds to `127.0.0.1`. Never `0.0.0.0` without authentication.
6. **Follow `docs/PRIVACY.md`.** No hidden monitoring, camera/screen only with owner consent,
   visible indicator, and logging. If a request conflicts with it, stop and flag it.
7. Lock mode must never trap the owner: always keep the delayed emergency override.
8. Test what you can: add pytest tests in `daemon/tests/` using a temporary DB. Do not claim
   something works on Hyprland unless it was run there; say "untested" otherwise.
9. Don't rewrite working files wholesale; make focused edits and keep commits small.
10. If something is unclear (window class, Hyprland version, IPC details), ask the owner or
    inspect the real system (`hyprctl activewindow -j`, `hyprctl clients -j`) instead of guessing.

## Conventions
- Python 3.11+, type hints, `from __future__ import annotations`, small functions.
- Time stored as unix seconds (UTC); "day" is local `YYYY-MM-DD`.
- Study minutes = `counted` samples x `sample_seconds` / 60.
- Names: package `tapasya`, CLI `tapasya`, DB `~/.local/share/tapasya/tapasya.db`.
- Commit style: `phase1b: add idle detection`.

## How to run
```bash
python -m venv .venv && source .venv/bin/activate && pip install -e .
cp config/config.example.toml config/config.toml
tapasya init && tapasya goal 120 && tapasya run
```

## Related projects by the owner (integration targets in Phase 4)
- `github.com/Guru934/ai-assistant`: PC voice assistant
- `github.com/Guru934/guru_agent`: voice assistant plus coding agent (PyQt6, Gemini Live, Ollama)
- goose: the agent the assistant delegates work to
The assistant should read `GET /v1/status` and speak reminders; do not tightly couple code:
integrate only through the local API.

## Handoff checklist (end of every session)
- [ ] ROADMAP.md checkboxes updated
- [ ] What changed, how to test it, and known issues written at the bottom of this file under "Session log"

## Session log
- Phase 0 scaffold created. CLI smoke-tested (`init`, `goal`, `status`). Tracker loop untested on Hyprland.
- Phase 1b/1c added: activity.py (idle heuristic), tests (pytest passes), tracker finds the Hyprland instance itself so it works under systemd, install.sh + tapasya.service. Not run on real Hyprland/systemd yet.

#!/usr/bin/env bash
# Tapasya installer: venv + config + systemd user service. Safe to re-run.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -e .
[ -f config/config.toml ] || cp config/config.example.toml config/config.toml
.venv/bin/tapasya init

mkdir -p "$HOME/.config/systemd/user"
sed "s|__REPO__|$REPO|g" scripts/tapasya.service > "$HOME/.config/systemd/user/tapasya.service"
systemctl --user daemon-reload
systemctl --user enable --now tapasya.service

echo "Done. Check: systemctl --user status tapasya  |  .venv/bin/tapasya status"
echo "Logs: journalctl --user -u tapasya -f"

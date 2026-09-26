#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="$(command -v python3)"
user_units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$user_units"
cat > "$user_units/charlie-memory-sync.service" <<UNIT
[Unit]
Description=Send queued Charlie memories to local MARM

[Service]
Type=oneshot
WorkingDirectory=$repo_root
Environment=PYTHONPATH=$repo_root
EnvironmentFile=-%h/.config/charlie/marm.env
ExecStart=$python_bin -m memory.sync
UNIT
cp "$repo_root/memory/systemd/charlie-memory-sync.timer" "$user_units/charlie-memory-sync.timer"
systemctl --user daemon-reload
systemctl --user enable --now charlie-memory-sync.timer
systemctl --user list-timers charlie-memory-sync.timer

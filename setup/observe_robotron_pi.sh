#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p robotron-runs
bundle=$(mktemp -d robotron-runs/detection-XXXXXXXX)
.venv-robotron/bin/python -m experiments.ppal.eyes.observe_sprites --source pi \
  --auto-calibrate --profile config/robotron/sprites-draft.json \
  --frames 60 --output "$bundle/results"
tar -czf "$bundle.tar.gz" -C "$(dirname "$bundle")" "$(basename "$bundle")"
printf '\nSend this detection bundle: %s/%s.tar.gz\n' "$PWD" "$bundle"

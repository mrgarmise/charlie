#!/usr/bin/env bash
# Capture only; this never connects to the arcade controller.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p robotron-runs
capture_dir=$(mktemp -d robotron-runs/camera-XXXXXXXX)
.venv-robotron/bin/python -m experiments.ppal.eyes.run_readiness \
  --source pi --frames 12 --interval-ms 250 --output "$capture_dir"
tar -czf "${capture_dir}.tar.gz" -C "$(dirname "$capture_dir")" "$(basename "$capture_dir")"
printf '\nCamera capture: %s/%s.tar.gz\n' "$PWD" "$capture_dir"

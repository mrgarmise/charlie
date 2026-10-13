#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p robotron-runs
bundle=$(mktemp -d robotron-runs/timing-XXXXXXXX)
.venv-robotron/bin/python -m experiments.ppal.eyes.benchmark --source pi \
  --frames 120 --auto-calibrate --output "$bundle/results"
tar -czf "$bundle.tar.gz" -C "$(dirname "$bundle")" "$(basename "$bundle")"
printf '\nSend this timing bundle: %s/%s.tar.gz\n' "$PWD" "$bundle"

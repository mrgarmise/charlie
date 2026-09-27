#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if (( $# > 1 )); then
  echo "Usage: bash setup/observe_robotron_pi.sh [seconds: 1..30]" >&2
  exit 2
fi
seconds=${1:-10}
if [[ ! "$seconds" =~ ^[0-9]+$ ]] || (( 10#$seconds < 1 || 10#$seconds > 30 )); then
  echo "Recording length must be a whole number from 1 to 30 seconds." >&2
  exit 2
fi
seconds=$((10#$seconds))
echo "Show the game border for calibration. Then: 5-second countdown, $seconds-second recording."
mkdir -p robotron-runs
bundle=$(mktemp -d robotron-runs/detection-XXXXXXXX)
status=0
.venv-robotron/bin/python -m experiments.ppal.eyes.observe_sprites --source pi \
  --auto-calibrate --profile config/robotron/sprites-draft.json \
  --seconds "$seconds" --countdown 5 --output "$bundle/results" || status=$?
tar -czf "$bundle.tar.gz" -C "$(dirname "$bundle")" "$(basename "$bundle")"
printf '\nSend this detection bundle: %s/%s.tar.gz\n' "$PWD" "$bundle"

exit "$status"

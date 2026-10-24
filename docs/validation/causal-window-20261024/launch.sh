#!/bin/bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
test "$(git rev-parse HEAD)" = c8db98768776bb43141530f90d331c0222f273eb
test -z "$(git status --porcelain)"
test -f /home/five/.local/share/charlie/development/learning-evidence.sqlite3
charlie_run=$(mktemp -d /home/five/charlie-native-trials/causal-window-20261024-XXXXXXXX)
PYTHONPATH="$PWD" CHARLIE_CONTROLLER_LEASE=required \
  /home/five/Projects/charlie/.venv/bin/python -m experiments.ppal.marathon_robotron \
  --arm --recovery-trial --developmental --learning-projects --ala-learning \
  --max-games 2 --qualified-games 2 --focus 2.0 \
  --root "$charlie_run" \
  --learning-root /home/five/.local/share/charlie/development \
  --campaign-notebook /home/five/.local/share/charlie/development \
  --project-evidence /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3

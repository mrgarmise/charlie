#!/bin/bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
charlie_release=795db6cdddc7c317f513d7939719c7c37f12600d
test -z "$(git status --porcelain)"
git fetch origin refs/pull/9/head
git merge-base --is-ancestor "$charlie_release" FETCH_HEAD
git switch --detach "$charlie_release"
test "$(git rev-parse HEAD)" = "$charlie_release"
test "$(git rev-parse 'HEAD^{tree}')" = f3fce41dbfad944270fa50f78c61e1579e14d865
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /home/five/Projects/charlie/.venv/bin/python -m pytest -q \
  tests/test_visual_readiness.py tests/test_supervised_controller.py -p no:cacheprovider

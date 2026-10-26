#!/bin/bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
charlie_python=/home/five/Projects/charlie/.venv/bin/python
charlie_release=00458579b0fdb5dd81fe5bf6ccaa7d93d8308dbc
test -x "$charlie_python"
test -z "$(git status --porcelain)"
PYTHONPATH="$PWD" "$charlie_python" -c 'from learning.cycle import gameplay_active; assert not gameplay_active(), "Stop active gameplay before updating"'
git fetch origin refs/pull/9/head
git merge-base --is-ancestor "$charlie_release" FETCH_HEAD
git merge-base --is-ancestor bb39d17207ef4b8877b5f8c3e8e847f874ffc2fe "$charlie_release"
git switch --detach "$charlie_release"
test "$(git rev-parse HEAD)" = "$charlie_release"
test "$(git rev-parse 'HEAD^{tree}')" = 86a10bbaf89c4602c436e5c81e1e184d6dd2f942
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" "$charlie_python" -m pytest -q \
  tests/test_supervised_controller.py -p no:cacheprovider

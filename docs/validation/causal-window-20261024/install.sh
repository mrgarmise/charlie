#!/bin/bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
charlie_release=c8db98768776bb43141530f90d331c0222f273eb
test -z "$(git status --porcelain)"
git fetch origin refs/pull/9/head
git merge-base --is-ancestor "$charlie_release" FETCH_HEAD
git switch --detach "$charlie_release"
test "$(git rev-parse HEAD)" = "$charlie_release"
test "$(git rev-parse 'HEAD^{tree}')" = 3d1064d050f3786da38b46013c2ec90fce598338
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /home/five/Projects/charlie/.venv/bin/python -m pytest -q \
  tests/test_causal_window_capacity.py tests/test_supervised_controller.py -p no:cacheprovider

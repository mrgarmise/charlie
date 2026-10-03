#!/usr/bin/env bash
# Update only the already validated isolated worktree. Never create/reset one.
set -euo pipefail
release=${1:?Supply the exact published 40-character commit SHA}
[[ "$release" =~ ^[0-9a-f]{40}$ ]] || { echo 'Exact commit SHA required' >&2; exit 2; }
checkout=/home/five/charlie-ala2-bae659f60b0e
python=/home/five/Projects/charlie/.venv/bin/python
baseline=bae659f60b0e396999caa85b763ce0f1622bd540
test -d "$checkout" && test -x "$python"
git -C "$checkout" diff --quiet
git -C "$checkout" diff --cached --quiet
PYTHONPATH="$checkout" "$python" -c 'from learning.cycle import gameplay_active; assert not gameplay_active(), "Active gameplay: stop handoff"'
git -C "$checkout" fetch origin feature/agency-first-self
git -C "$checkout" cat-file -e "$release^{commit}"
git -C "$checkout" merge-base --is-ancestor "$baseline" "$release"
git -C "$checkout" merge-base --is-ancestor "$release" origin/feature/agency-first-self
git -C "$checkout" merge-base --is-ancestor HEAD "$release"
git -C "$checkout" merge --ff-only "$release"
test "$(git -C "$checkout" rev-parse HEAD)" = "$release"
report=$(mktemp -d /home/five/ala2-handoff-XXXXXX)
cd "$checkout"
"$python" -m pytest tests -q | tee "$report/regression.txt"
"$python" -m learning.readiness --output "$report/readiness.json"
echo "Unarmed handoff reports: $report"
echo 'Physical authorization remains false. No learned physical policy was activated.'

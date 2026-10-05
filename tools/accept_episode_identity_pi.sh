#!/usr/bin/env bash
# Existing normal application, offline only. Never start a camera or controller.
set -euo pipefail
release=${1:?Supply the exact published 40-character SHA}
[[ "$release" =~ ^[0-9a-f]{40}$ ]] || exit 2
checkout=/home/five/charlie-ala2-bae659f60b0e
python=/home/five/Projects/charlie/.venv/bin/python
state=${CHARLIE_LEARNING_STATE:-/home/five/.local/share/charlie/development}
roots=/home/five/Projects/charlie/robotron-runs
test -x "$python" && test -d "$roots"
# Require the original persistent state rather than commissioning a fresh agenda.
test -f "$state/learning-evidence.sqlite3"
cd "$checkout"
test "$(git rev-parse HEAD)" = "$release"
[[ "$(uname -m)" = aarch64 ]] || { echo 'Native Pi aarch64 required' >&2; exit 2; }
report=$(mktemp -d "$state/native-identity-acceptance-XXXXXX")
"$python" -m learning.acquisition --output "$state" --export-history > "$report/pre-run-export.json"
CHARLIE_POLICY_TIMING_OUTPUT="$report/policy-latency.json" CHARLIE_IDENTITY_ACCEPTANCE_ROOT="$roots" "$python" -m pytest \
  tests/test_episode_identity.py tests/test_normal_learning_lifecycle.py tests/test_meditation_yield.py tests/test_developmental_stall.py tests/test_qualified_ppal_policy.py \
  tests/test_retrospective.py tests/test_learning_projects.py \
  tests/test_archive_qualification.py tests/test_meditation_candidate.py \
  tests/test_robotron_score_comparison.py -q --junitxml="$report/native-regression.xml" \
  | tee "$report/native-regression.txt"
args=(--offline --learning-state "$state" --episode-root "$roots"
  --history-root /home/five/charlie-meditation-20261003-01
  --history-root /home/five/charlie-offline-learning
  --learning-turns 12 --learning-interval .05 --learning-budget 10)
"$python" tools/inspect_developmental_progress.py "$state" > "$report/pre-development.json"
# No offline deployment grant is added; physical authority remains false.
"$python" main.py "${args[@]}" | tee "$report/first-twelve-turns.txt"
"$python" tools/inspect_developmental_progress.py "$state" > "$report/first-progress.json"
STATE="$state" REPORT="$report" "$python" - <<'PY'
import os,json
from pathlib import Path
from memory.evidence import EvidenceJournal
j=EvidenceJournal(Path(os.environ['STATE'])/'learning-evidence.sqlite3',read_only=True)
try: rows=[dict(id=r.id,document=r.document,committed_at=r.committed_at) for r in j.records()]
finally:j.close()
(Path(os.environ['REPORT'])/'first-records.json').write_text(json.dumps(rows))
PY
"$python" main.py "${args[@]}" | tee "$report/restart-twelve-turns.txt"
"$python" tools/inspect_developmental_progress.py "$state" > "$report/restart-progress.json"
STATE="$state" REPORT="$report" "$python" - <<'PY'
import os,json
from pathlib import Path
from memory.evidence import EvidenceJournal
state=Path(os.environ['STATE']);report=Path(os.environ['REPORT'])
j=EvidenceJournal(state/'learning-evidence.sqlite3',read_only=True)
try: rows=[dict(id=r.id,document=r.document,committed_at=r.committed_at) for r in j.records()]
finally:j.close()
before=json.loads((report/'first-records.json').read_text())
assert rows==before,'New evidence or unfinished eligible work changed state; inspect retained records before claiming restart dedup'
status=json.loads((state/'development-status.json').read_text())
assert status['physical_authorization'] is False and not status['error']
assert status['last_activity']=='waiting for evidence', 'Bounded work still pending; inspect advancing cursors and blocked dependencies before claiming steady-state acceptance'
(report/'native-result.json').write_text(json.dumps(dict(native=True,records=len(rows),
    restart_exact=True,physical_authorization=False,physical_score_improvement='UNKNOWN',
    identity_conflicts=status.get('identity_conflicts',[])),indent=2))
PY
"$python" -m learning.acquisition --output "$state" --export-history > "$report/post-run-export.json"
echo "Native acceptance evidence: $report"
echo 'Physical gameplay, movement, firmware and learned policy activation remain unauthorized.'

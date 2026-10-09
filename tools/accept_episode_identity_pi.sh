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
# Preserve a post-run history export even when a regression/assertion fails.
trap '"$python" -m learning.acquisition --output "$state" --export-history > "$report/post-run-export.json" || echo "Post-run export unavailable; retain report directory: $report" >&2' EXIT
"$python" -m learning.acquisition --output "$state" --export-history > "$report/pre-run-export.json"
CHARLIE_POLICY_TIMING_OUTPUT="$report/policy-latency.json" CHARLIE_IDENTITY_ACCEPTANCE_ROOT="$roots" "$python" -m pytest \
  tests/test_episode_identity.py tests/test_normal_learning_lifecycle.py tests/test_meditation_yield.py tests/test_developmental_stall.py tests/test_developmental_continuity.py tests/test_developmental_dependencies.py tests/test_qualified_ppal_policy.py tests/test_ppal_policy_continuity.py \
  tests/test_retrospective.py tests/test_preserved_meditation_recovery.py tests/test_learning_projects.py \
  tests/test_archive_qualification.py tests/test_meditation_candidate.py \
  tests/test_robotron_score_comparison.py tests/test_development_resources.py \
  tests/test_development_efficiency.py tests/test_development_profile.py \
  tests/test_controller_sandbox.py tests/test_robotron_exploration.py tests/test_sensory_recording.py tests/test_buffered_recording.py tests/test_sampled_visual_recording.py tests/test_incident_recording.py tests/test_perception_reconciliation.py tests/test_score_human_review.py tests/test_recording_handoff.py tests/test_recording_benchmark.py \
  tests/test_real_time_tactical_learning.py tests/test_robotron_agency_integration.py -q --junitxml="$report/native-regression.xml" \
  | tee "$report/native-regression.txt"
args=(--offline --learning-state "$state" --episode-root "$roots"
  --history-root /home/five/charlie-meditation-20261003-01
  --history-root /home/five/charlie-offline-learning
  --learning-turns 12 --learning-interval .05 --learning-budget 10)
"$python" tools/inspect_developmental_progress.py "$state" > "$report/pre-development.json"
# No offline deployment grant is added; physical authority remains false.
"$python" main.py "${args[@]}" | tee "$report/first-twelve-turns.txt"
"$python" tools/inspect_developmental_progress.py "$state" > "$report/first-progress.json"
"$python" tools/validate_developmental_restart.py "$report/pre-development.json" \
  "$report/first-progress.json" > "$report/native-first-continuity.json"
"$python" main.py "${args[@]}" | tee "$report/restart-twelve-turns.txt"
"$python" tools/inspect_developmental_progress.py "$state" > "$report/restart-progress.json"
# A bounded stop can leave legitimate work runnable. Acceptance verifies exact
# old history plus causal continuation; it reports steady-state separately.
"$python" tools/validate_developmental_restart.py "$report/first-progress.json" \
  "$report/restart-progress.json" > "$report/native-restart-continuity.json"
echo "Native acceptance evidence: $report"
echo 'Restart continuity passed; inspect classification and steady_state_reached before claiming developmental completion.'
echo 'Physical gameplay, movement, firmware and learned policy activation remain unauthorized.'

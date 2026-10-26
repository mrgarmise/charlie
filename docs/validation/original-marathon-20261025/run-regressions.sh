#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
CHARLIE_CHECK_OUTPUT=${1:?supply a fresh validation output directory}
mkdir "$CHARLIE_CHECK_OUTPUT"
CHARLIE_TEST_PYTHON=${CHARLIE_TEST_PYTHON:-python}
"$CHARLIE_TEST_PYTHON" -m pytest -q \
  tests/test_agency_recovery_boundaries.py \
  tests/test_agency_stream_engine.py \
  tests/test_buffered_recording.py \
  tests/test_gameplay_campaign.py \
  tests/test_incident_recording.py \
  tests/test_learning_projects.py \
  tests/test_marathon_camera_session.py \
  tests/test_marathon_deferred.py \
  tests/test_marathon_robotron.py \
  tests/test_meditation_candidate.py \
  tests/test_meditation_yield.py \
  tests/test_native_robotron_trial.py \
  tests/test_native_terminal_forensics.py \
  tests/test_normal_learning_lifecycle.py \
  tests/test_original_marathon_campaign.py \
  tests/test_ppal_agency.py \
  tests/test_ppal_policy_continuity.py \
  tests/test_preserved_meditation_recovery.py \
  tests/test_projectile_agency.py \
  tests/test_prompt_terminal_restart.py \
  tests/test_qualified_ppal_policy.py \
  tests/test_recording_handoff.py \
  tests/test_robotron_actuator_bootstrap.py \
  tests/test_robotron_agency_integration.py \
  tests/test_robotron_hud.py \
  tests/test_robotron_oct24_marathon.py \
  tests/test_robotron_qualified_comparison.py \
  tests/test_robotron_recorded_screen_states.py \
  tests/test_robotron_response_window.py \
  tests/test_robotron_score_comparison.py \
  tests/test_robotron_screen_state.py \
  tests/test_robotron_startup_boundaries.py \
  tests/test_sampled_visual_recording.py \
  tests/test_score_human_review.py \
  tests/test_score_observer.py \
  tests/test_score_tracker.py \
  tests/test_sensory_recording.py \
  tests/test_supervised_controller.py \
  --junitxml="$CHARLIE_CHECK_OUTPUT/regressions.xml" 2>&1 | tee "$CHARLIE_CHECK_OUTPUT/regressions.txt"

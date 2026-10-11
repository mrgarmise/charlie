# Persistent agency recovery — 2026-10-11

## Finding and scope

Base: 708a1f6b5177497f4e765dd1900fa8407d266d8c, verified remote agency branch. Native 5429298 and the failed recording are not accessible from this environment. Native observations below are user reports, not independently reproduced results. SSH could not resolve host charlie.

History recovered: 24001bd (persistent reacquisition), 312e1a0 (continue after SELF loss), a70149c (generic causal VisualAgency/AgencyTracker), 4ffb951 (fresh exposures), 4e29db2 (delayed response endpoints), dfdccde (provisional BODY+FIRE agency), b9624ce (progress supervision), 6ddba67 (independent episode boundary), 8a0198d (recording-qualified restart). The fatal initial acquisition check already existed in a70149c: this is a longstanding integration gap, not a demonstrated new regression. Persistence applied only after successful initial acquisition. b9624ce also introduced a default 60-second uncertainty cutoff. The marathon restart guard correctly refused an unknown boundary; merging another marathon is not the repair.

Recovered existing tracker, reversals, neutral controls, causality qualification, terminal observer, capture journal and restart rules. Newly integrated: initial failure enters recovery; bounded repeated 60/120/240 ms probe batches with 2/3-frame response windows; pulse escalation and unresolved efficacy are explicitly journaled. Healthy SELF uncertainty has no default time limit. Positive gameplay permits discovery without sprite recognition. All fresh probe and gameplay response frames reach the existing terminal observer; early frames previously bypassed it. Camera/controller faults and explicit diagnostic limits still halt safely. No appearance-derived SELF, threshold relaxation, new Executive or learned policy is introduced.

Only play_robotron.py and robotron_agency.py are production changes. Camera files, marathon, immutable recordings, ROMs and persistent developmental state are untouched. The saved native preflight overlay must be preserved. The prior 60 ms behavior remains the recorded baseline; larger pulses are exploratory recovery actions, not measured improvements.

## Host verification

Python 3.12.14; pytest 9.1.1; OpenCV 5.0.0; NumPy 2.5.4. Commands run from the isolated feature/persistent-agency-recovery worktree:

```sh
python -m pytest -q tests/test_ppal_agency.py tests/test_robotron_agency_integration.py tests/test_robotron_startup_boundaries.py tests/test_robotron_developmental_evidence.py tests/test_progress_supervision.py tests/test_agency_recovery_boundaries.py tests/test_marathon_deferred.py tests/test_recording_handoff.py -o faulthandler_timeout=60 --junitxml=agency-final-focused.xml
python -m pytest -v tests -o faulthandler_timeout=45 --junitxml=agency-full-rerun.xml
```

Focused: 127 passed in 106.16 seconds. Full suite: 863 passed, 21 skipped, zero failures/errors in 250.30 seconds. Skips require optional Torch, the full 119-original archive or original October 1 artifacts; retained original-image regressions ran. Passing JUnit receipts and logs are retained here. The first full-suite attempt stalled around desktop-launcher tests and was interrupted; the suspected test passed independently and the complete rerun passed. The interrupted log is retained, and no passing result is attributed to that run. Simulations cover initial failure followed by causal recovery, and never identifying SELF followed by corroborated terminal/attract evidence; both survive more than 60 simulated seconds, issue only one START and satisfy the existing recording-qualified restart checker. Additional tests cover no regions, terminal callback, source/controller failures, invalid response windows and positive gameplay without recognized sprites. Existing ambiguity, respawn, provenance, transport, cleanup and marathon tests are retained. Fixtures are not authentic games or learning improvement.

An intermediate test exposed missing early-frame terminal observation: a short high-score display did not reach the required corroboration count. The integration now delivers those frames without lowering requirements. Initial test iterations also found parser validation still assumed a numeric uncertainty default; corrected before the final suite.

## Guarded native integration — prepare only

Do not switch the current installed checkout wholesale to this branch. Its base camera configuration differs from the native working calibration. Keep the original worktree available for rollback.

```sh
cd /home/five/charlie-camera-calibration
git rev-parse HEAD
git status --short
# Record and back up the complete local overlay, including the untracked backup.
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/home/five/charlie-agency-backup-$stamp
mkdir -m 700 "$backup"
git diff --binary > "$backup/local-changes.patch"
git rev-parse HEAD > "$backup/native-head.txt"
cp -a experiments/ppal/preflight.py "$backup/preflight.py"
# Copy the actual untracked backup named by git status into this directory too.
sha256sum experiments/ppal/preflight.py > "$backup/preflight.sha256"
git fetch origin feature/persistent-agency-recovery
published=$(git rev-parse FETCH_HEAD)
git show "$published":docs/ppal/agency-recovery-20261011/gameplay-only.patch > "$backup/gameplay-only.patch"
# New worktree based on the current native commit, not remote agency base.
git worktree add -b feature/native-persistent-agency /home/five/charlie-agency-recovery HEAD
cp -a experiments/ppal/preflight.py /home/five/charlie-agency-recovery/experiments/ppal/preflight.py
cd /home/five/charlie-agency-recovery
git apply --check "$backup/gameplay-only.patch"
git apply "$backup/gameplay-only.patch"
sha256sum experiments/ppal/preflight.py
# Compare with the saved hash: it must be identical.
git diff --check
```

If apply-check fails, stop and inspect the native source differences; do not force/reset or replace camera files. Copy the three changed/new tests into this native worktree:

```sh
for testfile in tests/test_ppal_agency.py tests/test_robotron_agency_integration.py tests/test_agency_recovery_boundaries.py; do
    git show "$published":"$testfile" > "$testfile"
done
/home/five/Projects/charlie/.venv/bin/python -m pytest -q tests/test_ppal_agency.py tests/test_robotron_agency_integration.py tests/test_robotron_startup_boundaries.py tests/test_robotron_developmental_evidence.py tests/test_progress_supervision.py tests/test_agency_recovery_boundaries.py tests/test_marathon_deferred.py tests/test_recording_handoff.py --junitxml="$backup/native-focused.xml"
```

Verify the existing virtualenv path before invoking it; do not install or replace the native camera stack. Run the existing native regression suite as well before live acceptance. Preserve native version, timestamps, logs, source hashes and camera overlay hash. Native tests and camera-only verification are pending; installation and live acceptance are not claimed.

Rollback: stop the new runner safely, neutralize through its existing cleanup, and use the original /home/five/charlie-camera-calibration checkout and original invocation. Do not delete failed episodes, journals, either worktree or camera backups. No installed service was changed here.

## Live acceptance — separately authorize before running

Keep servos/CAL-1 and any learned physical policy disarmed. Use the user's currently qualified camera setup: manual focus 2.0 and preserved six-view / 12-pixel preflight overlay. This is the current installation's explicit verified configuration, not a new automatic focus default. First verify native preflight camera-only, then authorize the bounded marathon. No --seconds, --game-seconds, or --uncertainty-seconds limit should truncate live games.

The existing launcher already supports play-first and offline reflection. Example after authorization, from the new native worktree, using the existing persistent developmental state:

```sh
python experiments/ppal/marathon_robotron.py --developmental --learning-projects --play-first --max-games 3 --focus 2.0 --learning-root /home/five/.local/share/charlie/development --arm
```

Confirm the native launcher accepts these options before use. Preserve its normal notebook/project identity and baseline. max-games counts attempts, not independently completed games. Inspect every report: confirmed GAMEOVER, accepted episode_end rule, recorder readiness, capture hashes, scores and no uncertain boundary before claiming three complete games. If fewer than three complete, preserve attempts and resolve the blocker rather than relabeling them. Startup escalation must be visibly purposeful and every selected identity supported by causal agency evidence.

play-first automatically hands all three attempts to existing offline processing after gameplay; the Executive, not the operator, selects developmental work. If interrupted, its existing offline resume command is:

```sh
python experiments/ppal/marathon_robotron.py --reflect-session robotron-runs/ACTUAL-FIRST-SESSION --learning-root /home/five/.local/share/charlie/development
```

Never pass --arm to reflection. Inspect durable Executive work states and evaluations: a checkpointed handoff or expired processing budget is not completed meditation. Resume normal offline continuation as needed, respecting thermal limits. Only after first-group completion evidence and the intended offline learning work are verified, run the same three-game command for the second group with the same persistent state. Compare Charlie-originated plans, actions, journal references and independently qualified complete-game SCORE. Do not activate an unqualified candidate. No six-game completion, native acceptance or improvement is demonstrated by this patch.

Remaining limits: actual native source compatibility, camera behavior, pulse efficacy, CPU/thermal cost and live episode boundaries require Pi validation. Attract-only imagery without sufficient terminal or control-challenge evidence must remain unresolved under the existing rules. Live operator STOP and controller/camera health guards remain essential.

# Multi-game boundary recovery — October 11, 2026

## Evidence and recovered implementation

Parent: 0aadb65f4623f668f4e21631ed7b620e128d3ff2, feature/persistent-agency-recovery. Remote feature/agency-first-self remains 708a1f6b5177497f4e765dd1900fa8407d266d8c. Native base 5429298 with integrated agency changes and restored local camera overlay is user-reported; SSH host charlie still fails DNS here. The latest physical session's report and original images are unavailable here. This report distinguishes reproducible code defects from the unverified causal explanation of that session.

History searched across available branches/worktrees: 51a8334 introduced marathon child-game repetition and per-episode meditation; c940dd8 added conservative restart checking; 0da1b84 required evidenced terminal phase before another START; 312e1a0 added persistent SELF recovery; a70149c introduced generic causal agency; 6ddba67 added independent visual terminal/attract sequences; 8a0198d enforced recorder readiness; 95b2787 added play-first handoff to the existing Executive. The current restart orchestrator already contains these capabilities. Earlier loose time-based repetition is not restored.

Two reproducible handoff gaps:

1. The screen classifier returns positive NOT_GAMEPLAY with reason unrecognized_striped_page, but EpisodeEndObserver converted it to UNKNOWN unless a heading was recognized. Positive visual evidence was discarded.
2. Generic VisualAgency completed fresh reversal/neutral probes without delivering a negative discovery result to EpisodeEndObserver. Its causal fallback depended on an older appearance challenge, which cannot provide rejection when no plausible sprite exists. Thus the reported no-plausible-SELF loop has a corresponding reachable blocked state.

These defects explain how restart can be blocked. Exact attribution of the observed physical run still requires its classifier scores, source timestamps and probe records. Changed camera geometry or label-matching failure could also prevent qualifying page evidence; the patch does not pretend that all physical pages will be recognized.

## Small repair

Reuse the existing VisualAgency, EpisodeEndObserver, marathon restart gate, journal and offline Executive. Three production files change: episode_end.py, robotron_agency.py, play_robotron.py. No camera, marathon scheduler, notebook, ROM, controller protocol or physical authority changes.

A discovery receipt lists completed BODY/neutral commands and strictly increasing finite original capture timestamps. Only a full orthogonal/reversal probe with four neutral intervals and no confirmed causal SELF qualifies a negative discovery result. Interrupted, invalid and repeated receipts are rejected. The result means no controllable SELF demonstrated, never game-over. It is journaled and included in boundary evidence.

Unrecognized striped pages now contribute positive non-gameplay evidence, while truly unknown images and gameplay still reset the consecutive count. Negative agency alone cannot end a game. The causal fallback additionally needs three fresh recognized terminal/startable/title observations; an unrecognized striped page cannot authorize the next START. Existing eight-frame requirement, visual transition path and recording-qualified safe_to_restart remain intact. Successful SELF reacquisition clears negative evidence.

Experimental cadence: initial 30-second recovery period, a 120-second fallback horizon, at most 30 seconds per probe batch, then continued bounded observation/probe batches. After the initial period, eight fresh neutral observation frames precede each batch. These values and the existing 60/120/240 ms pulse plan are recorded, not established performance improvements. Expiration changes investigation cadence, never declares game-over, sends START or terminates a healthy live game.

## START assumption

The inspected arcade src/controller.py maps START to BTN_START and tap(); its TCP handler returns OK without game state. It does not implement a live-game START no-op safeguard. This cached source inspection cannot establish behavior of the currently installed emulator/core/ROM. No gameplay was executed to verify that assumption. Speculative START remains disabled; explicit existing session authority, sensory gate and independent episode-boundary evidence remain required.

## Score discrepancy

Preserve user-observed 2,200 and machine-reported 1,100 as conflicting claims, with the original machine record untouched. HUD confidence is derived from digit-pattern distances/temporal evidence, not independently calibrated probability of a correct final complete-game score. Missed final updates, channel assignment, calibration/ROI or digit errors are possible alternatives, not established causes. The latest raw HUD frames and calibration are needed to distinguish them.

Use the existing offline score inspection and independent review pathway, with exact original frame timestamps/hashes and episode identity. Example read-only extraction into a NEW diagnostic directory:

```sh
python -m experiments.ppal.inspect_robotron_score --calibration /ABSOLUTE/EPISODE/calibration.json --output /ABSOLUTE/NEW-REVIEW /ABSOLUTE/ORIGINAL-HUD-FRAME.png
```

Do not overwrite report.json or enter 2,200 as ground truth from recollection. A later independently linked annotation must preserve both original claims. No score-reader implementation change is justified by unavailable images.

## Verification

Host Python 3.12.14, pytest 9.1.1, OpenCV 5.0.0, NumPy 2.5.4; camera/controller fixtures are simulations. Commands:

```sh
python -m pytest -q tests/test_robotron_episode_end.py tests/test_ppal_agency.py tests/test_robotron_agency_integration.py tests/test_marathon_deferred.py -o faulthandler_timeout=60 --junitxml=restart-focused.xml
python -m pytest -q tests/test_restart_discovery_evidence.py tests/test_robotron_episode_end.py tests/test_robotron_startup_boundaries.py tests/test_recording_handoff.py --junitxml=restart-boundaries.xml
python -m pytest -v tests -o faulthandler_timeout=60 --junitxml=restart-full.xml
```

Focused: 73 passed in 96.88 seconds. Boundaries: 33 passed in 0.36 seconds. Additional targeted no-plausible-SELF integration and negative-evidence cases: 11 passed in 7.59 seconds. Tests include death/respawn, unknown images, prolonged live no-SELF, independent moving attract sprites, invalid/duplicate receipts, recognized-page corroboration, denied restart, recorder qualification, and simulated progression to games two and three before offline handoff. A checkpointed simulated reflection is not completed native meditation. Full-suite result is recorded separately when available.

Native tests, native integration, physical restart, six complete games, pulse efficacy and learning improvement remain pending. No physical activity or deployment occurred.

## Guarded native preparation

Do not replace the installed checkout or merge camera branches. Build a new worktree from the current native HEAD and copy its current agency overlay before applying this incremental patch. Preserve every original file and untracked backup.

```sh
cd /home/five/charlie-agency-recovery
git rev-parse HEAD
git status --short
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup=/home/five/charlie-restart-backup-$stamp
target=/home/five/charlie-restart-recovery-$stamp
mkdir -m 700 "$backup"
git rev-parse HEAD > "$backup/native-head.txt"
git diff --binary > "$backup/native-overlay.patch"
for file in preflight.py play_robotron.py robotron_agency.py episode_end.py; do
    cp -a "experiments/ppal/$file" "$backup/$file"
done
# Also preserve the exact untracked camera backup listed by git status.
sha256sum experiments/ppal/preflight.py > "$backup/camera.sha256"
git fetch origin feature/marathon-boundary-recovery
published=$(git rev-parse FETCH_HEAD)
git show "$published":docs/ppal/restart-recovery-20261011/gameplay-only.patch > "$backup/gameplay-only.patch"
git worktree add -b "feature/native-restart-$stamp" "$target" HEAD
for file in preflight.py play_robotron.py robotron_agency.py episode_end.py; do
    cp -a "$backup/$file" "$target/experiments/ppal/$file"
done
cd "$target"
git apply --check "$backup/gameplay-only.patch"
git apply "$backup/gameplay-only.patch"
cmp experiments/ppal/preflight.py "$backup/preflight.py"
git diff --check
for testfile in tests/test_robotron_agency_integration.py tests/test_restart_discovery_evidence.py; do
    git show "$published":"$testfile" > "$testfile"
done
PYTHON=/home/five/Projects/charlie/.venv/bin/python
"$PYTHON" -m pytest -q tests/test_restart_discovery_evidence.py tests/test_robotron_episode_end.py tests/test_ppal_agency.py tests/test_robotron_agency_integration.py tests/test_robotron_startup_boundaries.py tests/test_recording_handoff.py tests/test_marathon_deferred.py --junitxml="$backup/native-focused.xml"
"$PYTHON" -m pytest -q tests --junitxml="$backup/native-full.xml"
```

Verify the existing virtualenv path; do not replace the camera stack. On apply-check or hash mismatch, stop and inspect differences; never force/reset. Archive commands, revision, UTC timestamps, environment, original camera hash and native test receipts. Keep current persistent learning state and recordings untouched. Run camera-only preflight using the already qualified current configuration before deployment. Original worktree remains available; no service switch is included.

Rollback: stop the new runner safely through existing cleanup and return to /home/five/charlie-agency-recovery with its original invocation and preserved camera configuration. Do not delete new or old episodes, journals, local overlays or backups.

## Separately authorized live acceptance

No live gameplay or servo/CAL-1 activity is authorized by this task. Once native tests and camera-only gate pass, obtain separate live gameplay authorization. Preserve the currently verified camera settings; do not inherit the remote base's obsolete 1.30 default. Example uses the previously verified explicit 2.0 position only if it is still valid on this installation:

```sh
"$PYTHON" experiments/ppal/marathon_robotron.py --developmental --learning-projects --play-first --max-games 3 --focus 2.0 --learning-root /home/five/.local/share/charlie/development --arm
```

Observe death-to-next-life, prolonged SELF loss, then the actual terminal/attract transition. Check agency_discovery_result and agency_boundary_observation events, recognized page evidence, exact captures, recording readiness and safe_to_restart for every transition. An attract demo is never a game and a budget expiry is never an ending. There must be three independently confirmed complete episodes; max-games counts attempts, not successes. If a boundary remains unknown, preserve it and obtain its originals rather than forcing START.

play-first uses the existing offline handoff after the group. Preserve notebook checkpoints; inspect normal Executive commissions, evidence dependencies, evaluations and durable completed work. Resume an interrupted offline session via the existing --reflect-session option without --arm. A checkpointed/yielded/resource-blocked handoff does not prove completed meditation. Only after verifying the first three actual completions and the intended offline Executive work, separately authorize/run the second three-game group with the same state. Compare independently qualified complete-game SCORE and Charlie-originated plans; do not activate an unqualified policy or fabricate improvement.

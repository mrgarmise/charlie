# Autonomous camera calibration repair — 2026-10-11

Implementation and offline validation; native acceptance is pending. No installation, physical gameplay, servo/neck motion or developmental marathon was executed.

## Baseline and preservation

The remote `feature/agency-first-self` was independently checked at `708a1f6b5177497f4e765dd1900fa8407d266d8c`. This includes work published after the requested `6ba21fb` baseline. Repair work uses an isolated worktree and branch `feature/autonomous-camera-calibration`; the original branch and unrelated worktrees are preserved. Native checkout HEAD at `/home/five/charlie-ala2-bae659f60b0e` could not be verified: `ssh -o BatchMode=yes -o ConnectTimeout=5 five@charlie ...` fails with `Could not resolve hostname charlie: Temporary failure in name resolution`.

The four original Library PNGs from `robotron-runs/development-20261011-001506/game-01` were materialized unchanged and copied into `tests/fixtures/robotron-calibration-20261011`. Its `provenance.json` records original identities and SHA-256 hashes. Original native journal, notebooks, calibration, recordings and installed code were not modified. The original exposure/preflight JSON files remain unavailable here; their capture timestamps and code revision are not inferred from the directory name.

## Diagnosed causes and correction

1. Marathon supplied an obsolete manual lens seed before exposure; geometry-dependent fine focus could not recover from failed discovery. The default is now `None`, with `--focus` forwarded only when explicitly requested for diagnostics.
2. Initial focus now precedes exposure and geometry. Fresh Picamera2 requests supply pixels and AfState/LensPosition/SensorTimestamp from the same exposure. Hardware-advertised lens bounds are required; no substitute default is used. Continuous AF must report Focused, with finite, in-range, non-repeated timestamps and a stable lens over at least six frames and 0.25 seconds. The bounded scan uses at most 90 frames and 10 seconds, under the existing total preflight deadline. Reported stability is explicitly **not independently qualified sharpness**.
3. The AF-derived position is locked using existing manual controls. Fresh metadata must report Manual/Idle and the commanded lens position within 0.05 dioptres. The established playfield-specific local sweep is retained, now bounded by actual advertised hardware limits. Geometry is rediscovered after refinement; the final manual lock is verified again. Final current-frame geometry must agree within 8 pixels, and existing image-detail gates plus a finite positive current sharpness score must pass before calibration is saved.
4. The Hough candidate selector discarded useful tilted edge fits because its deduplication used midpoint location alone. Repaired clustering compares line intercepts at both frame ends and preserves distinct fits within the existing 12-line budget. The original area limits, complete-edge support, endpoint support, color guard, six stable observations and 8-pixel jitter gate are retained. Failed edge checks stop work on already disqualified candidates.
5. Exposure can retry up to two additional fresh views per EV when attract imagery lacks a qualified arena; failed views and rejection diagnostics are retained. There is still a 12-second sweep bound. Missing arena views cannot qualify screen measurements. A bounded failure remains a failure.
6. Midgame reacquisition continues to neutralize controls first, then runs fresh AF without the startup diagnostic seed. Separate numbered reacquisition directories preserve attempts. Failed calibration cannot silently resume gameplay.

[Original detector diagnostics](original-detector-diagnosis.json) were produced by instrumenting the pre-repair selection logic without changing its criteria. [Repaired diagnostics](repaired-detector-diagnosis.json) record the resulting actual saved-image behavior. EV 0 failed complete support; EV -1 had strong overall edges but lost the top-right endpoint through the selected line fit. With distinct fits retained, EV -1 passes all unchanged support gates. EV -2 and -3 contain no qualifying horizontal/vertical arena line pair. These results qualify one saved rectangle, **not native calibration, image sharpness, perception accuracy or learning improvement**.

## Files

- `experiments/ppal/eyes/autofocus.py`: bounded AF settlement and independently read-back manual lock; specific failure diagnostics.
- `eyes/sources.py`, `observation_camera.py`: same-request AF metadata and fresh capture through the existing recorder/owner.
- `eyes/settle.py`: endpoint-aware line deduplication and rejection diagnostics.
- `eyes/exposure.py`: bounded attract-screen retries and retained search failures.
- `preflight.py`: AF → exposure → stable geometry → screen fine focus → fresh geometry → verified lock → final current image gates; camera-only CLI and failure snapshots.
- `play_robotron.py`, `marathon_robotron.py`: automatic defaults, optional diagnostic input and fresh reacquisition.
- Tests exercise invalid/missing/nonfinite/out-of-range/unstable/repeated metadata, hardware bounds, lock refusal, startup defaults, actual original PNGs, refinement, safe rejection, cleanup and no controller before a failed sensory gate.
- Active operation guides omit the obsolete seed. Historical observations and historical focus fixtures remain; historical analysis guides explicitly mark old values as historical and update future operation commands.

## Native camera-only acceptance — not yet executed

A reachable Pi SSH endpoint is required. Verify native HEAD and worktree status before any changes. Keep the arcade controller disarmed, no marathon running and servos unmoving. Camera ownership safeguards remain in force. Do not kill another camera owner or bypass the lease to force this test.

Prepare a **new** native worktree after fetching the repair branch; this does not replace the installed checkout:

```bash
cd /home/five/charlie-ala2-bae659f60b0e
git rev-parse HEAD
git status --short
git fetch origin feature/autonomous-camera-calibration
repair_sha=$(git rev-parse origin/feature/autonomous-camera-calibration)
repair_dir="/home/five/charlie-camera-calibration-${repair_sha:0:12}"
git worktree add --detach "$repair_dir" "$repair_sha"
cd "$repair_dir"
python -m pytest -q tests/test_robotron_autofocus.py tests/test_robotron_changed_installation.py tests/test_robotron_preflight.py tests/test_robotron_exposure.py tests/test_ppal_settle.py tests/test_robotron_startup_boundaries.py tests/test_sensory_recording.py
run_dir="/home/five/Projects/charlie/robotron-runs/camera-only-$(date -u +%Y%m%d-%H%M%S)"
python -m experiments.ppal.preflight --output "$run_dir" --timeout 120
sha256sum "$run_dir"/*.json "$run_dir"/*.png
```

Use the existing native Python environment with Picamera2/libcamera; do not install host OpenCV wheels on the Pi. Record OS, Python, Picamera2/libcamera versions, actual commit, UTC time and hashes. The camera-only CLI imports no controller or servo interface, exposes no manual-focus argument, and refuses an existing output directory. `--timeout 120` is a bounded native acceptance allowance; normal sensory preflight retains its 60-second default. Native processing latency and success within the normal deadline remain acceptance requirements.

Inspect `sensory-preflight.json`: automatic initial focus, supported lens bounds, Focused fresh scan samples, stable verified Idle manual lock, selected exposure, two qualified six-view geometry stages, final lock, final geometry and detail, `status: usable` and a valid `calibration.json`. Independently inspect `sensory-final.png` and `sensory-playfield.png` to confirm the actual arena and usable detail. Require no controller connection/commands and no servo motion. If autofocus, scene availability or geometry fails, retain all files and report the exact stage/reason; do not supply a historical lens value or fabricate corners.

## Deployment and rollback

Native acceptance is pending, so this branch is **prepared, not installed**. Preserve native HEAD, source status and launcher/service configuration in a timestamped recovery record. Do not reset or overwrite a dirty checkout. Do not overwrite original recordings, developmental state or calibration. After native acceptance and separately authorized deployment, point the existing launcher at the reviewed isolated repair worktree using its existing deployment mechanism; back up the affected launcher/service file first. No firmware, emulator, controller protocol, learning policy or persistent evidence migration is needed. Rollback means restoring that backed-up launcher/service configuration and its previous checkout path; retain new failure/acceptance evidence and the repair worktree. No cleanup command should delete original runs or development state.

## Normal-operation command — future gameplay authorization required

The following is the existing three-game play-first developmental command with automatic optics. It is documented only and **was not launched**. The subsequent learning experiment and its pre-reflection checkpoint require separate authorization and review; the current play-first command automatically enters its existing offline reflection phase after gameplay.

```bash
python -m experiments.ppal.marathon_robotron --developmental --learning-projects --play-first --max-games 3 --retry-wait 5 --learning-root "$HOME/.local/share/charlie/development" --reflection-turns 12 --ala-budget 10 --arm
```

No physical Robotron SCORE improvement or learning improvement is claimed by this repair.

## Host validation

Host: x86_64, Python 3.12.14; pytest 9.1.1, numpy 2.5.4, OpenCV headless 5.0.0.93, Pillow 12.3.0, pyserial 3.5. No native Picamera2/libcamera hardware was emulated as a successful physical calibration.

Final focused command:

```bash
/workspace/scratch/a5d7375d8e4e/camera-test-env/bin/python -m pytest -q tests/test_robotron_changed_installation.py tests/test_robotron_autofocus.py tests/test_sensory_recording.py tests/test_robotron_preflight.py tests/test_robotron_exposure.py tests/test_ppal_settle.py tests/test_robotron_startup_boundaries.py tests/test_marathon_deferred.py --junitxml=/workspace/scratch/a5d7375d8e4e/camera-final-focused.xml
```

Result: **78 passed, zero failures/errors**, JUnit duration 13.144 seconds. [JUnit](focused.xml), [stdout](focused.txt), [source hashes](source-sha256.json). The focused suite includes final boolean-state rejection hardening, actual failed-image checks and real existing geometry/refinement algorithms driven by explicitly simulated camera metadata.

The first broad regression run passed **876 tests, 21 skipped, zero failures/errors**, 215.191 seconds (897 cases). It preceded later added regressions and bounded failed-edge short-circuiting. An initial focused run exposed a missing-controls exception type mismatch; it was corrected to an explicit safe optical failure and subsequent focused runs passed. These intermediate outcomes are retained; neither is native acceptance.

`git diff --check`, compilation of the changed Python modules and `python -m experiments.ppal.preflight --help` passed. Native acceptance and camera-on-Pi performance are pending. Full-suite final evidence is recorded alongside this report.

Final maintained regression: **882 passed, 21 skipped, zero failures/errors** (903 cases), 205.958 seconds; exit 0. Command and evidence hashes: [machine report](VALIDATION.json); [full JUnit](full.xml). Skips are existing optional Torch coverage unavailable on this host. Captured full stdout is partial; the complete JUnit XML and exit code are authoritative. The final focused suite additionally verifies the last strict boolean-state metadata guard. No native acceptance is implied.

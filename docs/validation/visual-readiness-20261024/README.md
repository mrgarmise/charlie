# Coordinated CAL / Active Vision / Robotron recovery — October 24

Runtime: `795db6cdddc7c317f513d7939719c7c37f12600d`.
Tree: `f3fce41dbfad944270fa50f78c61e1579e14d865`.
Direct parent: PR #9 `db3a09765135d8c13f43f8b6ac9854af49bfd4e4`.
Includes the previous `cancel_event` controller correction. The published tree
matches the tested local source, tests and authentic fixture bytes exactly.

## Finding and integration

| Existing mechanism | Previous Robotron boundary | Correction |
|---|---|---|
| CAL-1 durable neck profiles, primary ownership, health/quarantine | Health observations already share ObservedCamera captures; physical profile does not establish readability | Retained unchanged. No physical profile, servo position or commanded-pose estimate can qualify a screen. No calibration motion, activation or firmware change. |
| Active Vision finite qualification, acceptable target quality, released LOCKED `view.json` | `apply_validated_view` existed but Robotron never consumed a LOCKED result | Shared record admission through `eyes.visual_readiness`; optional `--viewpoint` accepts the existing result. Restore/verify manual focus on the task's own camera and confirm current screen support/detail. A suitable current angle terminates preparation without angle optimization or motion. |
| Calibration persistence | Bare promoted polygon was not a readiness certificate; Robotron always prepared optics again | Persist task-qualified visual evidence in `$XDG_DATA_HOME/charlie/vision/robotron-view.json` (default `~/.local/share/charlie/vision/robotron-view.json`). Treat it as a candidate, never current truth. Keep per-episode original records and a content digest. |
| CameraSession / CameraLease / ObservedCamera | One owner was already correct, but between-game calibration reuse lacked a fresh geometry handoff | Keep the same owner/borrower, capture evidence and stream. Reconfirm real visual-readiness records before another game; an invalid view invalidates the session. No second camera, worker, application, monitor service or serial owner. |
| Active Vision DegradationGate and Robotron LiveViewMonitor | Robotron used its separate optical symptom monitor | Consume the existing DegradationGate hysteresis in LiveViewMonitor, using ordinary frames and at most one structural check per second. Direct edge verification is cheap; discover displacement only when that verification fails. Expected page transitions do not establish degradation. Persistent degradation neutralizes and invalidates through the existing path; it does not issue movement permission. |
| Pre-START optics and gameplay recognition | Readiness and gameplay were distinct, but border-error wording sometimes requested active Robotron | Readiness accepts supported attract/instruction imagery and readable detail before START. START/restart decisions, gameplay recognition, causal SELF, terminal evidence and controller gates remain separate and unchanged. |

## Immediate geometry defect and bounded continuity

Authentic third failure at deployed `00458579b0fdb5dd81fe5bf6ccaa7d93d8308dbc`:
`/home/five/charlie-native-trials/controller-interface-20261024-44CFZyS9/development-20261024-221647/game-01`.
The initial discovery qualified six observations at attempt 7, with
**5.994313991210762 px** jitter. Focus remained 2.0. `run_preflight` nevertheless
discarded this qualification and started another six-consecutive-view search.
Attempt 8 detected the same screen; 9–26 missed candidate discovery; 27–31
recovered five stable detections before the 24-attempt final search expired.
Zero confirmed games; the original report remains immutable.

When focus is unchanged, retain the qualified calibration and require **three
consecutive fresh supported/readable observations**, within the existing
24-attempt geometry budget and sensory deadline. Full discovery still runs during
confirmation and rejects a supported rectangle displaced beyond the existing
12 px limit. If Hough candidate enumeration misses, independently measure the
qualified rectangle on the current pixels with the detector's **same** four-edge
contrast and endpoint support code. No polygon or confidence value substitutes
for those observations. All corners must remain in frame; blank, clipped, severely
blurred, shifted, repeated or metadata-deficient reuse observations fail.
The current playfield must have at least 50 detail pixels and meet Active Vision's
existing sharpness/target-quality requirements.

Changed focus still requires full geometry rediscovery. Final image confirmation
uses the same continuity mechanism, rather than reinstalling the single-frame
candidate-discovery veto. Bound all fresh reads, including manual-focus metadata
verification, by the existing sensory deadline. Failed current observations are
retained without overwriting earlier rejection images.

A persisted/Active Vision handoff additionally verifies hardware lens limits,
six stable fresh manual-lock metadata samples and three current structural/detail
samples. A failed candidate is diagnosed and falls back to bounded fresh optical
preparation; it cannot authorize START. A successful candidate avoids another
exposure sweep and freezes the currently measured exposure and white balance
where supported. No CAL profile is promoted to a visual certificate. Simulation,
unreleased locks, malformed records and bare polygons cannot pass record admission.
The original supplied Active Vision file is never overwritten.

## Authentic evidence and software verification

- October 22: existing `tests/fixtures/native-border-20261022` retains the actual
  final border miss and sensory history. That failed frame alone still cannot
  qualify its claimed edges. A bounded replay with subsequently supported archived
  imagery confirms current support without accepting a stale rectangle.
- October 24, first integration: `tests/fixtures/native-self-20261024` preserves
  the successful sensory report/final image and original `cancel_event` failure.
  The actual readable instruction image is classified `startable`, not gameplay;
  visual readiness is demonstrated separately from SELF/controller acceptance.
- October 24, third failure: `tests/fixtures/native-geometry-20261024` preserves
  the exact failed PNG, original 31-entry geometry history and failure report.
  Regression reproduces the discarded-lock failure with that history, then uses
  the same history plus independent photometry of the authentic failed frame to
  confirm continuity. Diagnostic-history replay and repeated archived pixels with
  synthetic advancing timestamps are explicitly software fixtures, not a claim
  about unarchived intermediate native exposures or a successful physical run.
- Each fixture has original path and SHA-256 provenance. Source reports/images
  remain byte-identical and are never rewritten by tests.

Combined CAL-1 / Active Vision / Robotron / controller selection:
**324 passed, 1 skipped in 189.99 s** ([output](final-tests.txt)). The skip is the
optional full 119-frame archive test; the retained authentic frame tests run.
Final handoff/recording selection after exposure-lock/failure-report refinements:
**35 passed in 35.83 s**, including all **29** new readiness regressions
([output](handoff-tests.txt)). The exact installation selection also passes **42 tests in 30.44 s**
([output](install-smoke.txt)). These selections overlap and are not summed.

The combined selection includes calibration integration, neck calibration,
Active Vision, readiness, Robotron preflight/autofocus, archived geometry,
final-image recovery, camera/session lifecycle, deferred marathon/recovery,
integration contracts, the supervised controller, streaming SELF/capture,
progress supervision and sensory recording. No live hardware/controller service
was contacted. Earlier development receipts are retained: [initial integration
failures](initial-integration.txt) were missing cache-directory creation, a
synthetic degradation displacement below the existing threshold and a mock
without structural calibration; those were corrected. [Earlier discovery /
Active Vision selection](discovery-active-vision.txt) also retains its scope.

Python compilation, source/handoff whitespace checks and `bash -n` pass.
Raw pytest trace whitespace is retained in the receipt files.
Exact marathon launch arguments, including `--viewpoint`, parse with execution
intercepted immediately after argument parsing. The install and launch commands
were not executed on the physical Pi.

## Minimal pinned installation

With gameplay stopped, run in the existing ordinary Charlie Pi terminal.
No pip reinstall, service replacement, review.json, focus sweep, servo movement
or firmware deployment is needed. Preserve edits if the clean-checkout check
fails. Existing origin must remain `mrgarmise/charlie`.

```bash
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
```

Require **42 passed**. This software check uses archived/synthetic inputs and
starts no hardware. The next native launch automatically uses the shared handoff
and corrected first-run geometry path. No saved profile has to be manufactured.
If an existing genuine released Active Vision lock is available, the unchanged
marathon entrypoint optionally accepts `--viewpoint /absolute/path/to/view.json`;
a physical neck-calibration file is not such a lock.

## Existing integrated native launch and remaining verification

The existing bounded launch remains the same, with a new pin and fresh evidence
root. It retains the newest integrated Executive/ALA/PPAL paths and existing
learning databases; no new policy/model artifact is activated. After installation:

```bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
test "$(git rev-parse HEAD)" = 795db6cdddc7c317f513d7939719c7c37f12600d
test -z "$(git status --porcelain)"
test -f /home/five/.local/share/charlie/development/learning-evidence.sqlite3
charlie_run=$(mktemp -d /home/five/charlie-native-trials/visual-readiness-20261024-XXXXXXXX)
PYTHONPATH="$PWD" CHARLIE_CONTROLLER_LEASE=required \
  /home/five/Projects/charlie/.venv/bin/python -m experiments.ppal.marathon_robotron \
  --arm --recovery-trial --developmental --learning-projects --ala-learning \
  --max-games 2 --qualified-games 2 --focus 2.0 \
  --root "$charlie_run" \
  --learning-root /home/five/.local/share/charlie/development \
  --campaign-notebook /home/five/.local/share/charlie/development \
  --project-evidence /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3
```

Standing gameplay authorization and existing camera/controller/resource/terminal
safety boundaries remain in force. No extra qualification project or physical
servo/firmware step is introduced. These software changes are implemented and
published; the outstanding native check is the normal bounded gameplay attempt
on this runtime: fresh accepted readiness, real SELF/control/capture cadence,
authentic Game 1 completion, eligible retained learning and genuinely playable
Game 2. Those outcomes cannot be established by archived-frame or software tests.
The three preserved failed launches still establish zero completed games; no
new E1/P1/I1, learned-policy performance or physical acceptance is claimed.
PR #9 remains draft and unmerged. No physical deployment, gameplay or device
movement was performed for this correction.

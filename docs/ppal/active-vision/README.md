# Active Vision — physical before digital

## Current recovery successor: permanent safe motion authority

The current implementation starts from published recovery `8777955`. See
[safe-motion-authority.md](safe-motion-authority.md) for the authoritative safety
contract, code-only Pi deployment, gated firmware procedure and rollback.
Physical authorization remains false; no assembled-head envelope or cleared
electrical gate is shipped. Telemetry reports commanded estimates, never
measured servo positions. Primary ownership terminates optimization; returning
requires a degradation permit and independent local physical arming.

The remainder records the earlier Active Vision checkpoint and its historical
validation. Its old physical integration/deployment instructions are superseded
by the permanent authority document above. Existing evidence is retained.

This branch is independent of ALA-2. Its verified base is
`bae659f60b0e396999caa85b763ce0f1622bd540`. It does not deploy to the Pi,
change ALA-2 operational policy, arm gameplay, or initiate hardware motion.

## Implemented behavior

`eyes.active_vision.ActiveVision.run()` is a finite synchronous process:
ACQUIRE → OPTIMIZE → VALIDATE → LOCKED. An error enters FAILED; interruption
enters STOPPED. A run cannot be restarted. Reacquisition uses a new instance
and a new evidence directory.

Acquisition starts with the current full camera image and, for hardware, the
current commanded servo pose estimate. It assumes neither a crop nor a winning angle.
A bounded serpentine search explores when no complete target is found. Search
budgets are finite: exhaustion fails without handing an invalid view to a task.
The rectangle detector handles rotated quadrilaterals; the Robotron adapter
reuses the existing complete-border detector. Generic rectangle discovery is
geometric discovery, not semantic recognition of every possible object. A task
can supply a detector returning the same Target contract.

Optimization experiments with adjacent pan/tilt positions, retaining measured
improvements and returning from unsuccessful trials. Quality prioritizes complete
edge support, visible area, and clipping margin over residual rotation and
opposite-edge perspective imbalance. It measures repeated corner stability
before accepting a trial. A movement penalty prevents gratuitous adjustments.
Task-local sharpness and stability must pass final validation. Pan/tilt does not
remove the distortion caused by camera location; homography correction remains
available after physical adjustments reach a local optimum or their budget.

Existing screen-focus search reads a seed from current camera metadata and
measures the target at nearby lens positions. It finishes in manual focus.
The initial camera uses its existing autofocus implementation for discovery;
severe blur can prevent discovery and exhaust acquisition. No general full-range
blind focus recovery or camera relocation is claimed in this checkpoint.

Every measured raw/corrected image and its corner correction parameters are
recorded in a fresh directory. Focus experiments also preserve paired images.
`decisions.jsonl` includes successful and unsuccessful experiments, normalized
geometry, sharpness, confidence, jitter, and decision rationale. An optional
existing EvidenceJournal receives the same events with simulation provenance.
The supplied journal is caller-owned; no competing learning store or selector
is created. HeadSearchMemory remains the existing face-search memory component.

LOCKED saves `view.json`. Success returns only after STOP, camera closure,
lease release, and passive-publication worker termination. Release failure
invalidates the lock file. No acquisition/detection/optimization worker survives
success. Controller heartbeat remains caller-owned when sharing an existing
controller; the standalone runner closes its own controller.

## Safety

Physical execution requires explicit authorization before serial/camera objects
are created. Only the existing RP2040Controller transport and PiCameraSource are
used. The existing camera lease is mandatory for physical runs; unavailable
cooperative ownership fails closed. Active Vision never steals a primary task's
active lease. The primary task must yield before optimization begins.

Travel bounds respect firmware limits (pan 0–180°, tilt 20–160°); each adjustment
is at most 6° by default and bounded by configured limits. LOOK now optionally
carries degrees/second. The existing firmware Servo implementation executes the
slew limit, rather than relying solely on host command spacing. Two-argument
LOOK, TRACK, face search, and existing callers remain supported. Fractional LOOK
angles use the existing protocol float parser.

STOP now freezes current targets and velocities on both heads. Servo updates
cannot overshoot a requested target. The communication watchdog freezes servo
travel on link loss and preserves its link-loss flag across loop iterations.
Disconnects, interrupts, failed commands, unsettled pose, and unstable views
abort rather than claim success. Electrical disconnect cannot guarantee an
instantaneous physical stop; the existing firmware heartbeat timeout is 10 s.

VIEWPOINT reports both heads' current commanded servo positions, motion state,
behavior mode, and STOP_HOLD capability. These are firmware position estimates,
not encoders or proof of mechanical movement. Active Vision requires stationary,
aligned heads at startup, validates pose after bounded moves, and verifies STOP
before lock. It refuses old firmware instead of assuming STOP is sufficient.
Real-world backlash, mounting geometry, servo travel, camera identity, and
mechanical clearance remain physical validation requirements.

## ALA-2 integration contract (v1)

Do not merge until both projects have stable published checkpoints. ALA-2 owns
primary-task lifecycle, experiment scheduling, authorization, and operational
learning deployment. Active Vision owns only finite viewpoint preparation.

| Boundary | Contract |
|---|---|
| Controller | Existing RP2040Controller: `look(pan, tilt, rate=...)`, `stop()`, `connected`, `viewpoint_status()`; no second serial controller |
| Camera | Existing PiCameraSource and CameraLease; source constructed after task yields; `read_fresh`, `lens_position`, `set_manual_focus`, `close` |
| Detector | Callable on full RGB PIL image → Target; ValueError means unknown/unavailable; task supplies semantic target policy |
| Result | `charlie-active-vision-v1`: LOCKED, resources_released, simulated, pose, focus, calibration, target, jitter, samples |
| Primary handoff | After its own lease acquisition, task calls `apply_validated_view(source, record)` to restore manual focus and get existing Calibration; simulated/incomplete results are rejected |
| Restart validation | Camera recreation can reset controls. Task must recheck fresh geometry/optics before starting or resuming dependent actions; never trust an old file as current geometry |
| Degradation | Primary task supplies fresh structural target corners and timestamps to DegradationGate; expected transitions suppress requests; sprite motion/global scene flow is not input |
| Reacquisition | Gate returns continue, request_permission, suspend_and_request, or reacquire; scheduling authority is the primary task, not the gate |
| Learning evidence | Optional existing EvidenceJournal events (`producer=ActiveVision`, version 1, category active_vision); no edits to LearningExecutive, learned policy, or its deployment guards |
| Passive viewer | Existing PassivePublisher submits raw/corrected frames and Active Vision metadata; existing Viewer reads an additional observational status file and never captures an active camera |

DegradationGate uses persistent corner displacement and a separate longer missing
geometry threshold. Temporary occlusion and expected level transitions do not
cause immediate reacquisition. Duplicate timestamps and invalid geometry cannot
be mistaken for independent camera-motion evidence. Persistent severe loss
requests suspension even during cooldown; movement still requires task permission.
Persistence counts fresh observations, so the task should tune thresholds to its
structural-observation cadence and explicitly identify expected transitions.

**Deferred integration:** this checkpoint provides tested adapters but does not
insert itself into unfinished ALA-2 play_robotron/marathon execution. At stable
checkpoints, the task must add its yield/run/reopen/manual-focus/fresh-validation
sequence, supply structural observations, and handle gate responses. Changes to
camera source, lease ownership, controller signatures, target detector shape,
LearningExecutive evidence schema, or task transition events require contract
review before merging. Neither branch should modify the other's head.

## Reproduce without hardware

From an environment containing pytest, NumPy, Pillow, OpenCV, and pyserial:

```bash
python -m pytest -q tests/test_active_vision.py tests/test_active_vision_firmware.py tests/test_passive_eyes.py
python -m experiments.ppal.eyes.simulate_active_vision --output /tmp/charlie-active-vision-new-run
```

The simulator changes target geometry with physical pose and blur with focus.
Only the simulated world knows its optimum; the optimizer receives observations.
Tests also change hidden optima to verify that the optimizer is not replaying a
hardcoded successful pose. Each run rejects an existing output directory.
The committed simulation bundle contains actual paired observations and decisions.
Its outcomes are simulation evidence, not successful physical optimization.

## Future deployment procedure — not executed

First review both published checkpoints and the integration contract. Create a
separate Pi checkout, preserving the original checkout, evidence, archives, and
local modifications:

```bash
git clone --single-branch --branch feature/active-vision https://github.com/mrgarmise/charlie.git /home/five/charlie-active-vision
cd /home/five/charlie-active-vision
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pytest -q tests/test_active_vision.py tests/test_active_vision_firmware.py tests/test_passive_eyes.py
```

Use a new destination if that directory already exists. Pi camera libraries
must remain available through system packages. Install missing test dependencies
in this isolated environment, not by overwriting the operational environment.
No physical execution should occur merely because software tests passed.

**Only after explicit physical authorization:** arrange servo power and clearance,
stop the primary task, and install this branch's RP2040 firmware using the existing
`python -m tools.sync_rp2040` workflow. That sync reboots the board, whose normal
startup can home the servos; it is itself a physical action requiring authorization.
Verify the board and camera mounting before permitting experiments. Old firmware
is refused by the capability gate. Then a separately authorized finite run is:

```bash
.venv/bin/python -m experiments.ppal.eyes.run_active_vision --target robotron --output robotron-runs/active-vision-unique-session --authorize-head-motion
```

The runner installs interrupt handlers, uses the existing controller and camera
lease, publishes to Charlie Eyes, saves evidence, and exits after lock. It never
starts Robotron, shoots, runs a marathon, or changes ALA-2 deployment authorization.
Mint should use its existing passive-viewer connection; no manual aiming controls
are introduced. Ordinary primary-task continuation requires the deferred stable
integration sequence above.

## Acceptance status

| Criterion | Independent software evidence | Physical status |
|---|---|---|
| Discover/maintain target | Full-FOV rotated discovery; finite acquisition and clipping failure | Requires varied real positions, blur, occlusion, and target identity checks |
| Select/evaluate adjustments | Deterministic measured experiments and rejected-trial restoration | Requires servo/camera response checks |
| Improve measured quality | Hidden-optimum worlds improve without supplied solution | No physical improvement claimed |
| Terminate at validated view | LOCKED and failed-lock resource tests | Requires real stability/focus and STOP confirmation |
| Primary without optimizer overhead | Finite runner; released camera; no optimizer workers | Requires stable ALA-2 integration and live handoff |
| Meaningful degradation | Corner persistence, transitions, invalid/duplicate evidence, cooldown tests | Requires representative gameplay structural observations |
| Permitted reacquisition → LOCKED | Permission gate and second finite simulated acquisition | Requires task scheduling integration and live repeat |
| Explain outcomes | Paired images, correction parameters, JSONL events, EvidenceJournal adapter | Requires real evidence bundle |

## Independently executed validation

Final complete repository test suite: **492 passed, 19 skipped, 0 failures** in
69.45 seconds. Python 3.12.14 / NumPy 2.2.4 / OpenCV 4.10.0 / Pillow 12.3.0;
x86_64, no Torch. The expected skips cover Torch-dependent tests. This is desktop
software verification with the Pi's reported NumPy/OpenCV versions, not execution
on ARM or physical validation. The 31 new Active Vision tests cover simulated
experiments, primary processing after lock, camera ownership, interruption,
release failure, permission/cooldown behavior, multiple hidden optima, protocol
compatibility, actual firmware STOP/slew updates, and watchdog loop execution
using simulated dependencies.

The published simulation bundle was generated with NumPy 2.5.3 / OpenCV 5.0.0.
It reports 2.475621 → 2.603696 quality, three retained improvements, four rejected
trials, 11 movements, 66 observations, manual lens position 1.5, camera release,
and zero background optimization workers. No gameplay-score claim follows from
this arbitrary viewpoint-quality scale. See `validation.json` and
`simulation-01/simulation-summary.json` for machine-readable provenance.

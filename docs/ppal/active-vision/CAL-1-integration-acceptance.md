# CAL-1 permanent application integration and acceptance

Repository: `mrgarmise/charlie`; branch: `feature/active-vision`.
Preserved parent checkpoint: `ff195c688e6aae98968d3fbe45908bb407beaa39`.
This report belongs to the published integration commit containing this file.
Physical authorization: **FALSE**. No operational Pi checkout, backup or Pico
was changed. No firmware installation, servo power, physical PWM, physical
movement, calibration or gameplay was performed. All execution used host mocks.

## Recovered implementation and bounded changes

The checkpoint already had the permanent RP2040 `Calibration` state machine:
`main.py` constructs one `ServoController`, `commands.py` dispatches CAL and
CAL_STATUS, and the normal scheduler calls `servos.update()`. Calibration uses
the controller's existing PWM creation/disable paths; there is no calibration
actuator controller. Scanner/behaviors, display, heartbeat, protocol, watchdog,
STOP, session/epoch checks and Robotron commands remain installed.

Existing v1 profile schema, durable immutable versions, independent physical
qualification, combined-axis envelope, positive margins/rate limits,
quarantine/unclean-operation markers and fail-closed reboot behavior were kept.
The prior host compilation/telemetry correction was not reimplemented.

Missing application integration is now supplied by one reusable adapter,
`hardware/calibration_service.py`:

- It projects durable pending requests from the existing EvidenceJournal, not
  a replacement memory system. Reasons include missing, invalid, incompatible,
  quarantined, degraded and uncertain calibration. Repeated evidence is retained
  under an existing request; explicit dismissal remains durable for the same
  diagnosis. A new diagnosis can generate another request.
- Reflection proposes the existing supervised-recalibration method to the
  Learning Executive. The Executive can request/discover it, but has no motion,
  qualification, profile-selection or quarantine-clearing handler. Projects
  remain ineligible without external authorization/resources. A crash between
  request commitment and Reflection publication is recovered after restart.
- A completed session does not resolve a request. Resolution requires a new,
  externally selected independently qualified profile; dismissal requires an
  explicit actor, rationale and evidence. Executive project dispositions mirror
  the durable request disposition and recover after an interrupted update.
- `Deck.request_calibration()` and the normal Pi `main.py` attach the service
  to the existing RP2040 link. `VisionStimulus` reuses its already captured frame
  and detector result; it creates no camera, inference worker or actuator owner.
- The existing console delegates to the adapter, adds offline request discovery
  and archives its sessions in that lifecycle. Its UART/evidence polling stays
  on one thread, avoiding SQLite access from a second poller thread. The existing
  RP2040 communications heartbeat is retained.

The RP2040 keeps its bounded event buffer. A fresh run identifier plus an
acknowledgment of the durably archived terminal predecessor permits a new buffer.
Unacknowledged full logs still block; stale run/step/epoch permits are not reused.
This removes the former lifetime-buffer reboot requirement without reinstalling
firmware. CAL dispatch returns the ordinary behavior scheduler to IDLE so it
cannot run an old scan alongside a supervised session.

Two fail-closed edge cases were tightened during this audit: supervisor shutdown
now sends STOP even if its status read or evidence write fails; Pi profile
activation/loading rejects an embedded calibration ID that disagrees with the
selected immutable filename, matching the RP2040 loader.

## Primary-task health and resource ownership

Active Vision can use the same service-backed NeckHealth instance. Its physical
runner requires the durable Pi profile to agree with the RP2040 profile before
optimization. Command-to-view discrepancy produces a persistent request and
quarantine through the existing monitor and STOP path.

Normal Pi vision feeds the service once per second. `ObservedCamera` also accepts
that service on its existing read path. Robotron's existing runner attaches it
when `--neck-state-directory` or `CHARLIE_NECK_STATE` specifies the installed
state, acquires existing PRIMARY neck ownership, and leaves the neck stationary.
It does not acquire another camera lease or start another inference process.
Without this setting, the existing digital-only Robotron runner remains unchanged;
a deployment using the calibrated neck must provide the shared state setting.

Unexpected commanded movement, changed commanded pose, wrong owner, invalid
positions, missing telemetry or profile disagreement revokes permission and
requests supervised recovery. A supplied fresh fixed-scene reference also feeds
the existing persistent viewpoint-shift check. All reports retain alternative
explanations and `mechanical_fault_confirmed=False`.

**Observation limit:** the color target can move, and Robotron's saved playfield
polygon is not a fresh measurement. Neither is invented as neck displacement.
Available capture provenance is retained, but these primary paths have no fresh
fixed-scene displacement estimator. Passive tracking loss by itself does not
diagnose a mechanical fault. Repeated inability to supervise an energized neck
fails closed; stationary, de-energized passive/digital operation can continue.
This conservative integration does not demonstrate mechanical diagnosis or live
mount-shift detection when reliable fixed references are unavailable.

## Acceptance evidence

| Criterion | Implemented and independently host-tested | Still pending |
| --- | --- | --- |
| Existing application retained | Real RP2040 main scheduler exercised with fake IO; PING, display feedback, progress, message, SESSION and disarmed CAL rejection; normal Pi main exercised with one camera/idle behavior | Native Pi/MicroPython execution and display/protocol timing |
| Sole PWM owner | Existing ServoController used throughout; only GP4/GP5 fake PWMs; Head B inactive | Actual output/cutoff measurements |
| Executive requests without authority | Durable typed evidence, blocked Reflection projects, restart recovery, dismissal/resolution | Live operational supervision workflow |
| Repeated supervised sessions | 25 complete simulated movement sessions through the same installed controller and UART, unique logs; console restart/reentry regression | Physical commissioning sessions |
| Restart persistence | Requests reconstructed from SQLite; existing profile/quarantine/unclean-reboot tests retained | Native filesystem/power-loss behavior |
| Uncertain calibration fails closed | Missing/malformed/incompatible/aliased profiles, stale grants, health/persistence failures, STOP/watchdog and uncertainty regressions | Physical binding/sag/noise/fault cases |
| Primary health shares resources | Existing capture/detector reused; telemetry and supplied fixed-reference checks; no added camera/inference thread | Reliable task-specific live fixed-scene evidence |
| No reinstall between sessions | Installed CAL protocol repeats with archived terminal runs; new profiles are metadata | Native repeated use and profile transfer/reboot |
| Physical enable gates disabled | Shipped configuration unchanged and asserted in regression tests | Separate authorization required for any change |

All four shipped profile/input fields remain `None`: `CALIBRATED_ENVELOPE`,
`CALIBRATION_PROFILE`, `LOCAL_ARM_PIN`, `PERSISTENT_PROFILE_DIRECTORY`.
`ELECTRICAL_GATE_CLEARED`, `CALIBRATION_INPUT_ENABLED` and
`AUTONOMOUS_MOTION_ENABLED` remain **False**. No test fixture is a physical profile.

## Independent validation record

Environment: x86_64, Python 3.12.14; pytest 9.1.1; NumPy 2.2.4; OpenCV headless
4.10.0; Pillow 12.3.0; pyserial 3.5; psutil 7.2.2. Torch is unavailable.
Commands ran in a new isolated clone and virtual environment, not the user's
operational Pi checkout. Baseline: 172 focused tests passed in 37.19 seconds.
Intermediate integration runs: 100 CAL-1 tests passed in 4.92 seconds; 199 focused
tests passed in 39.06 seconds; 649 broader tests passed and 19 skipped in 67.32
seconds. Subsequent reruns cover the final console/identity/Active Vision changes.

Final independently executed results:

| Check | Actual outcome |
| --- | --- |
| Six-file focused integration suite | **207 passed**, 0 failures/errors/skips, 40.29 seconds |
| CAL-1 subset of that suite | **112 passed**: 77 existing calibration tests + 35 integration cases |
| Broader available suite | **656 passed, 19 skipped**, 0 failures/errors, 69.19 seconds |
| Python compilation | Exit 0 |
| Whitespace and indentation checks | Exit 0 |
| Robotron, Active Vision and calibration console `--help` | Exit 0; no hardware opened |

The 19 existing skips are Torch-dependent ALA foundry/cycle/operational/portable/
refinement tests, not CAL-1. No host test establishes physical qualification or
native execution. Machine-readable results and source hashes are preserved in
[validation-cal1-integration.json](validation-cal1-integration.json).

The two edge cases were independently reproduced using the preserved checkpoint's
`hardware/neck_calibration.py` loaded by `git show ff195c6:hardware/neck_calibration.py`
into an isolated module and fake temporary state. A valid hashed selection pointing
at a profile with a different embedded ID was accepted as `SIMULATED_002` by the
baseline and refused by the correction (`profile identifier mismatch`). Injecting
an evidence-write `OSError('disk full')` during supervisor close produced **0 STOP
calls** in the baseline and **1 STOP call** in the correction. Regression cases
cover aliasing, non-object malformed documents and status/evidence shutdown failures.
No failing focused or broader run is omitted; the executed suites passed. This
audit found those defects by inspection and isolated reproduction, not a reported
failure of the existing suite.

```bash
../cal1-env/bin/python -m pytest -q \
  tests/test_calibration_integration.py tests/test_neck_calibration.py \
  tests/test_active_vision_firmware.py tests/test_head_recovery_lockout.py \
  tests/test_active_vision.py tests/test_passive_eyes.py \
  --junitxml=../cal1-integration-focused-final.xml
../cal1-env/bin/python -m pytest -q -rs tests \
  --junitxml=../cal1-integration-broad-final.xml
../cal1-env/bin/python -m compileall -q main.py behavior_manager.py \
  attention behaviors hardware memory motion rp2040 stimulus tools vision experiments
git diff --check
../cal1-env/bin/python -m tabnanny hardware/calibration_service.py \
  hardware/neck_calibration.py memory/learning_projects.py motion/controller.py \
  vision/stimulus.py rp2040/calibration.py rp2040/commands.py main.py \
  experiments/ppal/observation_camera.py experiments/ppal/play_robotron.py \
  experiments/ppal/eyes/active_vision.py experiments/ppal/eyes/run_active_vision.py \
  tools/calibrate_neck.py tools/sync_rp2040.py \
  tests/test_calibration_integration.py tests/test_neck_calibration.py
../cal1-env/bin/python -m experiments.ppal.play_robotron --help
../cal1-env/bin/python -m experiments.ppal.eyes.run_active_vision --help
../cal1-env/bin/python -m tools.calibrate_neck --help
```

Formatting validation is whitespace/indentation validation; this repository has
no configured Black/Ruff check. No unexecuted formatter or native check is claimed.

## Controlled upgrade and migration — procedure only

### Code-only Pi staging (no hardware access)

Set `CAL1_RELEASE_SHA` to the full published SHA from the completion handoff.
Use a new directory; keep the operational checkout and every backup untouched.

```bash
CAL1_RELEASE_SHA='FULL_PUBLISHED_INTEGRATION_SHA'
CAL1_STAGE="$HOME/cal1-integration-stage"
test ! -e "$CAL1_STAGE" || exit 1
git clone --single-branch --branch feature/active-vision \
  https://github.com/mrgarmise/charlie.git "$CAL1_STAGE"
cd "$CAL1_STAGE" || exit 1
git checkout --detach "$CAL1_RELEASE_SHA"
git merge-base --is-ancestor ff195c688e6aae98968d3fbe45908bb407beaa39 HEAD || exit 1
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install pytest numpy==2.2.4 opencv-python-headless==4.10.0.84 Pillow pyserial psutil
.venv/bin/python -m compileall -q main.py hardware memory motion rp2040 tools vision experiments
.venv/bin/python -m pytest -q tests/test_calibration_integration.py tests/test_neck_calibration.py \
  tests/test_active_vision_firmware.py tests/test_head_recovery_lockout.py \
  tests/test_active_vision.py tests/test_passive_eyes.py
.venv/bin/python - <<'PY'
from pathlib import Path
p = {}
exec(Path('rp2040/motion_profile.py').read_text(), p)
for key in ('CALIBRATED_ENVELOPE', 'CALIBRATION_PROFILE', 'LOCAL_ARM_PIN', 'PERSISTENT_PROFILE_DIRECTORY'):
    assert p[key] is None, key
for key in ('ELECTRICAL_GATE_CLEARED', 'CALIBRATION_INPUT_ENABLED', 'AUTONOMOUS_MOTION_ENABLED'):
    assert p[key] is False, key
PY
```

Do not run the live Pi main, sync helper, supervisor console or gameplay as part
of staging. Native code-only execution is a separate check from this host record.

### Durable state migration

Choose one stable absolute Pi directory, normally
`$HOME/.local/share/charlie/neck`, and configure `CHARLIE_NECK_STATE` for each
installed application. It contains `requests.sqlite3` and `profiles/`. New
request records are append-only; old JSONL/session files stay at their original
paths. Preserve their hashes and reference them as evidence rather than rewriting
their provenance or pretending old diagnostic logs were completed requests.

No profile schema conversion is needed: v1 remains v1. Inventory existing Pi and
Pico profiles, activation histories, quarantine and `.running` markers before
migration. Copy immutable files additively into the chosen Pi `profiles/` directory;
if a destination exists, require byte identity or stop. Never overwrite a
different version, remove markers, synthesize qualification or choose an older
profile to evade quarantine. Copy an externally reviewed valid selection pointer
last. Missing/unqualified selections simply produce a pending request.
Keep a fresh uniquely named snapshot of old state and hashes; do not overwrite
any existing backup. Calibration journals and requests persist outside checkouts.

Offline request discovery, with no UART/camera opening:

```bash
.venv/bin/python -m tools.calibrate_neck \
  --state-directory "$HOME/.local/share/charlie/neck" --list-requests
```

### Separately authorized disarmed application upgrade

This section is **not authorization to execute maintenance in this mission**.
Resolve electrical/USB backfeed behavior first; disconnect external servo power,
keep Head B disconnected and use the established independent cutoff/maintenance
setup. Stop the normal applications and sole UART owner only in that later
authorized maintenance window. Preserve a fresh full Pico filesystem backup in
a new directory, including support libraries, profiles and markers; compare its
hash manifest with prior preserved backups.

Review staged RP2040 configuration against the backup, retaining required custom
non-motion settings and compatible support libraries. Keep every motion gate
disabled. The existing synchronizer remains an additive full-application upgrade:
support libraries first, all application dependencies next, `main.py` last, then
reboot. It does not format the Pico, remove existing commands, delete unknown
files or replace Charlie with a calibration-only application.

Only after separate maintenance authorization, from the reviewed isolated stage:

```bash
.venv/bin/python -m tools.sync_rp2040
```

Verify the transferred file hashes and full file inventory, READY, DISARMED,
absent PWM/actuator construction, PING/status/display/progress/messages and CAL
rejection under shipped gates. Check STOP, heartbeat expiry and epoch changes
without arming. Verify GP10 cannot activate anything. Do not use
`tools.test_rp2040` as a supposedly passive test: it contains motion requests.
Any native failure stops maintenance and leaves power disconnected.

### Later supervised reuse and profile replacement

After separate electrical, alignment and supervised-calibration authorization,
the installed application needs a reviewed commissioning configuration once.
Ordinary subsequent sessions call its existing CAL protocol through the service,
with a fresh run ID, fresh pose/pulse verification, reviewed single increments,
GP10 release permits and actual clearance/displacement evidence. No reinstall is
needed between sessions. A changed assembly or commissioning constraints may
require a new reviewed configuration; routine sessions do not.

The existing console can attach a discovered request using `--request-id`,
`--state-directory`, a fresh `--evidence` path and its existing explicit
`--authorize-supervised-calibration` flag. That flag grants no firmware gate and
must not be used under this mission's authorization. Stop primary applications
first and establish a fresh existing UART session; PRIMARY ownership cannot be
silently bypassed. Reopening the supervisor archives the previous terminal run
and requires fresh verification. An interrupted session never resumes a permit.

Use existing offline `tools.neck_profiles` derivation and independent review;
preserve the superseded/quarantined predecessor. Qualification and metadata
selection are not PWM activation. Transfer new immutable profile/history metadata
and pointer last only under separate maintenance authorization. The current
firmware loads profiles at boot, so selecting a replacement requires a safe
metadata reload/reboot, **not a firmware reinstallation**. Every boot is disarmed.
The existing fresh START_VERIFY/AUTOSTART and ownership safeguards remain required
for any later physical operation. GP10 is not ordinary-operation authorization.

### Rollback

Stage the preserved parent in another new checkout/worktree. Do not reset the
integration branch, operational checkout or evidence directories:

```bash
CAL1_ROLLBACK="$HOME/cal1-integration-rollback-ff195c6"
test ! -e "$CAL1_ROLLBACK" || exit 1
git worktree add --detach "$CAL1_ROLLBACK" ff195c688e6aae98968d3fbe45908bb407beaa39
```

Actual Pico rollback is a separately authorized disarmed application transfer:
preserve new requests/profiles/quarantine and support-library fixes, transfer
reviewed dependencies before `main.py`, and verify DISARMED/no PWM afterward.
If a profile or persistent state fails validation, retain the evidence and leave
the neck disabled; never restore an old activation pointer to erase a fault.
An incomplete upload is not repaired by energizing hardware. Keep servo power
disconnected and restore only a verified disarmed application bundle.

## Remaining acceptance

No remaining reproduced host-software defect is known after final validation.
CAL-1 is not physically complete. Remaining checks include native Pi/MicroPython
behavior, real display/UART cadence, electrical topology/cutoff, actual pose/pulse
alignment, whole-region mechanical clearance, GP10 noise/debounce, PWM/rates,
watchdog/cutoff, torque-release sag, real filesystem/power-loss durability,
physical profile transfer/rollback, independent qualification and actual
autonomous command-to-view agreement. Reliable fixed-scene visual evidence during
primary operation must be demonstrated for that specific task/view; it is not
provided by saved geometry or moving sprites.

Next recommended mission: code-only native staging first, then separately
authorized disarmed maintenance, followed by a separately authorized supervised
commissioning/qualification plan. No deployment or physical phase starts here.

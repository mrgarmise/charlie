# Permanent motion authority — recovery successor

This implementation descends directly from recovery checkpoint
`87779558b78aeb5b36d4c3bc1eceed7831201e95` on `feature/active-vision`.
Physical authorization is **false**. No firmware was flashed, no physical PWM
was created, no servos were energized, and no gameplay was initiated during
implementation or verification. Hardware-free tests do not establish physical
Active Vision readiness.

## Shipped safety state

`rp2040/servos.py` is the sole motion authority. Startup creates no actuator
GPIO or PWM. The pico:ed buzzer also now creates PWM lazily, rather than at
module import. Head A alone is eligible: GP4 pan and GP5 tilt. Head B GP14/GP15
never acquires GPIO/PWM objects, including after arming.

`rp2040/motion_profile.py` deliberately ships with:

```python
CALIBRATED_ENVELOPE = None
ELECTRICAL_GATE_CLEARED = False
LOCAL_ARM_PIN = None
```

There is no inferred assembled-head envelope. Prior unloaded 60–120 degree
exploration is not calibration. A future independently reviewed firmware profile
must identify the assembled-head calibration, both angle and pulse intervals,
a physically confirmed arming pose, home pose, maximum combined-axis rate,
and maximum combined-axis step. The validator rejects invalid/nonfinite profiles
and pins other than GP4/GP5. Hard ceilings are 30 degrees/second and 12 degrees
per request; these are software ceilings, **not asserted safe physical limits**.
The physical calibration must supply appropriately smaller limits.

No serial command sets the profile, clears the electrical gate, or physically
arms motion. A future separate local input must be released for three samples
and then pressed for three samples after a live session is established. A held
button at boot or through STOP does not arm. The input cannot use an actuator
or Head B pin. Arming applies calibrated pulses at an operator-confirmed pose;
that initial energization itself requires physical validation. Software cannot
measure alignment, prevent sag after torque release, or diagnose shield power
and USB faults.

Physical arming and control authorization are separate. A live connection
session, current authority epoch, and explicit owner grant are required for
LOOK, TRACK, HOME, SCAN, MOVE, behavior updates, and public servo methods.
Direct servo construction, direct updates, exposed PWM access, Head B requests,
nonfinite values, out-of-envelope poses, excessive steps/rates and missing or
stale authorization are rejected. Nothing silently clamps a movement request.
A HOME outside the permitted incremental step is rejected rather than jumping.
These safeguards govern protocol and public firmware paths; arbitrary privileged
replacement of firmware is outside that boundary.

STOP, IDLE, SLEEP, watchdog expiry and new SESSION cancel targets, revoke grants,
increment the epoch and disable/deinitialize both PWM outputs. A driver failure
on one disable still attempts the other; telemetry cannot prove a defective
physical output is electrically off. The scheduler checks expiration before
processing arrivals. A late PING cannot rescue old authority. Pi reconnection
sends STOP and a fresh SESSION and clears cached permissions. It never resumes
an old target or grant.

## Protocol and integration contract

Non-motion feedback/display commands remain available. VIEWPOINT retains its
fields and ends with actual ARMED/DISARMED state. All angles are **commanded
software estimates**, including disconnected Head B's compatibility values;
there is no measured position. MOTION_STATUS additionally reports schema
`charlie-motion-authority-v1`, session, epoch, owner, primary-task state,
PWM state, calibration and gate status, `pose_source=commanded_estimate`,
`measured_position=null`, and `pose_verified=false`.

| Request | Meaning |
| --- | --- |
| `SESSION <token>` | Disarm and establish a new session; token length 8–64 |
| `AUTHORIZE ACTIVE_VISION <token> <epoch> INITIAL` | Grant control after independent local physical arming |
| `MOVE <token> <epoch> <pan> <tilt> <rate>` | Bounded, validated motion request |
| `LOOK/ TRACK <pan> <tilt> [rate] <token> <epoch>` | Scoped compatibility names |
| `HOME/ SCAN <token> <epoch>` | Same authority and limits; SCAN proposes bounded steps |
| `PRIMARY <token> <epoch>` | Disable motion and record primary ownership |
| `AUTHORIZE ACTIVE_VISION <token> <epoch> DEGRADATION` | Explicit return from PRIMARY after fresh local physical arming |
| `STOP` | Cancel, disarm, disable PWM and revoke authorization |
| `ARM` | Always rejected: local physical arming required |

Unscoped legacy motion requests intentionally fail safely. Existing software
must not infer motion success from an unchecked UART write. The Pi controller's
Active Vision path checks firmware acknowledgment and fresh authority status.
Legacy recovery VIEWPOINT responses remain readable, but cannot authorize
physical optimization.

The existing camera lease is extended, not replaced. Primary captures use the
existing default role. Active Vision uses `role='active_vision'`; passive Mint
Eyes consumes the existing observation publisher and never opens an owned
camera. A primary request asks Active Vision to yield at bounded observation,
focus and movement boundaries. Active Vision stops inference and movement,
sends PRIMARY/STOP, closes its source/publisher and releases the lease. No
second camera opens while another lease is held. A capture that does not yield
within the lease timeout causes the primary request to fail safely; hard
termination of arbitrary blocking camera drivers is not claimed.

Lifecycle is ACQUIRE → OPTIMIZE → VALIDATE → LOCKED, with terminal FAILED,
STOPPED or YIELDED on failure, interruption or primary preemption. Final STOP
releases torque **before final image validation** so an unpowered head that
sags cannot be handed off as a validated view. LOCKED saves raw/corrected
observations, correction parameters and decisions, closes processing resources,
and leaves no optimization worker running. The transport heartbeat may remain;
it performs no optimization or motion inference.

A persistent geometric degradation gate distinguishes target/viewpoint loss
from ordinary scene activity. Its one-use, short-lived reacquisition permit
requires actual degradation evidence (including severe persistent loss).
Normal transitions and restored geometry invalidate pending permits. The task
normally authorizes return; severe loss may request suspension. Each return
uses a new optimizer and evidence directory, an explicit DEGRADATION transition,
and fresh physical arming. A permit or Pi flag never energizes the head.

ALA-2 is not modified or merged. Its stable integration obligations are the
existing camera lease, checked RP2040 ownership API and degradation permit.
If ALA-2 changes these interfaces, record the mismatch and defer merging until
both branches publish stable tested checkpoints. Do not add a competing owner,
servo controller or learned-policy bypass.

## Pi code deployment — no hardware access

Use the full implementation SHA from the publication report as `RELEASE_SHA`.
Run these commands on the Pi only when ready to stage software. They create a
new checkout and leave the current recovery checkout, untracked `96.00`,
`recovery/`, Pico backups, Robotron evidence and local edits untouched. They do
not open serial/camera devices, start Charlie, flash, arm or run gameplay.

```bash
RELEASE_SHA='FULL_SHA_FROM_PUBLICATION_REPORT'
STAGE="$HOME/charlie-active-vision-safe-authority"
test ! -e "$STAGE" || exit 1
git clone --single-branch --branch feature/active-vision https://github.com/mrgarmise/charlie.git "$STAGE"
cd "$STAGE" || exit 1
git checkout --detach "$RELEASE_SHA"
git merge-base --is-ancestor 87779558b78aeb5b36d4c3bc1eceed7831201e95 HEAD || exit 1
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install pytest numpy opencv-python-headless Pillow pyserial
.venv/bin/python -m pytest -q tests/test_active_vision_firmware.py tests/test_head_recovery_lockout.py tests/test_active_vision.py tests/test_passive_eyes.py
.venv/bin/python -c "from pathlib import Path; n={}; exec(Path('rp2040/motion_profile.py').read_text(), n); assert n['CALIBRATED_ENVELOPE'] is None and n['ELECTRICAL_GATE_CLEARED'] is False and n['LOCAL_ARM_PIN'] is None"
git status --short
```

Tests intentionally use simulated UART/PWM/camera inputs. Package installation
may require the Pi's compatible Python/OpenCV packages; the published test
report identifies the workstation environment, not a verified Pi environment.
Do not run `tools.sync_rp2040`, mpremote, Charlie's live runner or armed gameplay
as part of this code-only deployment. The operational recovery firmware remains
installed.

## Firmware deployment gate and rollback

Firmware deployment is blocked pending separate authorization and resolution
of the Keyestudio shield power/USB fault. Before any future firmware write,
retain all original Pico backups and capture a fresh full filesystem backup
with the established recovery method into a new directory. Record its inventory
and hashes; never overwrite the originals. Review power isolation and wiring,
keep Head B disconnected, and retain the shipped false/None profile for the
first firmware smoke check. Only after that authorization, the existing
`python -m tools.sync_rp2040` synchronizes the application/support library and
reboots the Pico. That tool is not invoked by this implementation.

No firmware rollback is needed now: the actual Pico still runs recovery.
Code-only rollback uses a separate worktree and does not reset any branch:

```bash
cd "$HOME/charlie-active-vision-safe-authority" || exit 1
ROLLBACK="$HOME/charlie-active-vision-rollback-8777955"
test ! -e "$ROLLBACK" || exit 1
git worktree add --detach "$ROLLBACK" 87779558b78aeb5b36d4c3bc1eceed7831201e95
```

If this new firmware is later installed under separate authorization, a
firmware rollback also requires that authorization and the resolved electrical
gate. From the recovery worktree restore the recovery application with the
existing MpRemote helper, writing `main.py` last. This preserves the safer lazy
buzzer library and does not restore an older potentially energizing firmware.
Run only in the separately authorized, isolated firmware-maintenance setup:

```bash
cd "$HOME/charlie-active-vision-rollback-8777955" || exit 1
python3 - <<'PY'
from pathlib import Path
from tools.mpremote_helper import MpRemote
mp = MpRemote()
mp.require()
assert mp.is_connected(), 'No connected maintenance Pico'
files = sorted(Path('rp2040').glob('*.py'), key=lambda p: (p.name == 'main.py', p.name))
for source in files:
    mp.copy(source, ':' + source.name)
mp.reset()
PY
```

Unused new profile files are inert under the recovery main; no delete is
necessary. Verify recovery reports `VIEWPOINT ... IDLE DISARMED` without any
motion request. This is commanded-estimate telemetry, not alignment evidence.
Rollback tests execute the exact preserved recovery servo module and confirm
it creates no PWM and refuses movement. Actual Pico rollback is untested and
was not attempted.

## Acceptance boundary

Deterministic simulation demonstrates discovery, independently chosen trials,
improved quality, finite lock, zero continued optimizer work during primary
ownership, hysteresis against ordinary scene changes, permitted reacquisition,
resource release and decision evidence. The physical code path is additionally
exercised against the real authority/transport via simulated UART, local input,
PWM and camera world. Simulation profiles are isolated in tests and are never
installed as physical calibration.

Still blocked: assembled-head angle/pulse calibration, verified mechanical
clearance and arming alignment, local interlock installation/validation,
electrical gate resolution, real MicroPython/Pico execution and watchdog/PWM
measurements, actual camera-focus/geometry improvement, post-STOP mechanical
stability, real camera ownership timing and physical rollback. No successful
physical optimization or unattended safety is claimed.

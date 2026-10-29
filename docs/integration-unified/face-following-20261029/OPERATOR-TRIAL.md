# Operator participation checkpoint — physical acceptance still pending

This implements the user's checkpoint: finish/publish independent preparation,
then stop at the physical authorization boundary. **Do not launch an armed face
trial yet.** Availability of a face target, raised wheels and a cutoff does not
satisfy the existing independent actuator/measurement gates.

## Staged participation required

1. **Power-isolated stationary measurement/identity session first.** Operator
   present, ELEGOO secured, no people/animals in actuator paths, independent
   motor/servo cutoff accessible. Preserve the installed MCU/ESP32 identities
   and original source/protocol receipts without flashing/resetting equipment.
   Verify the existing camera/command owners; never terminate an owner to gain
   access. Attach the October 29 original ultrasonic result when available.
   Check whether existing Pi camera/display placement can supply independent
   real pan-angle and optical exposure-age measurements. No commanded angle,
   receipt-age substitution or prefilled `passed` evidence is admissible.
2. **Separately authorized actuator qualification.** Use existing reviewed
   calibration/evaluation interfaces and one owner. Observe exact N1 RX after
   the historical 50 ms failure (the corrected window is now 150 ms) to distinguish delayed from absent replies with motor power
   isolated; do not infer mechanical stopping from this protocol observation.
   Then independently witness pan envelope/settle/stop/loss/alignment/preemption,
   and staged chassis local expiry, explicit STOP, TCP/Pi loss, wheels-up,
   floor braking, cutoff and preemption, with the required three distinct trials
   (per direction where required). Preserve every failure and uncertainty.
   Existing `learning.mobile_safety calibrate` defaults to dry-run; its explicit
   physical execution additionally requires a reviewed, installed-source-bound
   `charlie.mobile.calibration-trial.v1` artifact. It is not a permission bypass.
3. **Full face test only after all gates pass.** Use current-runtime qualification
   artifacts, independent physical evaluation and separate telemetry, pan and
   chassis grants. The live producer must provide truthful source/frame/hash,
   exposure-age, actual pan, environment, cutoff, boot/device/zone and firmware
   bindings on each dispatch. No heartbeat process may blindly refresh booleans.
   N1 is not servo STOP; pan stopping must be independently demonstrated.

Raised, free-spinning wheels are useful for motor/expiry/cutoff qualification,
but a fixed elevated chassis cannot yaw in response to wheel movement. It cannot
prove chassis alignment or closed-loop yaw counter-rotation. Complete acceptance
needs a separately qualified protected floor or suitable mechanically reviewed
rotating fixture where actual body yaw is possible. Do not release the elevated
car onto a floor or change fixture under the present authorization. Obtain the
specific operator authorization and required floor/fixture qualification first.

## Exact conditional normal-application launch

After the operator approves that stage and independently qualified inputs exist,
use the verified PR #13 checkout, a foreground interactive terminal and continuous
external video. `script` is installed on Charlie and retains a terminal transcript.
The externally verified device/zone values must match the physical qualification
reports; setting environment variables is not a motion grant.

```bash
set -eu
cd /home/five/charlie-pr13-acceptance
export CHARLIE_FACE_HARDWARE_ID CHARLIE_FACE_ZONE
test ! -e /home/five/charlie-face-qualification-20261029/trial-001
test ! -e /home/five/charlie-face-qualification-20261029/console-001.typescript
script -q -e -f -c '/home/five/Projects/charlie/.venv/bin/python main.py --hardware --elegoo-face-track --learning-state /home/five/charlie-face-qualification-20261029/state --mobile-hardware-id "${CHARLIE_FACE_HARDWARE_ID:?verified hardware ID required}" --mobile-zone "${CHARLIE_FACE_ZONE:?qualified zone required}" --actuator-safety-feed /home/five/charlie-face-qualification-20261029/safety.json --face-evidence-dir /home/five/charlie-face-qualification-20261029/trial-001 --face-trial-seconds 60 --face-authorization-wait 120 --learning-budget 1' /home/five/charlie-face-qualification-20261029/console-001.typescript
```

Stop if either `test` fails; never overwrite a previous trial. Choose new numbered
paths for a separately authorized retry. Do not use nohup, detach the terminal,
pipe stdin, run two command clients, set legacy motion flags or run the historical
N3-based controller. The launch starts the existing application-owned ELEGOO
feeder. If an existing publisher/command owner is already active, coordinate an
approved application-owner handoff rather than starting a competing reader.

Startup prints the new `elegoo_executor_boot_id` and waits, without motor or
telemetry commands, for all three independent authorizations. External evidence
can be evaluated/installed through existing APIs, now with CLI wrappers:

```bash
# Each REPORT_PATH must be a genuine independently witnessed qualification.
python -m learning.actuator_safety --journal /home/five/charlie-face-qualification-20261029/state/actuator-evidence.sqlite3 evaluate REPORT_PATH
# AUTHORIZATION_PATH binds that evaluation ID to this printed boot/device/zone.
python -m learning.actuator_safety --journal /home/five/charlie-face-qualification-20261029/state/actuator-evidence.sqlite3 activate QUALIFICATION_ID AUTHORIZATION_PATH
python -m learning.actuator_safety --journal /home/five/charlie-face-qualification-20261029/state/actuator-evidence.sqlite3 status --boot-id PRINTED_BOOT_ID --hardware-id "$CHARLIE_FACE_HARDWARE_ID" --zone "$CHARLIE_FACE_ZONE"
```

Those placeholders deliberately cannot be filled with invented evidence. All
three groups must pass; grants last at most 600 s and never survive a new boot.
The static status inspects authority records, not live physical readiness. The
actual dispatch independently checks the real fresh safety feed and uncertainty
state again. Missing producer/measurement inputs remain a hard blocker even if
external grant records exist. The full follower's pan/chassis/yaw/search paths
are enabled together only after admission; no disabled-actuator acceptance mode
is offered as a substitute.

## Face behavior and synchronized evidence

Run separately authorized, bounded phases instead of attempting every case in a
single 60 s trial. Keep a second observer at the physical cutoff. Start external
video **before** launch; frame the wheels/chassis heading, camera pan mechanism,
operator/target and stop interaction. Use adequate frame rate for stopping
measurements; retain the original files, frame-rate metadata, clock/sync markers
at start/end, and quantified timing/angle uncertainty. A visible stop keystroke
and wheels in the same video can conservatively measure key-to-rest latency;
wire ACK timing alone cannot. Never claim exposure time from an after-the-fact
camera overlay. Do not exceed the reviewed envelope to make a turn visible.

Expected sequence and comparison points:

- Centered face: stable selected target and original hysteresis; small movement
  inside the deadband should not cause gratuitous pan/chassis motion.
- Left/right and stop: proportional original pan corrections, then actual
  authorized chassis alignment and fresh measured yaw/head counter-rotation.
  Record actual body heading and servo angle, not just motor spin or commands.
- Continuous cross-field movement and a second consenting target: original
  largest/nearest selection behavior and target-switch history remain intact.
- Brief loss, then 3/7/15 s losses: original prediction/hold, local sweep,
  incremental sentry search and real reacquisition, with bounded N2 renewals.
- Loss during alignment, wrong/stale yaw, source loss, authority expiry and
  preemption: veto/STOP and any failure must remain recorded. Inject only the
  separately reviewed faults; no casual cable pulling during an armed run.
- Operator `x` plus Enter, Ctrl-C or cutoff: observe actual motor and servo
  behavior, stop latency, residual motion and uncertainty. Cut power immediately
  for unexpected motion, no observed stop, bound breach or unsafe loss of control.

Compare the same target movements/conditions with the recovered historical
candidate sessions, especially v4 full sweep and v5 attention events. Do not
run their unsafe legacy actuator path as an A/B shortcut. Keep detector input
resolution, confidence, largest/nearest choice, proportional/hysteresis settings,
yaw alignment, prediction and search intact. Any degradation, missing source,
model/version mismatch or incomplete phase is an unresolved result, not a pass.

The trial folder contains the existing FIFO writer's journal, 5 Hz selected raw
frames plus all consumed-frame descriptors/retention status, target selections,
shared yaw/range/actuator receipts, alignment state, wire trace, monotonic/UTC
mapping and terminal disposition. `driver-wire-final.json` retains teardown's
bounded wire tail. Preserve `state/elegoo-uncertain-motion.lock`, full console,
external video and all artifacts, including failed attempts. Recording may pause
or fail closed; that is inconclusive physical acceptance. Independently hash and
review the actual synchronized evidence before publishing a physical verdict.
No ACK or automatically completed recording certifies physical success.

## Current request, not authorization

The operator should participate first in **power-isolated measurement/identity
and STOP-protocol observation planning**, supplying the real producer/baseline
inputs and approving the exact stationary procedure. Powered motor/pan tests,
floor/rotating-fixture tests and the complete face-following run each await their
independent gates and explicit supervised authorization. This follows the user's
operator-participation checkpoint and repository ownership/safety instructions;
the mission remains open until the actual combined behavior is witnessed and
independently accepted.

# Pi-connected Codex handoff: PR #13

This is a validation plan, not evidence of hardware acceptance. The PR is draft;
do not deploy, merge, flash, move an actuator or alter calibration until the
operator and independent safety gates for that particular step are satisfied.
Always verify the current PR head and its CI before choosing a candidate. PR #10,
#11, #12, the current native checkout and all evidence remain rollback sources.

## 1. Read-only native inventory

Run from the existing Charlie checkout; do not `reset`, `clean`, `stash`, switch
branches, stop services or alter any other worktree:

```bash
pwd
git status --short --branch
git rev-parse HEAD
git remote -v
git worktree list --porcelain
gh pr view 13 --repo mrgarmise/charlie --json number,isDraft,headRefName,headRefOid,baseRefOid,statusCheckRollup
ps -eo pid,ppid,args | rg 'charlie|python|robotron|libcamera|picamera|hailo'
ls -l /dev/serial/by-id /dev/ttyACM* 2>/dev/null
ss -ntp
```

Record command output, timestamp, operator, native checkout SHA and the actual
running service/process executable paths outside the existing evidence roots.
Inspect service definitions and owner/lease files read-only. Record current
RP2040 serial device, ELEGOO endpoint, camera publishers, consumers and Hailo
owners. Absence of a command or device is **unknown**, not a pass. Do not assume
`/dev/ttyACM0` identifies the same board after reboot. Obtain exact installed
firmware and bridge identities by a separately reviewed read-only method;
repository files are not a live firmware readback.

## 2. Isolated software validation

After fetching the candidate with an explicit, non-overwriting reference, create
a new separate worktree only if the desired destination does not already exist.
Do not use the deployed directory or reset existing checkouts. Replace the two
angle-bracket placeholders with the verified SHA and an unused path:

```bash
git fetch origin refs/pull/13/head:refs/charlie-inspect/pr13-candidate
git rev-parse refs/charlie-inspect/pr13-candidate
git worktree add --detach <unused-validation-path> <verified-pr-head-sha>
cd <unused-validation-path>
git status --short --branch
git rev-parse HEAD
python -m pytest tests/test_normal_multi_ability.py tests/test_unified_actuator_requests.py tests/test_actuator_authority.py tests/test_rp2040_gateway_fence.py -q
python tools/check_unified_contracts.py
```

If the local inspection ref already exists, inspect it and choose a new ref name;
do not force-update it. Confirm the resulting SHA and clean status. The commands
above use mock/fixture tests and do not authorize physical operation. Capture
command exit codes and complete results. The full suite can be run separately
without concurrent tests using the gameplay lock; compare with GitHub CI.

## 3. Separate stationary source and control gates

Before connecting any hardware, independently document power isolation,
physical emergency stop and operator authority; verify no other process owns the
camera, Hailo, ELEGOO command endpoint or RP2040 serial port. Validate the
installed ELEGOO read-only N21/D1=2 ultrasonic and N24 yaw commands against the
actual firmware and bridge; verify replies, units, timing and side effects before
creating telemetry qualification. Range is obstacle-only until its placement,
field of view and accuracy are independently measured; it is not target range
or a clearance map. Verify real firmware status meanings and serial identity;
RP2040 pan/tilt are commanded estimates, not measured pose.

Qualify chassis and pan **separately** using preserved raw measurements and
witnessed independent trials for the exact runtime, hardware, firmware, zone and
surface. Verify local timed expiry and each direction envelope, braking distance
with uncertainty, loss of Pi/TCP, physical cutoff, STOP/preemption and servo
stop/limits. Validate the independent source producer and its frame, capture-age,
pan, clearance and environmental bindings. The host parser checks record/hash
consistency only; an evaluator must independently establish authenticity and
adequacy. No source registration, learning project, environment variable or
capability listing constitutes a motion grant.

The admission code expects `charlie.actuator.qualification.v1` artifacts and an
independent journal evaluation/activation through `evaluate_actuator` and
`CapabilityDeployment.activate_actuator`. Inspect `learning/actuator_safety.py`
and `learning/deployment.py` for exact fields before preparing evidence. The
application prints a new `elegoo_executor_boot_id`; all grants must match that
boot, device, zone and group. The safety feed is distinct from that grant. The
host has no qualified sensor producer or trial records to copy.

## 4. Measured behavioral acceptance

In separately authorized stages, first verify one camera owner and one command
owner with simultaneous primary vision, pet/object perception and ELEGOO face
subscription, without motion. Record source IDs, sequence/generation, receipt
ages, dropped frames, memory, CPU/thermal and fault recovery. Confirm one
AttentionManager and the existing Learning Executive make decisions.

After independent chassis and pan authorization, compare against the preserved
original checkout in supervised, protected trials: largest/nearest face
selection; centered and proportional pan corrections; hysteresis; yaw-guided
counter-rotation and bounds; wrong-way/stale yaw; brief loss, prediction, local
sweep, sector search and reacquisition; competing requests; cancellation; STOP;
restart and stale/replayed commands. Record synchronized authentic video, exact
frame and request IDs, wire commands/ACKs, independent motion and stop
measurements, witnesses, operator interventions, calibration and uncertainty.
Measure STOP latency while serial/socket traffic and callbacks are busy. Do not
infer mechanical motion from an ACK or a commanded pose.

Preserve CAL-1 and firmware envelopes, local arm, heartbeat/watchdog and display
behavior. RP2040 tests require their own independently reviewed electrical and
mechanical gates. Confirm object labels and Robotron compatibility in separate
bounded runs. Physical face parity remains open until the comparison is witnessed
and accepted. Safe, voluntary real-cat following is a separate later gate: only
claim it when the normal Executive selects it and witnessed physical evidence
shows following and humane stopping with the cat free to decline.

## 5. Ambiguity and rollback

On unexpected motion or uncertain delivery, use the independently qualified
physical emergency stop/power isolation immediately. Preserve logs, raw frames,
trial artifacts and any `elegoo-uncertain-motion.lock` or
`rp2040-uncertain-motion.lock`; STOP and restart must not erase them. Reconcile
physical state and incident evidence with an independent operator before any
separately authorized recovery or new boot-bound grant.

To restore known software behavior after physical isolation, use the previously
recorded native checkout SHA and the original service/launcher configuration,
following the operator's deployment procedure in the preserved checkout. Verify
`git status --short --branch`, `git rev-parse HEAD`, the service executable path
and device owner before allowing any previously authorized operations. Do not
reset or delete worktrees, overwrite original evidence or calibration, change
firmware, or treat a software rollback as proof of physical safety. Firmware
rollback/flash requires its own explicit approval and independently preserved
verified image; this handoff does not authorize it.

## October 29 face-following preparation

See [the evidence-led face trial report](../face-following-20261029/REPORT.md)
and [exact conditional operator procedure](../face-following-20261029/OPERATOR-TRIAL.md).
Physical admission remains blocked by missing verified pan/exposure-age producers;
software tests and historical replay are not physical face-following acceptance.

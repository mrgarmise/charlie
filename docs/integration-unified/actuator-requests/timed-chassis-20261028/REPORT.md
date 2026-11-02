# Correct qualified ELEGOO pulses to firmware-timed N2

PR #13 continuation, started 2026-10-28 UTC. Base:
`08ae83f7a6f54a7b0acefc4f240df784f176573e`, existing branch
`integration/unified-sensory-motion-20261026`. No firmware flash, device
connection, motor operation, deployment or PR merge occurred.

## Source verification before implementation

The original audit already cites the manufacturer's source. This host has no
installed MCU/ESP32 source readback, so that citation is not an installed-byte
certificate. Both source variants were retrieved and inspected as data only:

- Manufacturer archive at commit `096094e07dc7e5eea8c986986158e2d9111dab64`:
  [SmartRobotCarV4.0_V0_20210104.zip](https://github.com/elegooofficial/ELEGOO-Smart-Robot-Car-Kit-V4.0/blob/096094e07dc7e5eea8c986986158e2d9111dab64/SmartRobotCarV4.0_V0_20210104.zip),
  immutable Git blob `086ce4eb37adc9a9a135319df981cc7e2e8cc473`.
  `ApplicationFunctionSet_xxx0.cpp` lines 1809–1828 dispatch N2 to timed
  control and load `T`; N3 selects unlimited control without reading `T`.
  The header declares a `uint32_t` timer. The timed handler, lines 1179–1223,
  compares elapsed milliseconds directly with the timer, requests motor STOP,
  switches to programming mode, then emits the command-tagged `_ok` reply.
  Its zero-timer branch does not expire. Timer expiry is main-loop serviced,
  with a strict greater-than comparison: it is not a hard real-time stop bound.
- The [newer implementation](https://github.com/elegooofficial/ELEGOO-Smart-Robot-Car-Kit-V4.0-New/blob/76d82704b20b8b38d3eb874afd865b349cbc1a48/ApplicationFunctionSet.cpp)
  at `76d82704b20b8b38d3eb874afd865b349cbc1a48`, blob
  `d8fd782cc385e04b5757478c80b70901e054754a`, also tests N2 in its executable
  handler, uses `millis()` with a millisecond duration, and requests STOP before
  its completion reply. Switch comments/README examples are inconsistent with
  that handler; executable code determines this contract.

Exact source/archive digests and line ranges are in `source-contract.json`.
Source bytes are preserved locally under the path recorded there, separately
from original evidence. Neither public source variant proves installed firmware.
The existing five October 25 motion records remain byte-identical; their N3
commands and unverified physical outcomes have not been rewritten or upgraded.

## Corrected existing path

Existing qualified request/pet executor -> MobileBase -> ElegooMobileBase.pulse
remains the only route. There is no second executor, socket, motor writer or
hardware discovery path.

- The pulse packet is always N2. Seconds are rounded **down** to integer
  milliseconds. Encoded `T` is 1–200 inclusive and cannot exceed the requested
  duration/envelope. Sub-millisecond, zero, nonfinite and oversized requests
  fail before a motor packet is sent. Direction/PWM/authorization checks remain.
- N2 has a **completion** ACK, not an immediate start ACK. The existing pending
  command transport now optionally polls cancellation/safety while waiting for
  the exact `{H_ok}` reply. The completion window is encoded duration plus at
  most 50 ms of acknowledgment grace. That grace grants no extra movement or
  lease authority. Cancellation, disconnect, safety veto, lease expiry and an
  exhausted completion deadline abort; a simultaneous ACK cannot override them.
- The wire-lock preflight rechecks the remaining lease horizon immediately
  before send. Independent safety I/O and ACK waiting stay outside the send lock,
  so the existing emergency STOP does not wait behind the motion-request lock.
  Network writes, scheduling and independent safety I/O still need native timing
  measurement; host tests are not hard real-time guarantees.
- Untagged, wrong-value, wrong-command and premature completion replies cannot
  establish successful completion. The actual send is never retried/reconnected.
  The existing explicit N1 STOP is attempted separately on every attempted-pulse
  exit, including a valid N2 completion. Its ACK must also be exactly tagged.
- A completion ACK cannot substitute for an explicit STOP ACK. All physical
  motion/stopping fields remain unknown. In the classic source N1 can acknowledge
  parsing before its motor-control loop executes, reinforcing this distinction.
- Failed wire commands, timing/error reasons and STOP results are retained in the
  driver's last attempt and the existing unified/pet executor evidence. STOP
  exceptions retain the attempted command too. Existing uncertainty latches,
  durable incident markers, restart denial, no-replay and independent recovery
  remain. A later ACK does not clear an ambiguous incident.

Only the qualified motion/STOP calls opt into strict ACK semantics. The generic
legacy sensor wait/reply behavior is preserved. `read_ultrasonic()` is
byte-identical to the original method; a real driver/fake-peer N21 regression
checks its unchanged numeric reply handling. Telemetry scheduling and readers
were not modified.

## Qualification and rollback

The existing independent chassis, pet and supervised-calibration validators now
require the installed protocol artifact to bind this exact contract:

```json
{"timed_motion":{"N":2,"T_unit":"milliseconds","completion_ack":"tagged_ok_after_local_stop","zero_duration":"forbidden"}}
```

This metadata is necessary, not sufficient. Installed source/bridge identity,
measured local expiry, stopping trials, fresh independent safety feed, current
runtime hash and external activation/lease remain mandatory. Copying metadata
cannot establish a physical observation. Old generic `local_expiry_verified`
assertions alone cannot qualify N3, unknown units or immediate-ACK behavior.
Only fictional test fixtures were updated; original records remain immutable.

Current/prior runtime hashes, preserved original evidence hashes and the
ultrasonic-method digest are in `preservation-audit.json`. The runtime change
invalidates earlier runtime-bound grants; no new activation was created.
Existing CapabilityDeployment rollback/revocation behavior is unchanged.
On failed qualification, retain incidents and keep the chassis disarmed. Do not
restore the unsafe N3 pulse as a compatibility workaround. Existing known-good
perception/ultrasonic software may remain available with motion disabled.

## Software validation

Python: `/home/five/Projects/charlie/.venv/bin/python`, cwd:
`/home/five/charlie-pr13-acceptance`. No real transport was opened.

- Initial focused selection: **126 passed**, 2.30 s.
- Expanded focused command:
  `python -m pytest tests/test_elegoo_timed_pulse.py tests/test_pet_completion.py tests/test_actuator_authority.py tests/test_shared_mobile_executor.py tests/test_unified_actuator_requests.py tests/test_mobile_legacy_regression.py tests/test_mobile_tracking_navigation.py -q -p no:cacheprovider --junitxml=/tmp/charlie-pr13-timed-final.xml`
  — **165 passed**, 2.33 s, zero skipped/failed.
- Canonical `python tools/check_unified_contracts.py` now includes the timed pulse
  regressions — **129 passed**, 3.33 s, zero skipped/failed.
- Existing CI on PR #13 will independently rerun the committed software suite.
  Its final observed status must be reported in the PR handoff; pending is not
  passing. Source SHA-256 identities and compressed console/JUnit receipts are
  retained in this directory.

The fake peer exercises actual driver serialization/pending replies, all four
D1 mappings, timer floor/bounds, normal delayed completion, bare/wrong/premature/
missing ACKs, cancellation/ACK race, lease expiry and wire-lock delay, safety
veto/disconnect, missing explicit STOP ACK, STOP exception, unified and original
pet execution, incident persistence/restart denial and unchanged ultrasonic reads.
These are software contracts, not MCU execution or physical qualification.

## Remaining native physical qualification

A separately authorized supervised procedure must:

1. Read back/preserve the actual MCU and ESP32 firmware/source identities. Verify
   installed N2 timer units, positive-T behavior, completion tag/ordering and N1
   STOP behavior against those exact bytes; inspect bridge buffering, heartbeat,
   disconnection, power-loss and shared command-tag behavior. Do not infer an
   installed match from the manufacturer's archive.
2. With an independent cutoff, begin wheels raised and the area isolated. Measure
   actual motor motion/STOP independently of acknowledgments, including local
   timer expiry without a host STOP masking it, explicit STOP, TCP loss, Pi loss,
   cancellation, preemption, delayed/missing completion, reconnect and restart.
   Preserve raw timestamps, command/reply traces, physical observations and all
   failed/ambiguous trials. This document authorizes none of those motor tests.
3. Bound MCU loop/transport/host scheduling delays, stopping time, braking travel,
   uncertainty, direction/PWM/duration envelopes, battery and surface conditions.
   Verify the 50 ms ACK grace/check cadence on the actual system; expiry and an
   ACK do not prove wheels are physically stationary. Continue to require the
   existing direction-specific trial counts and stop margins.
4. Requalify the new runtime and source-bound protocol before independent
   supervised activation. Retain persistent uncertainty/revocation through restart.
   Verify STOP races and serialized telemetry/pan traffic do not misattribute a
   shared firmware command tag. Only after the existing staged safety/empty-floor
   gates pass may separately authorized physical work progress.

No physical stop, native latency, safe floor motion or pet-follow qualification
is claimed by this correction. PR #13 remains draft and unmerged.

# Shared actuator implementation work in progress

Parent: published PR #13 `615f0aeca049bc43ed05bd7fa9e55c2ba0bc5080`.
All three independent workflows on that parent succeeded. No Pi access, firmware
write, deployment, physical measurement or animal following occurred here.

This increment adds an application-owned ELEGOO executor above the existing
controller. Pet dispatch can use its existing context and serialized executor;
face pan and chassis requests use separate independent admission envelopes.
Both share the transport, stop cutoff, cancellation and sticky uncertainty.
Normal application registration does not install a face/pan admission authority.
Thus this code is disarmed pending independent native qualification, not restored
physical face-tracker acceptance. The authority interface remains dependency
injected; native artifact ingestion for face/pan is still outstanding software.

The original face detector and face choice are unchanged. Proportional look,
hysteresis, predictive reacquisition, local search, yaw counter-rotation and
sector targets remain. Sentry now advances one bounded pulse per camera tick,
allowing source renewal and reacquisition. STOP no longer automatically centers
the pan. These changes require witnessed parity and stop tests; fake receipts
are not evidence of movement. Compatibility scripts still need explicit
application attachment; they must not open another motor transport.

The existing StimulusBus now supports owner-checked scalar publication,
independent latest subscribers and bounded recent history (32 x 16 KiB per
source, 64 sources/subscribers). Read failures invalidate live/history data.
ELEGOO telemetry reads share the application transport and require verified
installed read-only protocols. No protocol is enabled by registration. Range
never implies clearance, target distance or animal consent; pan/chassis pose
remains unknown where not measured. Command-state is explicitly distinct from
physical outcome. No acquisition is performed by subscriber reads.

The RP2040 request gateway calls the existing CAL-1 behavior/controller, never
opens serial or changes firmware. Existing Deck/CAL-1 and Active Vision paths
remain; full routing/conformance of all RP2040 consumers is still outstanding.

Normal application can attach the original face tracker with
`--hardware --elegoo-face-track`; this does not grant motion. The normal pet
runtime can also publish all object classes with `--object-recognition` and uses
its one existing AttentionManager and Executive. Simultaneous integration still
needs independent end-to-end tests and performance qualification.

## Native handoff and rollback

1. Record PR head and CI results; inspect native git status/worktrees, processes,
   motor/camera leases and connected devices read-only. Preserve deployed SHA,
   unpublished work, firmware images/readback and CAL-1 profiles. Do not deploy
   this work-in-progress revision to an operating robot.
2. Independently verify installed ELEGOO N3 timer expiry and N5 servo command,
   N1 STOP effects, N24 yaw, and N21/D1=2 read-only semantics. Record firmware and
   bridge hashes and raw responses; do not enable a guessed query.
3. Complete/review face/pan authority artifact validation before installing an
   authority. Qualify pan envelope separately from chassis directions, local
   expiry, cancellation/STOP, connection loss, electrical/power safety, floor,
   blind spots, human/animal exclusion and stopping distances.
4. Once separately admitted, start stationary sensing. Count one MJPEG owner
   and one command transport with multiple subscribers. Record source timestamps,
   faults, drops, history bounds, native RAM/CPU and freshness.
5. Compare preserved original tracker with integrated behavior in separate,
   supervised runs: largest-face acquisition, nearest-face continuity, look
   hysteresis, assist counter-rotation, wrong-way yaw, loss, predictive/local
   reacquisition, each sentry sector, cancellation and STOP. Record authentic
   synchronized video, requests, wire ACKs and independently measured movement.
6. RP2040 checks retain original CAL-1, electrical gate, servo envelopes, local
   arm, watchdog, display and heartbeat. Do not flash or alter original profiles.
7. On ambiguous motion: independently cut power/stop as qualified; revoke grants;
   retain all logs. Do not recreate an executor to erase uncertainty. After safe
   isolation, use preserved deployed checkout/launcher configuration to roll back;
   never reset/delete unrelated worktrees or firmware/evidence.

Real-cat following remains open until safe witnessed following is selected and
executed through Charlie's ordinary Executive. Native measurements are absent.

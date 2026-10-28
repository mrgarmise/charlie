# Shared actuator implementation work in progress

Parent: published PR #13 `615f0aeca049bc43ed05bd7fa9e55c2ba0bc5080`.
All three independent workflows on that parent succeeded. No Pi access, firmware
write, deployment, physical measurement or animal following occurred here.

This increment adds an application-owned ELEGOO executor above the existing
controller. Pet dispatch can use its existing context and serialized executor;
face pan and chassis requests use separate independent admission envelopes.
Both share the transport, stop cutoff, cancellation and sticky uncertainty.
The normal application now attaches the existing CapabilityDeployment journal to
separate chassis, camera-pan and read-only telemetry admission records. Source
frames, independent feed, boot, hardware, zone, runtime and measured trials are
rechecked. An installed registry or safety-feed path grants no authority. No
qualification or grant is included: physical operation remains disarmed until
independent native evidence and supervised activation. The evaluator can check
records and hashes, not attest that a witness or measurement is authentic.

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
3. Review the face/pan authority artifact validator and independently build its
   qualification records before requesting a supervised activation. Qualify pan envelope separately from chassis directions, local
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
   retain all logs. A durable `elegoo-uncertain-motion.lock` marker is written
   before dispatch. After a crash or ambiguous result it blocks new attempts;
   STOP does not erase it. Preserve the marker as incident evidence and only
   clear it after separately authorized inspection, proven physical isolation,
   reconciliation of the incident, and a fresh boot-bound qualification grant. After safe
   isolation, use preserved deployed checkout/launcher configuration to roll back;
   never reset/delete unrelated worktrees or firmware/evidence.

Real-cat following remains open until safe witnessed following is selected and
executed through Charlie's ordinary Executive. Native measurements are absent.

## Open software and acceptance boundaries

- `ActuatorSafetyAuthority` requires external, frame-bound, independently
  measured environment and current pan data. No qualified producer or actual
  deployment record exists in this environment. Hash/record checks do not
  authenticate a witness or certify the physical setup.
- The telemetry producer is polled by the application; read-only activation
  requires separate protocol and telemetry qualification. Captured measurement
  time, sensor field of view and pan pose remain unknown unless provided by a
  separately qualified source. A receipt is not independent movement feedback.
- The RP2040 gateway wraps the normal Deck frame/search/STOP path and retains
  CAL-1 as the actuator controller. Request scopes are invalidated on STOP
  before serial-lock acquisition; stale scoped writes and deferred search intents
  are rejected. A durable marker preserves interrupted or ambiguous gateway
  operations across restart. Existing standalone Active Vision and calibration
  call sites remain compatible, but are not all routed through this gateway.
  Serial-lock waiting and actual physical STOP latency remain unmeasured.
- The legacy standalone head scripts have not been migrated to an installed
  application executor. Preserve the old checkout for rollback; do not run the
  old direct-motion scripts concurrently with the integrated app.
- Independently test simultaneous normal-app object, pet and face operation,
  full parity, temporal STOP priority at the real socket/serial transport and
  native throughput. Tests with synthetic qualification records are fixtures.
- Publication of safety state and pose is partial: range/yaw query data and
  command receipts exist, but independently observed actuator outcomes and
  qualified full pose still require an actual source and native validation.

## RP2040 host-only STOP fence

Normal Deck observation uses the CAL-1 service inside a request scope on the
existing RP2040Controller. STOP invalidates all earlier scoped requests before
waiting for serial; a request checks its generation while holding the serial
write lock, and a stale search cannot be scheduled after STOP. The firmware's
existing session, arm, electrical, envelope, watchdog and CAL-1 decisions remain
unchanged. An interrupted request or unsuccessful STOP leaves
`rp2040-uncertain-motion.lock` in the learning state directory. Recovery needs
independent physical isolation and separately reviewed evidence; no restart or
STOP call clears it. This host fence does not demonstrate serial response time,
servo stopping, safe calibration, or cross-process exclusion.

## Emergency attention stop

The existing AttentionManager processes emergency STOP before other queued
intentions and keeps an in-session latch. Its application-installed callback
latches the shared ELEGOO executor before requesting STOP, so face, pet and
future requests cannot resume merely because a newer observation arrives.
The normal Deck is stopped independently. This is a software arbitration test;
serial/socket scheduling, power cutoff and physical stopping remain native
acceptance items. A STOP or restart does not clear an uncertainty marker.

## Normal application routing

With explicit `--hardware`, pet observation can run with or without Object
Recognition; adding `--elegoo-face-track` subscribes the existing face detector
to the same application-owned camera bus and actuator executor. Object-only mode
can also attach that face tracker. Those combinations remain independently
motion-gated. `x` attempts an emergency STOP on the input thread and then sends
the latched attention event, including while a bounded request is in progress.
The keyboard command is not a replacement for an independently qualified
physical emergency stop. Add `--primary-vision` to attach the existing Pi primary vision, Deck and
CAL-1 service to that same AttentionManager and application feeders. A host
fixture exercises primary vision, face, pet and object observations together;
it does not qualify native timing, tracking, physical motion or animal following.

## RP2040 serial ownership and observed status

The existing RP2040Controller holds a cooperative, device-path-based file lease
for its serial connection lifetime, including reconnects. A second gateway on
the same controller is rejected; a second cooperating process cannot open that
port while the lease is held. This does not constrain noncooperating programs or
prove that two different device aliases name the same physical controller.
`rp2040-motion-state` publishes session-checked firmware MOTION_STATUS through
the shared bus; pan/tilt remain commanded estimates and measured position is
unknown. Publication and controller registration never confer motion authority.

An idle face observer yields to a selected pet behavior without repeatedly
issuing a global chassis STOP. If it owns an active alignment or sentry search,
yield cancels that face-owned work. Emergency STOP remains global and latched.
`tools/check_unified_contracts.py` includes the shared actuator admission,
source ownership, RP2040 fencing and simultaneous-ability host tests; passing
it still does not qualify hardware.

Freshness validation includes both the producer-reported capture age at the
snapshot and elapsed host-monotonic time since that snapshot. Neither an old
feed nor an aged exposure can be made fresh merely by combining two individually
acceptable values. This applies to both face/pan admission and the existing pet
safety context; the actual exposure clock and producer remain native evidence.

Independent safety evidence may involve filesystem I/O. It is checked before
dispatch and during bounded chassis pulses, outside the socket write lock.
Cancellation and lease expiry are checked again under that lock immediately
before a command write, so a stalled evidence check cannot itself hold up a STOP
write. Safety state can change between an evidence check and the wire write;
car-local expiry, independent local stops, sensor timing and measured braking
remain mandatory, and host tests do not establish worst-case physical latency.

The normal Deck's frame-driven tracking and search use the gateway and existing
CAL-1 logic. Legacy absolute-angle, HOME and compatibility shortcuts cannot
write around it: unscoped requests return unavailable while a gateway is
attached. The reviewed RP2040 firmware already requires scoped session/epoch
commands. Standalone controller use without the application gateway retains its
original behavior; Active Vision and calibration still rely on their existing
firmware/lease gates and need further gateway migration and native acceptance.

The pet safety context retains the producer-reported capture age and rechecks
total age on each continuing pulse safety check, including elapsed time since
the snapshot. A stale capture is a veto even if its snapshot was recent.

The RP2040 gateway avoids creating a durable motion-attempt marker on every
explicitly disarmed, session-free observation. If authorization or calibration
session state is unknown, it retains the conservative marker behavior. This
reduces passive filesystem churn without treating passive observation as a grant.

In the combined mobile runtime, face-search outcomes reuse the existing
`HeadSearchMemory` and the lifecycle-owned memory gateway. Only authentic source
frames are eligible; fixture frames do not create search outcomes. Memory errors
are kept separate from motion decisions. The original remote-recall search preference is consulted at the authentic
sentry decision in the combined mobile runtime. Other application modes do not
yet share this lifecycle gateway; full behavioral parity remains unaccepted.

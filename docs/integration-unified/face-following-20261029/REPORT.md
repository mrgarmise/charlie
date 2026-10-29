# Real ELEGOO face following: preparation and authorization boundary

**Physical acceptance is pending. No face-following hardware trial has been run
by this increment. The complete test is not yet admissible: independently
verified pan-position and exposure-age safety producers are missing.** No
simulation, disarmed run, archive replay or passing software test substitutes for
that demonstration. PR #13 remains draft.

## Preserved starting point and correction

Existing integration branch only, starting published
`95a7cd583ea8a6a568bdfb274de21638bc1c604c`, local
`7707c53a397d61971b47bda59471f82d679e958d`, identical tree
`6cca12409fa555e6f0699358c33e0b3ba6b608e7`. Other worktrees, firmware,
calibrations, original journals and the five October 25 motion receipts are
preserved. The original YuNet detector (`vision/mobile_face.py`), complete
proportional/hysteresis/prediction/search behavior
(`behaviors/mobile_face_track.py`), and telemetry acquisition file are byte
identical to the starting commit. The working `read_ultrasonic()` method is
also byte identical. No tracker, camera manager or actuator controller is added.

A proven qualified-pan reply-validation defect was corrected: the generic
pending-command handler could accept bare `{ok}` or `{H_error}` as success.
Qualified pan now requires exact `{H_ok}` and polls cancellation, lease and
independent safety while waiting, including the simultaneous-ACK race. No
reconnect/retry or motor authority is added. Existing uncertainty persistence,
STOP/preemption, runtime binding, rollback and independent qualification remain.
The changed runtime invalidates older runtime-bound actuator qualifications.

The normal `main.py --hardware --elegoo-face-track` profile now enters the
existing ELEGOO feeder/publisher, one qualified executor, shared telemetry,
AttentionManager, original face runtime and normal Executive development child
without incidentally opening RP2040 or requiring Hailo. Combined object/pet/
primary-vision paths remain available as before. The bounded session waits for
separate **telemetry, camera-pan and chassis** boot-bound external authorizations
before constructing the tracker or submitting observations/queries. Its normal
loss timers start when tracking starts, not during the authorization wait.
This wait is startup coordination, not a disarmed acceptance demonstration.
All source/lease/environment checks still run on every actual dispatch.

The profile has a 1–120 s active duration and 1–300 s authorization wait. Keyboard
`x` followed by Enter attempts emergency STOP directly from the input thread;
EOF also stops this supervised profile. Ctrl-C/SIGTERM and observation/recording
faults exit through STOP before writer flush. Emergency STOP and uncertain
incidents cannot be cleared by installing another grant. Do not pipe away stdin
or run this profile unattended.

## STOP investigation: what is and is not proved

Both preserved manufacturer sources recognize N1/D1=0/D2=0/D3=0 and a tagged
`{H_ok}` response. The classic source acknowledges parsing before the motor loop
executes D3=0 STOP. N1 is a **drive-motor** command; it is not evidence that a
position-commanded camera servo stops. Neither source is an installed firmware
or ESP32 bridge readback. See the preserved timed-N2 source contract for hashes.

The operator supplied a chat transcription of a native 2026-10-29 00:37:40 UTC
wheels-raised trial: N2 LEFT/PWM35/T200/H=`expirytrial1`, exact
`{expirytrial1_ok}` completion at **0.292 s**, then an explicit STOP
`TimeoutError` with acknowledged false and physical stopping unknown. The
original text, including its damaged shell preamble, is preserved privately as
`operator-expiry-receipt.txt`; provenance is operator-supplied transcription,
not independently collected raw bytes/video.

The reported completion is 92 ms beyond the encoded duration and 42 ms beyond
the current T+50 ms qualified completion window. This establishes a recorded
latency mismatch; it does not establish where the delay occurred, an N1 reply's
arrival time, installed firmware identity or measured physical expiry. Historical
command-call timings also often exceed 50 ms, but missing controller helper code
means those timings cannot automatically be called wire RTT. A subsequent operator-supplied stationary N1 receipt reports an exact tagged
reply at **85 ms**. The separate minimal correction `f2a879ab37c6055c1e53e45a55509548a6dd03c1`
therefore changes only STOP response waiting from 50 to **150 ms**, as explicitly
requested by the operator. Pan remains 50 ms and N2 completion remains T+50 ms;
physical qualification thresholds are unchanged. The failed earlier STOPs remain
failed, with no retroactive repair. No deadline is enlarged to make the 292 ms
N2 receipt pass. A 292 ms reply also
needs reconciliation with the independent 250 ms freshness requirements.

The source-supported STOP packet is not changed speculatively. The unresolved
cause must be distinguished in a separately authorized motor-power-isolated
native observation: exact N1 bytes sent, partial/write failure, exact reply/tag,
late reply after timeout, missing reply, wrong/bare/error reply, disconnect,
heartbeat activity and time spent waiting for the send lock. Keep the existing
single command owner; do not connect a diagnostic second socket. Do not replay
N2 or issue an unlimited N3 start to investigate STOP.

The existing driver's new **512-event bounded in-memory** trace records raw
bounded TX attempts/completion/errors, all brace-framed RX including unmatched
late replies, ACK deadlines, sequence and host monotonic time. It performs no
disk I/O on RX/send-lock paths. The separate STOP diagnostic record retains exact command,
expected reply, bounded timeout, elapsed time, exception detail and original
receipt. The established STOP receipt dictionary shape remains unchanged. A late
reply never retroactively converts a failed STOP into success or clears a latch.
The face session drains this trace through the existing recorder; trace overruns
make the trial inconclusive and stop it. Application teardown preserves a final
wire-tail snapshot after executor close. ACKs never establish physical movement,
pose, braking or stopping.

The October 29 ultrasonic receipt has not yet been supplied in this workspace;
the working reader and older evidence are preserved. Attach/hash the original
receipt when available, with its actual protocol/units/side effects. Neither the
reported N2 trial nor an ultrasonic numeric reply is complete chassis/pan safety
qualification. No native result has been silently upgraded or relabeled.

## Historical working behavior: evidence-led baseline selection

The supplied immutable `facestuff.tar.gz` has SHA256
`7dcec7d028a99978061f1fba7d610c07bcce80c93c45eba623da646ef0441a34`.
It contains 1,547 entries, ten September 13 session directories, **10,850
telemetry rows, 1,493 annotated JPEGs and 414 logged command calls**. Recovery
used bounded regular members with traversal/link/duplicate rejection; original
archive/member hashes and timestamps remain private. Historical Python was
inspected as text/AST, never imported or executed against hardware.

The source candidates are `face_mobile_track_orig.py`, `face_mobile_track.py`
and `coordinated_attention_python_v3.py`. Their original hashes and UTC mtimes
are in the private manifest and sanitized history report. The first two import
an `elegoo_car` helper absent from the archive; the coordinated script contains
unlimited N3 pivot and swallowed STOP exceptions. Do not run that legacy
controller to obtain a superficially matching demonstration.

The early sessions establish centered/head-tracking and local-search diagnostic
coverage; the v4 `20260913_162903` recording adds logged full sweep; v5
`20260913_164531` is the strongest supplied **attention/reacquisition comparison
candidate**, with 41 logged command calls and an `attention_aligned` event.
Its final aligned pan is reported as 105 degrees, not proof of a measured
90-degree camera position. Its CSV has **no yaw fields**. The separate v3 source
implements yaw-guided alignment, but has no corresponding yaw recording here.
The newest source timestamp is not used as proof of success. No Git checkout,
per-session source snapshot, independent motor video, pan encoder measurement,
yaw trace or measured STOP record binds these files into the requested complete
previously successful cycle. That exact historical checkout remains unproven;
the identified recordings are useful comparisons, not fabricated acceptance.

Eligible native CPU work was completed: the **unchanged current detector** was
replayed under the existing resource/thermal guard over all 1,493 archived
annotated screenshots, joined by frame number to telemetry. It detected faces
in 622 screenshots and agreed with historical presence in 1,169/1,493 joins.
This disagreement is retained, not tuned away. These are annotated screenshots,
sparse selected history with different temporal selection and unknown historic
model bytes; the figures are **not accuracy, live tracking FPS or physical parity**.
The replay retained per-frame predictions/timings privately and used two CPU
cores, 768 MiB budget, required Pi thermal telemetry (57.85 C at final sample),
and approximately 181.8 MB peak owned RSS. No camera or motor was opened.

## Existing-hardware measurement feasibility, before new hardware

The current ELEGOO MJPEG publication explicitly has unknown exposure timing;
receipt time cannot establish exposure age. N24's installed MPU, once verified,
measures chassis yaw, not relative camera-servo position. N5's commanded angle
and ACK are not measured servo feedback. No installed independent producer for
the missing measurements has been verified. Manually writing the expected values
or `capture_timing_verified=true` would manufacture evidence and is forbidden.

Existing hardware offers testable optical approaches **without proposing a new
sensor**: the existing IMX708/Pi feeder could observe a calibrated physical
reference on the camera assembly relative to the chassis, using an independent
subscriber and bounded pose uncertainty. Installed OpenCV exposes ArUco and
solvePnP, but that is only available software, not a qualified measurement.
Stationary operator-assisted placement/calibration and actual visibility,
accuracy (including the gate's two-degree agreement) and latency must be tested.
No second camera owner is needed or permitted. Existing phone/external video can
independently evaluate trial movements, but a recording alone is not a live feed.

For exposure age, an existing Pi/Mint display visible to the ELEGOO camera could
show unpredictable, locally issue-time-bound visual challenges. A correctly
decoded nonce cannot have been exposed before its issue; receipt minus issue is
a conservative upper bound only after validating the issuer/clock, rendering,
uniqueness, decoder and frame binding. Missing/occluded/old challenges must veto
motion. This must be independently calibrated and tested across the tracking
field; a timestamp pasted onto received frames is not an exposure measurement.
The existing face tracker remains unchanged; a future measurement adapter would
subscribe to the existing owners. Neither approach is implemented or qualified
by this increment. First assess actual placement/visibility with power isolated;
only if existing hardware cannot meet the bound should additional hardware be
considered. This is an explicit missing producer/measurement gate, not a generic
claim that native software work was impossible.

## Tests, preservation and boundary

Focused tests cover the real driver with fake replies, pan bare/error/wrong-ID
rejection, cancellation/ACK races, strict timed N2/STOP behavior, bounded isolated
wire history, uncertainty preservation, no-owner startup, normal main routing,
EOF STOP, recording failure before attention, immutable/superseding evidence,
and all existing chassis/pan/telemetry authorization checks. The new admission
CLI only wraps the existing evaluator/deployment/revocation APIs; it never opens
a device or manufactures a passing trial. Its read-only status does not create
a missing journal and respects an existing uncertain-motion marker.

Local expanded selection before STOP integration: 112 tests passed; final combined
STOP/face/executor/authority/recording selection: **127 passed** in 2.41 s.
The final receipt-compatibility expansion passed **186 tests** in 3.31 s.
Canonical conformance: **129 passed**.
An initial new test used a mutable fake frame and correctly failed the existing
immutable-publisher check (110 passed, one failed); only that fixture was corrected.
Original failure logs remain private. The first independent combined-head CI
found one existing exact-receipt compatibility assertion failing (1,564 passed,
21 skipped). Diagnostic fields were moved out of the established receipt into
a separate record; the original compatibility assertion was retained unchanged. Independent full CI and exact published
commit are reported on PR #13 after publication. Tests and archived replay are
software preparation only, not the requested demonstration.

Private preparation receipts are under
`/home/five/charlie-face-qualification-20261029`, including the original supplied
archive inventory, immutable historical copies/member manifest, archive analysis
and per-frame replay, operator transcription, preservation hashes, worktree
inventory, test logs/XML. No personal face images or original historical source
archive is published. The new normal session will use the existing asynchronous
`CaptureEvidence` writer: all consumed source descriptors/target selections,
5 Hz selected original pixels with explicit retention dispositions, shared
actuator/pose/range observations, alignment state, monotonic/UTC mapping, raw
wire events, terminal disposition and final wire tail. Any missing samples,
source failures, queue/disk/trace overrun, timeout or ambiguous STOP remain visible.
Successful recording completion is not successful behavior acceptance.

**No physical operation has been performed.** Installed identity, independent
producer implementation/qualification, actuator-specific trials/authorizations,
real supervised face behavior and independent video evaluation remain pending.
The exact conditional launch, setup, measurements and operator checkpoint are in
[OPERATOR-TRIAL.md](OPERATOR-TRIAL.md). Do not merge this draft PR or declare the
mission complete at this preparation boundary.

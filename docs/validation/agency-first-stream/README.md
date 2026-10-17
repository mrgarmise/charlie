# Agency-first streaming repair of PR #5

Base: `fad0f96911c2168e3730a64b653fb7b73b3b5b54`, continuing
`feature/fast-projectile-self` and draft PR #5. No merge to main, physical
controller, gameplay, firmware, servos, or learned-policy activation is authorized
or performed by this work. E1, P1 and I1 remain independently NOT YET DEMONSTRATED.

## Implemented data path

`PiCameraSource` starts one `ObservationStream` after the current sensory
preflight has qualified the view and locked manual focus 2.0. Picamera2 queueing
of a cached last request is disabled. The producer requests successive completed
frames with `flush=False` and a one-second native request timeout. It copies pixels
and matching metadata, releases the request in `finally`, and appends only to RAM.
It performs no recognition, image encoding, evidence commits, or publishing.
Public raw read/AF entry points reject competing readers or gameplay autofocus.

`ObservedCamera` consumes the newest appropriate distinct exposure and records
it through the existing recorder. Sequence gaps and ordinary history evictions
are explicit. The stream belongs to the existing camera source, so new episode
borrowers reuse the producer and camera through the three-game session.
`CameraSession` remains the owner responsible for final close before reflection.
No second physical camera or competing Picamera2 reader was introduced.

The buffer holds at most 24 frames and 64 MiB using conservative four-byte pixel
accounting. Ordinary superseded history can be evicted and is counted. A firing
window pins its pre-command baseline and subsequent frames. Pinned overflow
fails the experiment and signals cancellation; it never silently drops a critical
frame. Replay of a pinned window may temporarily retain another bounded set of
image references while ordinary capture continues (at most another 64 MiB).
Existing recorder/score/semantic queues retain their own independent limits.

`capture_window` pins **before** synchronous FIRE submission. The independent
camera producer continues throughout transport acknowledgment, the held pulse,
release, and a bounded 250 ms post interval. Frames are replayed in original
exposure order through the existing lightweight candidates and `ShotOrigins`.
The previously recorded baseline is not delivered or journaled twice.

Firing remains 60 ms by default. The player supports explicit
`--acquisition-fire-ms 30..400`; it neither adjusts itself nor extends the
transport's existing 500 ms hold lease, the three-second recovery action budget,
or the unresolved-agency investigation deadline. A command is refused when the
remaining existing budget cannot contain the requested experiment. The marathon
continues to use its existing child defaults; this change does not grant a longer
marathon pulse or new campaign authority.

The trajectory path now accepts legitimate pre-ack exposures following wire
submission and allows later samples to extend a path born during FIRE. It retains
actual command submission/write/ack times, controls-ready, pulse end, release
submission/ack, sensor metadata and frame timestamps. Wire acknowledgment and
release brackets are **not** measured display response times. The existing
post-command inference tolerance is still unqualified on native hardware; no
latency calibration was invented. Missing, repeated, nonmonotonic, stale or
ambiguous frames cannot supply new causal evidence.

Three distinct observations, commanded direction, a unique back-projected
origin, and two nonparallel experiments remain required. Spatial/association
thresholds and movement qualification are retained. Projectile confirmation stays
separately gated by `--projectile-self`, off by default pending native evidence.
A supported visible SELF returns immediately rather than repeating E/N probes.

## Agency-first gameplay

An acknowledged START alone cannot seed expected SELF. The existing fresh
three-observation visual commencement gate remains required. A qualified new game
seeds an **expected** center hypothesis; a visible candidate makes it provisional;
causal identity remains separately confirmed. Attaching without a new acknowledged
START does not claim a newly spawned life. Center weights are priors, not evidence.

The existing velocity/time tracker and signed BODY response model remain in use.
Brief same-track occlusions are retained for at most two misses and 250 ms;
controls remain neutral without an observed position. Ambiguity, contradictions,
prolonged loss, new coordinates or independently confirmed respawn invalidate the
appropriate identity state. Missing SELF never establishes death or GAME OVER.
Native individual-life sensing remains unqualified; the guarded respawn API does
not manufacture it from missing detections.

During supported, stable gameplay `AgencyScreen` uses a small scene signature
and SELF continuity rather than title/high-score/GAME OVER templates. Significant
scene change or unsupported SELF restores full investigation. Brief retained
occlusion receives neutral observation first. The fast path cannot grant restart
permission or conclude game completion. Existing independently qualified restart
checks, the 15–20 second investigation horizon, and progress supervision remain.

The ordinary controller pulse can overlap main-thread perspective correction and
batched template classification of a newer frame. Only bounded transport I/O runs
on the controller worker; expensive recognition is not moved to another CPU
thread. There is at most one in-flight controller operation and one prepared
ordinary observation. Unused prepared observations are ordinary superseded data,
not fabricated extra decisions. No evidence is emitted using the old frame's
metadata: pixels and detector traces are committed only on actual delivery.

Prepared pixels must follow controls-ready and be at most 250 ms old. A stale
prepared decision sends no tactical action. These intermediate observations are
explicitly continuity observations, not completed causal BODY windows. Every
fourth confirmed native gameplay cycle retains the original two-frame BODY
measurement; uncertain acquisition retains it on every probe. Unmeasured tactical
feedback remains unresolved, never false negative feedback. Forebrain/Hindbrain,
their strategies, thresholds, prediction records, and Executive interfaces are
preserved. Batching computes the existing reference scores without changing
class admission thresholds; regression tests compare them to the old scorer.

## Measurements and evidence

The original `charlie-pr5-game01.tar.gz` remains unchanged in the supplied source
files. SHA-256:
`c02b9ec790a028f54bc143fb1c54d06aad8542c83122bf62e75f5a96c0b21780`.
The 156,285,077-byte archive is not duplicated into Git. `baseline/manifest.json`
identifies it and hashes exact selected JSONL/report/frame copies. These are
regression evidence, not new experience or successful replay.

`development-20261017-200109`, native revision
`73169db9ad2648ca7e4088979d22905900052c6a`, still has 37 agency observations,
six firing observations, zero accepted shot votes, no confirmed SELF, zero
tactical actions, and no verified GAME OVER. Recorded median delivery was 1.656
observations/s; frame-duration cadence 14.902/s; exposure 66,655 microseconds.
Automated retained score was 100. The operator reports 1,500; a complete-game
score is independently unresolved. Neither is relabeled as a successful run.
The earlier `development-20261017-182719` archive and 3,247-record notebook are
also unchanged. No historical observation was admitted as a new learning event.

On the six exact archived firing playfields, two host replay passes measured:

| Stage | Host median | Host p95 |
|---|---:|---:|
| Full terminal classifier | 86.25 ms | 92.96 ms |
| Hypothetical supported-SELF screen check | 1.63 ms | 1.68 ms |
| Old region/template path | 36.56 ms | 43.56 ms |
| Batched region/template path | 33.74 ms | 36.35 ms |
| Class-free acquisition | 19.58 ms | 19.85 ms |
| Tracking and belief | 1.88 ms | 3.04 ms |

This CPU benchmark explicitly supplies a hypothetical supported SELF only to
measure scheduling cost. It does not recover identity in the failed recording,
prove gameplay, measure Pi speed, or establish 8–12 native updates/s. The archived
EAST image also contains an elongated bright feature near the central candidate.
Its identity/motion cannot be established from these sparsely sampled images.
No new streak-specific recognition or weakened trajectory gate was introduced.

`report.json.performance` records sustained distinct supported decisions, median,
p95 and worst camera-to-decision age, stage costs, interruptions, identity changes,
producer cadence/gaps/evictions/RAM, CPU time, peak RSS, and a thermal snapshot.
Meaningful means one distinct exposure at most 250 ms old used for an existing
Forebrain/Hindbrain decision with supported SELF. Capture counters, duplicate
frames and raw FPS do not count. Samples are bounded to the last 2,048; the
sustained counter spans the run. Overlapping controller/preparation wall times
must not be added as serial CPU costs. Detailed wire timings remain in agency
and action evidence. Exact controller-to-display feedback delay remains unmeasured
without independent visual onset qualification; the report says so rather than
turning acknowledgment into display onset. Recording completion/failure and
queue statistics remain in the report's existing `recording_pipeline` and
`recording_error` fields; queued events are not reported as durable commits.

## Serialization repair and local history

`spawn_prior.weights` now has string JSON keys at the evidence boundary, while
internal track IDs and prior arithmetic remain unchanged. A host regression
writes the full snapshot through `CaptureEvidence`, closes the writer, opens
the durable `EvidenceJournal` read-only, and verifies its committed chain.

The native report authenticates revision 73169db, but GitHub cannot retrieve
that local-only commit. Therefore this is an explicit semantic incorporation of
the reported fix, not a falsely claimed cherry-pick. Keep the native checkout
and its commit intact. Install to a new worktree; do not reset or overwrite the
native branch, original notebook, or run archives. Preserve any additional local
changes before comparing/merging that local commit with the published repair.

## Host validation result

Final frozen-source full host suite: **1,324 passed, 21 skipped, zero failures
and errors**, 325.93 seconds. Focused suite: **109 passed**. The single full-suite
warning concerns JUnit property formatting. These include 23 additional cases
covering concurrent capture, pinned overflow, timestamp rejection, transport
cancellation, neutral-only occlusion, startup proof, three borrower lifecycles,
terminal scheduling, durable serialization and the existing shot/policy handoff.
Source hashes, final logs/JUnit and earlier development results are retained in
`tested-source-sha256.json` and `host-tests/`. No runtime source changed after
the final full run began. Native hardware, physical timing and learning are not
established by these host fixtures.

## Host and native acceptance

Use only `tests/`, not repository-root pytest (legacy scripts can access hardware):

```sh
mkdir -p /tmp/charlie-agency-tests
TMPDIR=/tmp/charlie-agency-tests python3 -m pytest -q tests
python3 -m pytest -q tests/test_agency_stream_engine.py tests/test_projectile_agency.py
```

Replay is offline and never opens a controller/camera. Output must be outside
the original frames directory:

```sh
python3 -m experiments.ppal.benchmark_agency_engine --frames docs/validation/agency-first-stream/baseline --output /tmp/charlie-replay-cost.json
```

Native installation, code and tests only (verify HEAD against the published SHA
in PR #5 before testing; leave the original native worktree untouched):

```sh
git fetch origin feature/fast-projectile-self
git worktree add --detach /home/five/charlie-agency-stream origin/feature/fast-projectile-self
cd /home/five/charlie-agency-stream
git rev-parse HEAD
PYTHON=/home/five/Projects/charlie/.venv/bin/python
mkdir -p /tmp/charlie-agency-tests
TMPDIR=/tmp/charlie-agency-tests "$PYTHON" -m pytest -q tests
```

After camera-only permission and with no other camera owner, this opens the
camera, verifies a bounded stable manual 2.0 lock, measures continuous capture
and lightweight processing, and closes before writing. It opens no controller:

```sh
"$PYTHON" -m experiments.ppal.acquisition_profile --native-camera --seconds 10 --output /tmp/charlie-continuous-camera.json
```

The profiler now waits for verified stable manual metadata instead of rejecting
the first pipeline-lagged frame immediately after requesting focus. It retains
fresh timestamp, lens-position, hardware-limit and Idle checks, with no autofocus
optimization or sweep. Numeric-timeout/cancellation support in Picamera2 is
required; unsupported drivers fail closed rather than using an unbounded capture.

A full gameplay acceptance still requires separate physical authority and native
qualification. Then retain one camera session and complete the existing three-game
marathon with independently fresh restart permission, followed by reflection
only after the block closes. Preserve the original notebook. Require fresh
supported tactical updates, no unqualified identity changes, no critical capture
overflow, no evidence errors, successful worker/camera close, and authentic
terminal/restart evidence. Evaluate sustained 8–12 meaningful updates/s, age p95
and worst interruptions; report measured shortfalls and their stage costs. Check
CPU/RSS/temperature throughout the run with existing thermal supervision; a final
temperature snapshot alone is not a sustained thermal qualification.

Native camera and controller performance, display feedback delay, candidate
shape/trajectory discrimination, life sensing, tactical success, complete games,
and the 8–12/s target remain **NOT YET DEMONSTRATED**. No armed launch command or
new physical grant is supplied here. E1/P1/I1 and all original ALA obligations
remain independently open.

## Rollback

No firmware or physical deployment occurred. Preserve new evidence, then select
an independent checkout of the exact previous published revision:

```sh
git worktree add --detach ../charlie-pr5-rollback fad0f96911c2168e3730a64b653fb7b73b3b5b54
```

The native 73169db checkout remains separate and retains its serialization repair.
Do not initialize, delete, reset or replace the original notebook. Any future
physical use of either revision still requires its own authorization.

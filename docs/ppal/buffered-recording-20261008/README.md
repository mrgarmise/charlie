# Buffered evidence recording within the normal PPAL application

Continues exact remote parent 70e5b714f0d2ddad72fc2f4792032fd22f99963e on feature/agency-first-self. That remote SHA was verified before changing code. Original historical directories, the October 8 failed-start archive/image/report, native developmental notebooks, firmware, controller sandbox, camera ownership, PPAL chooser and Learning Executive are preserved. All new execution here is x86_64 host software simulation, original-pixel replay and loopback tests. No native Pi or physical gameplay result is claimed.

## What changed

CaptureEvidence remains the recorder attached to the existing ObservedCamera. It now owns one bounded FIFO writer for original lossless frames, journal records, agency.jsonl and steps.jsonl. Camera ownership, CameraLease, browser preview and normal application entry points remain unchanged. No separate camera manager, learning scheduler or recording application is added.

The previous recorder already encoded PNGs on a worker, but event() synchronously waited behind those frames. Each step also fsynced steps.jsonl on the control thread. Both paths now enqueue snapshots and return stable identifiers. Image encoding/compression, PNG publication, artifact hashing, file fsync and journal commitment run on the writer. Frame copying, metadata validation, canonical small-document preparation and ID hashing remain bounded local foreground work. The ordinary controller protocol, watchdog publication and existing diary interfaces are preserved; this is not a claim that every application operation is free of I/O or a hard real-time guarantee.

Normal Robotron startup uses these configurable budgets:

| Interface | Default | Meaning |
|---|---:|---|
| --evidence-frame-capacity | 16 | In-flight and queued original frames |
| --evidence-record-capacity | 512 | In-flight and queued writer tasks, including logs/events |
| --evidence-memory-mib | 128 | Accounted source snapshots and queued document bytes |

One bounded emergency item retains the observation/event that triggered saturation. Telemetry separately exposes this slot and worker encoding allowance (up to twice the largest source-frame size). These account for buffers outside the ordinary queue; the configured byte budget is not an assertion about total Python/vision/camera RSS. The writer releases completed frame snapshots before waiting for another task. Telemetry includes current/peak occupancy, frame occupancy, buffered/peak bytes, capacity, accepted/written counts, encode/write costs, throughput, pause count, writer state and recovery gaps. Normal steps and final report include recording_pipeline.

During preflight, bounded waits may drain the recorder before controller creation. During ordinary play, a full frame/record/byte budget raises the existing observable ObservationFailure instead of waiting for routine image service or silently discarding evidence. Existing player supervision stops/neutralizes controls, releases the camera and drains the retained queue/emergency item. This ends the recording run conservatively; it does not pretend the game ended. Storage faster than sustained capture is still needed for uninterrupted operation. Buffering absorbs bursts, not unlimited excess production.

## Stable observation, prediction and action references

An immutable camera_observation descriptor fixes sample identity, original exposure/capture metadata, clock, size/mode and eventual source path before enqueue. Its content ID is available immediately. The writer commits that descriptor, writes the owned original pixels losslessly and adds a hashed camera_capture artifact linked to it. Caller mutation after enqueue cannot change the retained pixels or metadata.

The existing EvidenceJournal gains immutable PreparedEvidence and prepare/commit methods. PPAL prepares each forecast before executing its action, using the observation that informed it. Its ID, expected action and enqueue-time timestamp remain unchanged when the worker later commits it. Controller execution/outcome records preserve that ID and their own original observation references in FIFO order. Writer lag does not change the exposure time or move a forecast to the time of its outcome. Future-source, hindsight and duplicate-resolution protections remain.

Buffered predictions explicitly use mode buffered_live_prospective and disclose RAM-at-enqueue durability. They must not be confused with the existing live_prospective records committed synchronously before an action. An asynchronous RAM acknowledgement is not a crash-durable commitment receipt. A verified final writer receipt can establish that all accepted records arrived intact and in causal order; it cannot prove unpersisted predictions survived a crash or independently certify their causal correctness. Existing independent evaluation, partition, score qualification, policy readiness/authorization and rollback gates remain required.

## Completion, interruptions and admission

recording-state.json is durably created as open before capture begins. Shutdown verifies writer termination, the append-only journal, every observation/artifact binding, original PNG hashes and writer-owned log hashes before recording complete. PNGs are encoded on the worker and published from fsynced .png.pending files without clobbering existing originals. Final verification occurs after controls/camera close.

memory.episode_identity checks this completion receipt before sealing a new capture and before identity-based evidence acquisition/evaluation admission. Missing, corrupt, inconsistent, open or incomplete new-format receipts fail closed. Deleting a marker cannot turn new buffered observations into legacy evidence. Historical packages without the new claim continue under their existing semantics; they are neither rewritten nor retroactively qualified.

Interrupted .png.pending files and orphaned originals are preserved; sample numbering never overwrites them. Completed source records/receipts/manifests reopen for inspection without modification. A process killed while RAM work is queued leaves the durable open marker. Recovery retains committed records and reports an interrupted flush with an unknown RAM tail. It cannot seal that episode as complete merely because a later process can drain different work. Recovery must not fabricate missing frames or erase that gap. Future normal sessions use their existing distinct capture identities, while the same developmental notebook continues.

Writer failure and drain timeout leave incomplete status and uncommitted identifiers when known. A timed-out writer finishing later does not silently promote its status to complete. If storage cannot save even a failure marker, the initial open marker still prevents admission. Capacity counters are released before completion acknowledgement. A forced interleaving reproduced the pre-publication race as deque index out of range; the correction accepts the next capacity-one preflight capture without a false pause. Normal finalization now releases controller/camera before disk-backed progress/diary operations; a simulated finalization disk error verifies release and prevents manifest publication. A complete writer receipt is not a verified complete game or final score.

## Reproduce software acceptance

```bash
python -m pytest tests/test_buffered_recording.py tests/test_sensory_recording.py tests/test_robotron_agency_integration.py tests/test_episode_evidence.py -q
python -m pytest tests -q
python tools/benchmark_buffered_recording.py --output /tmp/charlie-buffered-benchmark.json
```

Tests use controlled camera/controller worlds or loopback transport only. Even simulated tests passing --arm do not connect physical hardware. Cases cover normal run ordering, bursts, independent memory/frame budgets, slow encoding, queue saturation and retained overflow, encoding/fsync thread ownership, input immutability, writer failure/full-storage simulation, shutdown timeout, abrupt process death, restart, immutable completed manifests, missing/corrupt completion rejection and normal-runner release on logging failure. Original records are retained exactly on repeated acquisition.

The benchmark freezes the original recorder module from commit 70e5b714f0d2ddad72fc2f4792032fd22f99963e and compares it with this implementation. Both use the same existing Forebrain/Hindbrain and the same 20 original failed-start images at a nominal 10 Hz. Those repeated images are software replay, not additional independent experience; controlled tactical WorldStates are not inferred from the attract image. Additional cases enqueue a burst or add 100 ms of artificial writer delay. Every run opens zero controllers and qualifies zero findings. Raw benchmark captures remain diagnostic software data outside normal episode acquisition.

## Guarded native Pi benchmark still pending

The Work host is x86_64, Python 3.12.14. No Pi endpoint/tool was available, and hostname charlie did not resolve. This is an access limitation, not a Pi failure or measured Pi performance. The benchmark's native guard was tested on the host and correctly rejected native camera execution.

On the actual Pi, preserve the persistent notebook/captures and previous failure reports. Verify the exact published SHA and existing Python/camera dependencies in the existing isolated checkout. Native software regression and the persistent unarmed Executive/restart acceptance can use the existing tools/accept_episode_identity_pi.sh with that full SHA; its software test list now includes buffered recording. It does not open a physical controller or camera.

For an authorized camera-only native performance run, use an unused diagnostic destination outside robotron-runs and the developmental episode roots:

```bash
python tools/benchmark_buffered_recording.py --native-camera --samples 60 --hz 10 --output /tmp/charlie-native-buffered-benchmark.json
```

This requires independently verified aarch64 Raspberry Pi 5 model data and the existing PiCameraSource/CameraLease interface. It opens the camera sequentially for each case and releases it each time. It creates no controller, game, servo or policy activation. Existing preview ownership/lease rules still apply. It records actual exposure/capture metadata, acquisition plus snapshot cost, tactical fixture cost, foreground recording cost, encoding/frame service, CPU/per-core counters, peak RSS, sustained throughput and worst queue behavior. Retain all outputs including failures; rerun only into a new diagnostic destination. Real camera pixels do not make its synthetic tactical states physical gameplay evidence. A later separately authorized actual arcade run is still needed for full live perception/transport latency and normal game responsiveness.

No native camera acquisition, microSD throughput, thermal behavior or Pi latency acceptance has been executed here. Do not claim the user requirement for native benchmarking is complete. ALA-2 remains open until independently measured complete-game Robotron score improves through Charlie-originated learning.

## Independently executed host results

Final full suite: **670 passed, 20 skipped in 127.00 seconds**. Focused shutdown/recording/acquisition suite: **43 passed in 17.05 seconds**. Torch and the unavailable original October 1 collision capture remain explicit skips. git diff --check and guarded shell syntax checks passed. Initial fixture-schema and memory-accounting assertion failures are retained in this directory; they were corrected to account for the explicit buffered prediction mode, observation descriptors and descriptor memory. No original evidence was rewritten.

Final benchmark ran after regression finished, on x86_64 Linux 6.18.44 / Python 3.12.14, with pytest 9.1.1, NumPy 2.5.3, OpenCV headless 5.0.0.93 and Pillow 12.3.0. Dirty candidate code hashes and frozen baseline module hash identify measured sources. All cases retained 20/20 images without writer failure. Foreground includes replay acquisition/snapshot, fixture tactical choice and recording enqueue; it excludes real recognition/tracking, transport and controller pulse duration.

| Workload | Frames retained | Pauses | Foreground median ms | p95 ms | Maximum ms | Writer median ms/frame | Encoding median ms | Wall seconds | CPU seconds | Peak RSS KiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline-normal | 20 | 0 | 84.329 | 87.589 | 92.006 | 81.034 | 79.187 | 1.987 | 1.697 | 31560 |
| buffered-normal | 20 | 0 | 1.361 | 2.770 | 4.826 | 81.435 | 79.223 | 2.028 | 2.337 | 53636 |
| buffered-burst | 20 | 1 | 2.323 | 5.091 | 6.045 | 81.971 | 79.817 | 1.771 | 1.819 | 111236 |
| buffered-slow-storage | 20 | 0 | 2.210 | 2.693 | 4.531 | 183.444 | 80.733 | 3.761 | 1.796 | 111236 |

This demonstrates reduced host foreground recording latency, not increased storage throughput or a Pi speedup. Buffering trades bounded RAM for fewer routine waits; initial measurements are also retained to expose variation. RSS is cumulative process high water, and per-core utilization includes unrelated OS activity. The delayed-storage case uses a deliberate software delay, not a real failing microSD. Twenty samples cannot establish a native worst-case timing guarantee. Uninterrupted sustained gameplay, native camera/vision latency, thermal effects and independently qualified complete-game SCORE improvement remain pending.

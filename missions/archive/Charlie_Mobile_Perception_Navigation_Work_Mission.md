# Charlie Mobile Perception and Pet-Aware Navigation — Work/Codex Handoff

**Prepared:** 2026-10-24. **Project:** `mrgarmise/charlie`. **Purpose:** Four staged, additive milestones extending Charlie's existing ELEGOO car tracking into distributed Hailo perception, animal tracking, guarded navigation and autonomous learning. This document is an implementation specification, **not authorization for physical actuation**.

## Verified repository reconnaissance (2026-10-24)

GitHub default `master`, latest surfaced consolidation commit `bcf8082f6319c63c4bd6bcceeab5faea37241654` (2026-10-13, “Merge verified Best of Charlie consolidation (#4)”). Recheck branch heads and working trees at execution time; no live Pi or car inspection was performed for this handoff. A 1,251-pass/21-skip software report is contained in the commit message; it is not new validation for mobile navigation.

Files inspected on `master`:
- `main.py`: normal application uses `vision.camera.Camera`, `vision.detector.FaceDetector` or `ColorDetector`, `vision.stimulus.VisionStimulus`, `stimulus.bus.StimulusBus`, `attention.manager.AttentionManager`, and separate `learning.lifecycle.run`. Mobile behavior enabled by `CHARLIE_MOBILE_ENABLED=1`; hardware startup separately selected with `--hardware`, offline default. The existing camera object is a Pi `Picamera2` camera, not a verified ELEGOO stream.
- `attention/manager.py`: forwards `vision_target` / `vision_lost` events to existing RP2040 `TrackBehavior` and a separate ELEGOO `MobileTrackBehavior`. Mobile initialization is lazy and an exception is logged.
- `behaviors/mobile_track.py`: currently uses target centroids to pan the mobile camera and, after an off-axis dwell, turn the chassis with yaw feedback. Stop/cancel on target loss applies to attention alignment, not yet proven to be a whole-car collision safety implementation. Preserve behavior and tests.
- `motion/mobile_base.py`: thin wrapper for `hardware.elegoo_mobile.ElegooMobileBase`, exposes connect, stop, pan, yaw, pivot, begin/update/cancel attention alignment.
- `hardware/elegoo_mobile.py`: TCP transport default `192.168.4.1:100`, background receive thread, heartbeat handling, request correspondence and guarded alignment state. Verify deployed firmware protocol, AP networking, motor STOP semantics and telemetry on actual hardware.
- `vision/mobile_face.py`: YuNet/OpenCV human face detector with stable selection. This is human-face tracking, not existing cat/dog detection.
- `vision/camera.py`: primary Pi `Picamera2` capture with camera lease ownership; don't commandeer this for mobile camera transport.
- `vision/stimulus.py`: emits 2D `vision_target` and `vision_lost`; preserve compatibility and add richer observations alongside legacy events.
- `motion/controller.py`: primary RP2040 head/neck `Deck` explicitly knows nothing about the ELEGOO car; preserve separation.
- `learning/lifecycle.py` and `ALA_LEARNING_CHARTER.md`: existing single Learning Executive, evidence journal, MemoryGateway/Evaluator and separately supervised lifecycle. Reuse; do not introduce a competing learning scheduler.

**Unknown and must discover before implementation:** actual deployed ELEGOO firmware branch/SHA; current camera module, camera stream type/URL, camera source used by live face tracking, video compression/rate, power topology, ultrasonic read/STOP implementation, interface versions, exact Hailo runtime/model availability, behavior branch vs installed checkout, real user network. GitHub code search returned no indexed hits for initial mobile terms, so the inspection above was direct file-fetch, not an exhaustive repository audit. Do not assert car-camera frames already stream to the Pi.

## Non-negotiable principles

1. **One Charlie, multiple bodies:** retain one identity, existing PPAL, Learning Executive, attention, evidence, memories, and safety authority boundaries. Mobile body is a capability, not a competing autonomous agent.
2. **Extend, don't replace:** retain existing human-face tracking, mobile LOOK/ATTEND, RP2040 neck, Robotron pathways, existing driver/protocol; add adapter-level functionality and structured observations. Avoid a new sidecar application, robotics manager, ROS stack or firmware replacement unless demonstrated necessary.
3. **Action authorization:** this mission allows inspection, code changes, tests, offline replay and *unarmed* perception checks. **No car motion, servo movement, firmware flash, policy activation, armed game, or physical pet-following without distinct explicit authorization.** No previous permission is implied.
4. **Safety remains local:** car-local timely STOP, disconnect timeout, collision/obstacle threshold, emergency override, bounded speed and turn limits, and an independent actuation authority gate. Depth model output is advisory—not certified clearance; ultrasonic alone may miss low/soft/angled obstacles. Fail closed on stale/missing frames, depth anomalies, invalid telemetry, uncertain obstacle clearance, controller error, or expired lease. Do not chase pets beneath furniture, into stairs, or into unobserved space. Require low-speed supervised acceptance before autonomous activity.
5. **Evidence:** capture source frame ID/time, clock domain and sync uncertainty, origin device, camera calibration and pan, model HEF/hash/version, runtime, software SHA, inference times, detections and uncertainties, source ultrasonic/IMU values, proposed actions, guards, actual execution acknowledgement, and outcomes. Retain negative/inconclusive results; never mistake queued commands for motor execution or estimated depth for calibrated meters.
6. **Resource discipline:** adaptive frame sampling/backpressure, drop old frames in favor of recent ones, do not block primary Pi camera or Learning Executive, benchmark thermals and latency before committing schedules. Model compatibility must be verified against **Hailo-8L** and actual HailoRT/compiler runtime; downloaded or synthetic HEFs must not be presented as physically qualified.
7. **Conformance:** read current `ALA_LEARNING_CHARTER.md`, ALA2 standards, hardware docs, existing tests and branches. Keep work isolated on a descriptive feature branch based on the intended integration branch. Small independently tested commits, push to branch at meaningful milestones. Record exact SHAs, artifact hashes and gaps. Never reset user worktrees or alter preserved experimental archives.

## Milestone 0 — Required foundation / audit (before coding)

- Fetch current remote refs, active PRs and relevant feature branches; record checked SHA and dirty state; inspect `hardware/elegoo_mobile.py` **in full**, `behaviors/mobile_track.py`, all car-related tests/docs, camera and networking adapters, Hailo inference code and camera ownership; verify any deployed firmware/face tracker actually in use.
- Produce concise capability inventory: implemented / host tested / native Pi checked / physically demonstrated / unknown, with exact links and SHA.
- Trace actual image route end-to-end; do not assume ESP32/board camera support or stream protocol from model name. Identify whether frames currently originate on the Pi 5 camera, car camera, or another source. Verify which devices can reach which others on ELEGOO AP `192.168.4.1` and home's LAN without disrupting working connection.
- Inspect actual Pi 5 Hailo-8L `HailoRT 4.23.0` environment (historical report, verify current), HEF availability/licensing and compatibility for YOLOv8n animal/object detection and FastDepth or SCDepthV3. Benchmark actual formats and quantized output decoding on authentic indoor frames.
- Record car stop, watchdog and ultrasonic behavior, power/thermal/wiring, hazards (stairs, edges, floor clutter, pets), and independently gated motion authority. List gaps to close **before** physical operation.

## Milestone 1 — Distributed image acquisition and perception (no movement)

**Deliverables:** Extend existing vision interfaces with a `MobileFrameSource` adapter matching the *verified* car stream/transport, leaving `vision.camera.Camera` and the RP2040 camera lease unchanged; timestamped bounded transport with reconnect, frame sequence, resolution, source ID, pan pose metadata, compression info, and fault telemetry. Reuse/extend shared inference scheduling, Hailo runtime initialization and model adapters instead of duplicating code. One acquired frame may feed both YOLO object detection (cats, dogs, people) and monocular depth on configurable cadence; CPU/offline fallback for tests must be visibly distinct from Hailo qualification. Generate structured `MobilePerceptionObservation` retaining legacy 2D target events where needed. Allow recorded-frame replay with actuation disabled.

**Acceptance:** authentic car frames reach the Pi with measured timestamp ages and provenance; independent detector/depth outputs are decoded and overlaid/logged; stale/dropout/reconnect tests pass; no motion command occurs in unarmed mode; other Charlie camera, face track, learning and Robotron tests remain green. Record throughput, model latency, end-to-end latency, dropped/stale frames, thermals, HEF hashes, and test environment. If car frames are not available, first milestone stops at tested adapter and documented blocker, not simulated success.

## Milestone 2 — Animal detection, persistence and attention (no chase)

**Deliverables:** Build on existing `MobileFaceDetector` selection pattern and `MobileTrackBehavior`/AttentionManager; allow task-specific target categories (`person`, `cat`, `dog`, `unknown`) with stable object IDs, tracked bounding boxes, confidence, temporal hysteresis, multiple-animal arbitration, target loss and reacquisition. Explicitly distinguish generic species classification from recognizing the identity of a particular pet. Keep manual/legacy human face tracking behavior intact. Let Charlie's Executive request observation or choose among safe investigations; record observations into existing evidence/journal via a bounded adapter—do not let detector itself choose the learning agenda.

**Acceptance:** replay authentic indoor sequences demonstrating stable cat/dog tracking, crossings, partial occlusions, loss/reacquisition and abstention; verified noninterference with human face tracking and main RP2040 behavior; no motor command required for acceptance. Quantify false positives, misses, track switches and stale updates. Record difficult cases (black fur, reflective floors, lighting, low angle).

## Milestone 3 — Guarded local navigation / obstacle-aware pet following

**Deliverables:** Create a bounded local navigation decision interface within existing PPAL/chooser, fusing model-relative depth, RGB object boxes/segmentation or estimated floor regions, actual ultrasonic measurements and available yaw/motion telemetry. Do **not** claim absolute metric depth without calibrated evidence; use measured ultrasonic and geometric constraints for guard checks. Segregate proposed `turn/advance/stop` from authorized actuator execution through existing `MobileBase` and car safety controller. Add explicit state/leases: `disarmed`, `supervised_trial`, `qualified_autonomous` with independent authorization. Enforce max speed, duration, stop distance, no-go areas/stair risk, camera blind-spot exclusion, stale frame limits, network heartbeat/watchdog and safe stop on pet proximity or uncertainty. No full SLAM claim; identify any mapping requirement separately.

**Acceptance levels:** (a) deterministic offline replay and simulated motor command trace; (b) hardware communication and sensor reading while disarmed; (c) separately authorized supervised empty-room trials with independent STOP; (d) separately authorized pet-present trial only after demonstrated safe empty-room performance and clear humane operating limits. Logs must show commands requested, approved/rejected, executed/acknowledged and actual observed consequences separately. An autonomous pet-following claim requires real physical evidence, not just passing unit tests.

## Milestone 4 — Continuous multi-body agency and learning

**Deliverables:** Register car camera, mobility and pet-observation affordances with **existing** Executive/PPAL capability discovery. Share observations through existing journal, MemoryGateway and Evaluator; resource-aware priority and preemption. Charlie chooses investigations (pets, exploration, stationary observation, eventually birdfeeder) himself; humans make sensing and safe trial opportunities available without prescribing hypotheses/conclusions. Preserve investigation bookmarks across interruptions, camera/network disconnection and Pi restarts. Safety vetoes movement but doesn't erase research goals. Qualified experience-driven improvements must pass independent evaluation, guarded integration and rollback.

**Acceptance:** at least one Charlie-originated investigation with authentic observations, durable hypothesis/bookmark, action proposal and evaluation; confirm memory survives restart; controlled comparison shows retained experience influences a subsequent choice (not just logs or programmed rule), with explicit negative/inconclusive outcomes. Separate Executive learning, PPAL learning, physical autonomy and improvement claims. Never declare ALA-2 completed based on mobile tests.

## Suggested observation contract (illustrative, adapt to existing schemas)

```json
{
  "schema": "charlie.mobile.perception.v1",
  "source_body": "elegoo-v4",
  "frame_id": "source-unique-id",
  "captured_at_source": "timestamp plus clock domain",
  "received_at_pi": "timestamp plus clock domain",
  "frame_digest": "sha256",
  "source_pose": {"pan_deg": null, "yaw_deg": null, "pose_confidence": "unknown"},
  "vision": {"objects": [], "depth": {"kind": "relative", "model": null, "artifact_hash": null, "quality": "unqualified"}},
  "sensors": {"ultrasonic": null, "yaw": null},
  "latency_ms": null,
  "software_revision": null,
  "motion_authorized": false
}
```

Don't force this schema if shared observation/evidence contracts already exist; extend them compatibly. Depth arrays/images may be stored content-addressably with record links instead of bloating journals.

## Implementation workflow for Work / Codex

1. Start with **Milestone 0** and publish reconnaissance and blocking conditions. Check current refs; never blindly base on the October 13 SHA.
2. Implement Milestone 1 in small increments; test and push each independently checked checkpoint. Prefer in-repo interfaces, existing application entry point and replay fixtures; avoid standalone servers except a demonstrably necessary transport adapter.
3. Keep milestones separately reviewable; do not rush into motion. File progress and dependencies in existing project tracker only after checking current tickets; avoid duplication.
4. Every handoff report: branch, exact pushed commit SHA, changed files/interfaces, tests with commands and outcomes, actual hardware/environment tested, artifacts with hashes, independently observed behavior, unverified assumptions, physical authority state (should remain false until separate approval), known risks, next smallest runnable step.
5. **Stop and ask for separate, scope-specific approval** before any physically moving trial, firmware update, autonomous motion, or sensor test that actuates hardware.

## First Work instruction

> Read `Charlie_Mobile_Perception_Navigation_Work_Mission.md` from my Library. Execute **Milestone 0 and the safe, unarmed parts of Milestone 1** against `mrgarmise/charlie`, preserving all working car face tracking, transport and RP2040/Robotron/ALA integrations. Verify actual camera source and model/runtime before implementing. Publish independently tested additive progress to an isolated feature branch. Do not move the car, flash firmware or activate autonomous navigation without separate authorization. Report exact commit, tests and blockers.
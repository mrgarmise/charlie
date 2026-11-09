# Charlie — Shared Sensory Architecture, Resource Ownership, and Connectivity Audit

**Mission type:** Architecture documentation, repository-wide inventory, incremental interface reconciliation, tests, and publication.
**Repository:** `mrgarmise/charlie`.
**Existing documents:** `docs/CHARLIE_ARCHITECTURE.md` is the canonical architecture entry point. Extend it; do not create a competing source of authority.
**Relevant ongoing work:** PR #10 mobile perception/pet following; PR #11 object recognition/pico:ed display and its ongoing shared-camera integration. Inspect current branch heads, PR discussions, and unpublished progress before making changes. Do not assume the older named SHAs are current.

## Core decision (approved architectural direction)

Charlie is **one persistent, multi-body learning individual**. Physical senses provide observations independently of the Learning Executive's current attention or the presence of subscribers. Producers publish through discoverable, reusable interfaces; consumers subscribe to or query published observations instead of opening or operating physical sensors. Producers own acquisition and health; consumers own interpretation and requests for evidence. The Pi 5 is Charlie's principal cognitive/integration host, **not** a global owner that directly operates every sensor or schedules every subscriber.

Do not interpret this policy as a command to run every physical device at its maximum rate. Passive, already-authorized sensors normally acquire continuously or periodically at a declared, safe, resource-bounded rate, independent of consumer demand. Expensive, intrusive, high-power, privacy-sensitive, or safety-gated acquisition may be on-demand, with an explicit published status and activation authority. No artificial 'idler' subscriber is needed to keep a normal passive feeder alive. A sensor's registry entry can remain visible while its physical stream is intentionally suspended.

## Mandatory architecture contracts

### A. Source ownership and publication

1. Each physical camera or sensor has **one authoritative acquisition owner** at a time. For cameras this feeder alone opens/configures/captures/reconnects and holds any exclusive hardware lease. Other abilities must use published frames, not silently call device drivers or capture APIs. Existing camera session/borrower lifecycles, leases, `PassivePublisher`, and stimulus bus are starting points to inspect and reuse—not a pretext to build a parallel manager. A lease **held by the feeder** is proper; a lease held by pet tracking that locks out other authorized subscribers is not.
2. Sensory sources register via a shared discovery contract with stable source ID, producing body/device, modality, data/schema version, source owner, endpoint, availability/health, acquisition policy, effective rate, clock basis, freshness limits, buffer availability, permissions, and limitations. A registry is a *directory and metadata authority*, not necessarily the process carrying all frame bytes. Avoid a single point of failure; remote camera feeders can serve their own bounded buffers.
3. Publish immutable or safely owned observation records with source ID, per-source sequence/frame ID, capture time (and clock basis/uncertainty), receive time, frame format/geometry, quality, and provenance. Do not label arrival time as exposure time. Preserve remote clock uncertainty; do not order frames across devices on unsynchronized timestamps without qualification.
4. Multiple subscribers may receive the same frame concurrently. Their rates, drop policies and buffering are independent; slow consumers never block capture or cause unbounded growth. Provide latest-frame queries and bounded recent-history retrieval, including data produced before a new subscriber arrived. A subscriber switching from Arducam IMX708 to ELEGOO camera switches **subscription**, not physical camera ownership; other subscribers continue uninterrupted.
5. Camera publication and computer vision inference are separate. Hailo-8L is a shared compute/inference resource, **not** a raw sense. Its published detections link to exact original source frame IDs, model/HEF/version/hash, preprocess/postprocess version and confidence. Deduplicate equivalent inference where practical; do not require all sensor data to be inferred continuously. Maintain fair resource limits and explicit unavailability.
6. Extend to future birdfeeder camera, distance sensors, IMU, temperature and other telemetry using modality-aware contracts, not camera-only abstractions.

### B. Memory, buffers and evidence

1. Separate: (a) latest value / current state; (b) bounded short-lived recent sensory buffer (RAM preferred where appropriate); (c) selective, durable evidence journal. Per-modality retention/rates are configuration defaults to be *measured* on Pi/hardware, not invented acceptance numbers. Avoid writing full-rate video continuously to SD/storage merely so consumers can access recent frames.
2. Frames directly supporting a prediction, decision, action, evaluation, safety event or investigation should be *eligible for default evidence preservation* via a durable bookmark of exact source frame IDs. Also support configurable representative context samples, scene changes, pre/post-event context and explicit diagnostic sampling, including some frames no consumer selected. This must be bounded and auditable (dropped/expired evidence reported).
3. Evidence acquisition owns preservation, retention and provenance. The Learning Executive independently chooses research questions/priorities, and the Evaluator independently assesses outcomes. A bookmark does not certify truth, and a saved inference is not independent ground truth. Record source, timestamps/clock uncertainty, hash, code/model revision, observation vs inference, selection reason, retention action, errors and competing interpretations.
4. A missing, stale, unavailable, corrupted, dropped, late or out-of-order observation must be explicit—not quietly replayed as live sensing. Preserve failures and inconclusive findings.

### C. Motion, transport and display

1. Motor transports and controllers may correctly hold exclusive physical connections, but abilities—including pet following—send requests through the existing independent command and safety authority; never grab motor device connections directly to bypass interlocks. Sensor access conveys **no** movement authorization.
2. Preserve RP2040 ownership and the established **Git repository -> Pi checkout -> `tools/sync_rp2040.py` -> MicroPython RP2040 filesystem/reboot** deployment chain. Document the exact deployed Git revision, firmware source, RP2040 `/lib` contents, device-local profile/calibration data if any, backup/rollback procedure, serial owner and handshake/heartbeat, and the distinction between source-in-Git and physically installed state. Never assume a Git checkout proves live firmware identity without a readback/manifest mechanism.
3. pico:ed object labels are low priority vs safety/status/connection displays. The working normal Pi application uses `--hardware --object-label-display rp2040`; object detection in normal mode must publish `object_observation` through the same Attention Manager that owns display selection. Do not introduce a second serial owner.
4. Preserve CAL-1 gates, GP10's supervised calibration-only role, servo electrical isolation, protected HEAD B pins, watchdog, STOP, and independent mobility gates. Firmware flash, physical servo/chassis movement, autonomous navigation or policy activation **not authorized** by this mission.

### D. Compatibility and branch hygiene

1. Inspect the actual Git repository, branch heads/SHAs, tests, docs, existing service processes and prior evidence before modification. GitHub is authoritative for published source; original hardware runs and journals for evidence; Linear for tracking, not proof.
2. PR #10 and PR #11 are active feature branches. Do not overwrite another ongoing Codex session's work or rewrite its worktree. Coordinate via inspection and compatibility contracts, working in an isolated branch when appropriate. Publish independently tested milestones and preserve branches until reconciled/accepted.
3. Preserve existing application entry points and compatibility APIs by making them adapt to feeder subscriptions rather than quietly retaining independent camera capture. For Robotron real camera, head Active Vision, Pi face tracking, ELEGOO mobile vision, pet following, learning/evidence, and future camera consumers, document supported migration state and needed tests. No disposable replacement app.
4. A feeder lifecycle may run in a thread, service or separate process; strict one-device capture ownership and cross-process readable publication matter more than OS process count. Device discovery must not imply that a sensor was tested or installed.

## Required work products (single canonical documentation hierarchy)

1. **Update `docs/CHARLIE_ARCHITECTURE.md`:** single identity/multi-body model, high-level flow, durable cognitive ownership, sensory publication principle; link to contracts below. Clearly separate approved target architecture vs verified reality.
2. **Create or update `docs/architecture/RESOURCE_OWNERSHIP.md`:** actual hardware owners, leases, frame publisher/subscriber API, registry schema, lifecycle, bounded buffers, modality policies, failures/backpressure, resource/authorization boundaries. Include consumer-to-source access diagrams and a source inventory table with implementation refs and evidence status.
3. **Create or update `docs/architecture/CONNECTIVITY_AND_DEPLOYMENT.md`:** Pi 5, RP2040 pico:ed, Hailo-8L, ELEGOO platform, Pi 4 Robotron game host, planned birdfeeder source; real endpoints and links only where verified. Detail source-of-truth Git branches, actual checkout/deployed SHA verification, communication channels, pairing/handshakes, process ownership, systemd/startup, firmware sync and rollback, operational troubleshooting; note unknowns explicitly.
4. **Create or update `docs/architecture/CONFORMANCE.md`:** testable invariants, inventory of every acquisition site, every subscriber/borrower, inference owner, hardware lease and transport, compliant/noncompliant/transitional/unknown status, remediation owner/branch, native evidence and acceptance criteria. Include a traceable migration matrix rather than claiming completeness prematurely.
5. **Publish a short audit report:** examined source paths/SHAs, discovered duplicative ownership or resource conflicts, proposed vs implemented vs simulated vs host tested vs Pi tested, exact changed files/tests, blockers and next safe native checkouts.

## Implementation audit and corrections

Inventory all camera and sensor access across the repository (including experiment and legacy scripts, persistent services, Robotron, Pi vision/face tracking, active vision, mobile/ELEGOO capture, pet following, evidence journal and Hailo). Search for direct Picamera2/libcamera/OpenCV/USB/HTTP stream reads, constructor-driven camera acquisition, `Camera.read`, frame session leases and direct motor controller connections. Confirm whether pet-service 'exclusive leases' apply to shared connection ownership or improperly monopolize resources. Do not assert nonconformance from naming alone. Classify each site and cite exact paths and behavior.

Implement safe, small extensions using established owners/interfaces if architecture gaps are confirmed. Migrate normal runtime and legacy consumers incrementally; do not break tested Robotron camera operation or existing mobile services. Where migration would be risky or out of scope, mark an explicit blocked item and design a contract + qualifying test. Publish independently verified milestones rather than waiting for all sources to be migrated.

## Minimum independently repeatable acceptance tests

- Single physical camera open/active capture owner despite concurrent subscribers; feeder retains exclusive lease while consumers share frames.
- At least two concurrent consumers of the same source get identifiable observations without invoking a second device capture; subscribe/unsubscribe/change-source does not restart an unrelated subscriber's stream.
- Bounded queue/backpressure, slow/stalled subscribers, late subscribers getting latest/recent frames, stale/dropped/out-of-order/fault signaling and clock provenance.
- Source switching clears stale object-label selection and keeps another subscriber working on the original feed.
- Hailo inference consumes frames through common interface from both Arducam and ELEGOO; results identify source/frame/model, not two camera-specific detector implementations. Distinguish host fixtures from actual Hailo/native frames.
- Evidence bookmarks preserve exact original frames used for decisions when available; bounded representative context sampling and expiration/truncation are recorded; original evidence unchanged.
- RP2040 stays under one serial owner; heartbeat, STOP responsiveness, CAL-1 default-disarmed behavior, and prioritized pico:ed output are preserved.
- Resource outages and thermal limits are explicit and do not silently substitute stale observations or authorize physical movement.
- No network/firmware/process deployment or hardware actuation without separately explicit operator authorization. Host tests alone do not establish Pi-qualified or physically demonstrated behavior.

## Reporting and publication

Use branch/PR ownership thoughtfully to avoid clobbering ongoing PR #10/#11 Codex work; do not merge untested stacks. Commit tested architectural documents and eligible code/test milestones to suitable feature branch(es), providing SHA(s), PR link(s), validation logs, provenance, exact unresolved native tests and rollback instructions. Preserve all previous artifacts and inconclusive outcomes. Architecture docs should be reviewed as contracts, not fictional statements that all devices already implement the target.

**Operator instruction to Work:** This is an implementation-and-audit mission, not a request for only recommendations. Complete eligible static audits, documents and safely testable corrections, publish meaningful independent milestones, and report honest remaining hardware-dependent acceptance work. Existing physical authorization for a stationary pico:ed test does not imply blanket authority for flashing other firmware, motors, calibration, or navigation.
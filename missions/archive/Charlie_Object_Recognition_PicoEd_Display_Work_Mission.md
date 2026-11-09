# Charlie — Object Recognition to pico:ed Display

**Mission type:** Integrated implementation and independent verification  
**Repository:** `mrgarmise/charlie`  
**Date:** 2026-10-24  
**Authorization:** Software implementation, automated testing, and non-actuating hardware inspection/tests only. **No firmware flashing, physical servo/car movement, autonomous navigation, or unapproved hardware activation.**

## Objective

Make Charlie display the name of the object he is currently observing on his **pico:ed 17×7 LED display**, using recognition results produced by Charlie's existing camera/object-detection pipeline. A recognized cat should lead to a readable scrolling `CAT`, a dog to `DOG`, etc. Do this as part of Charlie's **existing unified vision, attention, event bus, RP2040 and display architecture**, not a parallel standalone demo.

This is an **implementation mission**, not merely a proposal or research brief. Implement all eligible code and tests, publish changes in a dedicated feature branch and report any native/hardware acceptance that remains blocked.

## 1. Recover the real current state before editing

1. Inspect `mrgarmise/charlie`, the default branch, relevant open PRs and active vision/ELEGOO/pet-detection and RP2040 branches. Find the latest relevant software rather than assuming `main` is the most complete checkout. Check recent commits/worktrees and the established release/recovery notes.
2. Trace current components: Pi 5 camera and ELEGOO camera ingestion, Hailo-8L inference, object/pet detection and label vocabulary, AttentionManager/event bus, RP2040 serial protocol, `tools/sync_rp2040.py`, `boot.py`, pico:ed screen driver and any existing text/scroll primitives.
3. Preserve functioning ELEGOO face/pet tracking, servo control safety gates, Learning Executive/PPAL, Robotron and existing pico:ed behavior. Avoid unrelated refactors.
4. Confirm whether a model already generates class labels on authentic camera frames (recent field console output showed detections for `cat` and `dog`), which model/runtime supplies those, and how to consume its canonical results. **Do not introduce YOLOv8 or another competing detector unless actual capability gaps justify it.** Distinguish class labels from individual pet recognition.
5. Note the pico:ed firmware's actual command vocabulary, scroll behavior, 17×7 dimensions, maximum payload, handshake/ready state and how the Pi is expected to connect. Treat historical hardware and pin details as clues to verify, not assumptions.

## 2. Implement an end-to-end recognition-to-display pipeline

Create the smallest maintainable integration along these lines (adapt names/locations to existing code):

`camera → existing inference/class label → normalized object-observation event → attention/selection policy → display-label state machine → existing RP2040 transport → pico:ed LED scroll`

**Recognition:**
- Consume real outputs of the current object-detection path, including label, confidence, bounding box, camera/source and timestamp when available. Support at least `CAT`, `DOG`, `PERSON` and other model-supported object names without a hard-coded three-object-only implementation.
- If a general-purpose object-recognition model is genuinely missing, add a configurable model/backend suited to existing Pi 5/Hailo-8L deployment; maintain a CPU/fallback path if already established by the project. Record model provenance, supported labels, runtime dependencies, license, benchmark and confidence limitations. Do not imply the existing model knows a pet's identity.
- Do not make inference on every camera frame if this would disrupt existing pipelines. Reuse events or frame-sharing facilities; bound inference rate, latency and processor load.

**Attention and selection:**
- Prefer Charlie's existing AttentionManager current target over arbitrary detections. If no attention target is selected, use a deterministic configurable choice (e.g. strongest sufficiently reliable observation with an appropriate prominence rule).
- Apply confidence thresholds, short temporal confirmation/hysteresis, deduplication and minimum dwell time to avoid flashing labels with momentary false positives or repeated scrolling for every frame. Support multiple detections and explain tie-breaking.
- Handle no object, object lost, camera disconnect/timeouts, stale frames, inference failures and reconnects gracefully. Never display a stale label indefinitely as though it is current; define a sensible idle/blank or existing status behavior.
- Do not overwrite higher-priority safety/error messages already owned by Charlie's display system; respect arbitration and current display ownership.

**RP2040 and LED display:**
- Add a backward-compatible, bounded `show object label` message to the **existing** Pi↔RP2040 communication mechanism and display API, reusing current text-scroll functionality if available.
- Constrain/sanitize labels (uppercase, display-supported glyphs, finite length, safe fallback for unsupported Unicode and empty strings). Control scroll speed, queue length, frequency and cancellation/replacement semantics so that new observations cannot pile up indefinitely.
- Keep the RP2040 event loop responsive to STOP/heartbeat/safety and existing functions while text is scrolling; use nonblocking/cooperative rendering or preemptible tasks if the existing `scroll` call blocks.
- Use acknowledgements/capability handshake if compatible with the current protocol, and ensure old firmware does not crash if it receives an unsupported command. On disconnect, degrade safely and recover on reconnect.
- Treat object names as external model outputs, **not trusted commands**. Never execute strings received from detectors or remote cameras.
- Respect distinct RP2040 firmware versus host-side code. Implement firmware changes in the repository where necessary, but **do not flash or activate them** under this authorization.

**Multi-body design:**
- Keep the producer/source camera independent of display routing, permitting an ELEGOO observation or later birdfeeder observation to flow into Charlie's central awareness without implying physical movement.
- If display selection across bodies is already supported by Charlie, integrate with it; otherwise introduce only minimal metadata/hooks, not an unrelated distributed architecture. The default display should identify the object Charlie is currently attending to, not spam all camera labels.
- Where appropriate, publish observational events to the existing memory/learning bus without injecting unverified identity claims.

## 3. Acceptance and independent tests

Implement and actually run automated tests for:

1. Normalized detections (`cat`, `dog`, `person`, arbitrary supported class) produce the expected display labels.
2. Low confidence, one-frame flicker, rapid alternating objects and multiple simultaneous objects do not cause a flood of scrolls.
3. Current AttentionManager target selects the appropriate label; higher-priority error/safety display wins.
4. Label sanitization, maximum length and unsupported characters are safe; model text never becomes a control command.
5. Lost targets, stale timestamps, camera timeout/restart, unavailable inference backend, RP2040 disconnect/reconnect and unsupported firmware version recover without deadlock or false current labels.
6. Display updates are throttled/deduplicated, scroll jobs are bounded and preemptible, and STOP/heartbeat handling is not starved.
7. Existing servo/car safety behavior, face/pet tracking, Robotron control and existing display boot/status modes do not regress.
8. Host-side loopback/mock serial acceptance: feed realistic detector events, capture actual serialized display instructions, and verify display behavior without any physical motion or flashing.

Add a small operator diagnostic/dry-run mode using recorded or synthetic detection events, allowing a developer to observe `event → selected target → outgoing label command` with the display mocked or transport disconnected. Where possible, use authentic previously captured cat/dog event shapes as regression fixtures, but preserve privacy and avoid silently committing private imagery.

Run focused tests and all feasible relevant repository tests, note exact commands and counts, and benchmark message cadence/latency and inference impact where feasible. Do not misrepresent mock tests as native hardware validation.

## 4. Native validation boundaries

If Charlie's Pi is reachable by an existing authorized access path, run **read-only or non-actuating** checks of camera detector availability, installed Hailo runtime, RP2040 connection/protocol and display firmware identity; and run safe host-side software tests where practical. Do not assume access to the user's LAN from cloud Work. If native access is not available, provide the exact reproducible Pi commands for the operator.

**Prohibited without new explicit operator authorization:** flashing RP2040 firmware, altering servo safety gates, powering/moving servos, issuing ELEGOO drive commands, enabling autonomous navigation, moving the camera head, or changing a running production installation. Even the physical LED-scroll acceptance must be clearly distinguished from software simulation; if it requires a firmware flash or an interaction that has not been authorized, leave it pending.

## 5. Branch, deliverables and report

- Create/use a dedicated feature branch (suggested `feature/object-label-picoed-display`), based on the best verified integration point. Do not rewrite or disturb unrelated branches or uncommitted user work.
- Commit logically separated changes and publish them to GitHub; open a PR with a clear change summary, tests and operational/firmware compatibility notes. If GitHub permissions prevent publishing, preserve the diff/commit and report the exact blocker.
- Supply configuration defaults, a concise operator guide to start/stop the feature and run dry-run tests, a test trace of a `CAT` and `DOG` recognition reaching the outgoing display command, and a clear note on replacing/adding recognition labels or models.
- Summarize: **implemented**, **unit/integration-tested**, **Pi-validated** (only if truly done), **LED-device validated** (only if truly done), **pending firmware deployment/physical qualification**, and **known limitations**. Identify exact branch, commits, PR and relevant source/test paths.

## Success criteria

A current model-supported object observation causes one appropriate stabilized name to be sent via Charlie's established RP2040 interface for readable scrolling on the pico:ed; recognition and attention remain stable across real-world transient detections; the mechanism respects safety/status priority and cannot compromise existing motion controls. At minimum, demonstrate `CAT` and `DOG` end to end in automated host-side tests, with any unapproved hardware-stage test explicitly deferred.
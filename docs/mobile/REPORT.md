# ELEGOO mobile implementation handoff — 2026-10-24

Review: https://github.com/mrgarmise/charlie/pull/10 (draft). Tracking: CHA-15.
Branch: `feature/mobile-perception-pet-following`; base `bcf8082f6319c63c4bd6bcceeab5faea37241654`.
Software checkpoint under final verification: `429a47d57a5dfdee7b700280b2cd0bd7353796e1`.

## Published increments

1. `3c5735f85afc503ff97bb14c8972c36621ca31ed`: historical pipeline/repository audit and native blockers.
2. `c02ea082cf9a6e23c0fabd075ef4d5afe4dc4a2a`: existing MJPEG metadata/buffer/reconnect extension; shared-frame perception; reused PR 6 Hailo NMS backend; relative-depth adapter. First focused check: 16 passed including existing recall regression.
3. `26428219650d7dddd7fadfc8cc5d0be3ca485a0a`: stable species tracks and guarded navigation proposals; independent disarmed execution boundary. Focused checks then: 37 passed.
4. `91a8083f269f7faf5fa8c856950597b0aa3f4da6`: normal main.py unarmed entry, bounded pixels and evidence, Executive capability/request/import integration, labeled evaluation and runbook. Focused checks: 49 passed.
5. `429a47d57a5dfdee7b700280b2cd0bd7353796e1`: require target-associated ranging, actual finite yaw, and reject invalid telemetry time. Focused checks: 55 passed (includes four existing memory-recall tests).

No merges, deployment, firmware edits/flashing, controller connection, servo commands, car movement or policy activation performed. Source files for legacy face behavior, legacy mobile attention, mobile driver, MobileBase, YuNet detector, primary camera and RP2040 controller remain byte-identical to base. Camera `read()` still returns an ndarray by default; metadata is opt-in.

## Milestone disposition

|Milestone|Implemented software|Independent host evidence|Native/physical disposition|
|---|---|---|---|
|0 audit|Current refs/PRs/history, exact installed-state unknowns, route trace, charter compliance|Fresh clone and source/history inspection; clean feature checkout|Pi name unavailable; no installed firmware/car inspection|
|1 acquisition/perception|Existing latest-frame MJPEG, atomic receipt/sequence metadata, buffer bound/reconnect, cadence/backpressure, hash-bound Hailo NMS/depth adapters, thermal/resource guard and cooperative accelerator lease, bounded content-addressed pixels, timing/provenance|Fault/freshness/shape/resource/lease tests; original detector bridge tests for imported scope; no-motion end-to-end replay|No authentic car capture, HEF/runtime verification, real model decoding or latency/thermal benchmark; outputs always unqualified|
|2 species/attention|Category selection, IDs, confirmation, confidence filtering, crossing abstention, short-loss hold/reacquisition, rich observation event; optional explicit legacy conversion|Handwritten offline crossings/occlusion/loss/species fixtures and independent label scorer; legacy fake-IO regressions|No authentic indoor detection accuracy; no individual pet recognition; physical face regression pending separate authorization|
|3 guarded navigation|PPAL stop/turn/advance proposals; separate real obstacle/selected-target range, floor/hazard/blind-spot/pose/heartbeat checks; expiring boot-bound authority; independent safety callback; requested/dispatched/ACK/execution/consequence separated|Stale/invalid sensor, off-axis, pet proximity/distress, uncertainty, lease, controller fault and unarmed no-dispatch tests|No physical backend for unknown bounded forward/ranging protocol. Car-local watchdog/STOP, clearance, sensor calibration and staged moving trials remain open|
|4 multi-body continuity|Existing registry/Reflection/Executive/journal/MemoryGateway boundaries; bounded observations and negative acquisition faults; request bookmarks/completion across restart; normal lifecycle additive ingestion|Durability/idempotency/request/portfolio tests and real main.py offline smoke; fixtures excluded from authentic projects|No authentic Charlie-originated mobile investigation, retained-learning causal comparison, live MARM delivery, guarded learning-derived deployment or autonomous activity acceptance|

Milestone 4 supplies sensing affordances to the existing Executive; it does not replace its learner, invent hypotheses or force an agenda. The existing offline Robotron/CNN chooser does not acquire live mobile frames automatically: it needs the registered unarmed observation service/opportunity. This remains an integration/qualification boundary, not a claim of demonstrated continuous multi-body autonomy. Existing ALA-2 closure standards are unchanged.

## Verification

Baseline on base master: **1,251 passed, 21 skipped** in 306.92 seconds. Intermediate broader regression: **1,291 passed, 21 skipped** in 305.70 seconds. Those runs predate the final safety revision and are not substituted for final-source verification.

Final-source focused mobile + preserved-face/recall check: **55 passed**. Selected original PR 6 detector-bridge checks: **24 passed, 4 deselected**; initial exploratory full-file run exposed four imports for unrelated PR 6 replay/compiler tools that were intentionally not imported into this feature. Those four are outside reused module scope, not passing tests. No native Hailo emulation claim is made.

Final-source broad result: **1,302 passed, 21 skipped, 0 failures, 0 errors**, 304.71 seconds on exact code commit `429a47d57a5dfdee7b700280b2cd0bd7353796e1`.

Main application smoke: four fixture frames -> four durable observations -> normal existing lifecycle additive import -> clean shutdown; **zero dispatched motion commands**, revision bound to `429a47d57a5dfdee7b700280b2cd0bd7353796e1`. Reopened journal integrity verified. These are handcrafted fixtures with blank pixels, not authentic pet observations or learned improvement. Tests verify image artifact hash/PNG roundtrip and cap; live capture was not attempted.

See `VALIDATION.json` for tested source hashes/environment and `RUNBOOK.md` for reproducible commands/rollback. Host x86_64 Linux / Python 3.12.14; not Pi-validated. Native HEFs, camera route/source timing, installed firmware, power/wiring/thermals, independently calibrated ranging, car-local watchdog and physical hazard coverage remain unavailable. Conservative proposal defaults are not operationally calibrated thresholds.

## Next smallest eligible native step

Provide an actual Pi connection/session and verified model artifacts for an unarmed source/runtime inventory and finite capture. This mission's code never requires movement to do that work. Establish independently labeled authentic sequences and camera timing before qualifying model outputs. Any pan/chassis regression, firmware flash, empty-room motion, pet-present trial or autonomous motion requires separate scope-specific operator authorization. Never set qualification booleans or attach the current driver as a physical executor to bypass these missing gates.

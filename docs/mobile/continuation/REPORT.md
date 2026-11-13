# PR #10 continuation — 2026-10-25

Existing PR: https://github.com/mrgarmise/charlie/pull/10 (draft). Existing branch: `feature/mobile-perception-pet-following`. Start a25b2b7256dffe140c375916d882b759e85b9911; final software c2ec29e55acd6c50de4a96463646b2ecd188c576. No primary Pi/Robotron checkout, firmware, motion policy or original face behavior changed. No car/control socket, servo/chassis, game or policy activation performed. Native access remains unavailable here.

## Tested checkpoints

- 95c769fa140de2719957cd1790390dbfa4761ca6: remote/native evidence audit, prior CI success, current blockers.
- 8e98a46995e89e389d62936d67381b7cc545ab06: additive native importer/review and species-independent animal association. 30 targeted checks passed at that checkpoint.
- a21ec45812ed7f932258a8833de46660985832a2: bounded camera backoff/cancellation, generation-safe reader, stationary watcher, optional absent depth, reusable cooperative Hailo session and fault cleanup. 62 focused checks passed.
- 490d1e55c48ed21d69e31404f62ae01d839ba879: sourced spatial depth/navigation guards, original Nigel reference import, normal Executive native-label review, separate independent evaluator and retained outcome control. 65 focused checks passed.
- 4c98adbfebd31bf518dc6b89906184befd3fb54f: preserved legacy nonpersistent Hailo API behavior, coordinated mobile lease, provisional animal questions. 65 focused plus 24 upstream detector-module tests passed (four unrelated compiler/replay tool tests excluded).

- c2ec29e55acd6c50de4a96463646b2ecd188c576: bounded image-motion association and explicit expired lifecycle; final focused check 66 passed.

## A — Recovered authentic evidence

Recovered all 614 original events and nine Monty images; all nine decoded BGR pixel hashes match logged originals. Nigel JPEG independently matches supplied hash. Native log SHA256 03490c149e57795b013190bfaa5b9261f43cf8b9883f652014b446c5191130f3. Originals are untouched; only hashes/aggregate review data are published. Private review HTML/overlays, raw-vs-label journal and full replay remain outside public GitHub.

Operator labels identify Monty/cat in all nine: original model predicted dog six times, cat three. Classification agreement is 3/9 in this detection-triggered subset. Other 605 events remain UNLABELED; recall, localization accuracy and whole-session accuracy are unknown. The nine frames are one correlated animal sequence. Event intervals p50 .43219 s, p95 .45205 s, p99 .45615 s; event rate 2.3045/s is NOT MJPEG FPS or Hailo inference throughput. The terminal timeout is preserved as an attributed operator report, absent from original log rows. Missing source software SHA/exposure/inference timings are not invented.

Source mission previously reports native HailoRT 4.23.0/HAILO8L, YOLO HEF 90e2cdad2875f23fb436ecdba88b4789de3bd8112cdf6b34beb1c8aa9fd7eed1, successful Nigel cat inference and car→Pi→Hailo frames. Those observations are recovered context, NOT new native execution by this worker. No native depth or motion evidence exists.

## B — Tracking, camera and inference

Category-agnostic animal association preserves track ID through cat/dog flips while retaining uncalibrated accumulated species support. Tentative/confirmed/lost/reacquired/expired behavior, pose gating, bounded image-velocity prediction plus IoU, crossing abstention and bounded selection are exercised. Actual recovered replay associates all nine Monty detections to one track without using the operator name as an association key. Identity remains unverified; this is not nine independent confirmations or a general crossing-accuracy claim. Nigel's reference remains separate.

Reader recovery is bounded and cancellation-aware. Faults invalidate targets/proposals and release models; old reader generations cannot publish after reconnect. Watcher has duration/frame/fault/capture limits, event retention and heartbeat status; depth can be unavailable without blocking object-only observation. Existing face camera read() shape/API remains compatible; legacy behavior/driver and RP2040 source are unchanged.

The shared Hailo session retains configure/activate/vstreams across detector-only frames. Mock SDK verifies one configuration for multiple inferences and cleanup/release on cancel/error/contention. Legacy default nonpersistent backend remains preserved and upstream contract-tested. Detector/depth sequencing conservatively releases detector before depth. No actual hardware performance improvement or simultaneous-network scheduling claim is made. Only cooperating applications honor the lock; native primary-workload/thermal tests remain pending.

## C — Depth/navigation preparation

Official Hailo Model Zoo v2.19.0 Hailo-8L FastDepth bytes downloaded and hashed, source MIT licensing and model-specific pre/postprocessing inspected. See depth-source.json. Native parse/vstreams/runtime compatibility and TensorFlow/OpenCV parity remain pending. Spatial relative-depth zones, anomaly validation and source/frame/pose binding are implemented; they do not certify free floor, stairs or metric distance. Planner adds frame/FOV-associated obstacle/selected-target range and lateral-clearance requirements. Unknown depth/range/pose/clearance means stop. Installed read-only sensor protocol and local watchdog are unknown; no commands or physical backend were invented.

## D — Existing Executive and retained experience

The normal `main.py --offline` acquisition path imports the native journal additively. Existing Reflection generated a model-label retrieval question, existing portfolio selected it, existing commissioning retained its bookmark, and independent Evaluator compared preserved model predictions with separate pixel-bound operator annotations. Result: contradicted, six wrong species, one independent source log. On restart there is no second evaluation; it awaits independent new evidence. An initial report-rendering KeyError was found after the scientific result had already persisted; the optional reason field was corrected and the failed notebook preserved. A clean repeat completed and restarted successfully.

`executive-retention-control.json` records same-code/resource notebook ablation: before Executive outcome delivery portfolio score .50, after retained outcome .25 (one diagnostic evidence unit). This demonstrates the existing rule-based Executive's experience-dependent valuation for this scoped retrospective. It does NOT prove generalized autonomous learning, PPAL learning, better recognition, physical improvement or ALA-2 closure. Unqualified fresh animal detections can supply provisional observation questions rather than species facts; unavailable unarmed sensing services remain blocked with bookmarks preserved. No forced Monty/Nigel priority or second scheduler was introduced.

## Validation and open acceptance

Start focused baseline: 55 passed. Final focused: 66 passed; upstream reused detector module: 24 passed, 4 unrelated tooling cases deselected. Final exact-published-source broad result: **1,313 passed, 21 skipped, zero failures/errors**, 337.40 seconds on clean c2ec29e55acd6c50de4a96463646b2ecd188c576. Separate fake-I/O live-entry check: one passed, zero control socket calls. GitHub Actions run 40203291463 (#84) independently completed successfully on the same code revision.

Unchanged legacy face/attention behavior, driver, MobileBase, main primary-camera/RP2040 implementation and all original evidence are preserved. Host Linux x86_64 / Python 3.12; native Python 3.13/Hailo/car acceptance not rerun. Detailed source hashes, commands and counts are in validation.json; native observation-only commands and rollback are in RUNBOOK.md.

Still blocked: new live stationary recovery/throughput/thermal trial; actual FastDepth runtime/scene validation; safe installed sensor/STOP/watchdog protocol; source exposure timing; calibrated body/pose/FOV and target distance; floor/stair/lateral/blind-zone qualification; separate empty-room, pet-present and camera-pan authorization. No physical pet-following, autonomous roaming, SLAM, automated individual recognition, PPAL-learning or deployment claim.

# Charlie — Hailo-8L Robotron Perception Integration and Custom Object Detector

**Mission date:** 2026-10-18  
**Repository:** `mrgarmise/charlie`  
**Target hardware:** Raspberry Pi 5, IMX708 camera, AI HAT+ 13 TOPS / **Hailo-8L** (not Hailo-8 or Hailo-10H)  
**Mode:** Implement, test, document, commit and publish a narrow, reversible engineering change. Do not stop at a recommendation or mockup when implementation is feasible.

## Operator intent and governing scope

The operator wants Charlie's established visual and temporal reasoning to receive better observations via the Hailo. The desired perception output is **"what is where, where is it going, and how sure are we?"** Later, Charlie should use that information to identify a nearby safe firing position, move there and shoot threats. **Do not implement or hard-code the future firing-line tactical planner in this mission.** This assignment is only (1) a minimal Hailo detection backend compatible with Charlie's existing tracker and (2) a Robotron-specific detector training, export, and evaluation path.

**Critical distinction:** Existing OpenCV segmentation, color/shape matching, Hungarian track association, motion inference, and PPAL cannot simply be "moved to Hailo." Hailo accelerates supported *compiled neural networks*. Keep Charlie's present tracking and higher-level decision code on the Pi; replace/supplement its **object-detection observations** with Hailo inference. Preserve the existing CPU detection option for comparison and fallback.

Read `ALA_LEARNING_CHARTER.md` and `ALA2_ACCEPTANCE_STANDARD.md` before any edits. Training a CNN or running a HEF is not evidence of autonomous learning, causal SELF identification, E1/P1/I1, qualified PPAL improvement, or real Robotron gameplay performance.

### Strict non-authorization

This mission authorizes **repository development, isolated test execution, documented offline inference, model training on authentic properly labeled data if accessible, and publication of a draft PR**. It does **not** authorize physical gameplay, Xbox controller activity, changes to live player policy, servos/head movement, RP2040 firmware flashing, Pi deployment/installation, manipulating saved original episode archives/notebooks, merging existing PRs, or promoting an unqualified model into production. Native Pi validation is an operator-dependent acceptance phase unless actual authorized Pi access is available.

## Actual preexisting work: inspect and reuse, do not re-create

As of mission drafting, verify all refs before editing (they can move):

- **Draft PR #5**: `https://github.com/mrgarmise/charlie/pull/5`, head `feature/fast-projectile-self`, previously observed head `8c96db003b87246ee6b0f9dc9918cb42af726370`, based on `feature/closed-loop-gameplay`. It includes continuous camera production, controller/capture overlap, and the present `VisualAgency` + `SpriteTracker` wiring. Draft/native performance is NOT independently qualified; the October 17 baseline achieved ~1.66 agency updates/s, not the camera's nominal ~15 fps.
- **Vision Lab**: `feature/charlie-vision-lab`, docs `docs/vision-lab/README.md`, `docs/vision-lab/hailo-8l.md`, `docs/vision-lab/verification.md`. Existing `vision_lab/` supports local/SFTP observation discovery, human verified bounding boxes, immutable session-based train/val/test partitioning, genuine CPU YOLOv8n training, offline evaluation, and ONNX preparation. `vision_lab/adapter.py` already implements a candidate detector adapter, but is **observation-only** and is not connected to live PPAL or Hailo. The feature's synthetic training does **not** constitute a real Robotron model.
- **Existing recognition**: `experiments/ppal/eyes/sprites.py` (contrast segmentation + shape/color template matching); `experiments/ppal/eyes/taught_recognizer.py` (operator-confirmed reference vectors). Avoid weakening thresholds or silently promoting unreviewed observations.
- **Existing time-aware tracking**: `experiments/ppal/eyes/tracking.py` `SpriteTracker` (stable IDs, filtered velocity, elapsed-time association, crossing ambiguity and identity quarantine); `experiments/ppal/robotron_agency.py` `VisualAgency` (same tracker plus controller-causal SELF). `experiments/ppal/vision_tracker.py` is an older semantic tracker; do **not** run competing association systems in parallel on the armed path.
- **Current world/planner boundary**: `experiments/ppal/models.py` defines an `Object` with just `id` and `position`; `experiments/ppal/shadow_predictor.py` separately estimates/project velocities; `experiments/ppal/play_robotron.py` feeds Forebrain/Hindbrain current `WorldState`, while a **shadow** plan uses projected world only. Preserve semantics, but make the richer tracking signal available through a backward-compatible observation/motion packet for future planner consumption. No tactical activation here.
- **Optional semantic augmentation**: `experiments/ppal/semantic_observer.py` exists; inspect and reuse or interoperate if it is the right boundary. Avoid adding yet another asynchronous queue or camera owner.
- The Hailo preparation document predates a newer Ultralytics Hailo exporter. Current official docs describe custom `YOLOv8` / `YOLO11` detection export with `model.export(format="hailo", name="hailo8l", data="...")`, producing INT8 HEF on supported Linux x86_64 compilation hosts. **Verify version, toolchain and licensing in the execution environment; do not assume the Vision Lab's pinned Ultralytics `8.3.203` has that feature**. Hailo-8L uses compatible DFC v3.x; target architecture exactly `hailo8l`. See https://docs.ultralytics.com/integrations/hailo and https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html .

Recover the most recent relevant repository branches, commits, outstanding PRs, and any accessible Vision Lab work before choosing an implementation branch. Use a **new independent feature branch**; preserve existing drafts. Minimize diff overlap; document the chosen ancestry/port strategy. Do not force merges or cherry-picks without checking conflicts.

## Deliverable A — Minimal detector backend with proper evidence

Implement the smallest robust adapter to normalize observations from: (a) existing CPU/template detector, (b) offline trained CPU model for reference, and (c) **actual HailoRT/HEF** model when available. Prefer existing `Detection`, `CandidateDetector` and `VisualAgency.observe` interfaces; extend them conservatively. Keep optional Hailo packages lazy/optional, with no Hailo dependency when running standard tests.

Each detection should carry, without fabricating any missing fields:

- source frame ID, **actual exposure/capture timestamp and its basis**, source frame geometry and coordinate transform, pre/postprocess metadata;
- object class and class-score vector / confidence (not falsely calibrated probability);
- bbox in both original corrected playfield pixels and normalized 0–100 board coordinates where useful;
- detector backend, model name/hash/version, source evidence provenance, postprocessing settings, inference duration, and freshness age;
- unknown/unresolved class handling; objects not confidently categorized remain candidate objects, not vanished tracks;
- confidence/uncertainty kept separate from track association costs or causal SELF evidence.

Use the shared camera stream; never open another competing camera capture loop. Drop stale backlogged inferencing results rather than pretending late results are current; keep timestamp provenance and deterministic ordering. Distinguish actual inference on Hailo from CPU emulation. Implement startup/health checks; missing Hailo, missing HEF, incompatible hardware, timeout, inference failure, or shape mismatch must be explicit, logged, and safely fall back to the original detector **only when the configured mode permits**, without granting gameplay/SELF authorization from a fallback event. Retain a mode that forces failures visible instead of silently using CPU (for QA).

Preserve one generic tracker and persistent IDs. Map specific labels to legacy `human`, `threat`, etc. only at the existing semantic boundary and without renaming physical IDs on label changes. Preserve original raw positions and temporal evidence. Do not use a model appearance label as an alternative to signed BODY-response and shot-origin SELF authorization.

Add an **optional versioned rich world-observation view** exposing per-track ID, class hypothesis, observed-vs-extrapolated location, velocity units, timestamp, displacement history, current prediction/horizon and ambiguity/occlusion/confidence. Reuse `SpriteTracker` values rather than building another tracker. Ensure existing `WorldState` callers continue to work exactly as before. The existing live tactical planner remains unmodified. Explain why any richer view is not yet connected to action policy.

## Deliverable B — Robotron-specific training/data path

Build on `feature/charlie-vision-lab` rather than replacing it. Where branch divergence requires care, publish a small integration bridge plus precise instructions for using the separate Vision Lab checkout, or create a focused compatible backport. Avoid duplicating annotation UI, training job scheduler, label storage, dataset partitioning and scoring functions.

**Data:** Discover and inventory authentic original Robotron frames already available in accessible archives; preserve originals read-only. Respect verified annotations and their provenance. Treat prior automated labels, heuristics, synthetic examples, ROM-derived images, and track guesses as *proposals*, not ground truth. Require explicit human verification before adding labels to training/evaluation. Separate train/val/test by original game/session, and prevent adjacent-frame or duplicate-frame leakage. Do not fabricate a data volume or report authentic performance from fixtures. The actual user's Mint/Pi/SFTP archives may not be accessible to Work; design runnable import/annotation commands and a concise operator data request instead of pretending to possess them.

**Starting taxonomy:** implement user-configurable labels and an initial practical set with `player`, `grunt`, `hulk`, `tank`, `human`, `mine`, `other_enemy`; expand to `brain`, `enforcer`, additional enemy families, and subtypes when enough verified examples exist. Projectile is a **first-class evaluation target**, but because bullets are tiny and fast, benchmark a dedicated high-resolution blob/temporal candidate path versus YOLO; don't assume YOLO resolves them. Unknown must remain representable. Validate actual labels against Robotron images rather than hard-coding uncertain taxonomy. Include difficult examples (crowds/overlap, laser/projectiles, flash, disappearing sprites, transitions, CRT bloom/glare, varied focus and geometry) and manually verified *empty* playfield negatives.

**Model:** Start with the smallest viable supported model, e.g. YOLOv8n for reliable compatibility with the existing Lab training and Hailo-8L. Compare fine-tuning from pretrained weights vs Vision Lab from-scratch training if permitted by dependencies/licensing and data supply; do not imply COCO pretrained classes already recognize Robotron. Train on actual verified data **only if available**. Preserve training seed, hyperparameters, class mapping, image size, input aspect preprocessing, augmentation choices, best weights SHA, metrics, and dataset manifest. If only fixtures are available, test the actual optimizer/ONNX/export plumbing with **SYNTHETIC / NOT ROBOTRON-QUALIFIED** prominently in output.

**Evaluation:** Baseline against existing taught detector and any CPU YOLO model on the **same held-out authentic recordings**. Report per-class precision, recall, AP50, tiny-object/projectile recall, confusions, false-positive density, tracking continuity/ID swaps, class permanence under animation, and processing/latency at each stage. Use session-specific error galleries and false positives. Neither synthetic metrics nor a passing compile suffices to claim recognition quality. Where data is insufficient, produce a quantified labeling backlog and required operator steps rather than invented results.

## Deliverable C — Hailo-8L HEF path and actual execution gate

If training data and compiler are accessible, build and validate a **custom** compiled HEF for `hailo8l`. The current Ultralytics Hailo export can be evaluated as a simpler route: `.pt` -> ONNX -> parsing -> INT8 quantization -> HEF (toolchain on compatible Linux x86_64, **not on the Pi**). Use representative **training-only** calibration imagery; docs recommend around 1,024 diverse calibration images for best accuracy, but smaller datasets must be accurately reported as constrained rather than padded with test images. Preserve artifact hashes, HEF architecture metadata, decoder/NMS assumptions, calibration manifest and logs. Inspect output tensors, letterbox/coordinates, postprocess, class counts and model names. If exporter is unsupported or unavailable, produce a reproducible versioned Hailo Model Zoo v2.x/DFC v3.x compilation script/instructions instead and report the blocker. Do not rename an ONNX or CPU model as an actual Hailo HEF.

Create a **read-only Pi hardware acceptance procedure** (operator-triggered, not remotely executed here): device enumeration/health, HailoRT/driver/firmware compatibility, load compiled HEF, run recorded real frames with exposure metadata and compare predictions to CPU model and ground truth; log FPS, latency (P50/P95), camera-to-observation latency, frame-drop/freshness, thermal and memory implications, and coordinate consistency. Preserve a rollback command to CPU backend. Never infer useful gameplay FPS just from 13 TOPS marketing specs. Keep no-hardware test mode isolated from real hardware measurements.

## Tests and acceptance

Implement unit tests using deterministic fake detector backends and fixtures for protocol/schema, pixel↔board coordinates/letterbox, exact timestamp propagation, UNKNOWN handling, class transition with stable ID, Hailo failure/fallback, stale results, one-camera ownership, model mismatch, deterministic replay, and **no movement/control authorization from an unqualified detector**. If practical, add recorded-frame side-by-side evaluation CLI saving a JSONL trace with per-frame detector outputs and shared tracking, plus a minimal annotation overlay for operator inspection. Reuse the existing test suites; run targeted and regression suites, report exact counts and differences.

Stop short of claiming these without proof:

1. authentic fine-tuned Robotron checkpoint, unless verified labeled authentic data was used;
2. compiled Hailo-8L HEF, unless the actual DFC/Ultralytics Hailo path completed;
3. real Hailo inference, unless the actual Hailo-8L device ran a compiled HEF;
4. production gameplay benefit, unless separately authorized and independently measured in full games;
5. ALA E1/P1/I1 or model-driven SELF acquisition, unless separately admitted via their existing evidence standards.

Publish a **draft PR** with source code, limited integration diff, docs, tested commands, exact source/ref/commit hashes, benchmark results, models/dataset manifest hashes (large model binaries as appropriate to project policy), explicit blockers, data-collection/annotation instructions, operator-native Pi acceptance and rollback. If no dataset/driver/compiler access, finish all eligible code/documentation/tests and list missing evidence precisely; do not stall the entire mission awaiting access. Preserve the original PR #5 and Vision Lab work. No merges, no activation, no servo/controller/gameplay operations.

## Final operator handoff (keep brief)

Report: code/PR link + SHA; backend modes implemented; Vision Lab reuse; authentic-class and training status; `.pt`/ONNX/HEF status explicitly distinguished; offline test evidence; what remains to be executed on Mint/compiler host and Pi; one short copy/paste command or documented procedure to inspect observations; and recommended next milestone. That next milestone is **expose safe firing-line opportunity data to Charlie's learning Executive as an optional observation-only feature**—not implementation of a new hard-coded firing tactic in this mission.
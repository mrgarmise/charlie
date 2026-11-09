# Charlie — Hailo-8L Robotron Score Reader: Audited Implementation Mission (Revision 2)

**Revised:** 2026-10-18, incorporating `Charlie_Project_Audit_Phase1.md` (source verified 2026-10-17).  
**Repository:** `mrgarmise/charlie`  
**Hardware target:** Raspberry Pi 5, IMX708 camera, official Raspberry Pi AI HAT+ **13 TOPS / Hailo-8L**, not Hailo-8 or Hailo-10.  
**Library location:** `/Charlie the Cyberdek/Charlie_Hailo_Score_Reader_Work_Mission.md`  
**Related mission:** `/Charlie the Cyberdek/Charlie_Hailo_Robotron_Perception_Work_Mission.md`.

## Mission and execution mandate

**Implement, test, commit, and publish** a genuinely **Hailo-8L-targeted neural Robotron score recognizer** that replaces *only visual score recognition* behind Charlie's existing HUD/score-tracker/evidence interfaces. The primary intended inference backend is Hailo, to relieve Pi CPU contention **if independently measured end-to-end costs confirm a benefit**. Also implement a CPU reference/fallback for correctness, portability, and recovery; do not deliver only a CPU model or an unconnected training notebook.

This is an implementation assignment, **not** a proposal, architecture study, another replacement Robotron app, another score-review portal, or permission to conduct physical gameplay. Start immediately using accessible code and evidence. Publish the maximum eligible, genuinely tested implementation even if authentic images, compiler access, physical Hailo runtime, or the original review database are unavailable. Clearly mark incomplete items and retain usable artifacts. Do not claim an ONNX graph is a compiled `.hef`, a synthetic training result is authentic recognition, or a committed feature is deployed on Charlie.

**The October 17 Phase 1 project audit is a versioned starting point, NOT an exhaustive history.** Its historical ChatGPT/Work audit is **PENDING EXPORT**. Do not wait for that export, reconstruct unseen conversations, or claim it establishes the Pi's installed/running state. Phase 2 must be able to reconcile later recovered context against the same durable capability IDs and project records.

### Nonnegotiable preservation/authorization

Read `ALA_LEARNING_CHARTER.md`, `ALA2_ACCEPTANCE_STANDARD.md`, the audited `docs/best-of-charlie/README.md`, and current project audit before changes. Preserve original game observations, the score-review SQLite/WAL database, all learning notebooks, independent Evaluator and Executive decisions, and their exact identities. Keep gameplay, controller, camera ownership, servo/motion, firmware, safety gates, score qualification, and model/policy activation unchanged.

**This mission authorizes software implementation, tests, synthetic engineering fixtures, offline/replay evaluation using authorized read-only source copies, and publication of a draft PR. It does NOT authorize live gameplay, controller/Xbox commands, servo movement, firmware changes, installation/deployment on the Pi, running a new notebook writer, live score-model activation, or merge to `master`.** Publish read-only operator acceptance instructions; do not secretly execute deployment as a prerequisite for them.

---

## 1. Reconcile the audited baseline BEFORE creating duplicate capabilities

Treat current GitHub `master` as the authoritative *integrated source*, not necessarily the source **installed or running** on Charlie. On 2026-10-17 the audit pinned `master` and tag `best-of-charlie-v0.1.0` at `bcf8082f6319c63c4bd6bcceeab5faea37241654`. **Fetch and independently recheck current remote refs, commit ancestry, selected files, and open PRs** rather than treating those historical SHAs as immutable current heads. Preserve a read-only comparison of originals if needed.

Use audit capability IDs **`ROB-SCORE`, `ROB-FEEDBACK`, `VIS-CORPUS`, `VIS-LAB`, `VIS-HAILO`, `SYS-NATIVE`, `SYS-MIGRATION`**. Existing Linear **`CHA-9`** is the appropriate Robotron score/observation issue. Link the draft PR and work report to those identities; do not create duplicative issue records, duplicate dashboards, or claim an issue closed merely from software tests. The ongoing Project Dashboard/Phase 2 historical audit must be able to incorporate this work by those stable identifiers. Do not mutate Linear as a substitute for code completion unless separately authorized.

### Inspect and reuse actual integrated source

- `experiments/ppal/robotron_hud.py` — original calibrated **extended HUD ABOVE the playfield**, separate P1/P2 crops, current brightness/geometry reader; normalized playfield crops omit the score pixels.
- `experiments/ppal/robotron_score_system.py`, `score_tracker.py`, `score_observer.py`, `score_events.py` — score candidate acceptance, independent P1/P2 temporal beliefs, score attribution, timestamped asynchronous evidence/diaries, gameplay versus non-gameplay partitioning.
- `experiments/ppal/score_feedback.py`, `inspect_robotron_score.py`, `tools/recover_score_reviews.py`, `tools/score_feedback_candidate.py` — **already integrated** offline review import, immutable corrections, digit exemplars, feedback provenance, evaluation adapters and recovery. The existing candidate's live activation may still be deliberately absent; verify.
- `docs/score-feedback/{REPORT.md,native-recovery.md,authentic-camera-regression.json}` and `docs/ppal/deferred-score-review-20261010/README.md` — preservation and qualification obligations.
- `docs/best-of-charlie/README.md`, release/capability manifests and operator status tools — distinguish source, installed, running, and persistent-state identities.
- `feature/score-feedback-master-integration` / draft [PR #3](https://github.com/mrgarmise/charlie/pull/3): the audit found **selected implementation files already present in consolidated master** while the feature branch/PR stayed open. Compare by hashes/behavior and import **only actually missing scoped behavior**; do NOT merge PR #3 or resurrect redundant files.
- `feature/fast-projectile-self` / draft [PR #5](https://github.com/mrgarmise/charlie/pull/5): newer continuous capture, controller overlap and camera ownership; preserve PR #5 and account for its interface and timing without rebasing unrelated source en masse. Audit snapshot predates some October 17–18 work; inspect live heads.
- `feature/charlie-vision-lab` (audit snapshot `9156940a89651ec0b16d8972f8fed1261ae8f3da`): local authenticated source discovery, review, frozen train/val/test partitions, CPU neural training, ONNX/export, and Hailo handoff. **Reuse applicable abstractions; a sequence-labeled score crop is not a YOLO box dataset.** Keep the existing vision branch intact.
- Current `memory`, `learning`, score reader evaluation, and game boundary interfaces. Preserve the operator's original feedback and the distinction between numerical score recognition, official game score, game-over determination, and causal reward attribution.

Produce a **short baseline/integration ledger** with current branch SHAs, source files already consolidated, narrowly missing components, lowest-conflict chosen base, and explicit exclusions. **Default to a fresh feature branch from verified `master`.** A minimal, audited, selective bridge may be made where needed; no force merges, resets, deletion of local uncommitted work, or wholesale imports of historical branches.

### The known evidence problem, not a permission to fabricate

The audit reports an original October 10 score-review store at `/home/five/.local/share/charlie/score-review/learning-evidence.sqlite3` with historically **16 status records / 8 annotation records**. Those counts are **not independently verified distinct valid images or accepted final labels**. The original database and hash-bound source photos were inaccessible to prior host sessions. Distinguish evidence **present in this Work environment**, evidence **reported by historical documentation**, and evidence **verified via actual original bytes**. Locate/reconcile sources read-only if available; preserve SQLite consistency including WAL without writing to the live store.

The Oct 11 episode with **operator-observed 2,200 versus reader-reported 1,100** must become a named regression investigation, **not** an automatically accepted training label; recover its particular original images, capture and review status first. Preserve the historical 3/14 score-reader regression and limited later 2/2 camera-derived regression as different experiments with different corpora/calibrations. Never summarize them as a statistically meaningful acceptance rate.

### Runtime prerequisite; do not turn this into a platform migration

The audit marks `VIS-HAILO` designed, not hardware-qualified. Historical device detection and an OS architecture mismatch were reported; a possible 64-bit SSD migration (`SYS-MIGRATION`) was *proposed*, not verified or authorized. If an approved read-only path exists, identify Pi architecture (`uname -m`, `getconf LONG_BIT`), OS/kernel, Python ABI, camera, PCIe device, HailoRT/driver/firmware/device status, installed-release SHA and model/HEF inventory. Distinguish **device enumeration** from **successful Hailo inference**. If Pi access is unavailable, provide precise safe operator commands and mark native status UNKNOWN; no automatic migration, driver install or firmware deployment.

---

## 2. Scope: new visual reader; retain old temporal decision layer

Build a **backend-neutral neural visual score reader** that takes a full *raw-camera* frame or its provenance-bound HUD crop, uses the existing calibrated extended-HUD transformation and channel mapping (or a documented qualified correction), and returns score candidates for both P1 and P2.

Keep and reuse the existing `VisualScoreTracker`, `DualScoreTracker`, `RobotronScoreSystem`, `ScoreObserver`, score events, and score review/Evaluator interfaces. Scores must **not** decide SELF identity, restart/game-over, gameplay versus attract mode, or independent complete-game certification; those remain separately qualified questions. Report score increments as uncertain reward evidence, not automatically attributable to a particular firing action.

Output for each channel must include at least:

- `score: int | None` plus **canonical recognized digit string** when valid; `None` for unreadable or indeterminate, with reason.
- Raw model evidence/sequence logits or diagnostically bounded information, confidence/uncertainty **without pretending an uncalibrated softmax is a probability**; explicit disagreement and abstention.
- P1/P2 channel identity, actual image/crop coordinates, full-frame provenance, original capture ID and **sensor/capture timestamp basis** versus inference completion time.
- Backend/mode (`cpu-reference`, `hailo-required`, `hailo-preferred`), model/checkpoint/HEF/hash, preprocessing/decoder versions, source image hash and fallback/health event when applicable.
- Wall/CPU/device timing components, queue wait, dropped/stale evidence, image age, observed input shape, and calibration identifier.

**Never infer a missing leading zero, drop an ambiguous digit, append zeros, swap P1/P2, reinterpret a high-score/attract display as active-game reward, or emit a confident shorter number because part of a crop was dim.** Handle score zero, score absent, blanks, variable lengths, edge clipping, channel bleed and an explicitly unreadable crop. The detector may decline to answer.

Implement independently selectable modes:

1. **`cpu-reference`**: real working neural inference using the same model representation/preprocessing as the Hailo candidate, plus the existing fixed reader as separate baseline/rollback (do not conflate them).
2. **`hailo-required`**: load only explicitly matching Hailo-8L HEF/runtime; fail safely and visibly with exact cause, never silently mislabel CPU execution as Hailo.
3. **`hailo-preferred`**: attempt qualified Hailo inference, with logged explicit fallback to CPU on unavailable/unhealthy model/device; never promote a nonqualified reader into live authority.

Use **optional/lazy Hailo imports** and no new camera owner. The Hailo inference adapter must use an actual HailoRT API contract with correct input/output quantization, tensor order, shape, and lifecycle; a stub claiming to execute hardware is not acceptable. Host-tested dependency injection/fake-device tests are valid as **adapter tests**, not hardware inference. Keep the existing asynchronous score worker **bounded, nonblocking, drop-aware and subordinate to camera/controller/servo safety**, including shutdown. No new background writer to original evidence stores.

---

## 3. Hailo-first architecture: prove compiler feasibility early

**Do NOT consume weeks training an architecture that cannot compile for Hailo-8L.** Before substantive authentic training, implement a minimal, genuine *forward pass → ONNX → selected Hailo-8L parser/compile* feasibility spike with the **actual graph architecture and intended final output tensor shapes**, using deliberately labeled engineering data. If an appropriate Hailo compiler host is unavailable, make the graph/operator inventory, version-pinned scripts, shape tests and complete reproducible compiler instructions, and mark compilation **UNVERIFIED**. Do not label ONNX export as `.hef`.

Prefer a **small fixed-input fully convolutional sequence reader** on each rectified P1/P2 score crop. Let it predict `0`–`9` plus `blank` along horizontal positions; perform CTC greedy/beam or other validated sequence decoding on the **Pi CPU** (very small postprocessing cost), avoiding recurrent layers or unsupported hardware-side string decoders. Use only Hailo-8L-supported graph operators, fixed spatial dimensions and batch assumptions proven by the selected toolchain. Document the entire input contract (crop/letterbox, RGB vs grayscale, luminance, normalization, padding, aspect ratio, output layout, quantization) so CPU and Hailo see equivalent pixels.

Training labels should be **whole score strings**, e.g. human confirmation `3500`, with **no per-digit boxes required**. Derive diagnostic alignment only through validated algorithms; distinguish a good numeric string label from actual glyph segmentation truth. Explicitly test CTC repeated-digit strings (`11`, `100`, `2200`), blanks, trailing/leading blanks, long values, zeros, and low-confidence/truncated results.

Use a supported architecture if a relevant Hailo Model Zoo model genuinely fits; do not assume a stock license-plate reader, YOLO/COCO HEF, or current Ultralytics `format=hailo` automatically supports a custom score model. Verify **actual Hailo-8L**, appropriate Model Zoo **v2.x / DFC 3.x when applicable**, HailoRT and firmware/driver versions against vendor compatibility documentation; pin exact working versions, input/output nodes and configuration. Preferred verification steps:

- Run PyTorch forward and reproducible real optimizer step; export fixed-shape ONNX; checker plus ONNX Runtime numeric equivalence on engineering tensors.
- On an actually supported compiler environment, attempt parse, optimization, INT8 calibration and HEF compilation targeted **`hailo8l`**, retaining complete logs and hashes.
- Quantization calibration images must come from **authentic training-only** partitions for a deployable candidate; a synthetic graph feasibility compile does **not** qualify quantization accuracy.
- Compare FP32, ONNX, and real Hailo HEF outputs on the same independent crops for shape, alignment, digit accuracy and abstention.

If the first proposed convolutional sequence architecture proves impossible to compile, **record the specific blocker and implement the smallest compatible alternative** rather than abandoning the Hailo requirement: e.g., a fixed-shape convolutional glyph classifier with robust, explicitly uncertain crop/segmentation, or a compatible bounded slot/blank network. No imaginary successfully compiled artifact. Retain the whole-string supervision/review interface if feasible so the operator does not draw glyph boxes. Document any extra labeling unavoidable for an alternative.

Do **not** silently train a generic COCO sprite detector and call it a score reader. This is an independent model with shared infrastructure only where justified.

---

## 4. Authentic corpus recovery, selective review and reproducible training

Recover authorized data from original score-photo sources and existing feedback without overwriting anything:

- Audit `robotron-runs`, preserved score-photo provenance, `score.jsonl`/report/diary references, score review journal and hash-bound photos, current review supersession/acceptance status. A reported `16/8` is an **inventory lead**, not a ready dataset.
- Reuse the existing inspector's accepted/corrected **whole-score numerical labels** and its human attestation, original image bytes, channel, session, source identity, timestamp, status/finality, image hash and review history.
- Treat `pending`, disputed, superseded, unreadable, test/validation labels and unsupported gameplay claims according to their original roles. **Do not turn proposals, game scores inferred from a planner, score deltas or the operator's spoken observation without matching imagery into verified training ground truth.**
- Preserve `0`, `100`, `1200`, `1300`, `1500`, `2200` and other values **only if individually verified by existing evidence**. Do not insert examples to reach those numbers or fabricate missing digit coverage.
- Include negative/no-score, dim, low saturation, blur, CRT/camera changes, partial crops, title/attract, game-over/high-score views and both channels, retaining screen state and whether the sample represents *actual active-game* score.

Enhance the **existing** score-review UI, if needed, to show an original full camera frame, rectified score crop, suggested full numeric string, explicit unreadable/unknown, and one-click confirm/correct with acknowledged durable save. Avoid a second independent review database or portal. Training examples can be labeled with entire numbers, not individual digit rectangles; humans should review high-value uncertain/diverse cases rather than every frame. All assisted/auto proposals remain unverified until separately accepted. Do not write into the Pi's original store from Work.

Build a **versioned, immutable score-crop corpus** with hashes and provenance, source group/session/episode identity, reviewer and qualification status, preprocessing version, model training eligibility, negative samples, and frozen splits by **independent original sessions** (not near-identical adjacent frames). Respect irreversible prior test consultation and held-out commitments from existing Vision Lab/MemoryEvaluator datasets. Deduplicate exact and near-duplicate frames where possible; explicitly document remaining correlation risk. Keep calibration **training-only**, validation for tuning, genuinely isolated unconsulted final test data for independent measurement. Augmentation only from eligible training originals, never from test/validation; preserve augmented ancestry.

Implement actual neural training and model/export tools (PyTorch, reproducible seed, versioned config, correct whole-string loss/decoder, training controls, model/checkpoint hashes, resume, evaluation), using Vision Lab's infrastructure only where it genuinely supports the required formats and partition rules. When authentic labels are insufficient, **still implement, run and test the full training/export pathway on clearly marked synthetic/engineering fixtures**, but report authentic dataset counts and coverage shortfalls exactly. Do not claim a synthetic learning run demonstrates effective real-world reading.

---

## 5. Independent validation against historical failures

All comparisons must process the **same image crops and equivalent original camera pixels**, with original full-frame and crop geometry available for review. Evaluate:

1. The original fixed brightness/geometry HUD reader (**preserved unchanged** as reference and rollback).
2. The existing reviewed digit-exemplar candidate, **only where available and appropriately qualified**, not silently activated.
3. The new neural reader using CPU/ONNX reference.
4. The **same qualified checkpoint** as compiled Hailo-8L HEF on the actual device, if genuinely available.

Measure exact full-string accuracy **at reported coverage**, canonical digit edit distance, wrong high-confidence score, abstention/error calibration, false positives on no-score/transition frames, P1/P2 channel swaps, length/truncation/leading-zero and repeated-digit errors, robustness to illumination/color/focus/viewpoint and monotonic tracker behavior. Include confidence intervals/denominators where feasible, not only aggregate percent. A model that abstains on most images must not be called accurate based on the few accepted ones.

**Named mandatory investigations:**

- **October 11 discrepancy:** reported `1100` versus human-observed `2200`; identify exact original session/frame, score channel, observation time, display/phase, crop, prior score state and review outcome. If original bytes unavailable, keep a red **UNRESOLVED HISTORICAL CASE** with a reproducible recovery procedure; do not silently certify 2200 or 1100.
- **Historical 3/14 HUD reading** and later **2/2 camera-derived regression**: preserve original corpora, calibration differences and provenance; do not splice denominators or treat the tiny later result as proof of generalization.
- **Attract/high-score contamination** and phase-dependent observation: a visually plausible number in the wrong screen phase cannot be admitted as gameplay reward.
- **Score-review feedback**: demonstrate with authentic independently reviewed originals, when available, whether learning/correction improves subsequent inference, including a retained-state versus ablation comparison. Synthetic perturbation tests are engineering checks only.

Keep `ScoreTracker`/`ScoreObserver` temporal logic and acceptance thresholds as a **separate downstream layer**. Compare raw recognition proposals separately from after-tracker accepted scores; otherwise monotonic stabilization may disguise a reader mistake. Preserve complete-game official score certification as an independent gate.

---

## 6. Sharing a Pi, camera and Hailo with Robotron detection

The score reader must not introduce a second camera owner, duplicate Hailo device scheduler, or block urgent PPAL/SELF/perception operation. Coordinate with the separate Hailo Robotron sprite-perception mission, without making completion of that mission a prerequisite for independently useful score reading.

- Feed both from **one authoritative timestamped camera/capture pipeline** when possible, preserving raw frames, perspective geometry, ownership, and source observation IDs.
- Provide a small shared Hailo resource-admission interface or an explicit integration contract where one already exists. **Before adding a new scheduler, locate one**. Separate models may require serialized inference and memory admission; do not assume arbitrary concurrent HEF residency, throughput or batching.
- Make gameplay sprite/SELF observation higher priority than opportunistic HUD reads. Score sampling may be lower frequency, bounded and configurable; validate actual read/accept latency and queue drops instead of presuming a fixed cadence guarantees timely final scores.
- Preserve continuous capture introduced by PR #5 and distinguish **sensor exposure, source timestamp, enqueue, preprocessing, accelerator start/end, CPU decode, and temporal acceptance**. Never label processing completion as exposure time or let stale results rewrite later score state.
- When score inference fails, falls behind, overheats, or exhausts memory, return unreadable with status/telemetry and preserve existing safety/cleanup. Do not starve tracking/PPAL, create a separate gaming thread or claim the hardware is faster without end-to-end evidence.

Benchmark **isolated score inference and combined score + sprite inference**, once both are available, with end-to-end p50/p95/p99 latency, CPU time and CPU utilization, Hailo infer/transfer cost, throughput, frame age, queue backlog/drops, peak memory, temperature and effect on meaningful Robotron perception updates/s. Demonstrate saved CPU headroom rather than merely higher theoretical TOPS. Clearly distinguish recorded-frame host tests from live native tests.

---

## 7. Required tests and realistic execution milestones

Execute in this order where dependencies permit; **continue eligible milestones even when later ones are blocked**.

### M0 — Audited integration and baseline (required)

- Read governing docs, current audit and branch heads. Record source/installed/running distinctions, master already-integrated score feedback, pending original reviews, and current runtime uncertainty.
- Freeze old-reader reference behavior and independent source/photo hashes where available; no changes to original journals.
- Publish a bounded integration/duplication ledger and choose a narrow new branch.

### M1 — Working neural score recognition on host (required)

- Implement complete-score crop → fixed-shape model → sequence decode → backend-neutral score packet → `ScoreTracker` adapter, retaining original fixed reader and independent scores.
- Execute real model forward/training/evaluation/ONNX checks on explicitly labeled fixture data even if authentic training is blocked; clearly separate CPU prototype, reference inference, dataset quality and hardware qualifications.
- Add offline CLI to run saved authenticated frame/crop through each available backend and emit machine-readable uncertainty and provenance.

### M2 — Hailo adapter and genuine compatibility proof (required implementation; device/compiler may block qualification)

- Implement real optional HailoRT inference adapter, runtime health/discovery, explicit HEF compatibility checks, fallback/required modes and device lifecycle, with deterministic host doubles that don't count as real accelerator evidence.
- Provide runnable pinned compiler scripts, precise target `hailo8l`, ONNX node/operator/shape description, calibration contract, quantization comparison procedure, expected input/output normalization and realistic troubleshooting.
- If compiler exists, run actual parse/compile and publish `.hef` hash/log; if not, explicitly label HEF **ABSENT/UNVERIFIED**, not “ready.” Early compatibility trial precedes expensive authentic training.

### M3 — Verified original feedback and authentic model (as evidence permits)

- Read-only recovery/import with exact hashes; selective human-approved whole-score labels; frozen independent dataset; real training and held-out evaluation where enough sources exist.
- If absent, report exact recoverable source paths, missing immutable original records/images and **minimal operator actions**. Maintain fully working fixture-tested training and annotation adapter and do not invent a trained authentic checkpoint.

### M4 — Native offline Hailo qualification (only when independently accessible/authorized)

- Publish **read-only** operator-run checks of Pi OS ABI/driver/firmware/HailoRT/version and passive device detection; offline replay of already saved authentic score frames through candidate HEF; no game execution.
- Report true CPU/Hailo parity, latency, CPU savings, memory/temperature and fallback failure behavior. No physical gameplay, package installation, reboot, driver/firmware modification, model activation or mutation of original notebook without a separately scoped authority.

### Test suite obligations

Cover: stable P1/P2 geometry and independence, extrinsic-camera ROI extension, full-string/repeated-digit/blank/length cases, severe dim/glare/blur and calibration mistakes, unreadable/negative screens, source identity/timestamps and original scores, invalid/future/stale frames, backend switching, missing HailoRT/HEF, incompatible target/driver/operator/tensor type, timeout/exception/fallback, resource contention/nonblocking bounded queues, replay determinism, review immutability and supersession, data leakage, quantization drift, integration with existing `score_observer`, score tracker and independent game-boundary gates. Test shutdown/neutralization unaffected by score failures. Run focused suites plus feasible repository regression tests, retain exact commands, versions, stdout/JUnit and source SHA. Report skipped/blocked native tests honestly.

No synthetic, simulated or host checks are allowed to appear under **authentic improvement**, **native deployed**, **Hailo validated**, or **ALA complete**.

---

## 8. Publication, audit reconciliation and completion report

Publish a **draft pull request** containing minimal added/changed source, reproducible training/ONNX/HEF scripts, Hailo/CPU adapter and tests, dataset and model provenance manifests, benchmark/evaluation tools, operational read-only acceptance handoff, and accurate receipts. Include related audited workstream IDs and `CHA-9`; do not close them as solved. Preserve original PR #3, PR #5, Vision Lab branch and `master` unless separately authorized. Do not make broad branch consolidation the success criterion.

Report a six-column acceptance matrix as distinct truth claims:

| Acceptance gate | Proof required |
|---|---|
| **A. Code integrated in draft branch and host-tested** | Exact commit SHA, test commands/counts, isolated source provenance |
| **B. Authentic score-trained checkpoint** | Verified labels, distinct eligible sessions, frozen partitions, checkpoint hash, held-out metrics |
| **C. Compiled Hailo-8L `.hef`** | Real DFC compile logs, Hailo-8L graph target, calibration provenance and immutable HEF hash |
| **D. Native Hailo inference** | Actual Pi device/runtime, exact installed software identity, saved authentic images, device parity and measured latency |
| **E. Recognition benefit and CPU headroom** | Independent same-input accuracy/abstention, high-confidence errors, joint-load CPU/Hailo timing |
| **F. Independently qualified gameplay scoring benefit** | Original complete-game/phase/SELF/score evidence with separate certification and permission; never inferred from A–E |

Label each **PASS / PARTIAL / BLOCKED / NOT EXECUTED**, and say why. In final response return: PR URL, branch and commit, baseline source refs, exact test results, real saved binaries/ONNX/HEF or explicit absence, qualified original label counts (not historical guesses), measured/unknown results, unresolved October 11 discrepancy, data recovery instructions, Hailo toolchain/runtime blockers, and the **smallest possible requests to the operator**.

Also publish a brief **audit reconciliation note** keyed to `ROB-SCORE`, `ROB-FEEDBACK`, `VIS-CORPUS`, `VIS-LAB`, `VIS-HAILO`, `SYS-NATIVE`, `SYS-MIGRATION` and `CHA-9`, distinguishing “new implemented code” from “already integrated source” and “needs original evidence.” Make this consumable by the same Project Dashboard inventory when its historical-conversation Phase 2 runs; do not create a rival dashboard or mark the historical audit exhaustive.

**Success for this mission is the most complete tested implementation and truthful checkpoint obtainable now—not a false claim that real Hailo-8L scoring or gameplay improvement has already been demonstrated.** Do not stop at a design proposal or ask the operator to re-explain already provided information.
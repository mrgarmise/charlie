# Hailo-8L observation bridge — unqualified draft

This changes detection observations only. No live gameplay entry point selects
this backend. Forebrain/Hindbrain, WorldState, safety gates, manual focus 2.0,
continuous camera ownership, marathon and reflection order are untouched.
`player` appearance maps to UNKNOWN at the legacy boundary; it cannot replace
signed BODY response or two-direction shot-origin evidence. E1, P1 and I1 each
remain **NOT YET DEMONSTRATED**. No physical operations were performed.

## Ancestry and reuse

New independent branch `feature/hailo-observation-bridge` starts at PR #5 head
`8c96db003b87246ee6b0f9dc9918cb42af726370`. PR #5 is preserved. Vision Lab is
separate at `9156940a89651ec0b16d8972f8fed1261ae8f3da`; none of its UI, label
store, optimizer, partitioning or evaluator is duplicated/cherry-picked.
Use its pinned checkout on PYTHONPATH for the optional Lab and compiler bridges:

```bash
git worktree add --detach ../charlie-vision-lab 9156940a89651ec0b16d8972f8fed1261ae8f3da
export PYTHONPATH="$PWD:$(cd ../charlie-vision-lab && pwd)"
# Install Lab dependencies in a separate operator-selected venv per its README.
python -m vision_lab --state /absolute/separate/robotron-lab
```

Do not point state at the original notebook. Its 3,247 records and all episode
archives remain unchanged. The Lab's existing Ultralytics 8.3.203 environment is
not assumed to support Hailo export. Do not upgrade it in place for compilation.

## Implemented boundary

`DetectorBridge.observe(Frame(...))` accepts an already-corrected image and exact
exposure timestamp, timestamp basis, source ID and provenance from its caller.
It owns no camera, thread or queue. A future reviewed integration may pass the
existing ObservedCamera/Exposure image and capture metadata; it must not open
another reader. This draft provides that API and offline replay, **not live
activation**. `tracking_pairs()` is compatible with VisualAgency.observe and
SpriteTracker; select one existing tracker, never run both for a physical path.
SemanticObserver remains optional crop refinement, not a second association pass.

Modes: `strict` propagates startup/inference/shape/timeout errors. Explicit
`fallback` uses the supplied original CPU detector, emits a bounded failure event
and names the actual backend; it never grants authority. Replay intentionally
uses strict mode. Backends are original CPU template detector, hash-checked
Vision Lab CPU CandidateDetector, and actual HailoRT HEF virtual-stream inference.
No Hailo imports occur for CPU use. Hailo input/output stream timeouts are bounded;
late results are discarded even if inference succeeds. Native device setup may
have additional driver latency; this is an offline candidate, not a real-time
qualified service. Each HEF call currently configures/releases its VDevice for
clean resource ownership; measure this overhead before considering persistent
context optimization. No throughput claim is made.

Hailo startup checks HEF SHA, parse-hef architecture exactly HAILO8L, device
presence, one RGB square input, and one NMS output. Configuration enforces driver
compatibility. Class count is checked on output; **class order must be verified
against the signed/exported contract by the operator**, since NMS does not encode
semantic names. Raw-head, segmentation and differently decoded HEFs are rejected.
Contract decoder is `hailo-nms-yxyx-score`, normalized per-class y/x/y/x/score,
letterbox RGB 114, float32 0..255 (HEF must contain exporter normalization).
The runtime does not silently reinterpret arbitrary ONNX output as HEF.

Packets preserve pixel and board boxes, source timestamp/basis, geometry,
provenance, model identity, backend, uncalibrated score and available class-score
vector, settings, processing time and age. Missing vectors/confidence are null,
not invented. Hailo score <.5 remains a tracked UNKNOWN candidate, with the raw
class hypothesis retained. CPU template thresholds stay unchanged. Labels not
in the explicit semantic mapping remain UNKNOWN. Rich world v1 uses the shared
tracker's IDs, timed history, velocity in board units/second, observed position,
occlusion/quarantine and bounded prediction. Association cost is separate from
class confidence and causal identity. No predicted position is passed to policy.

## Authentic data and training

`data-inventory.json` inventories the six preserved PNGs already committed under
`docs/validation/agency-first-stream/baseline`, with byte and decoded-pixel hashes.
They come from `development-20261017-200109`, original archive SHA
`c02b9ec790a028f54bc143fb1c54d06aad8542c83122bf62e75f5a96c0b21780`.
These are raw camera frames, **not corrected playfield training labels**. Six
frames, one session, zero human-verified annotations, zero eligible training
images. This is an accessible subset, not an inventory of the user's Mint/Pi.
The October 17 failed session and later ~1.66 delivered observations/s remain
baseline evidence, not successful new Hailo runs. Sensor ~15 fps is not delivered
agency throughput. All original bytes are preserved.

```bash
python -m experiments.ppal.inventory_robotron /copied/frames --session ORIGINAL_SESSION --output NEW-inventory.json
```

Operator request: supply read-only original recordings from at least three
independent game sessions, camera/geometry/exposure metadata, and human-reviewed
boxes or permission to annotate in Lab. Group entire sessions, including nearby
frames, together; inspect near duplicates across sessions. Lab already prevents
exact duplicate and persistent partition leakage. Model proposals, synthetic
fixtures, guessed tracks and automated labels are not ground truth. Verify
empty negatives explicitly. Correct/crop raw camera geometry before annotation;
retain raw-to-corrected transform/provenance rather than relabeling raw images as
normalized playfields.

Configure Lab classes to `player, grunt, hulk, tank, human, mine, other_enemy,
projectile`; UNKNOWN remains unresolved. `detector_bridge.LABELS` provides the
initial configurable suggestion, not proof all classes occur in these images.
Add brain/enforcer/subtypes after verified examples. Include overlap/crowds,
flash, disappearances, CRT bloom/glare, varied geometry/focus and empty playfields.
Use Lab verified annotations → frozen train/val/test → YOLOv8n from scratch →
validation → one-use held-out comparison → ONNX preparation. Retain Lab model
records (seed, augmentations, hyperparameters, image size, dataset/checkpoint
hashes). Pretrained-vs-scratch comparison requires an explicit local
pretrained checkpoint, licensing review and matching frozen data; the existing
Lab worker intentionally uses from-scratch, with no implicit downloads.

No authentic .pt was trained here; no new ONNX exists; no HEF was compiled.
No synthetic optimizer run is presented as Robotron performance. Torch,
Ultralytics, HailoRT/driver, DFC and hardware were absent on the Work host.

## Offline inspection and evaluation

Create a JSONL manifest, one row per corrected image, in exposure order:

```json
{"image":"corrected-001.png","frame_id":"session:1","exposure_at":123.456,"timestamp_basis":"monotonic sensor exposure start","provenance":{"session":"original-session","capture_metadata":{},"geometry_transform":"operator-verified homography"}}
```

Use actual capture metadata; never substitute file mtime for exposure. The replay
clock uses historical exposure time for ordering; native freshness is **null**,
with separate measured wall processing duration. Output creation is exclusive.

```bash
python -m experiments.ppal.replay_detectors frames.jsonl --backend template --profile verified-sprites.json --output NEW-template.jsonl
# PYTHONPATH includes the separate frozen Lab checkout:
python -m experiments.ppal.replay_detectors frames.jsonl --backend lab --lab-state /separate/robotron-lab --model-id MODEL_ID --output NEW-cpu.jsonl
python -m experiments.ppal.replay_detectors frames.jsonl --backend hailo --hef custom.hef --contract export.json --output NEW-hailo.jsonl
```

Run all backends on identical held-out recordings. Convert packet boxes to Lab's
`class_name,x,y,w,h,confidence` samples and use its `evaluation.measure` and
error-gallery workflow, not a duplicate scorer. For template UNKNOWN confidence,
do not invent a calibrated score or rank AP; report coverage/detection counts and
unresolved fraction separately. Required authentic report: per-class P/R/AP50,
confusions, FP/frame, tiny/projectile recall, continuity/ID swaps and class
permanence, stratified by session/difficulty. Current values are **unmeasured**.
Retain all detector traces and visual review examples. Existing class-free
projectile candidate/ShotOrigins path is the temporal comparator; benchmark it
at original corrected resolution against YOLO on verified projectile sequences.
No ground truth here supports a recall winner or streak-specific tuning.

## Compiler host: operator only

Official sources checked 2026-10-18:
https://docs.ultralytics.com/integrations/hailo and
https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html .
HailoRT interface reference:
https://github.com/hailo-ai/hailort/blob/master/hailort/libhailort/bindings/python/platform/hailo_platform/pyhailort/pyhailort.py .

Official exporter supports YOLOv8 detection → ONNX → INT8 HEF, `name=hailo8l`,
Linux x86_64, DFC v3.x. Compilation does not run on Pi. Use a separate versioned
venv with compatible DFC from Hailo Developer Zone and an Ultralytics release
whose `export_formats()` includes hailo; freeze `pip freeze`, compiler license,
AGPL-3.0/enterprise terms and platform requirements before running. No dependency
installation/license acceptance was performed here. The bridge checks actual
versions rather than assuming Lab's pinned version supports this feature.

```bash
python -m experiments.ppal.compile_hailo_lab --lab-state /separate/robotron-lab --model-id MODEL_ID --output NEW-export-dir
```

This reuses Lab manifest/hash verification and YOLO dataset export, copies weights
into a fresh workspace, and points exporter train **and validation** calibration
roles only to training images. No test/validation calibration leakage or padding.
All training frames are used; fewer than recommended 1,024 is recorded as a
constraint. Preserve export.json, stdout/stderr, exact versions, generated HEF,
ONNX intermediate if available, input normalization, NMS tensor metadata and
class order. ONNX preparation alone is not HEF success. If the exporter/version
or proprietary compiler is unavailable, that is a blocker; do not rename ONNX.

### Versioned Model Zoo alternative (not executed)

If the Ultralytics exporter is unavailable, reuse Lab's checked `best.onnx` and
its training-only calibration export. The upstream **v2.17** tag resolves to
`1bde1102a7706e43688c863330a93acbc0f4db90` (verified with git ls-remote).
Use its compatible DFC 3.33 / HailoRT 4.23 toolchain on supported x86_64 Linux,
subject to vendor installation/licensing requirements. Do not use current Zoo
master, which targets other architectures. In that separate environment:

```bash
git clone https://github.com/hailo-ai/hailo_model_zoo.git hailo-model-zoo-2.17
cd hailo-model-zoo-2.17
git checkout --detach 1bde1102a7706e43688c863330a93acbc0f4db90
# Install this checkout per its vendor guide, alongside matching DFC.
hailomz compile yolov8n --ckpt /absolute/checked/best.onnx --hw-arch hailo8l \
  --calib-path /absolute/verified-training-only-images --classes YOUR_CLASS_COUNT
```

This is a versioned compiler procedure, **not a tested custom graph compile**.
Inspect the pinned YOLOv8 YAML/model script and graph's actual six detection-head
endpoints; supply `--start-node-names`/`--end-node-names` when required. Class-count,
NMS decoder, letterbox and input normalization must match the runtime contract.
Never substitute a stock COCO HEF or guess graph node names. Preserve exact
commands, parser/optimizer/compiler logs, training-only calibration hashes,
actual HEF hash and `hailortcli parse-hef` output. A constrained 128-image Lab
calibration bundle remains 128, not the recommended 1,024. This path remains
blocked here by absent verified data and proprietary compiler dependencies.
Pinned guide: https://github.com/hailo-ai/hailo_model_zoo/tree/1bde1102a7706e43688c863330a93acbc0f4db90/training/yolov8 .

## Read-only Pi acceptance and rollback

Operator-triggered, no controller connected and no gameplay launcher:

1. Preserve current checkout and environment. Inspect `hailortcli scan`,
   `hailortcli fw-control identify`, `hailortcli parse-hef custom.hef`; retain
   driver/HailoRT/firmware versions, device architecture and HEF hash. Use
   Hailo-8L, not Hailo-8/10H. Do not flash firmware/install packages via this task.
2. Run strict Hailo replay above on recorded real corrected frames. Verify
   normalization, decoder, class count/order, CPU-vs-HEF coordinate and score
   tolerances against verified boxes. Test missing device, corrupt HEF, shape
   mismatch and inference timeout separately. Never silently pass via fallback.
3. Retain raw durations and compute delivered FPS and P50/P95 inference,
   pre/postprocess/association time, setup cost, RSS/CPU/temperature/throttling.
   Repeat long enough to observe thermal effects. Hardware setup per frame is
   currently a likely cost; measure it, do not infer speed from 13 TOPS.
4. Separately authorize camera-only acceptance if desired: use the existing
   CameraSession/ObservedCamera source, one owner, manual focus 2.0, preserve
   exposure metadata. Measure camera-to-observation age, drops and delivered
   independent observation FPS. Historical replay cannot measure that latency.
5. Native recognition quality, model qualification and gameplay benefit remain
   separate gates. No model promotion or tactical action follows these commands.

Rollback: select `--backend template` for offline replay (or stop the optional
bridge and retain the unchanged original live detector). Remove optional
PYTHONPATH/venv. To inspect baseline without destroying work:
`git worktree add --detach ../charlie-pre-hailo 8c96db003b87246ee6b0f9dc9918cb42af726370`.
No model, notebook or firmware rollback is needed because none was activated.

Next milestone: expose safe firing-line opportunity data to the Learning
Executive as an optional observation-only feature, after perception evidence
qualifies. No new hard-coded firing tactic is implemented here.

## Host checks and measured costs

`tests/test_detector_bridge.py` exercises protocol/timestamps, letterbox, UNKNOWN,
class transitions with stable IDs, startup/timeout/shape failures and fallback,
late/reordered/duplicate results, HEF integrity, fake SDK NMS/stream-timeout and
context-release contracts, deterministic replay/output protection, no SELF from
appearance, and training-only calibration/export-version gates. Fake SDK/exporter
fixtures are explicitly synthetic; they do not show real compilation/inference.
The regression suite includes the existing single-camera/marathon tests.

`host-baseline-cost.json` contains 18 calls per existing CPU stage on the six raw
archived images, three repeats each. Host median: segmentation 33.53 ms,
projectile candidates 17.61 ms; P95 40.80 and 19.11 ms. These measure host processing
cost only, not corrected-frame quality, authentic projectile recall, native
latency, camera FPS, model speed or gameplay benefit. No YOLO/HEF performance
comparison can be made without the missing model/toolchain. See `host-tests.json`
for exact test outcomes/environment and tested-source hashes.

Reproduce host stage costs into a new file (timings will differ):
`python -m experiments.ppal.benchmark_detector_candidates docs/validation/agency-first-stream/baseline --output NEW-costs.json`.
P95 uses nearest rank. This is not a native or accuracy acceptance measure.

# Neural Robotron score reader — unqualified draft

**October 18 continuation — archival screenshot training path:** [Sampling to authentic
HEF](SAMPLING-TO-HEF.md) documents the newly implemented preserved-game
source sampler, existing human review UI queue, strict game-level
train/validation/test commitments, portable Mint labeling export, and an
explicit `score.hef` compiler-required pipeline. The compiler is still
not available in this workspace, no authentic model or HEF has been
produced, and native/activation acceptance remains open.

Revision 2 mission, October 18, 2026. Workstreams: **ROB-SCORE, ROB-FEEDBACK,
VIS-CORPUS, VIS-LAB, VIS-HAILO, SYS-NATIVE, SYS-MIGRATION; CHA-9**.

This is a working, host-tested visual-reader implementation with real synthetic
training and saved CPU/ONNX artifacts. It is **not an authentic Robotron-trained
model, compiled HEF, Pi installation, live activation or score certificate**.
No gameplay, controller, camera, servo, firmware, notebook writer or deployment
was started. E1/P1/I1 each remain NOT YET DEMONSTRATED. Master and existing drafts
are preserved. The historical ChatGPT/Work audit remains **PENDING EXPORT**;
Phase 1 is not exhaustive.

## Audited base and narrow integration

Fresh branch `feature/hailo-score-reader` starts at verified master/tag
`bcf8082f6319c63c4bd6bcceeab5faea37241654`. `baseline-ledger.json` records source
hashes and actual feature heads. The existing score-feedback reader, recovery
and candidate tools match PR #3's branch byte-for-byte: they are already
integrated, not newly imported. PR #3 remains open and its authentic acceptance
remains blocked. Governing charter, acceptance standard, Best of Charlie README
and the current Phase 1 audit were read before edits. The executed Library
mission was Revision 2, version 1, modified October 18 at 18:44:19 UTC under
Charlie the Cyberdek.

PR #5 head `8c96db003b87246ee6b0f9dc9918cb42af726370` owns newer continuous
camera/capture work. PR #6 head `ab58a3d3d3f83a44e77184d329f0e28c1f9cbda8`
adds an unqualified sprite Hailo bridge. Neither is merged here. Vision Lab stays
at `9156940a89651ec0b16d8972f8fed1261ae8f3da` in its independent checkout.
Its annotation UI, SQLite store, YOLO optimizer/job scheduler and box metrics are
not copied: whole-string CTC is a different supervised format. This implementation
reuses Charlie's existing numeric review, immutable journal, geometry and temporal
tracker APIs, and follows Lab's frozen-session and one-use test commitments.
The operator must supply all prior Lab/MemoryEvaluator partition commitments
before admitting authentic data; cross-application identities cannot be inferred
from filenames or an inaccessible store.

Only two existing runtime files change: `RobotronScoreSystem` accepts an optional
reader and source metadata; `ScoreObserver` accepts an optional reader factory and
capture metadata, records raw neural diagnostics in its existing worker, and
ensures a full queue cannot prevent shutdown sentinel admission. Defaults retain
the original fixed reader. No production launcher flag selects the unqualified
model. `robotron_hud.py`, ScoreTracker, DualScoreTracker, VisualScoreTracker,
score events, Forebrain/Hindbrain, Executive, Evaluator and game boundaries remain
unchanged. The old reader's source hash is frozen in the ledger. No thresholds
or physical authorization gates were relaxed. Installed and running Pi identities
are UNKNOWN, separately from integrated source.

## Reader and timing contracts

Input is the **full original camera image**, not normalized playfield pixels.
`NeuralHUDReader` uses the existing extended HUD above the arena: side vectors
extend upward by .10; rectify to 640×96; P1 x=.10–.28, P2 x=.72–.90. It rejects an
extended strip outside the captured frame. Each complete channel is resized by
explicit fixed x/y factors to 256×32 RGB, bilinear, NCHW float32 /255. No glyph
segmentation, inferred leading digits or content-dependent word trimming is used.
This fixed channel transform retains all pixels and makes the score span useful
CTC timesteps; its native recognition quality is unqualified.

Graph `score-conv-ctc-v1`: Conv/ReLU, Conv/ReLU, Conv/ReLU, final Conv; no recurrent
layers, dynamic dimensions, string decoder, softmax or transpose in the exported
inference graph. Input `[1,3,32,256]`, output **logits** `[1,11,1,64]`. Classes 0–9
and blank=10. CPU performs log-softmax for CTC training and conservative greedy
CTC decoding for inference. Repeated runs collapse; explicit blanks separate
repeated digits. Empty output is unreadable, not zero. Noncanonical leading zero,
edge tokens, excessive length, nonfinite tensors, uncertain digits **or blanks**
abstain. No dropped ambiguous token or appended zero can yield a shorter answer.
Confidence is an uncalibrated minimum softmax/margin statistic, not correctness
probability. Decoder gates are fixture-tested conservative engineering settings,
not authentic calibration. Dim, saturated and clipped crops decline early.

Packets include channel/crop geometry, raw HUD quad, calibration identifier,
source capture metadata/ID/exposure basis, image and crop pixel hashes, model/
ONNX/HEF/training provenance, bounded 64×11 diagnostics, uncertainty and failures.
Actual raw file SHA is added by the CLI; pixel SHA is explicitly different.
Exposure, enqueue/queue wait, rectification, preprocessing, inference submission/
return, CPU decode and completion remain distinct. FLOAT32 stream wall time
includes host/device transfer and setup, **not measured on-chip execution time**.
Device duration is null. Invalid, future, stale, repeated or nonmonotonic exposures
cannot update numerical candidates; late results become unreadable. Raw replay
never claims native frame freshness from a historical clock.

Modes:

- `cpu-reference`: actual ONNX Runtime inference from the exported network,
  one intra/inter-op thread; fixed HUD recognition remains a separate baseline.
- `hailo-required`: only hash-bound Hailo-8L HEF with exact contract, NHWC input
  `[1,32,256,3]`, NHWC logits `[1,1,64,11]`; one input/output/network group.
  Missing runtime/device/HEF, wrong target/order/shape, driver failure and timeout
  are explicit unreadable health events. Offline required-mode failure exits 2.
- `hailo-preferred`: records actual CPU fallback and exact Hailo cause. It never
  labels fallback as accelerator inference. Resource denial drops score work
  rather than moving contention onto CPU fallback.

Actual HailoRT adapter uses HEF, Device.scan, VDevice.configure, FLOAT32 input and
output virtual streams, a bounded timeout/queue size, InferVStreams and activation
contexts. Driver quantizes/dequantizes according to the HEF; host values are /255
with **no embedded second normalization**. It validates parse-hef target and
stream layouts. Contexts close on exceptions. Device setup/release currently
happens per call; this may be expensive and must be measured before any persistent
context optimization. No performance claim follows from fake SDK tests.

## Existing worker and shared resources

No new camera, background inference queue, writer service or gaming thread was
added. Source submits independent copied raw pixels to the original queue of two;
new overloads drop with counts. Neural mode requires explicit gameplay phase;
attract/unknown/retired frames stay in the existing non-gameplay partition. Late
inference cannot replace a later source observation. Queue wait and raw proposals
are journaled separately from accepted temporal score. A confirmed visual score
does not establish SELF, game over, restart, action reward attribution or complete
game certification.

The existing generic ResourceGuard is not a Hailo residency scheduler. No shared
Hailo scheduler was found on master or PR #6. `backends.HAILO_ADMISSION` supplies
a small cooperative process-local admission **contract**: all future sprite/SELF
and score callers must share that object; urgent perception reserves its `urgent`
event and lock, scores never wait, in-flight work has bounded stream waits.
The existing thermal/memory owner can call `suspend(reason)`/`resume()`; suspended
resource admission and MemoryError do not trigger CPU fallback. Native health
wiring remains part of the blocked joint integration, not a new thermal policy.
PR #6 does not yet use this gate: **joint activation is blocked until its caller
uses the same admission owner**. Uncooperative external processes are not excluded
by a Python lock; do not claim cross-process or preemptive device scheduling.
There is never more than one device context through this gate. No simultaneous
model residency or batching benefit is presumed. Native setup may exceed stream
timeouts; a stuck worker is reported, not falsely reported shut down. Existing
camera/controller cleanup still precedes score worker close. Manual focus remains
2.0 and camera/marathon behavior is untouched.

## Reproduce host engineering work

Use a separate Linux x86_64 Python 3.12 environment, not Charlie's Pi runtime:

```bash
python3 -m venv /new/score-env
/new/score-env/bin/pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
/new/score-env/bin/pip install -r requirements-neural-score.txt
/new/score-env/bin/pip install pyserial mpremote
/new/score-env/bin/pip check
```

`environment.json` records the exact tested versions. This does not install any
Hailo dependency or accept vendor compiler licensing. Torch checkpoint loading
uses `weights_only=True`; load only the hash-bound trusted artifacts.

```bash
PYTHON=/new/score-env/bin/python
"$PYTHON" -m experiments.ppal.neural_score.train --synthetic /new/SYNTHETIC-corpus
"$PYTHON" -m experiments.ppal.neural_score.train --manifest /new/SYNTHETIC-corpus/manifest.json --output /new/stage150 --steps 150
"$PYTHON" -m experiments.ppal.neural_score.train --manifest /new/SYNTHETIC-corpus/manifest.json --output /new/stage1650 --resume /new/stage150/score.pt --steps 1500
"$PYTHON" -m experiments.ppal.neural_score.train --manifest /new/SYNTHETIC-corpus/manifest.json --output /new/stage1850 --resume /new/stage1650/score.pt --steps 200
"$PYTHON" -m experiments.ppal.neural_score.cli --onnx /new/stage1850/score.onnx --model-record /new/stage1850/training.json --manifest /new/SYNTHETIC-corpus/manifest.json --role val --output /new/validation.jsonl
# Freeze model selection before the one-use final synthetic test:
"$PYTHON" -m experiments.ppal.neural_score.cli --onnx /new/stage1850/score.onnx --manifest /new/SYNTHETIC-corpus/manifest.json --role test --output /new/test.jsonl
```

The generator rendered 96 fixture files; exact deduplication retained 94 manifest
records: 66 train, 14 validation, 14 test. None is an authentic Robotron image.

Steps, wall deadline and SIGTERM cancellation are bounded; optimizer/RNG/seed,
losses, dataset digest, augmentation (none), checkpoint hashes and resume lineage
are retained. No implicit weight downloads. Outputs refuse overwrite. Final test
consultation is recorded **before** evaluation; later training on that dataset
and repeated final-test evaluation are rejected. The released fixture corpus ZIP
already contains its closed test ledger: use it for validation/inference, not
further training or repeated test selection. To reproduce training, generate a
fresh SYNTHETIC corpus. Supplied `.pt`/ONNX are **SYNTHETIC_ONLY**, never a model
for deployment. Artifact hashes are in `artifacts-sha256.json`.

Observed fixture results, not authentic accuracy: first 150-step validation had
0/14 coverage. After resumable training (1,850 total optimizer steps), validation
accepted 10/14 strings, all ten correct; **the reserved synthetic test accepted
0/14**, so accuracy at accepted coverage is undefined there. No false high-
confidence accepted strings occurred in that tiny test; this says nothing about
unseen Robotron images. The synthetic groups deliberately vary background and
share a renderer/font; they are not independent original games. Do not tune this
model against the now-consulted test set. Tests independently cover zeros,
repeated digits, blank, leading zeros, length, clipping and unreadable outcomes.

`host-benchmark.json.gz` compares the same two historical full-camera JPEGs/crops.
Ten calls are repeated measurements of **two images**, not ten independent
examples. Host medians: fixed reader 7.12 ms; neural rectification plus both
channels 2.22 ms; original CPU sprite-region extraction 106.76 ms; joint CPU
reference work 108.91 ms. These include recorded pixels and diagnostic geometry,
not native camera throughput or accelerator CPU savings. Original fixed regression
remains 2/2 on this separate tiny corpus. Neural fixture weights are unqualified;
raw output is retained rather than promoted by temporal smoothing. Reviewed
exemplar baseline is unavailable because original reviews are missing. To inspect:

```bash
"$PYTHON" -m experiments.ppal.neural_score.benchmark --onnx docs/neural-score/SYNTHETIC_ONLY/score.onnx --output /new/host-costs.json
```

## Authentic evidence and recovery

**Qualified original labels available for new training: 0.** Original October 10
review DB/WAL and hash-bound photos remain unavailable here. Historical counts
16 status / 8 annotation records are leads, not image/label counts. Two camera-
derived JPEG fixtures retain historical labels 0 and 100 with diagnostic geometry;
they are not fresh independent human reviews or new training data. Other saved
raw score PNGs have no newly verified review binding. Accessible archive inventory
is `accessible-archive-inventory.json`; copied journal examination never appends
to originals or treats old observations as new experience.

**UNRESOLVED HISTORICAL CASE — October 11:** operator-observed 2200 versus reader
1100, session `development-20261011-192041`. Exact matching original photo,
observation/capture time, channel, phase, prior temporal belief and final human
review remain unverified. Neither number is admitted as training truth. Preserve
the later `development-20261011-203343`/900/finalization failure as a separate case.

Historical 3/14 in `docs/ppal/score-tracking-integration.md` used an older 14-image
corpus and raw_004-derived calibration; the eleven abstentions and later 4/14
historical experiment remain separate from the later 2/2 camera regression.
This task does not recover all 14 originals or combine denominators/calibrations.

Smallest operator evidence request: run the existing **read-only SQLite/WAL-safe
export procedure** in `docs/score-feedback/native-recovery.md`, returning the
original review database snapshot, image-location map and exact hash-bound photos.
Include the specific October 11 session's `score.jsonl`, report, original score
photos and calibration/capture metadata. No new game, notebook writer or label
reconstruction is needed. Preserve the original store. Its review import/reviewer
portal already supports full-number confirm/correct, unreadable, supersession,
full-frame inspection and durable acknowledged saves; do not build another portal.

On the host, import into a fresh working copy using the existing recovery tools,
review through the existing inspector, then build crops **read-only**:

```bash
"$PYTHON" -m experiments.ppal.neural_score.corpus --journal /working/copied-review.sqlite3 --calibration /verified/calibration.json --output /new/corpus-v1
# For subsequent versions pass every prior frozen score manifest:
# ... --prior-manifest /old/corpus-v1/manifest.json
```

The adapter reuses `reviewed_labels`: only current, independently attested,
unambiguous, hash-bound accepted numeric reviews with explicit channel/session/
calibration binding enter. Superseded, disputed, unreadable, missing images,
synthetic and split-conflicting records are excluded with reasons. Whole-number
labels require no digit boxes. `None` unreadable is not a blank/negative label.
Verified no-score negatives require explicit human absence attestation; the
existing unreadable status must not be relabeled as absence. Such authentic
negative labels are currently missing.

Manifests are immutable and hashed, use portable relative image paths, and keep
annotation IDs/reviewer, original full-frame hash, crop hash, session, channel,
source review and preprocessing. Exact crops, same full-frame channels, sessions,
low-resolution near-duplicates and prior version roles cannot cross splits.
An append-only corpus-local commitment ledger records freeze/test consultation.
Always retain that ledger and supply prior manifests when changing corpus roots.
Different-source near-duplicates and prior Lab/MemoryEvaluator consultations still
need their original commitments reconciled; they are prerequisites to authentic
independence, not proven by this fresh local ledger. Validation is for tuning;
one-use isolated final tests are for measurement. No train augmentation from
validation/test is allowed. All original archives/notebooks remain unchanged.

## Compiler feasibility and actual hardware gate

The graph's Conv/Relu inventory and fixed node names/shapes are in the saved
`training.json` export report. PyTorch forward, real optimizer, ONNX checker and
ONNX Runtime numeric equivalence actually ran. The proprietary compiler is
absent; attempted feasibility command failed with PackageNotFoundError for
`hailo-dataflow-compiler`. `compiler-blocker.log.gz` preserves the failure.
**HEF ABSENT; parse/INT8 optimization/compile UNVERIFIED.** No impossible operator
has yet been demonstrated, so switching architectures without evidence would be
premature. If DFC rejects an operator/layout, preserve its exact error and try the
smallest compatible Conv slot/glyph alternative before substantive authentic
training; do not call a stock YOLO/COCO or plate-reader HEF this score network.

Pinned target: Linux x86_64 compiler environment with **DFC 3.33.0**, compatible
HailoRT **4.23.0**, target **hailo8l**. Model Zoo v2.17's upstream tag is
`1bde1102a7706e43688c863330a93acbc0f4db90`; it documents this version pair. The
custom graph uses ClientRunner directly, not Ultralytics YOLO export or a guessed
Model Zoo network. Vendor compiler access/licensing and supported OS are required;
none was installed on Pi or acquired here.

```bash
# On the prepared supported x86_64 compiler host, not Pi:
"$PYTHON" -m experiments.ppal.neural_score.compile score.onnx --manifest /verified/training-corpus/manifest.json --output /new/score-hef
# Engineering graph feasibility ONLY, if using the released synthetic graph:
# ... --engineering-feasibility
```

Script verifies graph operators and fixed contract, selects actual graph input
`images` and final Conv node from ONNX, saves parsed/quantized HARs, calibrates
using **train only**, and writes `.hef` only after `runner.compile()` succeeds.
Retain full stdout/stderr, compiler environment, `hef.json`, HEF/ONNX/calibration
hashes and parse-hef tensor names. Host calibration is NHWC RGB float32 /255,
matching runtime; do not add another /255 normalizer in the compiler. Calibration
count is reported exactly; do not pad from evaluation data. Synthetic compilation
would prove graph feasibility only. The runtime intentionally rejects alternate
layouts until an explicit tested decoder conversion is supplied.

Primary references checked October 18:
https://github.com/hailo-ai/hailort/blob/master/hailort/libhailort/bindings/python/platform/hailo_platform/pyhailort/pyhailort.py ,
https://hailo.ai/developer-zone/documentation/hailort-v4-23-0/ ,
https://github.com/hailo-ai/hailo_model_zoo/tree/1bde1102a7706e43688c863330a93acbc0f4db90 ,
https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html .

## Native acceptance — operator-triggered, read-only

No installation, migration, reboot, service restart, model activation or live game
is part of this procedure. Run from an independently approved prepared checkout;
a checkout SHA alone does not prove installed/running identity.

```bash
uname -m
getconf LONG_BIT
uname -r
cat /etc/os-release
python3 -c 'import sys,sysconfig; print(sys.version); print(sysconfig.get_config_var("SOABI"))'
lspci -nn
hailortcli scan
hailortcli fw-control identify
hailortcli parse-hef /verified/score.hef
# Existing operator tool, if present, separately reports installed/running state:
python -m charlie_ops status
```

Return versions/architecture, installed-release receipt, running checkout/process
identity and actual HEF inventory. Historical enumeration/architecture mismatch
and proposed 64-bit SSD migration remain unverified, not completed by this code.
AI HAT+ 13 TOPS is Hailo-8L; enumeration alone is not successful inference.

With compiled contract and copied already-verified saved crops:

```bash
"$PYTHON" -m experiments.ppal.neural_score.cli --mode hailo-required --onnx /verified/score.onnx --model-record /verified/training.json --hef /verified/score.hef --hef-contract /verified/hef.json --manifest /verified/corpus/manifest.json --role val --compare-reference --output /new/native-strict.jsonl
```

Raw-frame replay additionally accepts `--frame`, `--calibration`, and `--source`
JSON with actual observation ID, exposure_at, timestamp_basis and capture metadata.
Do not invent timestamps for JPEGs lacking capture metadata. Historical replay
records completion and wall costs but does not measure camera-to-observation age.
The live source's actual exposure clock must be matched for camera latency tests,
under separate camera-only/native authority, one owner and focus 2.0.

Compare identical CPU/Hailo inputs, checkpoint/ONNX/HEF identities, normalization,
CTC alignment, class order and scores. `--compare-reference` retains per-frame
logit drift and accepted/proposed string parity only when actual Hailo succeeded.
Measure exact full-string accuracy **with coverage and denominators**, edit
errors, wrong high-confidence strings, no-score false positives, channel swaps,
length/repeat errors, and phase contamination. Keep raw proposals separate from
tracker acceptance and full-game certification.

Then measure isolated and joint sprite/score work through the same admission
owner: p50/p95/p99 end-to-end and transfer/setup latency, process CPU time and
utilization, meaningful tracking updates/s, queue/drop/age, RSS, temperature and
throttling. Repeat for sustained load; return original timing samples, not just
marketing TOPS or nominal sensor FPS. Drop or abstain on stale/thermal/resource
failure. Joint Hailo measurements and useful CPU headroom remain UNKNOWN here.

Rollback: leave the default `RobotronScoreSystem`/`ScoreObserver` constructors
without `reader`/`reader_factory`; that retains the unchanged fixed reader. For
neural offline reference select `--mode cpu-reference`. No model or firmware was
activated, so rollback requires no notebook rewrite or service manipulation.
A nondestructive baseline checkout is:
`git worktree add --detach ../charlie-pre-neural-score bcf8082f6319c63c4bd6bcceeab5faea37241654`.

## Acceptance matrix (independent truth claims)

| Gate | Status | Evidence | Limitation | Needed next | Authority |
|---|---|---|---|---|---|
| A — Draft integrated code/host tests | PASS after publication | Exact PR/head, source hashes, focused/full JUnit | Host only | Review draft | No activation |
| B — Authentic score-trained checkpoint | BLOCKED | 0 eligible original labels; synthetic binaries retained | Original review DB/photos absent | Recover reviews and independent sessions | Offline approved copies |
| C — Compiled Hailo-8L HEF | BLOCKED | Compiler attempt/error and runnable graph script | DFC absent; no HEF | Supported compiler host, training-only calibration | No Pi installation |
| D — Native Hailo inference | NOT EXECUTED | Host doubles only | Pi/runtime identity unknown | Read-only inventory and saved-frame replay | Operator-triggered |
| E — Recognition benefit/CPU headroom | BLOCKED | Synthetic results and host same-pixel costs | Synthetic held-out abstains 14/14; no authentic/joint Hailo proof | Independent same-input native metrics | No promotion |
| F — Qualified gameplay scoring benefit | NOT EXECUTED | Original boundaries/acceptance preserved | No complete-game experiment authorized | Separate independent qualification/permission | No gameplay |

See `host-tests.json` for exact commands/counts and `audit-reconciliation.json`
for durable capability IDs. Tests include genuine optimizer/export/resume,
CTC strings/blanks/uncertainty, raw extrinsic P1/P2 geometry, temporal integration,
phase partitioning, source clocks, bounded queue/shutdown, Hailo contract/failure/
resource doubles, quantization drift, immutable reviews/supersession and leakage.
Passing these tests never closes ALA-2 or CHA-9.

A no-data-needed inspection example using released **synthetic** artifacts:

```bash
unzip docs/neural-score/SYNTHETIC_ONLY/fixture-corpus.zip -d /new/score-fixtures
"$PYTHON" -m experiments.ppal.neural_score.cli --onnx docs/neural-score/SYNTHETIC_ONLY/score.onnx --manifest /new/score-fixtures/manifest.json --role val --output /new/synthetic-inspection.jsonl
```

The PNGs/manifests are portable; generated trace/metric outputs must be new paths.
Host package license strings are retained as package metadata, not a compiler
license grant. No third-party pretrained weights or authentic labels were fetched.

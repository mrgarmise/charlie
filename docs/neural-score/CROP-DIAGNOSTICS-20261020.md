# Crop and CTC diagnostics — PR #8, October 20

Parent inspected: `d45cce134e10d342f64a4d33f8baf9fcc1a41b01`,
`feature/hailo-score-reader`, existing draft PR #8. The latest incremental
sampler work is preserved. This Work checkout was clean before changes.
The operator's Mint checkout and its uncommitted fixes were not accessed or
overwritten. The attached ALA charter and acceptance standard were read.

## Findings and access limits

The current remote already has `reviewed_labels().display_digits` and the corpus
uses it. Explicit human `00` is not currently collapsed to numeric `0` upstream.
The earlier local `dbb7499` behavior described in the mission is historical;
the private Mint diff still needs preservation by its owner.

The operator reports a 64-image training-only corpus, digest
`7a91c73d9ce47d8616abf07a5fbf03727398774972ab8e5fc9d2d9fbc437276f`,
and model-002 ONNX SHA
`e3b44a0894429a148e4fccf51301f4c6179eed00ba33309e2f865b0ff3002686`.
The mission and `Pasted text(9).txt` contain training/log evidence; the log
shows 1,000 steps, the export downgrade warning and ORT error about 2.86e-6.
Library searches for score/corpus/portable/model-002 did not expose the actual
corpus, checkpoint, ONNX or raw per-image logits. Those files remain a specific
operator dependency, not a reason to repeat the 100 human reviews.

Reported training results remain **operator-reported training fit**: raw exact
39/64 (60.94%), accepted 0/64, always-`00` raw baseline 37/64 (57.81%). All
64 reportedly had nonblank first and last timesteps and the edge rejection.
Those are not independent validation results. Neither reproduction of that
model nor its actual ONNX opset/native compatibility is claimed here.

## Actual pixel trace

The pipeline is full original photograph → calibrated HUD → score channel →
CNN input. It does not train on a whole-screen image. `rectify()` returns
640×96. P1 bounds `[64,0,179,96]` produce **115×96**; P2 bounds
`[460,0,576,96]` produce **116×96**. The legacy preprocessing resizes the whole
channel to 256×32. For P1 its scales are 2.2261 horizontally and .3333 vertically:
approximately 6.68 times more horizontal than vertical scaling. This is in
addition to the calibrated HUD transform, not a claim about square source pixels.

The [contact sheet](crop-diagnostics/historical-geometry/contact-sheet.png) and
[pixel/geometry audit](crop-diagnostics/historical-geometry/audit.json) use two
hash-verified historical originals already retained in repository fixtures.
They are **historical diagnostic photographs, not the private 64 training
images**. Source run/file/calibration/hash identity is retained in
`crop-diagnostics/historical-examples.json`; no new score labels were assigned.

Both source photos are 1280×720, with all sampled score-channel pixels inside
the camera image. Visual inspection shows the crop contains substantial dark
margin, upper bezel and, in one image, a lower arena border. The score lies
near the lower-right. The first crop's bright-pixel box touches the boundary;
this alone does not prove a clipped digit because the arena border is bright.

Two fixed diagnostic ROI hypotheses are saved without changing the reader:
vertical trim `[64,48,179,92]`, and wider/trimmed `[64,48,205,92]` for P1,
with corresponding P2 bounds. The vertical trim removes bezel/border from
these two photographs while retaining their visible characters. **Widening
includes an adjacent life icon in the first photograph**. Therefore automatic
widening is not justified. No content-dependent or label-specific crop was
installed. The same candidate boxes can be audited on every training source.
Correctness of these bounds on corpus-005 remains unverified until its pixels
are supplied. The historical examples cannot qualify a replacement ROI.

## Alignment diagnosis and controlled evidence

The graph remains the existing four-convolution ScoreNet with Conv/Relu only,
input `(1,3,32,256)`, output `(1,11,1,64)`, blank class 10. The horizontal
stride is 4 and receptive field 15 input pixels. CTC targets preserve repeats:
`00` encodes `[0,0]` and needs at least three timesteps, including a separator;
`100` and `800` need four. The 64-step output is not structurally too short.

CTC loss permits a nonblank at either end; the strict decoder requires blanks
there. The existing objective therefore did not explicitly teach an assumption
used by acceptance. This explains why lower CTC loss can coexist with universal
edge rejection; it does not establish the pixel/optimization cause of each
model-002 error. Greedy CTC merges adjacent identical tokens, so a missing blank
separator can collapse trailing zeros. Actual model-002 paths are needed to
distinguish that from missing/ambiguous visual features or a bad crop.

`diagnose` records the raw 64-token path, probabilities, margins, run boundaries,
raw proposal, accepted text, rejection reason, minimum target time length,
source/crop/tensor hashes and actual ONNX opsets when an ONNX is supplied.
Contact selection is deterministic and restricted to training examples; all
training images contribute to metrics. Final/validation rows are not evaluated.

An explicit experimental profile resizes to 224×28 and pads 16 pixels left/right
and two top/bottom. The uniform .875 shrink preserves the legacy input aspect;
this is not an aspect-ratio correction. A separate optional training objective
adds weighted blank NLL at the first/last timesteps. Default weight is **0** and
legacy preprocessing stays the default. Neither changes decoder edges or .85
confidence/.25 margin gates. Mismatched resume profiles/objectives fail.

The reproducible 8-image **synthetic software control**, seed 17, 300 Adam steps
per variant, gives:

| Variant | Raw exact | Accepted | Images with nonblank edge |
|---|---:|---:|---:|
| Legacy | 0/8 | 0/8 | 8/8 |
| Padding only | 0/8 | 0/8 | 8/8 |
| Padding + boundary weight .25 | 0/8 | 0/8 | 0/8 |

The majority-`00` baseline is 4/8. Boundary supervision removes the edge symptom
in this control, but all eight still abstain for uncertainty. **Recognition
benefit is not demonstrated.** Padding alone is insufficient here. Detailed
actual hashes/results are in `crop-diagnostics/synthetic-alignment-control.json`;
`python -m tools.score_alignment_experiment --output /new/control --steps 300`
reproduces the control. Synthetic images are never substituted for originals.

## Corrections and integrity

- Shared exact-display validation admits explicit `0`/`00` and canonical positive
  strings. It rejects `0000`, other unsupported zero runs, ambiguous numeric-only
  historic zero, conflicts and malformed strings. New annotations cannot add
  `0000`; historical records remain intact. Active invalid historical labels are
  excluded until genuinely superseded. No `0000`→`00` rewrite occurs.
- Regression coverage follows annotation → effective review → frozen crop →
  repeated CTC targets → raw/accepted metrics. It verifies historical invalid
  review exclusion and linked supersession without rewriting the old record.
- Near-duplicate checks now include supplied **prior frozen manifests**, not
  only the current batch. The threshold is unchanged. Pixel/frame/session and
  frozen partition guards remain in force; validation failures must not be
  bypassed by moving labels or lowering the overlap threshold.
- Export explicitly uses `dynamo=False`, checks actual ONNX opset 11 and the
  static compiler graph contract, then verifies ORT equivalence. Compiler
  validation rejects an actual opset 18 graph. ORT numerical agreement alone
  cannot establish Hailo compatibility.
- New ONNX metadata binds preprocessing and dataset digest. CPU replay, compiled
  calibration, model records and the optional reader must agree. Legacy models
  without metadata retain their legacy preprocessing contract. Experimental
  models cannot silently use the default input preparation.
- `python -m experiments.ppal.neural_score.model` re-exports identical existing
  weights into a new directory with a new integrity record and original-artifact
  lineage. No original checkpoint, ONNX or training record is overwritten.

## Operator commands using existing data

First preserve the existing Mint checkout's local work. Use a separate directory
for this PR revision; the existing environment may be used without reinstalling
the Pi or the validated compiler environment. If SSH Git authentication is still
unavailable, the public HTTPS fetch below avoids changing the configured remote:

```bash
git -C ~/charlie-hailo/score-reader status --short
git -C ~/charlie-hailo/score-reader fetch https://github.com/mrgarmise/charlie.git feature/hailo-score-reader
git -C ~/charlie-hailo/score-reader worktree add --detach ~/charlie-hailo/crop-diagnostics FETCH_HEAD
cd ~/charlie-hailo/crop-diagnostics
SCORE_PY=~/charlie-hailo/score-reader/.venv/bin/python
```

Run the central training-only diagnostic immediately with the existing files:

```bash
"$SCORE_PY" -m experiments.ppal.neural_score.diagnose \
  --manifest ~/charlie-score-training/corpus-training-005/manifest.json \
  --checkpoint ~/charlie-score-training/model-002/score.pt \
  --output ~/charlie-score-training/model-002-crop-audit-001
```

This already produces exact crop/input/CTC diagnostics. To populate source-frame
and calibrated HUD overlays, add `--review-export /exact/existing/portable-export`
and `--calibration /exact/matching/calibration.json` to a new output run. The
calibration must match the proposal's recorded geometry digest. Existing paths
can be listed with `rg --files ~/charlie-score-training | rg 'image-locations.json$|manifest.json$'`.
Missing source panels are labeled unavailable, not reconstructed.

For Work to inspect the actual 64 images/model directly, package only existing
training artifacts and originals (no new reviews or reserved evaluation pixels):

```bash
"$SCORE_PY" -m tools.bundle_score_crop_diagnostics \
  --manifest ~/charlie-score-training/corpus-training-005/manifest.json \
  --model-directory ~/charlie-score-training/model-002 \
  --review-export /exact/existing/portable-export \
  --calibration /exact/matching/calibration.json \
  --output ~/charlie-score-training/crop-diagnostics-bundle-001
```

Return that `.tar.gz` or the existing diagnostic output. The bundle preserves
the manifest bytes/digest, model hashes, original photo bytes and crop paths.
It refuses mixed train/validation/final corpora and mismatched calibration.

Inspect actual ONNX metadata using the same diagnostic with `--onnx` and
`--model-record` instead of `--checkpoint`. To re-export identical model-002
weights into checked opset 11 without retraining:

```bash
"$SCORE_PY" -m experiments.ppal.neural_score.model \
  --checkpoint ~/charlie-score-training/model-002/score.pt \
  --training-record ~/charlie-score-training/model-002/training.json \
  --output ~/charlie-score-training/model-002-opset11-001
```

Keep the failed collapsed-label 100-step model and original model-002. Do not
resume either into a changed preprocessing/objective experiment. After inspecting
actual crops, compare matched 1,000-step runs from fresh seed 17 checkpoints,
same frozen corpus, with legacy, padded-only and padded-plus-boundary profiles:

```bash
"$SCORE_PY" -m experiments.ppal.neural_score.train \
  --manifest ~/charlie-score-training/corpus-training-005/manifest.json \
  --output ~/charlie-score-training/padded-boundary-001 --steps 1000 --seconds 600 \
  --seed 17 --preprocessing score-rgb-channel-resize-224x28-pad16x2-v2 \
  --boundary-blank-weight .25
```

Run the same diagnostic on each model and preserve all results. Use legacy
profile/weight 0 for the baseline and padded profile/weight 0 for padding-only.
If invalid labels remain in an old frozen corpus, first produce a new corpus
from the existing effective review history; the trainer refuses invalid targets.
It never changes frozen labels or infers zero count.

## Validation and qualification limits

Final frozen-source host suite: **1,375 passed, 2 skipped, zero failures**,
346.70 s. Focused: **144 passed**, 4.70 s, including 20 new crop/label/CTC/export
cases. The two optional skips require `CHARLIE_IDENTITY_ACCEPTANCE_ROOT` and
`CHARLIE_GEOMETRY_ACCEPTANCE_ROOT`; their original-archive roots were not configured
for this run. Retained original-image regressions did run. One existing JUnit
`record_property` format warning remains. Torch optimizer, fixed-seed weight
reproducibility, actual opset-11 export/ORT parity, profile mismatch rejection
and portable bundle integrity were exercised on controlled host fixtures.

Exact source/environment, commands, counts, skips and compressed log/XML receipts
are under `crop-diagnostics/`. Earlier concurrent development runs used the same
default temporary resource lock while source was still under revision; they had
guarded acquisition/thermal/camera fixture failures (3 and 2 failures). Those
failed receipts are retained and are not acceptance evidence. The final run was
alone with a separate `TMPDIR`; resource/physical safety guards were not weakened.

Reserved validation must be admitted with all applicable training/prior-manifest
commitments. A useful first check is the existing corpus adapter's
`--partition validation --prior-manifest /frozen/training/manifest.json` into a
new output. If it fails overlap checks, an independent subset has **not been
established**; do not treat this as permission to reuse adjacent frames. Existing
external consultation/group commitments also need review. No sealed final set
was consulted in this work. No authentic independent validation total or accuracy
is claimed from inaccessible private files.

No additional manual labeling is requested now. First diagnose the existing
corrected labels, crops, effective CTC paths and admissible validation. Additional
labels become useful if readable diverse training scores remain underrepresented
after those checks, or if all reserved validation sources overlap development.
Then prioritize missing digit/score patterns and independent source groups over
more `00`; select only from authorized existing evidence unless new capture is
separately authorized. Training confidence bins are descriptive, uncalibrated.

DFC 3.33.0 and actual native Hailo execution remain operator-host activities.
After choosing an admissible candidate, compile its checked ONNX with the matching
new `training.json` (`compile --model-record ...`) and training-only calibration
corpus, then perform isolated saved-image required-Hailo parity and reliability
testing. The prior synthetic HEF execution does not qualify model-002 or a new
authentic model. No gameplay, camera activation, servos, firmware, live policy,
original evidence writer or physical operation occurred here.

E1, P1 and I1 are each **NOT YET DEMONSTRATED**. Independent recognition benefit,
authentic HEF qualification and ALA-2 acceptance remain open. Roll back this
software change with a normal revert of the published repair commit; the fixed
reader and legacy preprocessing remain defaults. For an isolated source rollback
use parent `d45cce134e10d342f64a4d33f8baf9fcc1a41b01` in a separate worktree,
retaining all new evidence and artifacts.

# Hailo score reader continuation — native findings and recovery

This is the October 19 implementation follow-up to the operator's October 18
hardware findings. Parent inspected before modification:
`207c3f053b86d4b75078badef574535d8853dd91`, existing **draft PR #8**, branch
`feature/hailo-score-reader`. No merge, live activation, camera session,
controller command, servo operation, firmware change or Pi package change.

**Primary objective remains BLOCKED: no new authentic-trained HEF or independent
authentic accuracy/coverage result was produced.** The synthetic HEF is not a
substitute. E1, P1 and I1 remain independently NOT YET DEMONSTRATED.

## Targeted adapter correction

`backends.py` now accepts exactly NHWC input and FCR output metadata for
`charlie_score/input_layer1` (32,256,3) and `charlie_score/conv4` (1,64,11).
Previously supported NHWC output remains supported for these same names/shapes;
other orders, substring lookalikes and incompatible names are rejected.
FCR is **HEF metadata order**, not the returned Python array's axis contract.
FLOAT32 virtual streams must return finite `(1,1,64,11)` float32 arrays. The
unchanged `transpose(0,3,1,2)` yields decoder `(1,11,1,64)`. Canonical inputs
must be finite float32 `(1,3,32,256)` in [0,1]. Hash, hailo8l architecture,
normalization, stream timeout, one network, resource admission and explicit
backend/fallback checks remain enforced. Optional new manifest metadata must
agree with runtime; old compiler manifests without these fields still undergo
actual name/shape/order validation. `hailo-required` never falls back to CPU.

`compile.py` now writes separate HEF names/orders/dimensions and Python vstream
dtype/shape fields. This does not rewrite the operator's original `hef.json` or
change any existing model/HEF bytes. Do not reinterpret the old textual
`output_layout` field as actual native metadata. Newly compiled networks must
meet the fixed names/orders contract or require an explicit reviewed revision.

No decoder or temporal acceptance threshold changed. Proposed digits remain
distinct from accepted digits. Confidence .81895 vs .89027 can legitimately
cross the unchanged .85 threshold with the same proposed text; neither
abstention nor a valid threshold disagreement is an inference failure.

## Evidence status

The operator-reported baseline is preserved in
[`operator-synthetic-parity-20261018.json`](operator-synthetic-parity-20261018.json).
No original native logs, logits or HEF bytes were supplied to this Work host.
The report is not a claim that Work executed the accelerator.

Demonstrated **by operator report**: DFC 3.33.0 synthetic compilation with 66
calibration images, HAILO8L parsing, physical Hailo-8L execution (10/10), Python
FLOAT32 inference, finite output and correct canonical conversion. The ~7078 FPS
result is only a short streaming accelerator benchmark. HEF SHA-256:
`d0e977e11eb4d1c4bb6d8338da79ce4cb503fae0cbcd22d28ad6fd963492d0f3`.

Five **synthetic, now consulted engineering validation** examples proposed the
correct text on both backends (5/5); CPU accepted 2/5, Hailo accepted 3/5, all
accepted strings correct; acceptance decisions agreed 4/5. Mean logit MAE
0.18657, maximum individual error 0.842. These are not untouched final-test
examples, calibration evidence, or evidence that Hailo is more accurate.
Controlled host logits in regression tests are explicitly not reconstructed
native logits or new gameplay observations.

Not demonstrated: authentic recognition accuracy, calibrated confidence,
extended native reliability, camera-to-score latency, multi-client Hailo
concurrency, or independent gameplay improvement. The existing `native_validated`
flag is not silently set true: successful native execution and recognition
qualification need separate provenance, not one overloaded boolean.

## Authentic recovery performed here

[`authentic-recovery-20261019.json`](authentic-recovery-20261019.json) records
actual host archive scans: **54 archives, 3,228 image members** (including
duplicates/derived images, NOT 3,228 distinct eligible training observations).
The October 18 audit archive itself has 397 members, 258 SQLite snapshots and
zero image files. Its SHA is
`752c957b1b4ea35677c4d26f5efc572653d20b8fe9eaa55b13a052d92241e63f`.
The recovered original review snapshot SHA is
`ee612110302b40d89b977fc7dbb57ae2dc3a2ac09f7482bd78aa83d682464d21`;
its 1,641 records include eight annotations over six image hashes, not eight
independent training images. All six original image hashes were recovered,
including direct original archives corroborating two repository fixtures.
The snapshot remains byte-identical; original notebook/media were not written.

The **existing** `reviewed_labels()` validator finds six eligible diagnostic
reviews, zero training, zero validation, zero final. Seven other diagnostic
proposals remain unresolved/unattested. Existing supersession, review IDs and
partitions were retained. The six old review contexts also lack explicit
channel/calibration bindings required by the full-string corpus adapter. They
are not silently relabeled or re-partitioned into a new training/final corpus.

Two standalone `score-raw-0037` uploads have identical SHA
`7e49cf868160473a87b5d02054bd94a081a6baab80fb050b9bf94f50a821de71`;
neither is one of the six human-annotation hashes. No prediction or visual guess
was assigned as truth. Library title searches covered score/review, Charlie,
Robotron/game, tar archives, pilot, portable, corpus, HEF and SQLite exports.
All 55 distinct tar filenames returned were inspected: this audit plus the 54
archives in the recovery receipt, including earlier camera/detector bundles.
No pilot/portable/corpus/SQLite export or HEF bytes were returned by those title
searches; absence from search alone is not proof of absence on original media.
This is scoped accessible-archive recovery, not
proof of original-SD completeness or a search of inaccessible Pi/Mint files.

Reproduce the byte-bound recovery without arbitrary archive extraction:

```bash
python -m tools.recover_score_review_evidence \
  --audit-archive /saved/2026-10-18-ala2.tar.gz \
  --image-archive /saved/development-20261002-005944.tar.gz \
  --image-archive /saved/development-20261002-012801.tar.gz \
  --image-archive /saved/development-20261002-015817.tar.gz \
  --image-archive /saved/exposure-calibration-20261001-010300.tar.gz \
  --image-archive /saved/response-window-20261001-012341.tar.gz \
  --image-archive /saved/charlie-game-20261004.tar.gz \
  --output /new/recovered-review-copy
```

The fresh working output contains unchanged SQLite bytes, six hash-addressed
originals, the existing relocation overlay and exclusions. Only bounded regular
image members are read; arbitrary archive paths and links are never extracted.
Memory is bounded per image (32 MiB) and snapshot (256 MiB); processing is linear
in input bytes, offline, never part of camera/gameplay acquisition.

## Exact dependency to unblock the authentic HEF

Export the **actual pilot working notebook**, not the historical October 10
diagnostic notebook. In the isolated PR #8 checkout on Charlie, using its
existing interpreter (no installation or live activation):

```bash
python -m experiments.ppal.neural_score.export_reviews \
  --journal /home/five/charlie-score-sampling/review-copy/working.sqlite3 \
  --output /home/five/charlie-score-sampling/portable-native-followup
```

Return the entire new export with `images/`, `image-locations.json`, `export.json`
and SQLite snapshot; also the existing frozen `pilot-002.json` (and every prior
selection/corpus manifest and consultation ledger), exact matching calibration
file, and relevant source/calibration provenance. Confirm actual paths first;
do not replace or reset missing files. The exporter reads originals and uses a
SQLite backup including committed WAL. This request does not authorize new
attestations or permit abandoned/empty UI text to become labels. Pending,
unreadable or insufficient cases require genuine operator review through the
existing workflow. Preserve train/game/marathon/validation/final ownership.

Then use [SAMPLING-TO-HEF.md](SAMPLING-TO-HEF.md) to freeze verified whole-score
crops, train the existing ScoreNet and export checked ONNX. Train/select only on
permitted train/validation roles. Original diagnostic material and the five
synthetic parity samples cannot become fresh independent final evidence.

DFC 3.33.0 is absent on **this** Work host (actual compiler_preflight fails);
the operator's working Mint compiler removes that infrastructure blocker there.
Do not reinstall/replace its validated dependencies, or install pinned host ML
requirements blindly into its Python 3.10 compiler environment. A separate
training environment may produce ONNX; the already validated DFC environment
can run the existing compiler module on that ONNX and training-only corpus:

```bash
python -m experiments.ppal.neural_score.compile /new/authentic/model/score.onnx \
  --manifest /new/authentic/corpus/manifest.json \
  --output /new/authentic/hef
```

No `--engineering-feasibility`: an authentic release must not substitute the
synthetic checkpoint. Publish `.pt`, ONNX, actual HEF, all integrity manifests,
training configuration, exclusions and independently measured accuracy/coverage
with immutable provenance. No artifact is claimed until actually generated.

## Isolated operator native acceptance — saved images only

Use a separate checkout and saved copied images, existing HailoRT 4.23.0 packages
and the shared admission owner; no live reader/policy enablement. Verify artifact
SHA, `hailortcli parse-hef` names, HAILO8L, NHWC input, FCR output and dimensions.
Retain version/inventory output and actual logs outside original evidence.
For an already consulted **validation** corpus, compare the same preprocessed
arrays using the existing replay (new result path each time):

```bash
python -m experiments.ppal.neural_score.cli \
  --onnx /isolated/model/score.onnx --model-record /isolated/model/training.json \
  --hef /isolated/hef/score.hef --hef-contract /isolated/hef/hef.json \
  --mode hailo-required --compare-reference \
  --manifest /isolated/corpus/manifest.json --role val \
  --output /new/native-parity.jsonl
```

Missing or invalid HEF/runtime must fail, not relabel CPU output as Hailo. Preserve
every failure/abstention and actual output shape/dtype, raw decoder diagnostics,
same-input hashes, max/mean logit drift, proposals vs accepted strings, exact
accuracy and coverage. Do not tune thresholds for agreement. `--role test` is a
separate single-use final consultation only after model selection and independence
review; never repeat it for selection. Retain extended saved-image reliability,
CPU/wall/RSS/temperature and admission-denial measurements. Live camera latency,
multi-client scheduling and gameplay improvement remain separate unqualified
activities and need their own scope/authority.

## Rollback and acceptance

Final host validation: **1,356 passed, zero failures, zero skips**, 363.73 s;
focused **126 passed**, 3.94 s. The recovered October 1 identity collision and
all 119 original geometry frames passed both separately (2 tests, 42.35 s)
and in the final full run. One existing JUnit `record_property` format warning
remains. Actual synthetic optimizer/ONNX tests ran with Torch/ORT available;
fake SDK tests are not native Hailo qualification. Exact environment, tested
source hashes, commands and compressed log/XML receipts are retained in
`fcr-environment-and-source.json`, `fcr-host-tests.json` and `fcr-*.gz`.

The first full development run found a pre-existing UI-test mismatch: the
current exact-visible-digits UI returns string `"1300"`, but its test double
expected numeric `1300`. The expectation now matches HTML input string
semantics; UI behavior and all stale-photo/failed-save guards are unchanged.
That failed run (1 failed, 1,353 passed, 2 skipped) is retained, not counted as
acceptance. Initial isolated host package-install metadata conflicts were
repaired before final validation; `pip check` now reports no broken requirements.

| Acceptance | Current evidence |
|---|---|
| Host repaired code | PASS; exact source and test receipts |
| Authentic training checkpoint/ONNX | BLOCKED; no eligible bound training corpus |
| Authentic-trained Hailo-8L HEF | NOT PRODUCED; pilot export and actual compiler execution required |
| Synthetic native execution | OPERATOR-REPORTED PASS; repaired adapter still requires operator replay |
| Independent authentic accuracy/coverage and native reliability | NOT DEMONSTRATED |
| Gameplay benefit / E1 / P1 / I1 | Independently OPEN; no activation |

No production selector changed; the existing fixed score reader remains default.
For isolated offline rollback, use parent
`207c3f053b86d4b75078badef574535d8853dd91` in a separate worktree; preserve new
receipts and artifacts. A repository rollback can revert this repair commit
without rewriting history. Do not overwrite an installed model or original
notebook. Keep PR #8 draft. Native adapter execution with this repaired code,
authentic model/HEF, independent recognition qualification and E1/P1/I1 remain
open; host mocks close none of them.

# Authentic Robotron dataset preparation on Charlie, 2026-10-29

The Raspberry Pi 5 completed historical recovery, offline review preparation and
the normal Executive missing-evidence path. **NEEDS_LABELS; no authentic candidate
trained, evaluated or activated. Charlie has not demonstrated the complete
Executive-originated authentic training cycle.** All operational policy remains
unchanged and all future candidates remain shadow until qualified and approved.

## Checkout and preservation

Existing draft PR #15 / `feature/executive-model-learning` only. Starting local
commit `f4789776ad33eb1b30e78d9eb0a16981e2cf425d` and published
`e0d94e1730cdf53e8bf82dbaf6aa220b153ea307` have identical tree
`c03e2bdc4d2ce31fa47c9455e4874e917091c536`. Worktree was clean; PR remained open
and draft. Other PR branches and the original agency checkout were untouched.

The persistent state is `/home/five/charlie-model-review`, not the score reader's
database. A SQLite read-only-source backup was saved as
`/home/five/charlie-dataset-qualification-20261029/review-before.sqlite3` before
intake. All **12** original journal records retain identical documents and commit
times. All six original labels retain attribution/history. The operator-reviewed
marathon attract screen remains `title_menu` and its incumbent remains `unknown`.
No original images, archives or review records were overwritten. Application
startup additively records its normal evidence and operational status in this
same notebook; no state replacement or migration was performed.

## Inventory, recovery and readiness

Read-only inventory of three canonical historical roots found:

| Root | Image files | Outside `tracking`/`crops` |
|---|---:|---:|
| Original `Projects/charlie/robotron-runs` | 8,969 | 2,321 |
| `charlie-native-trials` | 675 | 675 |
| `charlie-play/robotron-runs` | 1,171 | 1,171 |

Seven root-level `.tar.gz` archives contain 719 images (several archives contain
only nonimage diagnostics). These are files, **not counts of independent
exposures**. Historical track identity labels and filename phase hints are not
screen-state ground truth. Crop/tracking products, missing calibration/origin,
unverifiable manifest entries, copied aliases and near duplicates are ineligible
for this intake. Other unadmitted files remain available for later provenance
work; this is a bounded representative recovery, not a claim every file is useful.

Intake examined 71 selected full-frame candidates and admitted 64: 25 preserved
repository developmental photographs, 22 manifest-verified native photographs
from three capture origins, and 17 manifest-verified photographs recovered from
three immutable archives. Archives were read through bounded regular members;
no `extractall`, original-tree extraction or application startup was used. Archive,
member, original capture-origin, manifest and image hashes are retained locally.
Real `capture_id` identity is used for native/archived recordings rather than
inventing sessions from copied directory paths. Repository photographs retain
their four original developmental session IDs and calibration. Seven candidates
were excluded for identical pixels or dHash distance <=4 to already retained data.

There are now **70 authentic frames across 13 session identities**, 34,869,557
retained image bytes. Of these, six labels remain confirmed and 64 are unreviewed.
No new human label was submitted or attributed to the operator. Private
`coverage.json` contains the full class-by-session matrix; sanitized matrix in
`authentic-data-native-20261029.json` uses session aliases.

| Original labeled session | title/menu | gameplay | terminal | unknown |
|---|---:|---:|---:|---:|
| body-fire bootstrap | 1 | 1 | 1 | 0 |
| response window | 1 | 1 | 0 | 0 |
| marathon attract | 1 | 0 | 0 | 0 |
| Totals | 3 | 2 | 1 | 0 |

The ten newly admitted session groups have 8/7/6/3/8/7/3/7/7/8 unreviewed
frames respectively in sorted session-identity order. There are **zero retained
pairs at dHash distance <=4** (all pairs checked), but absence of a hash match
alone does not establish independence. Whole capture sessions must stay together.
All 70 remain unassigned; no dataset was frozen and no final holdout was spent.
Known-class coverage in each of train/validation/test is unresolved. Even if all
current confirmed labels were test data, they fall short of the default five
held-out examples per class by at least title/menu 2, gameplay 3, terminal 4,
unknown 5; train/validation need separate sessions too. Qualification thresholds,
unknown requirements and leakage rules were not changed.

## One operator handoff

**Copy/open `sftp://five@charlie.local/home/five/charlie-dataset-qualification-20261029/review-ready.html`
on Mint, review the 64 pending photographs (leave the six existing labels
unchanged), enter your own reviewer name, download `reviews.json`, and copy that
file back to the same Pi directory; then run its `apply-reviews.sh` once.**

The 1.8 MB standalone gallery embeds images and works through ordinary file
viewing, without a web service. It shows IDs, original sessions, original names,
source hashes, confirmed labels and separate machine proposals. No reviewer name
is prefilled. Attract-mode gameplay and damaged/transition displays may need
context: leave uncertain cases open; do not label them `unknown` merely because
the incumbent abstained. The batch uses the existing immutable label API,
explicit supersession, integrity checks and atomic transactions. Existing human
review contracts remain available; PR #14's Human Interaction Gateway module is
absent from this feature checkout, so this local path needs no incompatible
merge or new service. Gallery/answers, backup, retained images and personal
review attribution are private local artifacts and are not committed.

## Actual native commands and results

Run from `/home/five/charlie-model-learning`, using
`/home/five/Projects/charlie/.venv/bin/python` as `python`:

```bash
python -m learning.model_learning --state /home/five/charlie-model-review ingest /home/five/charlie-dataset-qualification-20261029/intake.json
python -m learning.model_learning --state /home/five/charlie-model-review review-gallery /home/five/charlie-dataset-qualification-20261029/review-ready.html
python -m learning.model_learning --state /home/five/charlie-model-review coverage
python -m learning.model_learning --state /home/five/charlie-model-review baseline
python main.py --offline --model-learning --learning-state /home/five/charlie-model-review --learning-turns 1 --learning-budget 10 --learning-wall-seconds 60
```

The normal application, not a direct trainer call, retained 70 incumbent
classifications, a Reflection need, Executive portfolio selection, a model turn
and a missing-data outcome. Independent read-only journal inspection confirms
`NEEDS_LABELS`, zero proposals, zero dataset freezes, zero candidates and zero
model evaluations. Its offline process shut down cleanly after one attempt:
24.56 s elapsed, 23.10 CPU s, 72 ownership checks, 171,933,696 peak owned RSS
bytes, two CPU core budget, 768 MiB memory budget, 56.2 C final temperature below
75 C ceiling. Thermal telemetry was required and present on aarch64 Linux.
Physical authorization is false, controller writes zero and active pointer null.
The run recorded the starting commit with dirty tooling changes; this is not a
claim the then-uncommitted review UI was a previously released artifact.

CPU incumbent replay matched 5/6 reused confirmed labels (83.3%, one abstention).
This is descriptive replay, not independent acceptance. The sixth label exposes
the genuine attract-mode gap. Unknown recall and transition timing remain
unmeasured. No missing labels were inferred from predictions. Baseline metadata
now identifies the actual architecture/runtime instead of hardcoding 'host'.
The final gallery/baseline commands additionally use the existing guard.

An early baseline/Executive attempt collided with the legitimate notebook lock
while gallery generation was finishing. Both failed closed with `BlockingIOError`;
those logs are preserved. Sequential retries succeeded. A mistyped test filename
also produced a retained no-tests-collected log before the corrected test run.
No failure or ambiguous outcome was deleted or represented as a pass.

## Native device and remaining qualification boundary

This is physically Charlie's Raspberry Pi 5, Python 3.13.5/aarch64. Hailo and
Picamera2 packages are installed, but `/dev/video*`, `/dev/media*` and `/dev/hailo*`
are absent in this execution namespace. The gameplay lock was free at the sampled
instant; this is not proof the host has no live application. Process namespace
visibility is restricted. The canonical passive Eyes publication roots had no
published files. Consequently there was no existing read-only camera publication
to consume safely; no owner was replaced and no second camera process started.
Hailo execution is also inapplicable to the current fixed NumPy CPU JSON model:
installed packages do not make this model accelerator-qualified. No Hailo
inference/compilation or physical capture is claimed.

Remaining conditions are specific:

- **Missing evidence / operator-only review:** label the 64 authentic review
  candidates where visually justified, then inspect the class-by-session matrix.
  Genuine unknown/OOD and independent terminal coverage may still need capture.
- **Operator-only state changes / safety authorization:** if recovery does not
  supply coverage, use the already owning capture application to preserve full
  frames, calibration, `capture-origin.json` and hash manifest in separate real
  recording sessions. The operator supplies title/attract, manually played active
  gameplay and terminal states; Charlie stays a read-only observer. For genuine
  OOD, the operator may deliberately show a known non-Robotron screen to the
  existing observer. Do not infer OOD from rendering artifacts or classifier
  abstention. Obtain at least five varied final-test examples per class including
  OOD, with different whole sessions for training and validation and no dHash
  cross-split matches. Starting games, changing the displayed application or
  controller activity is an operator action, not authorized autonomous capture.
- **Inaccessible device:** any fresh native camera or Hailo execution requires a
  normal host session exposing its actual device and existing owner; CPU evidence
  preparation and the normal missing-data path have already run here.
- **Unproven acceptance:** after genuine review and sufficient independent
  coverage, assign whole-session partitions through the existing CLI, keep test
  sealed, and rerun the normal Executive command above. Require native training,
  independent incumbent/majority comparison, abstention/transition/calibration
  and resource qualification, durable rejection/rollback evidence as applicable,
  and explicit shadow approval. No implementation shortcut replaces this cycle.

No firmware, ultrasonic reader, chassis, controller, live camera application,
active PR branch or operational model was altered. PR #15 stays draft.

## Validation and reproducibility

Local review integrity/transaction tests cover escaping untrusted provenance,
truth/proposal separation, no export mutation/overwrite, exact receipt replay,
stale/foreign/duplicate/corrupt/invalid reviews, explicit supersession preserving
history, final-test exclusion, cancellation and atomic failure rollback.
The initial review+model selection passed 42 tests; expanded model/lifecycle/
resource selection passed 65 tests before adding two final integrity cases.
The final review suite passed all 14 tests in 2.34 s. The focused independent
workflow now includes the review suite; combined CI also
collects it through the full tests directory. CI outcomes and exact published
commit are reported on PR #15 after publication, rather than guessed here.

Private reproducibility files are under
`/home/five/charlie-dataset-qualification-20261029`: `inventory.py`, `inventory.json`,
`inventory-summary.json`, `prepare.py`, `intake.json`, `selection-audit.json`,
`coverage.json`, contact sheets, gallery receipts, original backup, baseline and
Executive logs, independent `verify.py`/`native-summary.json`, test logs and XML.
Recovery scripts and private provenance remain local; reusable admission,
immutable review, partition and Executive flows remain the existing APIs.

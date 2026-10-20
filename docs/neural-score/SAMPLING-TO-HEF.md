# Robotron score reader: archived screenshots → human labels → real Hailo-8L HEF

**Status:** training pipeline implemented on PR #8, pending native authentic review
and DFC compilation. This document does not claim a compiled HEF, authentic
accuracy, qualified score outcome or E1/P1/I1. The fixed score reader stays
Charlie’s default. No game, controller, camera or model activation is authorized.

## Goal

Use the 57 inventoried September–October preserved Robotron recording
candidates as sources for *full original camera frames* of the extended score
HUD. Not all 57 are actual complete games, and not every retained image contains
the original HUD. The sampler explicitly rejects playfield-only crops, missing
source evidence, bad geometry and unavailable pixels.

Charlie proposes a visible **whole score string** (or abstains). The human
reviewer confirms/corrects/marks unreadable. No digit boxes are required.
Human review is the only source of supervised truth. A game ending at a time
limit can still supply visible score training frames; it cannot become a
certified final-score game merely by receiving a label.

The trained checkpoint and ONNX are **intermediate outputs**. The explicit
target deliverable is a genuine Hailo-8L `score.hef`, produced by licensed
DFC 3.33.0 on a supported Linux x86-64 compiler host and verified against
saved original frame evidence. No fake HEF or renamed ONNX is permitted.

## 1. Prepare an isolated Pi checkout and training notebook

Do not install PR #8 over the current Pi operational checkout. Review the
current branch/PR changes, including the local unpushed serialization fix and
PRs #5/#6/#7, before a later integration. Use a separate worktree or checkout.

The original audit inventory is expected at

```text
/home/five/charlie-e1-probe/audit/2026-10-18-ala2/canonical-game-manifest.json
```

and the previous real review notebook is

```text
/home/five/.local/share/charlie/score-review/learning-evidence.sqlite3
```

Verify both paths and their bytes on Charlie; the preserved SSD and original SD
image are not interchangeable proof of original-media completeness. Run from
the independently staged PR #8 repository checkout:

```bash
mkdir -p /home/five/score-neural-work
python -m experiments.ppal.neural_score.sample \
  --inventory /home/five/charlie-e1-probe/audit/2026-10-18-ala2/canonical-game-manifest.json \
  --calibration config/robotron/playfield-latest.json \
  --prior-review-journal /home/five/.local/share/charlie/score-review/learning-evidence.sqlite3 \
  --output /home/five/score-neural-work/selection-001.json \
  --limit 300 --per-game 18 \
  --queue-to-working-journal /home/five/score-neural-work/review-copy/working.sqlite3
```

The new `selection-001.json` is immutable. It records each selected file's
SHA-256, recording identity, exact original score-log line or camera-journal
record, source clock, nontruthful fixed-reader proposal (if present), geometry
and train/validation/final partition. It is safe to run without
`--queue-to-working-journal` for a read-only selection preview.

Source selection:
- `score-raw-*.png` with authentic gameplay `score.jsonl` source time
- otherwise original `observations/camera-*.png` with hash/time bound to a
  preserved `session-evidence.sqlite3` record
- never arbitrary `raw-*.png` normalized playfield, a generated/derived
  screenshot, or an invented timestamp

Duplicates, missing images, untrustworthy geometry, prior-consulted games
and unavailable SQLite snapshots appear in the exclusions ledger. Prior
score-review sources are excluded rather than secretly turned into new
independent final examples. An active journal with WAL/SHM must be quiesced
or snapshotted atomically; the sampler will not read an unsafe bare DB.

The split is deterministic by stable game/marathon identity, not individual
frames or human score. All games in the same marathon use one partition.
Never reassign a reserved final session to training. For later batches pass
**all prior** frozen `--prior-manifest` and repeat
`--prior-review-journal` for the old and newly labeled journals. Do not
select on knowledge of held-out labels.

### Continue labeling in additional frozen batches

The first October 18 pilot selected 25 original images out of 1,507
screened, source-linked candidates. Additional rounds may use *new* images
from recording groups already included in a prior sampler manifest, but
only under that group's original committed train/validation/final role.
Previous-image SHA-256s are excluded. Historically reviewed sessions without
a frozen split remain ineligible for fresh independent holdout selection.
Passing the frozen manifest and **both** previous score-review sources is
necessary for this safeguard.

After reviewing the previous batch, stop the review server (`Ctrl+C`) and
run from the isolated checkout:

```bash
python -m experiments.ppal.neural_score.sample \\
  --inventory ~/charlie-e1-probe/audit/2026-10-18-ala2/canonical-game-manifest.json \\
  --calibration ~/Projects/charlie/config/robotron/playfield-latest.json \\
  --prior-review-journal ~/.local/share/charlie/score-review/learning-evidence.sqlite3 \\
  --prior-review-journal ~/charlie-score-sampling/review-copy/working.sqlite3 \\
  --prior-manifest ~/charlie-score-sampling/pilot-002.json \\
  --output ~/charlie-score-sampling/pilot-003.json \\
  --limit 75 --per-game 12 \\
  --queue-to-working-journal ~/charlie-score-sampling/review-copy/working.sqlite3
```

This keeps the original 25 reviews and appends only newly chosen,
hash-verified review requests. Do not overwrite `pilot-002.json`, delete the
working journal or move samples between roles. For `pilot-004`, include
both earlier manifests with repeated `--prior-manifest`; continue to pass
the prior review journals. Restart the existing browser server against
the **same** working review database.

There is no fixed count of labeled frames that guarantees accurate
whole-string recognition. A working plan is a **100–200 readable-score
prototype** to inspect network failure modes; **300–500 genuinely different
human-reviewed frames** for a serious training trial; and **500–1,000+
varied train/validation/test examples** if coverage and accuracy remain
poor, with the bulk reserved for training. Avoid adjacent near-duplicate
frames and repeated identical scores. Track digit coverage, lengths,
all-zero displays, camera calibration, blur/lighting, P1/P2 identity,
and independent recording-session splits. Model usefulness must be
established by unseen-game exact-string accuracy, coverage/abstention,
high-confidence false reads and eventual CPU/Hailo device parity, not
by meeting any sample-count target alone.

## 2. Label in the existing score-review interface

From the same checkout on Charlie:

```bash
python -m experiments.ppal.inspect_robotron_score \
  --serve-review \
  --review-journal /home/five/score-neural-work/review-copy/working.sqlite3 \
  --review-port 8769
```

The server listens only on Charlie's `127.0.0.1:8769`, not the LAN.
To review in Linux Mint, open a separate Mint terminal:

```bash
ssh -L 8769:127.0.0.1:8769 five@charlie.local
```

Then browse `http://127.0.0.1:8769` on Mint. The same existing interface
shows entries as **Training review sample**, their original photograph,
proposed score if available, zoom and Confirm / Correct / Unreadable. Your
review does not need a complete-game terminal decision. Read what is visibly
on the screen: correct the complete score number, not just a single digit.
Mark clipped/dim/ambiguous digits unreadable; do not fill in guesses. Attest
independent visual review only when the score really was read from the image,
not copied from Charlie's prediction.

The original image, original score-log/camera source, prior predictions,
immutable human review IDs and validation/final partition are retained.
Human review records are written only into the isolated working notebook.

**Mid-game screenshot labeling recovery.** Do not use `Not a final-score
image` as a substitute for a readable-score label. The first Oct 18
25-frame pilot contained 17 original reviews marked `insufficient` because
the operator thought the photo needed to be from the end of a game. The old
UI silently ignored numbers typed before that button was clicked, so no
authentic digit transcription for those 17 was persisted. Never
reconstruct those lost digits from the proposed numeric score, an
empty input, or a guessed `00`.

The updated **score-sample** interface hides the irrelevant final-score
exclusion and confirmation shortcuts. It requires typing the **exact visible
digit string** (including `00` when two zero glyphs actually appear) and
choosing `Save visible score`, or marking the photograph Unreadable.
Legacy samples can be revisited using **Needs visible-score label (legacy
reviews)** in the filter dropdown. The form defaults those samples to
`Not a verified final score`. The earlier `insufficient` event is
preserved in append-only review history; a genuine new correction changes
the effective current status and stores both the numeric score and the
exact visible string. We do not create artificial score evidence for
screenshots the reviewer cannot read.

A numeric score of zero does **not** establish that the visible display
contains `0` instead of `00`. The updated CTC corpus/decoder permits
exactly human-verified all-zero visual sequences; arbitrary mixed
leading-zero strings continue to abstain. Earlier numeric-only zero
reviews without explicit visible-width verification remain excluded
rather than becoming invented visual targets. This is a recognition
labeling correction, not independent complete-game qualification.

To recover the existing pilot, stop the local review server with Ctrl-C,
`git pull --ff-only` inside the isolated
`~/charlie-score-sampler` checkout, restart the same score review
server against the **same**
`~/charlie-score-sampling/review-copy/working.sqlite3`, refresh the
browser, choose the **Needs visible-score label** filter and re-read the
17 original photographs. No re-sampling or review-database reset is
needed. Afterward inspect `reviewed_labels()` per partition and
preserve the original train/validation/final assignments.

**Checkbox removal and October 18 pilot recovery.** The updated browser
interface treats submitting Confirm, Save correction, or Unreadable while the
verified primary photograph is displayed as the operator's attestation that
they actually read it. There is no extra checkbox. This attests to a
photograph-based human score judgment; it is not a complete-game certificate,
a second independent reviewer, or automatic model accuracy acceptance.

If you labeled the existing `pilot-002.json` batch using the older version
without checking the redundant photo-reading box, do **not** re-enter your
scores. The original annotations are immutable and remain saved. Stop the
review server (`Ctrl+C`) before updating the checkout and processing the
retrospective confirmation. Then, from the updated PR #8 checkout:

```bash
~/Projects/charlie/.venv/bin/python -m experiments.ppal.neural_score.attest_reviews \\
  --journal ~/charlie-score-sampling/review-copy/working.sqlite3 \\
  --manifest ~/charlie-score-sampling/pilot-002.json
```

This first command is a **read-only preview**; inspect its number of
unattested completed labels, split counts and reviewer name(s). Then only
after confirming that these were **your** original photo reviews, append
a separately dated attestation for the identified frozen batch:

```bash
~/Projects/charlie/.venv/bin/python -m experiments.ppal.neural_score.attest_reviews \\
  --journal ~/charlie-score-sampling/review-copy/working.sqlite3 \\
  --manifest ~/charlie-score-sampling/pilot-002.json \\
  --attest-photo-reading
```

If multiple different reviewers are present in the batch, the write
command refuses a blanket attestation and requires
`--reviewer "exact name entered in the form"`. The write is idempotent,
checks every original photograph SHA and source identity, retains the
original unchecked-box state and timestamp, and appends one new
`score_photo_read_attestation` linked to each eligible existing
annotation. It never modifies the original Pi score-review notebook,
original photographs, prior reviewed digits, game identities or frozen
training/validation/final partitions. Unreadable submissions remain
unreadable and are **not** valid digit labels.

## 3. Transfer a labeled corpus to Mint

No Torch, ONNX training or Hailo DFC is needed for the Pi labeling stage.
After a first batch of reviews:

```bash
python -m experiments.ppal.neural_score.export_reviews \
  --journal /home/five/score-neural-work/review-copy/working.sqlite3 \
  --output /home/five/score-neural-work/portable-001
```

This exports a SQLite **read-only backup** (including committed WAL), only
original human-reviewed photos, an `image-locations.json` relocation map,
and hashes. Transfer the whole `portable-001` directory to Mint using your
existing SSH/SFTP link. This does not rewrite the original Pi review store.

On Mint, in an independent PR #8/score-ML environment with its declared
dependencies and the exact matching calibration file:

```bash
python -m experiments.ppal.neural_score.corpus \
  --journal /path/on/mint/portable-001/learning-evidence.sqlite3 \
  --calibration /path/on/mint/playfield-latest.json \
  --partition all \
  --output /path/on/mint/score-corpus-001
```

The new immutable corpus contains only independently attested,
hash-verified, current, unambiguous whole-string labels. Each score crop
is 256×32 RGB with the fixed network preprocessing. Training, validation
and final test roles remain separate and source/game leakage is rejected.
`review-exclusions.json` names every withheld, unreadable, disputed,
missing/invalid or otherwise ineligible record. The historical eight review
annotations are leads, **not** automatically eight eligible new labels.

Prior manifests and prior Vision Lab/score consultation commitments still
need review before asserting independent final evaluation.

## 4. TRAIN TO HEF, not just ONNX

On the supported x86-64 Linux **compiler host**, install the declared
score-ML packages from `requirements-neural-score.txt` and obtain licensed
Hailo DFC **3.33.0** with compatible HailoRT **4.23.0**. DFC availability
must be verified locally; it is not bundled into this repository and cannot
compile natively on Charlie's Raspberry Pi.

Check before starting a long training run:

```bash
python tools/train_score_to_hef.py \
  --manifest /path/on/mint/score-corpus-001/manifest.json \
  --output /path/on/mint/score-release-001 \
  --preflight
```

If and only if this confirms DFC support and eligible training data:

```bash
python tools/train_score_to_hef.py \
  --manifest /path/on/mint/score-corpus-001/manifest.json \
  --output /path/on/mint/score-release-001 \
  --steps 1850 --train-seconds 7200
```

This runs PR #8's genuine Torch optimizer, saves
`model/score.pt`, exports and checks `model/score.onnx`, and calls
the actual DFC Hailo-8L compiler. On successful compilation it produces

```text
score-release-001/hef/score.hef
score-release-001/hef/hef.json
score-release-001/hef/parsed.har
score-release-001/hef/quantized.har
score-release-001/state.json
```

with exact model/data/HEF SHA-256 provenance and bounded logs. Compilation
uses **training-only** crops for optimization/calibration, never validation
or final test. If the compiler is absent, fails graph parsing, or cannot
produce a nonempty HEF, this workflow fails visibly; **HEF remains blocked**.
The old synthetic checkpoint can be compiled only with explicit
`--engineering-feasibility`, and such an HEF is not qualified Robotron
recognition or deployable learning.

The existing final-test evaluation remains a separate, one-use, immutable
consultation after checkpoint selection. Do not train/tune on held-out
scores or repeat the final test to select variants.

## 5. Qualify the compiled HEF before activation

On Charlie's Pi with a **separate read-only saved-frame qualification scope**
and verified HailoRT runtime, use PR #8's `hailo-required` replay against
the matching CPU ONNX model. Capture actual logit drift, digit/whole-string
agreement, abstentions, false high-confidence numbers, P1/P2 swaps and
latency/CPU/memory/thermal measurements. Joint sprite-and-score scheduling
must use a shared admission owner before live integration; PR #6 does
not yet use PR #8's score admission object.

An actual `.hef` file establishes compilation, **not** acceptable score
recognition, a corrected October 11 1100-versus-2200 result, a complete-game
score gain or E1/P1/I1. The fixed score reader remains the default and
rollback. Do not install, activate gameplay/servos or move the model into
the operational process without the existing separate authorization gates.

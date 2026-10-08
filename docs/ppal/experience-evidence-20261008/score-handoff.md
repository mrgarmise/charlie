# Original score review and guarded consecutive-game handoff

Continues 05e1643595098ef25363c1f96942628031302002. All newly executed tests are x86_64 Python 3.12.14 software fixtures. Original October 4 pixels are replayed for review only; no new game or human confirmation is inferred. No physical or native performance acceptance.

## Existing score reader and human workflow

ScoreObserver retains its existing HUD reader and observational score tracker. Its observations/final view now also bind the exact camera observation ID. Required regular originals remain recorder-owned; score-change selection is explicitly best-effort additional instrumentation. Instrumentation buffer/queue bytes are disclosed, and an unfinished score worker prevents sealing or next-game readiness. No score worker chooses actions or becomes a score authority.

The existing `python -m experiments.ppal.inspect_robotron_score` supports immutable proposals and confirm/correct/unreadable review in EvidenceJournal. The journal must be a separate derived review destination, never the sealed source journal. A proposal stores the original file/hash/time/clock, proposed digits/confidence, calibration and reader revision, original source identity, source session and evidence partition. Exact-source journal binding is supported when original records have been merged. Otherwise operator-supplied historical metadata remains unqualified. Original images must decode as images. No proposal/annotation rewrites an original score log.

Example procedure on archived evidence (no camera/controllers):

```
python -m experiments.ppal.inspect_robotron_score ORIGINAL.png --calibration ORIGINAL_CALIBRATION.json --output REVIEW_DIRECTORY --review-journal DERIVED_REVIEW.sqlite3 --source-episode ORIGINAL_SOURCE_ID --source-session ORIGINAL_SESSION_ID --timestamp ORIGINAL_TIMESTAMP --partition diagnostic
python -m experiments.ppal.inspect_robotron_score --review-journal DERIVED_REVIEW.sqlite3 --review-proposal PROPOSAL_ID --annotator REVIEWER_ID --verdict correct --correct-score DIGITS --reason 'Visible digits and context' --independent-review
python -m experiments.ppal.inspect_robotron_score --review-journal DERIVED_REVIEW.sqlite3 --review-proposal PROPOSAL_ID --annotator REVIEWER_ID --verdict unreadable --reason 'Blur/occlusion prevents exact digits' --independent-review
python -m experiments.ppal.inspect_robotron_score --review-journal DERIVED_REVIEW.sqlite3 --review-metrics --partition final
```

Open the generated score-review.html: original screenshot and derived rectified HUD appear together with proposed digits/context and immutable proposal ID. Choose confirm, correct, or unreadable; confirmation cannot fabricate digits for an abstaining proposal. Each reviewer records identity, wall time, rationale and independence attestation. Independent reviewers can disagree; the disagreement is preserved, not silently adjudicated.

Reader metrics are descriptive on independently attested annotations, with exact-score accuracy, Wilson 95% interval, false >=.99-confidence acceptance count, abstention/coverage, confidence calibration bins, unreadable/disputed counts and duplicate-pixel deduplication. Synthetic proposals are excluded. A single source game/session or identical original cannot cross training/validation/final partitions. Conflicting predictions of duplicate originals do not inflate accuracy. Final images must remain untouched until frozen reader testing; inspected diagnostic images cannot silently become final holdout. A 50/50 controlled batch cannot establish >=99% accuracy. These metrics do not establish independence of adjacent images or qualify a reader by themselves.

The existing complete-game comparison validator now accepts an optional `human_annotation_id` on its independently authored official_score_measurement certificate and validates it against the original hash/time/episode/value. Unreadable, synthetic, non-independent, altered-image or conflicting reviews fail. Human review alone is never that certificate. Existing independent start + persistent terminal originals, exact final score on a terminal capture, capture identity, preregistered slot/policy/conditions, independent qualification proof, frozen baseline and rollback still apply. Missing critical score/boundary originals prevent qualification. No certificate or verified score was authored by this Work execution.

## Authentic review preview

score-review-original-provenance.json records original report/log/pixel hashes and calibration provenance for `play-20261004-205356/score-raw-0015.png`, native timestamp 1000.717239, source revision bb40d02... with reported dirty tree. score-review-example/score-review.html embeds those exact original PNG bytes plus a derived HUD crop. The current existing reader proposes 0 with confidence 1.0 on that early image; this is NOT a final-game SCORE, newly independent ground truth, or user confirmation. This image is diagnostic/previously inspected, not a held-out final test. No human label has been invented. Authentic complete-game qualification and a properly segregated ~50+ image annotation dataset remain evidence dependencies.

## Between-game barrier and completion

Normal and developmental marathon share the existing developmental_marathon entry. After child completion it now records recording_readiness before a further attempt. Readiness requires terminated prior writer, no recording error, finished score worker, exact verified writer receipt with all selected originals and incident requests resolved, and an unchanged sealed capture manifest. Open/incomplete/missing/corrupt receipts fail closed. Healthy receipt alone does not authorize another START: existing verified episode-boundary and independent physical authorization gates remain. Pure historical boundary inspection retains its old predicate, but new buffered reports require source-root verification. All source files are fsynced after writers finish and before publishing the durable seal; hashing reads are not claimed equivalent to storage synchronization.

Focused results: 36 score/review/comparison/startup/marathon/normal sampled-player cases passed in 5.95s; 29 finalization/recorder/review/normal-player checks passed in 6.95s after adding score-source IDs and syncing source bytes. Tests cover correction/abstention/disagreement, original mutation, partition/dedup safeguards, small-sample uncertainty, human certificate link and disagreement rejection, distinct consecutive recorder receipts, incomplete/live/failed score handoff, and no controller construction for receipt tests. Guarded shell syntax and diff checks passed. Full integrated suite is running; prior host watchdog baseline failures remain preserved. No native suite pass claimed.

## Native handoff (pending reachable Pi)

Existing tools/accept_episode_identity_pi.sh adds sampled/incident/reconciliation/review/handoff regressions to its unarmed persistent-notebook acceptance. Preserve the original notebook/captures and all earlier failure reports. Use the exact published SHA according to the existing script usage; it does not create a controller. For separately authorized camera-only measurements using existing CameraLease/preview ownership:

```
python tools/benchmark_buffered_recording.py --native-camera --samples 120 --hz 30 --visual-hz 5 --output /tmp/UNUSED-native-sampled.json
python tools/benchmark_buffered_recording.py --native-camera --samples 120 --hz 30 --visual-hz 5 --rolling-seconds 1 --incident-every 30 --output /tmp/ANOTHER-UNUSED-native-incidents.json
```

No new bridge or hardware deployment is part of this mission. x86 native guard rejects before opening a camera. Benchmark tactical states are simulations even with real camera pixels. Report actual camera rate, PPAL-fixture foreground/decision latency, encoded bytes, CPU/core counters, RSS, writer latency, queue/rolling peaks, explicit optional shortfalls/critical pauses and interrupted receipts. Queue growth is approximately max(0,incoming retained frames/sec - durable service frames/sec) times seconds, but record/fsync demand and byte budgets must also be measured. Do not enlarge RAM to conceal sustained overload. Pi thermal/power/storage/vision responsiveness and real complete-game score acceptance remain pending; no speedup is asserted from unmeasured Pi conditions.

ALA-2 stays open until statistically supported improvement in mean independently verified complete-game Robotron SCORE, on separate games and frozen baseline/candidate conditions with rollback.

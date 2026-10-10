# Deferred Robotron score review

Parent verified before implementation: `177b0b2d52c198d24e403da3142df755c48877fc`.
This extends ScoreObserver, the existing marathon diary and score inspector. No
physical gameplay, motion, firmware or policy activation is authorized or performed.
ALA-2 remains open; no score improvement is claimed.

Milestone A records every marathon child attempt before execution and appends its
outcome afterward. Missing reports/images and interrupted children remain durable
records. Selected score photographs retain source timestamp, camera observation ID,
source-log hash and original PNG hash. The original prediction is immutable.
Photographs observed in a reported terminal sequence are distinguished from other
score photographs; reported boundaries are not independent game qualification.

Offline validation:
`python -m pytest -q tests/test_score_review_queue.py tests/test_marathon_deferred.py tests/test_marathon_robotron.py tests/test_score_human_review.py tests/test_score_observer.py`.
The 30-game fixture collects 30 attempts and 29 proposals without human review;
the missing photograph remains a record. Fixtures are not physical games. Test
transcripts and JUnit are retained alongside this report. Native Pi validation
and real unattended-marathon acceptance remain outstanding.

Milestone B extends the same inspector with loopback batch review:
`python -m experiments.ppal.inspect_robotron_score --review-journal /path/to/existing/learning-evidence.sqlite3 --queue-root /authorized/robotron-runs --serve-review`
Open `http://127.0.0.1:8769` locally (remote Pi access requires an operator SSH tunnel).
It supplies originals, zoom, prefilled corrections, six verdicts, queue filters,
keyboard navigation and durable immutable reviews. Reviewer independence is an
explicit attestation, not a complete-game certificate. Corrections supersede only
that reviewer's earlier annotation; other reviewers' disagreements remain visible.
Direct HTTP and journal tests: 28 passed in 1.96s, including a 30-attempt queue,
original image bytes, authenticated correction, denied tokenless write, and durable
review after server termination. Exact test names are in milestone-b.xml. Browser
visual validation is unavailable: Chromium installation failed with an invalid ZIP
from the download endpoint. No browser-rendered usability result is claimed.

Milestone C: normal DevelopmentLifecycle.acquire imports existing session and
marathon diaries into its existing notebook and reconciles immutable human reviews
through MemoryEvaluator. Restart imports are idempotent. Observations supply no
selected project, priority, physical authorization or replacement reader.
MemoryEvaluator.evaluate_score_reader accepts an existing Reflection/ModelFoundry
candidate with explicit training consultation, compares immutable original baseline
predictions with reviewer labels, rejects source/session/image overlap, mixed
baselines, changed images, invalid digits and nonfinite confidence, and records
coverage, accuracy, high-confidence errors and timing. Evaluation is bounded to
256 originals. Synthetic reviews require an explicit fixture mode and remain
labeled. Diagnostic/validation results cannot grant deployment; sealed final
reader evaluation needs an independent protocol and is rejected by this adapter.
Complete-game certificate validation rejects superseded annotations and unresolved
review statuses. Legacy content aliases do not create extra queue games.
32 tests passed in 3.79s (milestone-c.xml), including normal acquisition/restart and
candidate interface fixtures. There are no new authentic independent reviews,
Charlie-originated score-reader candidates or native Pi results in this environment.

Milestone D: the same inspector exposes policy-separated qualified history and
rolling 10/30 batches with variability, standard error, exact contributing records
and descriptive uncertainty. Every measurement passes the existing independent
complete-game certificate validator. Duplicate or conflicting capture aliases,
unqualified scores, noninteger values and mixed-condition rolling batches are
excluded. Evidence order is journal order; clocks from different sessions are not
silently treated as globally synchronized capture chronology.
Freeze a reproducible collection with:
`python -m experiments.ppal.inspect_robotron_score --review-journal /existing/notebook/learning-evidence.sqlite3 --freeze-baseline NAME --baseline-policy EXACT_POLICY --baseline-count 10`.
This freezes the last 10 currently qualified records for that policy. The named
snapshot cannot be replaced; policy and conditions must agree. Invalidated proofs
change current eligibility without deleting the immutable baseline.
23 tests passed in 0.72s (milestone-d.xml). The 30 certified-game test uses explicitly
controlled qualification-interface fixtures, not real games. No genuine qualified
30-game baseline, rolling trend, score-reader gain or Robotron score gain is claimed.

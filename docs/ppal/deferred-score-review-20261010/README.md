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

Final integration corrections: the first broad run found 17 failures (retained in
full-before-finalization-fix.xml): a removed local digest import in perception
reconciliation, a forbidden direct gameplay journal import, and post-completion
journal writes invalidating camera-writer receipts. These are repaired without
weakening the recording gate. Standalone gameplay now stores pending review
metadata and the exact final-observation image hash in its existing report;
marathon/acquisition deliver queue records into their existing journal. The sealed
camera diary is never amended after its writer completion receipt.
54 integration tests passed in 81.21s, including mocked normal gameplay/controller
release, original writer completion, startup failure and perception reconciliation.
These are offline hardware doubles, not armed physical gameplay. 19 feedback tests
passed in 0.97s. Diagnostic/training reviews now enter existing Reflection context
and recurring-question interfaces; validation/final labels are not passed to the
generator. These contexts do not create a human-selected candidate or priority.
Reviews commit annotation/status atomically, retain superseded history, and reject
sealed source-diary writes. Hash-matching recorded aliases remain reviewable after
path relocation. The historical-pixel test preserves
`003511-review-000-0-gameplay.jpg`, SHA-256
`bf52abb6f741e8d3e042cf1944adadc6ed7450eb7104e8b2fc068d04741c6c32`.
Its synthetic review metadata explicitly has no authentic source clock or score
label; it contributes zero qualified reader examples and zero complete games.

Further bounded acceptance: supporting originals are available through the same
inspector, with preserved hashes and timestamps. Reviewing another image does not
silently relabel the primary photograph; numeric controls are disabled until the
primary is selected. A newly selected primary image invalidates the prior queue
status while retaining its old annotation. A corrupt diary produces a durable
source deficiency and does not block available diaries; identical retry is
idempotent. The existing capability registry exposes offline reader evaluation
under explicit method/resource authorization and excludes fixture admission.
Rejected evaluations are journaled before raising the validation error. An empty
eligible batch returns an explicit unsatisfied evidence requirement.
The real UI JavaScript passes batch/navigation/correction/filter/zoom checks with
a DOM double (frontend.xml); this is not browser-rendered visual validation.
The repaired broad suite passed 763 tests with 21 skips in 202.19s
(full-after-finalization-fix.xml). Final incremental source/capability tests are in
queue-final.xml and negative-source.xml. The final full-suite rerun and exact
source SHA-256 manifest are published separately when complete.

Final regression: **767 passed, 21 skipped, zero failures/errors in 196.94s**.
Command (Node runtime explicitly enabled for the JavaScript DOM-double test):
`CODEX_PRIMARY_RUNTIME_NODE=/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node /workspace/scratch/a5d7375d8e4e/test-env/bin/python -m pytest -q tests --junitxml=docs/ppal/deferred-score-review-20261010/full-suite.xml`.
Implementation bytes match published `49ad061d34a58506580b0baadceb08917a17282a`;
all eleven equality checks and source/test SHA-256 values are in environment.json.
The final commit adds reports and updates the old fixed-eight registry assertion
to require the new reader adapter and unique capability identifiers. The earlier
one-failure broad run is retained in full-before-registry-expectation-fix.xml.
Root-wide collection also encountered platform-specific hardware modules;
root-collection-failure.xml preserves that failed command. The bounded supported
`tests` suite, rather than hardware utility scripts outside it, is the passing run.

Authentic normal-Executive persistence (host only): copied the previously preserved
October 4 notebook continuation into a separate working notebook. Its 507 original
records are intact, and the source inventory is byte-for-byte unchanged. Normal
application operation produced seven existing-artifact location receipts, eleven
unsatisfied acquisition search results, eleven consolidated references, eleven
Executive result receipts and one durable waiting decision: 548 total records.
A further restart from a clean checkout of published 49ad061 adds zero records.
No script selects a question, hypothesis, candidate or learning conclusion.
First command was executed in the verified source worktree (local parent 177b0b2,
dirty, implementation bytes equal published 49ad061); subsequent restart commands
executed in a clean checkout of 49ad061:
`python main.py --offline --learning-state /workspace/scratch/a5d7375d8e4e/score-authentic-continuation --episode-root /workspace/scratch/a5d7375d8e4e/authentic-original --learning-turns 3 --learning-budget 2 --learning-interval 0.05`.
Exact retained requests, work IDs, next requirements and restart assertions are in
authentic-continuity.json; immutable added records and pre-restart IDs are in
authentic-before-final-restart.json. There is no fresh independent experience.
This older notebook is not the 1,406-record native Pi notebook, which remains
inaccessible here. Its missing original capture/trajectory measurements were not
replaced by fixture images, simulated trajectories or reviewer labels.

Remaining authentic gates: independently measured persistent object identities
and board trajectories, at least one validation and three unconsulted final
experience groups with compatible 150ms +/-25ms horizons, native candidate-specific
cadence/ownership/recovery/rollback qualification, synchronized independently
qualified start/terminal/HUD evidence, and a separate sealed final reader protocol.
There is no generated and independently qualified authentic score-reader candidate
or complete-game score improvement. Physical comparison, gameplay and policy
activation remain unauthorized. Tracker implementation/offline validation is
published; native unattended marathon, rendered-browser usability and ALA-2
learning acceptance remain open.

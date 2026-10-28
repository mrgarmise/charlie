# Guarded perception learning

This draft implements reusable workflow contracts and a first Robotron adapter.
It does **not** establish that Charlie can train his own useful models. A complete
Executive-originated authentic training/qualification cycle remains blocked by
labels and independent sessions. No candidate or new perception has been activated.

The existing LearningExecutive selects the investigation in its portfolio.
EvidenceJournal retains needs, original-frame hashes, attributed labels, frozen
session splits, proposals, candidates, independent evaluations and decisions.
Existing MemoryGateway receives the diagnostic outcome. Existing
CapabilityDeployment owns the versioned `perception-shadow` pointer. There is
no competing Executive, camera owner, notebook scheduler or actuator route.

`learning/model_learning/contracts.py` defines LearningNeed, DatasetCandidate,
TrainingProposal, ModelCandidate and QualificationDecision. Data, worker,
evaluation, qualification, human and subscriber adapters are separate modules.
Robotron vocabulary, calibration and incumbent screen logic live in the domain
adapter. Additional tasks must register their own vocabulary, preprocessing and
measurement adapter; task IDs do not automatically make another task supported.

## Inspect and label

Use a separate local state directory for acceptance. These commands do not open
cameras or initialize physical capabilities. `STATE` must be the same directory
as normal `main.py --learning-state`; stop its worker before CLI writes. The CLI
honors the existing `offline.lock` and never edits original evidence.

```bash
python -m learning.model_learning --state /tmp/charlie-model-review import-fixtures
python -m learning.model_learning --state /tmp/charlie-model-review status
python -m learning.model_learning --state /tmp/charlie-model-review baseline
```

The first command retains six repository photographs from three capture sessions:
five fallibly annotated regression fixtures from two sessions, plus one original
unknown startup failure from a third session. No random image split is assigned.
The unknown startup frame has **no reviewed semantic label**. A filename or
incumbent UNKNOWN does not certify title/menu or OOD ground truth.

Status lists observation IDs and local retained image paths. Inspect a frame
locally, then record an attributed review (replace placeholders with actual IDs):

```bash
python -m learning.model_learning --state /tmp/charlie-model-review label OBSERVATION_ID unknown --reviewer alex --reason 'Reviewed historical frame; screen state remains ambiguous'
python -m learning.model_learning --state /tmp/charlie-model-review partition CAPTURE_SESSION train --reviewer alex
```

For corrections add `--supersedes PRIOR_LABEL_ID`. Original reviews remain
immutable. Label answers remain fallible evidence. Train/validation/test must
use different physical capture sessions; dHash near-duplicates across partitions
and re-encoded identical pixels are rejected. A frozen session cannot be moved
between partitions. New sessions can be added; excluded old observations remain
in the lineage. A consulted final holdout cannot qualify another candidate.

Additional authentic evidence can be retained through `ingest MANIFEST.json`.
The manifest is a local JSON list (at most 256 rows) with `path`, `session`,
`provenance`, Boolean `authentic`, optional `partition`, and optional normalized
four-corner `calibration`. Authenticity declarations must be backed by original
capture records/hashes; the software cannot prove a human declaration true.
Do not mark synthetic data authentic. Each frozen partition needs all three
known classes; test also needs reviewed unknown/OOD examples. Default independent
qualification requires at least five heldout examples per class, with independent
capture-session coverage reviewed by the operator. One small session is not
statistical confidence or generalization certification.

## Charlie's path to a request

```bash
python main.py --offline --model-learning \
  --learning-state /tmp/charlie-model-review \
  --learning-turns 1 --learning-budget 10 --learning-wall-seconds 60
```

The ordinary application's existing Executive examines persisted observations.
Unknown incumbent predictions, disagreements with attributed labels, or registered
shadow abstentions constitute evidence-backed gaps. Reflection proposes a typed
project; existing portfolio selection compares available alternatives. Active
higher-priority projects, primary gameplay ownership, resource/thermal readiness
and held budgets can defer it. A human training goal alone does not manufacture
a measured gap. `--model-learning` is opt-in and defaults off.

A selected investigation returns NEEDS_LABELS with a durable asynchronous review
request if data are insufficient. Otherwise it freezes the exact dataset and
commissions one fixed nearest-centroid CPU classifier. This deliberately simple
spatial RGB baseline must beat existing template/color/OpenCV logic and a
train-only majority baseline; no neural network is selected for appearance.

The fixed worker receives only training and validation rows, never final-test
rows/labels. It executes in a scratch subprocess with one CPU affinity, five CPU
seconds, 512 MiB virtual memory, a 16 MiB file limit, no core dumps, and a
configurable 0.1–60 second wall bound. Intake has a 256-frame/64 MiB retained
pixel budget and an 8 MiB per-image limit. The worker creates only fixed JSON
numeric artifacts, with no arbitrary algorithm/code/plugin execution. These are
trusted-code process/resource restrictions, **not an adversarial OS security
sandbox**. Model files never have movement, shooting or motor-gate authority.
Evaluation independently checks integrity and compares frozen heldout evidence,
with cooperative readiness/cancellation checks and its own same-length wall
budget. Evaluation plus training can consume twice the configured wall budget.

Completed training receipts/candidates/evaluations are reused after a crash;
training is not repeated to invent a new trial. An interrupted worker without a
completed receipt is durably deferred with its budget consumed. It requires a
new evidenced need/reviewed corpus rather than an uncontrolled retry. Unchanged
needs/data reuse the prior result. One reviewed corpus cannot produce an
unbounded sequence of models from repeated shadow abstentions.

`development-status.json` includes what is missing, needs, candidates,
qualification decisions, the shadow pointer and latest Executive result.
`model-learning/models/HASH/model-card.json` records candidate lineage, metrics,
limitations and disposition when a worker has completed. Confusion matrices,
precision/recall, false positives, abstention and host inference latency appear
in evaluations. Distances are explicitly uncalibrated, not probabilities.
Timed transition behavior remains unmeasured until authentic sequences exist.

## Human review, subscriptions and rollback

PR #14 provides the asynchronous HumanInteractionGateway and loopback UI.
When that module is available, the model service attaches its existing typed
`interpret_result` contract, queue budgets, freshness, expiry and immutable
answers. Otherwise durable requests remain `pending-adapter`; no voice question
or substitute web server is started. Labels enter a pending independent-review
inbox. They never automatically relabel frames or update a model.

A qualified candidate asks for `approve_shadow`, `reject` or `defer`. A reviewed
explicit asynchronous answer can produce a grant through
`ModelHumanGateway.review_approval(answer_id, reviewer=..., reason=...)`.
`CapabilityDeployment.activate_perception_shadow(service, grant.id)` rechecks
independent metrics, artifact identity and approval linkage, then atomically
moves only the shadow pointer. Rollback uses
`rollback_perception_shadow(service, operator=..., reason=...)`, restoring the
prior valid pointer or baseline and revoking the rolled-back grant. A revoked
grant cannot reactivate. No physical/gameplay activation adapter exists here.
Review/activation APIs are local trusted-operator APIs, not remote authorization.
The PR #14 browser can collect the answer; a separate operator review is required
before promotion. Neither a gateway answer nor qualification auto-activates.

PR #13 supplies registered scalar subscriptions. `RegisteredShadowPerception`
consumes capture-owner-published immutable evidence bookmarks, validates source
and generation, and publishes independent shadow observations. It never opens a
camera or consumes another subscriber's queue. A bad candidate abstains and the
incumbent remains available. Source capture/bookmark production must be attached
by the authoritative owner after integration; that live attachment is pending.
The base master lacks both PR #13's observation bus and PR #14's gateway. Exact
pinned source-file compatibility tests exercise these adapters without merging
or modifying those active PRs. Full combined-stack acceptance remains pending.

For explicit monitoring, inspect `model_shadow` records and evaluation failures;
a human may invoke the rollback API on drift/errors. Automatic monitoring-driven
promotion or rollback is not implemented. Shadow samples are bounded indirectly
by the owning capture/bookmark admission policy; do not attach an unbounded
high-rate durable recorder.

## Localization and retention

The separate `robotron-localization-v1` annotation format binds frame SHA,
session, normalized boxes, player/enemy/projectile/obstacle/unknown vocabulary,
uncertainty and session-local track identity. Whole-screen predictions never
provide coordinates. Existing PPAL sprite proposal/tracking and observation-only
Hailo paths should supply the baseline; zero verified object-box annotations
were admitted here, so no detector was trained or accuracy claimed. Pet error
review can reuse the workflow after registering its separate task adapter.

Retained pixels stay local; no automatic public upload is performed. Use a
private state directory and exclude private camera pixels from Git. Exclude a
retired observation with `DatasetStore.exclude(..., reviewer=..., reason=...)`
to remove it from future datasets while preserving its historical references.
Default retention is until explicit operator purge. Before deleting bytes,
archive the notebook and manifests and check candidate/rollback dependencies;
missing bytes fail integrity checks rather than fabricating successful replay.

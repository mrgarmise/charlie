# Charlie — Autonomous Visual Model Learning (Codex Implementation Mission)

## Purpose
Implement a **reusable, guarded, evidence-driven local model-learning capability** in `mrgarmise/charlie`, with Robotron visual perception as the first qualification use case. This is an implementation and validation mission, not another design-only report. **Codex is the developer and trainer of the initial baseline; Charlie's own existing Learning Executive is the long-term operator of the learning workflow.** Do not represent Codex as Charlie's brain, or claim Charlie has learned to train himself merely because Codex executed a training script.

## First: inspect the live project
1. Inspect the repository, current branches, open PRs, CI, existing architecture contracts, and actual deployed/hardware interfaces. In particular preserve unfinished PR #8 Hailo score reader, #10 pet following, #12 shared sensory contracts, #13 unified sensory/motion integration, and any newer human-question gateway work. Verify actual status; do not assume the referenced PRs remain open or unchanged.
2. Identify existing Robotron frame acquisition and authentic stored frame evidence, classifier/state detection, terminal recognition, scoring feedback, Executive/PPAL/ALA-2 candidate evaluation, model registry/inference services, Hailo execution, and safe deployment/rollback patterns. Reuse these; do not create competing frame owners, independent executives, or alternate actuator routes.
3. Establish a clean, scoped feature branch/PR from a safe base, coordinating conflicts and existing branches. Do not merge or overwrite active PRs. Document dependencies and any integration blockers.

## Architecture and ownership
Implement a shared `model_learning` (or suitably consistent existing-module) service with stable interfaces for:
- `LearningNeed`: which task is failing or uncertain, why new data/model might improve it, desired measurable outcome, bounded priority/budget, evidence lineage.
- `DatasetCandidate`: sourced authentic observations, labels and provenance, train/validation/test partitions, deduplication, quality checks, retention/privacy controls.
- `TrainingProposal`: task type, baseline, algorithm, resource budget, stop criteria, safety restrictions, model compatibility.
- `ModelCandidate`: immutable artifact, digest/version, label schema, preprocessing spec, inference runtime, metrics, training metadata, exact data split/version.
- `QualificationDecision`: independently measured performance, comparison with incumbent and non-ML baseline, failure cases, uncertainty/calibration, regressions, approval state.
- `Activation/Rollback`: governed atomic activation, monitoring, revert to previous known-good model, audit trail.

The Executive—not a hardcoded job scheduler—must be capable of discovering a genuine information/performance gap, selecting evidence acquisition or training as an action subject to readiness/priority/budget, considering results, and preserving learning outcomes. Do not claim unconstrained self-modification. Train in a sandbox/subprocess with strict limits; never give a trained model direct authority over movement, shooting, motor gates, or safety policy. A new model may offer predictions through existing registered perception subscriptions; normal action, safety, permission and deployment gates remain authoritative.

## Phase 1: Robotron task definition and authentic baseline
- Start with **screen-state classification**: title/menu, active gameplay, game-over/high-score (split as warranted by authentic evidence), and unknown/out-of-distribution. This is the simplest qualification of the training workflow, not the final goal.
- Evaluate existing template/color/OpenCV methods and existing screen-state logic as baselines. If suitable data already exists, produce a small CPU-compatible trained classifier (e.g. conventional features + linear model, or compact PyTorch/TFLite model). Choose the simplest measured method rather than neural for appearance's sake.
- Use **authentic frames only** for claimed Robotron accuracy. Synthetic data is allowed for plumbing tests but must be explicitly labeled; never contaminate authentic holdout evidence. Split by capture session/time (avoid near-duplicate leakage). If insufficient labeled data exists, build a bounded review/labeling queue and stop at `NEEDS_LABELS`, not fabricated success.
- Produce visible comparison reports: per-class precision/recall, confusion matrix, abstention/unknown handling, transition behavior, false positives, inference latency/resource use on tested hardware, and comparison against incumbent. Explicitly note if only host validation occurred.

## Phase 2: Charlie-controlled learning loop
- Connect existing Executive/PPAL/ALA-2 mechanisms so Charlie may **propose** new training based on durable evidence of errors, uncertainty, distribution drift or poor outcomes, not merely user commands or periodic retraining. Log why the Executive chose the proposal and what alternative actions it considered where supported.
- Collect/label/review evidence via current single-source sensory contracts; never open a rival capture process. Integrate pending asynchronous human question interface if available, otherwise design an adapter/queue contract without blocking this implementation. Ask humans only about meaningful unresolved labels; human feedback is attributed evidence, not unconditional ground truth.
- Execute candidate training within bounded CPU/RAM/disk/time budgets and configurable schedule; fail gracefully, cancel safely, and resume from records after restart. No uncontrolled loops or automatic bulk model proliferation.
- Evaluate held-out results independently. Default to **candidate-only** and shadow inference. Qualification/promotion must meet explicit user-configurable gates; if human approval is required, use the asynchronous human gateway, not voice. Record why a candidate was accepted, rejected, deferred, or rolled back. No unapproved autonomous deployment to active gameplay or movement controls.
- Keep a durable registry and model card for every candidate; lineage must trace from the need and original frames through labels, splits, training and evaluation to any promotion.

## Phase 3: beyond screen-state classification
- Specify and, where authentic annotated evidence permits, prototype **sprite/object localization**: player, enemy, projectiles, obstacles, motion/track identity and uncertainty. A whole-frame Teachable Machine-style classifier is **not** a detector and cannot be presented as yielding object coordinates.
- Prefer a simple detection/tracking baseline on authentic frames before selecting heavier vision models. Create data and annotation formats that can serve later object detectors, pet tracking, or additional tasks without conflating their separate label spaces.
- Keep Robotron-specific rules in a domain adapter; model learning and evaluation infrastructure should be reusable by Charlie's other capabilities, including pet-perception error review. Avoid coupling model training to controller logic.

## Phase 4: runtime/hardware discipline
- First qualify on host CPU using available data and tests; optionally run native Pi 5 inference/resource tests where accessible. Consider Hailo only after measured need and verified export/compile/parity; preserve PR #8 Hailo score-reader evidence and runtime compatibility. Never claim accelerator deployment from an ONNX export or simulated run.
- Do not actuate Xbox controller, RP2040 servos, or ELEGOO motors during software validation. Physical gameplay/movement tests require separately authorized, supervised native procedure and all existing safety gates.
- Make this useful from Charlie's normal application, not a standalone Codex notebook. Expose user-readable status: what he wants to learn, why, what data are missing, each candidate's measured result, and whether anything has been activated. The human may submit a suggested training goal, but Charlie's Executive should have its own path to propose one.

## Engineering requirements
- Add deterministic unit/integration tests for Executive initiation; data integrity, dedupe and leakage; missing labels; unknown/abstain; resource limits; persistence/restart; approval gating; versioned activation and rollback; subscriber continuity; no movement or authority escalation; candidate rejection; backwards compatibility with prior perception and scoring behavior.
- Independently test eligible code; report exact commands/results and CI statuses. Commit and push coherent increments to the feature branch. Keep PR draft until all eligible integration and independent checks pass. No claims of completed self-training, improved gameplay, or native performance without observed end-to-end evidence.
- Provide concise docs: architecture/ownership, CLI or UI for inspection, how a human labels a frame, how Charlie proposes training, training/qualification/rollback runbook, limitations, and exact Pi-connected and supervised acceptance steps.
- If external tools/dependencies cannot be installed, implement and validate all available pieces; identify exact blockers rather than silently substituting mock success.

## Acceptance gates
1. Existing application still works; no competing capture ownership or motor safety bypass.
2. Authentic Robotron frames form a reproducible dataset with held-out evaluation and visible baseline comparison; otherwise clearly report the missing evidence.
3. A real Executive-originated learning need triggers a persisted training proposal or correctly defers with rationale.
4. Candidate training/evaluation runs within limits; results are registered and can be rejected safely.
5. New inference stays in shadow mode until independently qualified and approved; rollback demonstrated in tests.
6. At least one end-to-end host-backed learning cycle is independently validated (using authentic frames for accuracy claims); physical/Hailo acceptance is separately identified if inaccessible.

## Final handoff
Report the branch, PR, commits, tests/CI, working features vs pending gates, exact authentic frame counts and dataset provenance, performance metrics without overclaiming, and the first steps for Charlie to request a new model himself. Do not declare success merely because Codex produced a Robotron model: the deliverable is **Charlie's guarded, reusable learning capability**.
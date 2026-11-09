# Charlie ALA-2 — Completion, Stabilization, and Handoff to Charlie UP

**Repository:** `mrgarmise/charlie`  
**Feature branch:** `feature/agency-first-self`  
**Mission:** Finish the existing ALA-2 project. Do not restart it, replace its architecture, or expand it into Charlie UP.

## Governing objective

ALA-2 remains **open** until a **Charlie-originated learning change** produces an **independently measured improvement in verified complete-game Robotron score** against a frozen, appropriately qualified baseline. Score is the primary outcome. Survival, rescues, tracking, predicted scores, replay counts, and tests are diagnostics, not substitutes.

Use Charlie's existing Learning Executive, Reflection/Meditation, evidence journal, MARM/MemoryGateway, independent Evaluator, PPAL chooser/planner, deployment gates, and normal application interfaces. Extend these rather than creating a second learning scheduler, game application, memory manager, or recovery agent.

**Scope boundary:** ALA-2 needs enough reliable recovery and integration to complete its own learning/evaluation loop. General always-on operation, boot-time service supervision, autonomous external research, universal failure recovery, and general-purpose self-directed experience commissioning are **Charlie UP**, not prerequisites for ALA-2 unless a specific defect directly blocks acceptance.

## 0. Recover and verify before changes

1. Inspect the **actual remote** `feature/agency-first-self` head, SHA, recent commits, open worktrees, application entry points, relevant tests, and existing issue/decision history. Do not assume any previously reported SHA is still the head. Identify newer published milestones and resume from them.
2. Inspect the Pi checkout and runtime state **only through available, authorized access**. Do not claim Pi validation from GitHub or simulated tests. If Pi access is unavailable, publish independently tested repository changes and provide precise, safe Pi validation instructions.
3. Preserve all original recordings, frames, journals, SQLite databases, experiments, meditations, manifests, historical identities, failures, and prior baseline results. Never clean/reset unrelated worktrees or overwrite originals. Use read-only inventories and hashes before any migrations.
4. Establish the current status of the previously interrupted marathon `robotron-runs/development-20261009-024021`: Game 1 had an operator-observed score of **1,100** and a confirmed GAME OVER transition; the between-game learning stage failed/interrupted. This is **not** automatically a qualified baseline or evidence of improvement. Previously observed database integrity checks were: experiment commitments **4**, original session **1,503**, retrospective replay **12,066**, processed episode journal **13,752** records. Reverify before using them; counts alone do not establish independent evidence.
5. Inspect the existing Learning Executive's persistent state and the two distinct temporal-estimation investigations. Preserve both investigation identities, source Reflection/meditation IDs, history, and dependencies; coordinate without silently merging or duplicating independent experience.

## 1. Finish marathon/reflection separation

Complete and independently test the existing Robotron developmental marathon so it can collect a **bounded series of complete games** without expensive between-game meditation or autonomous learning stalling subsequent games.

- Preserve the existing controller transport, real-camera observation, game-state/attract-mode handling, scoring and termination evidence, and normal gameplay interfaces.
- Between games, perform only essential evidence sealing, safe cleanup, and next-game preparation. Defer costly retrospective import, Reflection, Meditation, and autonomous learning until the marathon finishes or stops safely.
- Afterward, hand preserved experiences to the **existing Learning Executive** for normal offline processing. Do not introduce a parallel scheduler or processor.
- Ensure interruption, restart, and repeated processing are idempotent: never count a replay, duplicate archive, or re-import as an independent new game.
- Preserve game-over transitions, operator observations, score-reading uncertainty, incomplete games, and reasons for stopping. Do not infer complete games or verified scores from elapsed time, estimates, or terminal-looking frames alone.
- Do not let a processing timeout destroy collected gameplay or erase partial analysis.

## 2. Repair the current Executive blocker without weakening evidence safeguards

The Pi's latest supplied `development-status.json` reported:

- `phase: "stopped"`, `last_activity: "blocked"`, `turn_outcome: null`;
- `error: "ValueError: finite preserved prediction errors required"`;
- recorded temperature **58.4°C**, below the configured **75°C** limit;
- `physical_authorization: false`;
- temporal-estimation projects paused and other investigations retained.

The published branch's `learning/meditation.py`, in `consume(...)`, validates `quality['adjacent']['mean_error']` and `quality['gaps']['mean_error']`, rejecting nonnumeric, non-finite, or negative values. **This is a valid evidence safeguard. Do not delete, coerce, zero-fill, or silently normalize invalid measurements.**

Required work:

1. Reproduce and trace the failure with the exact original artifact, producer, version, timestamps, hash, historical use, and affected project. Distinguish a genuinely invalid source finding from schema incompatibility or a bug in the producing calculation.
2. Preserve the original artifact and record the validation failure as explicit inconclusive/rejected evidence with provenance and an actionable dependency.
3. Ensure one invalid meditation import cannot terminate unrelated eligible developmental work. Use the existing Executive's bounded error handling, durable state, and project lifecycle. No infinite retries or silent skipping.
4. Verify that stopping and restarting the normal offline application resumes unfinished work without duplicate commitments, episodes, or false success.
5. Retain the current independent evidence requirements and conservative score/identity qualification.

## 3. Restore the actual developmental learning loop

Using Charlie's existing components and original preserved experiences:

1. Recover and reconcile original episode identities at their source; distinguish physical experience, retrospective replay, reprocessing, and imported historical evidence. Preserve provenance and failures.
2. Let the **existing Learning Executive** choose among its eligible questions, evidence needs, investigations, and Charlie-originated experiments. Do not hardcode a new human-selected research agenda or promote unsupported tracker beliefs.
3. Process relevant Robotron experiences through existing evidence acquisition, Reflection/Meditation, independent evaluation, and experiment lifecycle.
4. Investigate demonstrated performance weaknesses where the evidence supports them: player ownership/SELF loss, action execution and neutral periods, movement/shooting choices, score attribution, game-over observability, rescue behavior, and prediction uncertainty. These are candidate questions, **not predetermined findings**.
5. Execute the next eligible Charlie-originated **offline** experiment and retain both positive and negative results. Show causal continuation: a specific question leads to evidence selection, a hypothesis, a testable candidate, independent evaluation, and a recorded decision.
6. Where a candidate is eligible, exercise the existing offline-shadow integration and guarded rollback path. Tests, shadow results, and simulator/replay scores are not proof of physical gameplay improvement.
7. Keep projects that require missing evidence paused with explicit requests, rather than declaring them completed or inventing observations.

## 4. Independently qualify the score-improvement claim

Before declaring ALA-2 complete:

- Define and freeze a reproducible baseline and evaluation protocol with game build/ROM, camera and controller configuration, code revisions, session boundaries, score-reading method, sample counts, and environmental assumptions.
- Use verified **complete games** and independently qualified final scores; preserve raw frames and transition evidence. Record uncertainty and exclusions.
- Segregate training, prior-consulted, validation, and final held-out evaluation evidence. Do not use duplicated or retrospective archives as independent trials.
- Show that the candidate originated from Charlie's learning records, was independently evaluated, and was integrated into the **existing PPAL tactical path** through the applicable deployment safeguards.
- Measure candidate performance against the frozen baseline using enough independently qualified complete-game observations to support a credible improvement claim; report distribution, uncertainty, confounds, and failures rather than only the best score.
- Require **separate explicit authorization** before physical Robotron gameplay, servo movement, firmware deployment, or physical policy activation. No authorization is implied by this Work request. If authorization is unavailable, complete all offline work and stop at the physical acceptance gate, reporting exactly what remains.
- Preserve rollback and demonstrate that a failing candidate can be rejected or deactivated without corrupting the baseline or original evidence.

**Acceptance is not met** by successful imports, meditation output, a proposed policy, offline-shadow success, a higher estimated score, or a single operator-observed number without independently qualified complete-game comparison.

## 5. Stabilize ALA-2; do not start Charlie UP

Once the relevant ALA-2 loop is working, perform bounded stabilization:

- Verify normal entry points, repeated offline runs, interrupted processing recovery, journal/database integrity, idempotent imports, ownership and resource safeguards, and regression tests.
- Document exact commands, expected outputs, checkpoints, known failures, and Pi-specific qualification still required.
- Preserve frozen baseline, evaluation artifacts, original journals, versioned candidate identity, deployment state, and rollback instructions.
- Do **not** add a new daemon/service architecture, boot-time automatic physical operation, external research agent, generalized self-healing platform, or new learning manager under ALA-2. Capture those as explicit **Charlie UP** follow-ons.

## 6. Execution, publication, and reporting

Work **in this order**, without waiting for another architecture discussion:

1. Recover and verify current remote/Pi/evidence state.
2. Complete marathon/post-marathon separation.
3. Fix invalid-preserved-meditation failure handling and restore Executive continuity.
4. Resume eligible Charlie-originated offline experimentation and candidate evaluation.
5. Prepare and independently validate the frozen score-comparison pathway.
6. When separately authorized, conduct guarded physical complete-game evaluation; otherwise report the exact authorization gate and remaining acceptance evidence.
7. Stabilize, document, and hand off to Charlie UP.

At **each meaningful milestone**, publish independently tested progress to `feature/agency-first-self` promptly. Never leave hours of completed work unpublished pending final acceptance. Report:

- Exact remote commit SHA, parent/base, branch and changed interfaces.
- Tests executed, environment, observed outcomes, and unresolved failures.
- Source run IDs, timestamps, artifact hashes, code revision, prior evidence use, assumptions, and uncertainty.
- Clear status distinctions: **proposed / implemented / simulated / independently tested / Pi-validated / physically demonstrated**.
- The next smallest executable milestone and any required authorization.

Do not claim completion until the ALA-2 score-improvement criterion is actually met. If blocked, leave the branch, evidence, and next steps recoverable from GitHub and the preserved Pi artifacts.

## Final deliverables

1. Published, independently tested ALA-2 implementation on the existing feature branch.
2. Preserved original and processed evidence with traceable provenance and integrity checks.
3. Demonstrated normal Executive continuation through at least one Charlie-originated offline investigation and bounded failure recovery.
4. Frozen baseline, qualified candidate and evaluation protocol, or explicit documented reasons any of these remain unqualified.
5. Independently measured complete-game Robotron score improvement **if separately authorized and demonstrated**; otherwise an honest **ALA-2 OPEN** report specifying the exact remaining physical/evidence gates.
6. A concise stabilization handoff and separate **Charlie UP** backlog, without implementing Charlie UP inside ALA-2.

**Start by verifying the current remote branch and recovering existing work. Execute; do not substitute another proposal for implementation.**
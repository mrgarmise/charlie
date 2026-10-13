
Charlie — Dual-Layer Learning and Mission Closure

Status: Proposed binding acceptance standard
Version: 1.0 — October 12, 2026
Governing charter: ALA_LEARNING_CHARTER.md

1. Purpose and scope

This standard defines the evidence necessary to close ALA-2. It adds mandatory, independently demonstrated learning in the Learning Executive and PPAL agent to the original ALA-2 mission. It does not replace, waive, or silently close any prior mission requirement, safety gate, physical-play authorization, or host-acceptance obligation.

Closure principle: ALA-2 is not complete until authentic retained experience causally influences future decisions at both levels and the required guarded integration is demonstrated.

2. Separate acceptance gates

E1 — Learning Executive adaptation

Demonstrate that outcomes of authentic Executive investigations affect a later selection, prioritization, or design of an investigation. Required evidence:

• Baseline Executive state and choice under a defined opportunity set.
• Authentic investigation and outcome, including failures or inconclusive results.
• Identified retained state or notebook record and persistence across the relevant restart/session boundary.
• Later comparable decision with the same available alternatives or a defensibly controlled comparison.
• Traceable causal explanation showing how retained evidence affected prioritization, hypothesis, experiment design, or strategy, rather than a fixed rule, random draw, or operator instruction.

A completed experiment, saved candidate, or automatically drafted plan is not sufficient.

P1 — PPAL agent adaptation

Demonstrate that authentic gameplay experience affects later PPAL perception, outcome estimation, action preference, or policy in comparable conditions. Required evidence:

• Identified pre-learning policy/model/state and an observed baseline decision or decision distribution.
• Authentic observation-action-outcome transitions and explicit feedback/evaluation mechanism.
• Identified learning update and persistent artifact (weights, values, rules, learned memory, or equivalent), including its reload/use after a relevant boundary.
• Later decision trace or controlled replay showing an experience-caused change in evaluation, preference, or action selection.
• Comparison controlling for changed visual inputs, game phase, random exploration, manually modified code, and environmental variation.

A different action alone is insufficient; a reinforced existing choice can count only if a retained learning update demonstrably affects its valuation.

I1 — Guarded Executive-to-PPAL integration

Demonstrate that an independently qualified, evidence-backed improvement is advanced through existing qualification, integration, authorization, and rollback safeguards and influences subsequent PPAL operation. Preserve provenance, candidate identity, acceptance tests, deployment version, and rollback path. A proposal, test-only improvement, or inactive artifact is insufficient. Never activate physical gameplay or motion without separate explicit authorization.

3. Evidence chain for each gate

Every acceptance claim shall document:

1. Baseline and exact decision context.
2. Authentic experience and source evidence identifiers.
3. Learning/evaluation mechanism actually implemented (do not assume SARSA, Q-learning, or RL).
4. Persistent learned state, identity, and provenance.
5. Subsequent decision and its relationship to retained evidence.
6. Causal control, replay, ablation, or equivalent comparison.
7. Confounds, limitations, uncertainties, and independently reproducible commands/artifacts.
8. Outcome: PASS, FAIL, or NOT YET DEMONSTRATED. Missing evidence is not a pass.

4. Preserve original ALA-2 work and constraints

The following remain independently open until evidenced and accepted under the existing mission:

• Native, unarmed Raspberry Pi acceptance using Charlie’s original persistent notebook, preserving historical sessions and the exact October 9 failure.
• Executive recovery after invalid meditation evidence, continued authentic investigations, and distinct project/candidate identities without evidence collisions.
• Exact evidence dependencies for existing Charlie-originated candidates; no fabricated, duplicated, or simulated replacement observations.
• Next eligible authentic offline investigation through the existing Executive, evidence-acquisition, Reflection/Meditation, and Evaluator interfaces.
• Independent qualification and guarded PPAL integration/rollback of eligible candidates.
• Frozen, independently measured complete-game Robotron comparison, distinguishing score/performance from learning. Do not represent a timed partial run as a complete game.
• All existing authorization boundaries, including no unapproved physical gameplay, physical motion, or policy activation.

This list summarizes known obligations; it is not exhaustive and does not supersede the original ALA-2 mission/handoff or subsequent accepted changes.

5. Three distinct claims

Report separately:

• Learning: retained experience demonstrably changes subsequent decision processing (E1 and P1).
• Performance improvement: independently measured outcome improvement versus a frozen baseline; may fail even if learning succeeds.
• Autonomous operation: activities run without continuous human intervention inside expressly authorized boundaries; not implied by learning or performance.

Do not collapse these into a single success label.

6. Verification protocol

1. Freeze versions, experiment identifiers, inputs, and baselines before comparison.
2. Preserve the original notebook and immutable source observations; make no destructive resets.
3. Establish baseline decisions at each layer and document random seeds or nondeterminism where feasible.
4. Acquire authentic new evidence through existing interfaces.
5. Record exact retained-state updates and restart/reload behavior.
6. Recreate comparable decision conditions with and without the relevant learned state (or an equivalent justified causal control).
7. Independently evaluate E1, P1, I1 and the original mission obligations.
8. Record performance separately and report uncertainty and failures.
9. Obtain explicit authorization for any activity that requires it before execution.

7. Closure decision record

Use the following fields in every closure review:

|Gate                              |Result                   |Evidence links/IDs|Limitations|
|----------------------------------|-------------------------|------------------|-----------|
|E1 — Executive learning           |NOT YET DEMONSTRATED     |                  |           |
|P1 — PPAL learning                |NOT YET DEMONSTRATED     |                  |           |
|I1 — Guarded integration          |NOT YET DEMONSTRATED     |                  |           |
|Original mission obligations      |OPEN — audit individually|                  |           |
|Independent performance comparison|NOT YET DEMONSTRATED     |                  |           |
|Authorization/safety compliance   |REVIEW REQUIRED          |                  |           |

ALA-2 may close only when E1, P1, I1, and every mandatory original mission requirement have affirmative, traceable evidence. Performance gains and autonomous operation must be reported honestly and independently; their required original-mission thresholds, if any, remain in force. No document wording grants new operational authority.

8. Required ongoing question

At every ALA-2 status review ask:

What did the Executive learn that changed its next investigation? What did PPAL learn that changed its next decision? Where is the retained evidence, and how do we know it caused those changes?

────────

Companion document to ALA_LEARNING_CHARTER.md. If this standard conflicts with an existing safety/authorization gate, the stricter constraint controls.
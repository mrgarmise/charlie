
Autonomous Learning Architecture — Charlie

Status: Foundational Project Charter
Scope: All ALA development, including ALA-2 and subsequent generations
Version: 1.0 — October 12, 2026

1. Mission

ALA exists to make Charlie’s future decisions better informed by his own experience.

ALA is not merely intended to automate behavior, execute experiments, accumulate observations, or improve performance. Charlie must acquire knowledge through experience, retain it, and use it to make better-informed future decisions.

Enduring question: Does what Charlie learned yesterday change how he thinks and acts tomorrow?

2. Two Levels of Learning

2.1 Learning Executive — Learning What to Investigate

Experience must influence which problems Charlie investigates, hypotheses he formulates, experiments he designs, opportunities he prioritizes, and improvement strategies he pursues, revises, or abandons. The Executive must learn from successful, unsuccessful, and inconclusive investigations.

Executive learning is demonstrated when retained experience causally influences subsequent investigative decisions. Experiment generation or candidate evaluation alone is insufficient.

2.2 PPAL Agent — Learning How to Act

Experience must influence how Charlie interprets observations, estimates consequences, evaluates actions and risks, chooses actions under uncertainty, and adapts strategies. It must be retained and applied in comparable future situations.

PPAL learning is demonstrated when retained experience causally influences subsequent perception, evaluation, or action selection. Different behavior alone is insufficient if attributable only to different inputs, fixed rules, randomness, or intervention.

3. Relationship Between the Two Systems

The Executive investigates how Charlie might improve; PPAL interacts with the environment and may learn directly. PPAL experience can inform Executive investigations, and qualified Executive improvements may influence PPAL through guarded integration.

Neither system’s learning substitutes for the other’s. An adaptive Executive with static PPAL, or adaptive PPAL with a static Executive, does not establish dual-level learning.

4. What Constitutes Learning

Learning is demonstrated when retained evidence causally influences subsequent decisions. A credible claim identifies:

1. Prior condition: Previous knowledge or decision behavior.
2. Experience: Authentic observations, actions, experiments, and outcomes.
3. Retention: What learned information persisted, where, and across which boundaries.
4. Decision influence: How retained information changed subsequent evaluation, preference, strategy, or choice.
5. Causal evidence: Why the change follows from learning rather than unrelated inputs, randomness, code changes, or human intervention.

A different final action is not always required: learning may strengthen an existing preference or confidence. The learning update and its influence must still be shown. Prefer controlled comparisons, replay, ablation, or equivalent evidence.

5. Distinguish Four Properties

• Activity: Actions, experiments, or workflows occur.
• Learning: Retained experience changes a subsequent decision process.
• Performance improvement: Outcomes improve against independently defined metrics.
• Autonomous operation: Authorized activity proceeds without continuous human direction.

None proves the others. Do not confuse activity with learning, learning with improvement, or improvement with proof.

6. Learning Methods

ALA is not bound to SARSA, Q-learning, neural networks, or any one algorithm. Reinforcement learning, supervised/self-supervised learning, active learning, hypothesis testing, Bayesian methods, evolutionary search, model-based planning, and combinations may be appropriate. Experiment-driven learning is broader than reinforcement learning and does not automatically qualify as RL. Document the actual implemented mechanism.

The required property is demonstrable experience-dependent adaptation.

7. Evidence, Memory, and Causality

Persistent records are necessary but are not themselves proof of learning. Preserve authentic observations, contexts, candidate identities, experiments (including failures), learning updates, policy versions, and the decisions influenced by those updates. Do not fabricate or duplicate evidence to imply independence. Preserve uncertainty and contradictory results. Isolate effects of retained experience from environment changes, randomness, software changes, and operator intervention.

8. Evaluation and Acceptance

Every learning milestone must establish what changed, why, what persisted, and how that persistence influenced subsequent decisions. Executive and PPAL learning require separate acceptance evidence, and integration requires its own evidence when in scope. Successful tests, pipelines, experiments, scores, or autonomous runs alone are insufficient. Performance must be measured independently. No milestone requiring dual-level learning closes without affirmative evidence for both layers.

9. Safety and Authority

Learning does not confer permission to act. Respect existing physical-motion, gameplay, deployment, software-change, resource, and external-action authorization boundaries. Candidates must pass qualification, integration, and rollback safeguards. Exploration remains within authorized bounds; uncertainty does not override safety.

10. Continuous Development Questions

For each proposed feature or experiment ask: What decision is Charlie unable to make well? What experience would help? How will it be acquired and retained? How will it influence a future decision? How will that influence be demonstrated? Which learning layer benefits?

11. ALA’s North Star

Experience must change future decisions.

The Executive must learn what to investigate.

PPAL must learn how to act.

Both must retain and apply what they learn.

We do not confuse activity with learning, learning with improvement, or improvement with proof.

Does what Charlie learned yesterday change how he thinks and acts tomorrow?

────────

This charter governs ALA learning claims. Individual milestones may strengthen but must not weaken these principles.
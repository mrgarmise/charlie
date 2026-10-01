# Learning return-path audit (before implementation)

Historical tactical-gap audit. For the current strategic ownership review and
optional project integration, see [Learning Executive audit](learning-executive-audit.md).

Concrete source: `body-fire-bootstrap-20261001-020552`, `dfdccde`.

| Existing path | Actual behavior | Reuse / gap |
|---|---|---|
| `closed_loop.EpisodeRunner` → `ShotAdaptation.observe` → `hindbrain.shot_model` | Accepted visible-HUD, one-threat examples retrain and replace a model that changes route-clearing movement. | Real return path, synthetic-only runner. Requires lives, reward and semantic one-threat hit/miss labels absent here; cannot safely route Robotron UNKNOWN telemetry through it. |
| `run_training/run_adaptation` → ShotModel checkpoint → Hindbrain | Offline supervised toy-shot learning; run_closed_loop loads model only in synthetic mode. | Reuse evidence-validation discipline; do not invent Robotron shot labels. |
| Hindbrain last-clear/last-panic state | Surviving recognized blockers change the next tick's action. | Existing within-game rule, not reflection/memory or cross-episode learning. Leave intact. |
| ShadowPredictor → shadow Forebrain/Hindbrain → report | Forecasts/actions logged, actual controller gets baseline action. | Reuse diagnostics; no actual deployment or usefulness feedback. |
| `evaluate_robotron_shadow` | Scores forecasts vs observation/no-motion baseline. | Diagnostic output only; not an experiment chooser. |
| `meditate_robotron` → predict/reconstruct/evaluate | Iteratively reconnects interpreted fragments and evaluates CV predictions. | Reuse offline; never rename canonical live tracks or treat reconstruction as SELF truth. No behavioral return path. |
| `reflect_robotron` → Experience → Gateway/Evaluator/store | Findings, prior comparisons, questions; new E/E summaries consolidate through this path. | Reuse. No existing Robotron actuator hypothesis producer/consumer. |
| `MemoryFormer/MemoryEvaluator/MemoryGateway` | Selection, IDs, provisional/promoted/dormant/superseded, local retrieval, recall, explicit decision-use credit and correction. | Reuse all memory lifecycle; missing task adapter from measured actuator evidence to an explicit proposal and next action. |
| `head_search.preferred_direction` → MobileFaceTrackBehavior | Structured sourced outcomes can choose a later face-search direction; actual use registered with Evaluator. | Working cross-episode knowledge-to-action precedent. Face-specific predicate cannot be reused as a Robotron rule; use the same Gateway/Evaluator boundary. |
| PPALMemoryAdapter / dense Memory | Stores observations and transitions, without success causation. | No consumer that changes Robotron action. |
| `marathon_robotron` | Runs bounded subprocess episodes, checks confirmed game-over, evaluates shadows, meditates after all games/failures. | Reuse subprocess/restart/session machinery. Missing between-game E/E/reflection/consolidation, selection, prospective commitment and resolution. |
| `play_robotron` | New Forebrain/Hindbrain each game; agency-first/provisional SELF; score passive. | No memory/model/experiment input. Missing one explicit opt-in experiment slot, not a new controller/brain. |

Actual current path ends at stored memory/diagnostic files. No code path brings a
completed Robotron episode's memory back into the next `play_robotron` decision.
Adding a general Learning Executive would duplicate existing mechanisms.

## Smallest justified implementation

1. Extend existing Reflection with a general one-actuator-variation proposal
   adapter based on existing AgencyTracker's measured response distributions.
   Derive BODY setting and expected verdict from data; enumerate FIRE bindings
   from the known actuator vocabulary. Use existing Experience and Evaluator.
2. A narrow adapter reads eligible active proposals from existing local Evaluator,
   records actual memory use, and commits one conditional prospective prediction
   through the accepted E/E journal before starting the next game.
3. An opt-in plan changes at most one eligible normal action. Preserve acquisition,
   recovery, collision/arena bounds, score and single generic tracking. No normal
   SELF is fabricated to execute a plan.
4. Between games, resolve using existing AgencyTracker's response evidence for
   the same scoped physical candidate and exact action window. UNKNOWN, lost ID,
   missing window, different clock/horizon and no eligible action remain unresolved.
5. Reuse existing memory feedback only for explicit **diagnostic predictive
   usefulness**; no score, survival or semantic benefit is credited automatically.
6. Extend marathon with opt-in 3–5 attempt bounds, automatic between-game work,
   visible summary, timeout and existing conservative restart authorization.

## Concrete hypothesis, not a supplied strategy

Sample 18: provisional track 146, BODY NE + FIRE NW, displacement
`[1.796875,-2.708333...]`, signed-command agreement .9801.
Sample 24: provisional track 146, BODY NE + FIRE SE, displacement
`[2.578125,-3.229166...]`, agreement .9938.

These support a tentative context-bound relationship: aligned NE BODY response
occurred under two different FIRE settings. They do **not** establish certified
SELF, FIRE independence, kills or score improvement. The first draft manually
specified neutral FIRE as the contrast; Alex's clarification correctly rejected
that specificity. It was replaced before publication by generic proposal logic:
all nine FIRE states become alternatives, expected response is the observed modal
agency reason, and setting frequencies supply an explicit tie-break. No NE,
neutral FIRE or signed-response target is encoded as a selected constant.

Score observer baseline 888 conflicts with Alex's reported 400; no accepted
score delta exists in this run. Shot adaptation or score-driven action credit is
therefore unjustified. The return path's first experiment is diagnostic, not a
policy claiming to maximize score. SCORE remains the performance objective.

## Deferred

General curiosity/information-gain optimizer, broad environmental hypotheses,
learned death/contact/rescue semantics, projectile-origin learning, score strategy,
bulk policy updates, remote prose as executable advice, 50–100 games. Do not use
unverified TIME LIMIT/SELF loss as authority to START another game. A developmental
marathon may safely stop early when no confirmed episode boundary is available.

# Learning Executive: actual architecture and smallest vertical slice

Audit baseline: `feature/agency-first-self`, `0da1b84f65a725105b0ba74e489a7c72d7fe744f`.
This review follows executed code and tests, including the completed tactical
return path. The earlier [return-path audit](return-path-audit.md) describes the
state **before** that path was implemented; its gaps are not all still gaps.

The missing capability is sustained project ownership, not another intelligence,
memory store, Reflection service, tactical chooser or controller. The implemented
milestone adds operational continuity over the accepted evidence journal and an
optional project context for the existing chooser. It demonstrates a controlled
campaign; it does **not** establish autonomous strategic learning in physical play.

## 1. Actual existing capabilities

| Mechanism and executed path | What it actually supplies | Strategic limitation |
|---|---|---|
| `play_robotron` → one SpriteTracker → AgencyTracker / provisional BODY/FIRE embodiment → Forebrain/Hindbrain → existing controller | Generic persistent physical objects, uncertainty, control evidence, bounded normal actions, immediate responses | Objects and controller decisions are episode-local; agency evidence is not semantic certainty |
| `models.Goal` / `forebrain.Forebrain.update` | Retains a current rescue target while present, otherwise survive; each player process creates a new Forebrain | “Persistent objective” in the docstring means an in-process target, not a durable intellectual project |
| `reflect_actuator_evidence` → Experience → Gateway/Evaluator | Derives BODY binding and modal agency verdict from actual eligible windows; generates all FIRE alternatives; stores tentative hypotheses | Bounded one-variable proposal generator, not broad environmental curiosity or a project portfolio |
| `experiment_return.select_experiment` | Eligible local promoted structured hypotheses; Evaluator priority, then explicit evidence rank | Originally chooses from the latest 100 memories without an overarching scope |
| `EvidenceJournal.predict` / `resolve`, `resolve_experiment` | Actual prospective commitment, horizon/order checks, measured outcome, supported/contradicted/unresolved; no retrospective forecast passed off as live | Individual prediction lifecycle, not cumulative project completion |
| Existing experiment hook in `play_robotron` | At most one eligible normal action differs; respects UNKNOWN, immediate-response priority, bounds and occupied routes | No authority to rewrite policy or bypass acquisition/safety |
| `developmental_marathon` → `process_completed_episode` | Child closes, then E/E → resolution → derivation → Reflection → shadow evaluation / Meditation → memory; automatic next selection and child launch | Previously no durable project owner; changing memory salience could change the investigation |
| `memory.former.Experience` / MemoryFormer | Selects and formats significant observations/outcomes with origin, goal prose, evidence and confidence | Goal is metadata, not an operational lifecycle |
| MemoryEvaluator / MemoryGateway | Durable candidates, priorities, provisional/promoted/dormant/superseded status, explicit use, feedback and correction; routes promoted memories to selected store | Memory usefulness is not project success; dormancy must not erase an unfinished project |
| MARM client, outbox and recall | Persistent selected knowledge, deduplicated queued transport, project/session namespaces, conservative structured recall | No Charlie campaign execution/completion path in this checkout |
| Reference MARM project CLI and console project endpoints | Repository code-graph indexing, status, search and memory bindings | Those “projects” are not learning undertakings. No new MARM server schema is needed |
| `reflect_robotron.reflect` / `learning_review.review_session` | Findings, recalled context, question queue, diagnostic session review | No execution of queued questions or strategic project ownership |
| `meditate_robotron`, reconstruction, ShadowPredictor and shadow evaluator | Offline interpreted track reconnection, predictions, CV/error diagnostics | Do not rename canonical tracks, deploy interpreted SELF, or change live policy |
| `ShotAdaptation.observe` → `hindbrain.shot_model`; synthetic training/checkpoints | Actual model adaptation can alter later toy-arena movement/clearing | Requires toy semantic/visible-HUD labels unavailable in this Robotron evidence; not autonomous code modification |
| `head_search.preferred_direction` → mobile face tracking | Recalled independent structured outcomes can change a later search direction, with recorded memory use | Working knowledge-to-action precedent; its face predicates are not Robotron rules |
| `experiments.comparison.runner.Plan/run/analyze/publish` | Preregistered metrics and guardrails, paired trials, conservative intervals, immutable artifacts, Experience publication; genuine ablations can earn usefulness credit | Reusable method for later performance projects, but no project-selection/lifecycle consumer |
| AttentionManager / BehaviorManager / main physical loop | Event-driven behavior transitions; attention priority is recorded, pending request replaces pending request | No durable learning portfolio or learning return path; do not mistake the `priority` attribute for implemented strategic arbitration |
| `tools.update_charlie.CharlieUpdater` | Human-invoked git pull → RP2040 synchronization → service restart | No autonomous proposal→patch→test→authorize→rollback loop found. An updater is not a self-modification system |

Search covered executable Python, tests and relevant docs, including modification,
rollback, goal, priority and planning terms. No autonomous code-modification loop
was found **in this repository**. The review does not assert that an external
system cannot exist. Existing comparison and adaptation mechanisms are reused or
reserved as methods; a new Executive must not assume code-edit authority.

MARM reference inspected read-only: `marm-mcp-server/marm_mcp_server/services/projects_cli.py`
and `console/endpoints/projects.py` in the pinned reference checkout. Its
code-graph project management is not imported into Charlie's experiment loop.

## 2. Complete existing decision trace

Concrete source: `body-fire-bootstrap-20261001-020552`, source revision `dfdccde`
with reported local changes. Samples 18 and 24 observed provisional track 146
responding to BODY NE under FIRE NW and SE. These were eligible same-ID response
windows; neither certified SELF nor FIRE independence was established.

1. **Origin:** `reflect_actuator_evidence` reads verified original agency rows.
   The observed modal verdict supplies the expectation. All nine FIRE states
   come from the known actuator vocabulary, not a selected Work direction.
2. **Priority:** Experience significance/novelty enters the existing Evaluator's
   usefulness score. The explicit tie-break ranks untested binding, observed
   modal support, window count and recorded setting frequency.
3. **Choice:** `select_experiment` selects a promoted local structured proposal.
   Remote prose is never executed as an action.
4. **Expectation:** the existing journal commits a live prospective prediction
   before starting the next child; the episode-scoped plan records the condition,
   deadline, originating memory and alternatives.
5. **Execution:** the existing one-action hook may execute under provisional or
   confirmed SELF. Lack of an eligible action remains unresolved.
6. **Outcome:** `resolve_experiment` checks the actual transport, endpoint window,
   timing, identity continuity and existing AgencyTracker verdict.
7. **Knowledge:** diagnostic predictive-usefulness feedback reaches the existing
   Evaluator, and a resolution Experience reaches the existing selected store.
   Score utility is not credited from proximity.
8. **Next decision:** the next marathon selection reads the updated Evaluator;
   contradicted expectations can change the next selected experiment.
9. **Former overarching objective:** none beyond the runner's declared official
   score objective and episode-local baseline intent. No cumulative project
   completion was implemented.
10. **Restart persistence:** evaluator candidates/evidence/corrections/decisions,
    MARM outbox/selected knowledge, raw episodes and E/E notebooks persist. Live
    SELF, track IDs, current Forebrain target and child state do not transfer.

Alex reported official score 400. The observer recorded baseline 888 without
accepted increases. The discrepancy remains unresolved; this milestone neither
claims score causation nor teaches a firing or rescue strategy from it.

## 3. Boundary and explicit interfaces

| Strategic Executive | Existing tactical chooser / execution |
|---|---|
| Owns active project, goal, cumulative criteria, history and declared constraints | Owns eligible proposals, concrete alternative ranking and one-action experiment |
| Selects a portfolio project and explains alternatives/costs | Commits expected outcome through the existing prospective journal |
| Supplies `chooser_context(project_id)` | `select_experiment(..., project_context=...)` filters by method, scope, expected predicate and linked hypothesis evidence |
| Receives `record_result(project_id, plan, resolution, journal, episode=...)` | Resolves actual evidence using the existing adapter and feeds existing Evaluator |
| Assesses cumulative replication, coverage, stagnation and budget | Chooses coverage alternatives if declared coverage is unmet, then uses existing Evaluator/rank; Executive selects no BODY/FIRE setting |
| Records interruption, completion, blocked state and resumption | Preserves urgent live response, UNKNOWN, calibration, START checks and all controller limits |
| Records method availability and external authorization separately | Existing execution mechanism still decides whether it is permissible/eligible to act |

Project context, ranking, alternatives and cumulative history are inspectable.
The pre-game recalled-memory observation preserves project context alongside the
existing prediction. Project ID is in the plan and its resolution/history link.
There is no Executive computation in `play_robotron`'s time-critical loop.

## 4. Project model and persistence

`memory.learning_projects.LearningExecutive` folds project events from the existing
`EvidenceJournal` format. No second Experience, memory database schema, correction
system, Reflection engine, hypothesis store or MARM service is introduced.
This notebook is durable **operational evidence**, not a selectable knowledge store.
Project conclusions use the existing Experience → Gateway → Evaluator → selected
store/MARM outbox path. Tests verify local promotion; a remote MARM upload is not
claimed merely because an item was queued.
Restart replay recovers a crash between outcome and cumulative assessment, or
between durable conclusion and memory handoff. Existing Evaluator evidence IDs
deduplicate that handoff; no new memory queue is created.

| Conceptual field | Representation |
|---|---|
| Stable ID | Digest of method, scope, expected predicate, proposal revision and implementation version |
| Origin / motivation | Exact preserved Reflection proposal; E/E journal paths, source IDs and episodes |
| Goal / success criteria | Generated reproducibility question; declared cumulative `CompletionCriteria` |
| Current understanding / open questions | Explicit diagnostic interpretation; unresolved questions retained at closure |
| Hypotheses | Links to existing Reflection/Evaluator hypothesis evidence, not copied semantic facts |
| Experiment history / progress | Prospective prediction and resolution IDs, episode, conditions, verdict, memory ID; cumulative counts/coverage |
| Constraints | Resource/dependency requirements, method availability, external authorization, attempt budget, existing execution restrictions |
| Status / next direction / rationale | Immutable lifecycle/assessment/selection events projected into current state |

Cross-episode consolidation imports references explicitly. It does not join
physical identities or splice monotonic clocks across runs. Source records are
looked up in their existing journals; imported references preserve their content
IDs. Earlier observations, provisional identities and interpretations remain
unchanged. The authoritative state is replayable events, not `session.json`.

The default durable notebook is `learning-project-evidence.sqlite3` beside the
existing local Evaluator database, outside per-marathon directories. An explicit
`--project-evidence` path can override it. Original episode/evidence directories
must be retained for full provenance. This initial implementation assumes one
orchestrator writer, not competing distributed Executives.

Closed projects do not silently reopen when the same proposal is seen again.
New evidence is retained. A new explicit Reflection proposal revision can create
a reconsideration campaign; automatic revision generation and memory correction
for such reconsideration are deferred to the existing correction boundary.

## 5. Portfolio, interruption and completion

Initial project generation is deliberately narrow and general: typed hypotheses
with an observed expectation and a condition vocabulary generate a question about
reproducibility. BODY and expectation are data from existing Reflection. The
production adapter registers `actuator-response`; no startup/focus/strategy goal
list is installed. A previously unspecified opaque instrument uses the same
proposal and lifecycle interfaces in controlled tests.

Portfolio score is an explicit first-version heuristic:

`objective contribution + learning value + uncertainty/(1 + resolved trials) - cost - risk`.

The present producer uses uncovered-condition fraction for learning value and
uncertainty; contribution/cost/risk are declared generic priors, **not learned
score utility**. Alternatives expose each term, missing resources, unmet
dependencies, method availability and authorization. Opportunity cost is visible
as the other eligible alternatives. This is not a calibrated value-of-information
or risk model.

An eligible active project is sticky. A documented urgent project can interrupt
it, but urgency supplies no new authority. Missing prerequisites block an active
project. When the interrupting project closes and prerequisites return, the
original project is resumed before a fresh candidate; hypotheses/history remain.
An explicit paused/blocked hold requires evidence-backed release. Budget holds
do not renew themselves. No eligible project, or no eligible tactical experiment,
is a valid outcome; existing baseline policy and conservative episode boundaries
remain authoritative.

| Disposition | Implemented decision / limit |
|---|---|
| Achieved | Default ≥3 resolved predictions, ≥2 episodes, ≥2 conditions, supported fraction ≥.8; one success/failure never completes a project |
| Sufficiently explored | Resolved recent conditions/verdicts repeat earlier distinctions, **all declared conditions have been sampled**, and cumulative/window minimums hold; unmet sampled conditions cannot be disguised as stagnation |
| Blocked | Required resource, dependency, method or authorization unavailable; histories retained |
| Paused | Interrupted worthwhile project, explicit hold, or declared attempt budget exhausted without achievement |
| Superseded / abandoned | Explicit evidence-backed lifecycle interpretation; no code authority and no destructive memory deletion |

Five contrary experiments covering both declared conditions can close the old
question as sufficiently explored without claiming the expected relationship was
true. Contradictions reduce empirical support. Unresolved results count against
cost budget but supply no achievement/contradiction credit. These thresholds are
declared diagnostic policy, not statistical proof or learned completion wisdom.

## 6. Integration and authorization

The smallest implemented milestone is opt-in:

```bash
python -m experiments.ppal.marathon_robotron \
  --developmental --learning-projects --max-games 3 --game-seconds 20 \
  --focus 1.30 --arm
```

This is the invocation **when a physical campaign is appropriate**, not a claim
that the last physical startup repair has been validated. The unchanged runner
may safely stop after one attempt: TIME LIMIT, uncertain screens, missing report,
failed calibration, tracking loss or child timeout do not authorize another START.
The current `--arm` authorization permits only the existing bounded actuator
method. The supplied resource set describes available method plumbing, not a
claim that focus is good or SELF is certified; the child's existing preflight and
action eligibility still apply.

Between games: resolve the actual trial → existing Reflection/Memory/Meditation →
generate project opportunities → record cumulative result → select active project
→ ask existing chooser → commit prospective prediction → launch bounded child.
The default runner and standalone player remain unchanged when the option is off.
Turning the option off also leaves the durable project notebook intact for later
resumption. There is no migration or destructive rollback step.
No code edits, shell commands, learned semantic strategy, score reward feedback,
second association pass or weakened restart checks are added by the Executive.

There is no existing validated self-patching loop to connect. Later registered
methods may include comparison, observation, retrieval or authorized modification.
Unsupported/unapproved methods are blocked today. Permission and strategic value
remain different checks; this implementation offers no code-modification executor
or substitute rollback mechanism.

## 7. Demonstration, regression and remaining work

See [controlled provenance/results](learning-executive-controlled-example.json).
The complete archived BODY/FIRE run is processed through the real E/E/Reflection
path. Its nine hypotheses generate one reproducibility project; the original
raw report/agency hashes remain unchanged. Later transport outcomes and terminal
screens in the demonstration are explicitly synthetic.

`tests/test_learning_projects.py` covers:

- Real-source proposal → portfolio → existing chooser → live prospective
  commitment → synthetic measured response → existing resolution/Evaluator →
  cumulative conclusion → another evidence-generated project.
- Different tactical conditions within one preserved objective; no selected
  BODY/FIRE direction or expected verdict embedded in the Executive.
- Previously unspecified instrument/project, restart persistence, active-project
  stickiness, interruption/blocked prerequisites and automatic resumption.
- Single-episode repetitions, contradictory evidence, tolerated imperfection,
  five negative trials with no new distinctions, and UNKNOWN/budget exhaustion.
- Durable hypothesis retrieval beyond the existing latest-100-memory window.
- Method availability versus authorization, exact Reflection-origin validation,
  dependency achievement, crash recovery and deduplicated memory handoff.
- Opt-in three-game orchestration, a four-game campaign that discovers a
  competing project during game one and switches after completion, and the
  unchanged unverified-boundary stop. Later measurements/terminal screens are synthetic.

Run the focused architecture tests or the full regressions:

```bash
python -m pytest tests/test_learning_projects.py tests/test_experiment_return.py -q
python -m pytest tests -q
```

Validation for this integration: **364 tests passed**, including 14 new project
tests and all existing tracking, agency, startup, scoring, replay, memory,
comparison and developmental-runner regressions. `git diff --check` passed.
The complete original archive was processed offline, beyond the smaller committed
fixture excerpt; source SHA-256 checks confirmed no raw evidence changes.

The production return method is still diagnostic actuator testing. Automatic
camera-fault recognition and focus remediation, startup-latency experiment
adapters, score-strategy hypotheses, multi-domain learned project value,
automatic abandonment/supersession explanations, automatic reconsideration,
broader method registration and autonomous code modification are **not built**.
The interruption test proves persistence/scheduling, not physical focus repair.
Comparison Plan/Metric/guardrails are the preferred existing foundation for a
future latency/performance method; do not substitute BODY/FIRE trials for it.

Recommendation: validate the bounded project-scoped actuator campaign physically
after startup/preflight evidence is available. Then add one evidence-backed
readiness/observation method and connect its real interruption conditions. Retain
the same journals, Reflection, Evaluator, project interfaces and chooser. A larger
refactor or general-purpose Executive intelligence is not justified by this slice.

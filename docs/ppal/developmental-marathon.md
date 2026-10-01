# Autonomous developmental return path

The [audit](return-path-audit.md) found no Robotron memory-to-action consumer.
Two existing return paths work in other tasks: toy shot adaptation updates a
Hindbrain model; face-search memory changes a future search direction. Their
domain predicates are inappropriate for these unlabeled Robotron observations.
This implementation connects existing components with a narrow actuator-test
adapter, rather than introducing a Learning Executive or a second memory system.

## Actual path

`marathon_robotron --developmental` runs a bounded game subprocess, then, with
camera/controller already closed:

1. `process_completed_episode` imports original artifacts using E/E, resolves any
   pre-game live commitment from new agency evidence, runs E/E replay diagnostics,
   and invokes existing `reflect_evidence` and Meditation (`meditate/quality`).
2. New `reflect_actuator_evidence` in existing Reflection generates tentative
   proposals using recorded response distributions. These are existing Experience
   instances stored/selected by MemoryGateway, MemoryFormer and MemoryEvaluator.
   Meditation's reconstructed IDs and shadow predictions remain diagnostics;
   they do not overwrite physical IDs or enter the action plan as truth.
3. A small task adapter, `select_experiment`, reads eligible promoted proposals
   from the existing local Evaluator. Its priorities have first say; explicit
   evidence ranks resolve ties. MARM/outbox remains the normal selected-memory
   path. Remote prose is not executable advice, and no remote service is needed
   between games.
4. Before launching the next player subprocess, the adapter writes one E/E
   `live_prospective` conditional prediction and a scoped plan. The predicate is
   conditional on a later eligible provisional/confirmed SELF, not a claim that
   an unknown future ID is already SELF. Prediction time precedes the child game.
5. `play_robotron --experiment-plan` loads/validates that plan before camera setup.
   At most one normal action changes because of it; the step records baseline vs
   experimental action, memory/prediction IDs, current physical candidate,
   identity status and exact observation origin. Acquisition/recovery logic,
   score acceptance and single generic tracker remain unchanged.
6. After the game, `resolve_experiment` requires the matching two-endpoint window,
   same scoped physical ID, actual BODY/FIRE transport, later timestamp within
   horizon, no global motion and adequate existing AgencyTracker response evidence.
   It compares the actual reason to the **data-derived** expected reason. Missing
   ID/window, ambiguous association, no eligible action, invalid timing or partial
   evidence yields unresolved, not fabricated success/failure/death.
7. Supported/contradicted diagnostic predictions feed existing
   `record_decision/assess_decision` with an explicit comparison and half-weight
   usefulness evidence. Unresolved evidence gets no usefulness credit. Existing
   Evaluator priority, dormancy/supersession and exclusion affect later selection;
   no duplicate retain/revise/discard implementation is added.

The feedback measures whether the memory anticipated an observed actuator
response. It is **not** score credit, survival benefit or proof of causal FIRE
independence. SCORE remains the ultimate performance objective. The live score
worker stays passive.

## Proposal generation and provenance

The implemented adapter does not contain selected literals `NE`, `FIRE=NONE`, or
`expected=signed_command_response`. It knows the existing BODY/FIRE vocabulary,
including neutral settings and simultaneous operation. Its bounded proposal rule:

- Group trustworthy measured windows by current physical candidate and BODY
  setting, using provisional/confirmed origin context.
- Require at least two distinct windows and two recorded FIRE settings.
- Form the empirical distribution of existing agency response reasons. A tied
  modal response yields no justified proposal.
- Hold the observed BODY setting fixed and enumerate **every** allowed FIRE state.
- Attach all supporting evidence IDs, episode/track scope, source samples,
  empirical distribution, joint observation count, setting-frequency evidence,
  tentative status and no score claim to each existing Experience.

The generic ranking is explicit, not learned or optimal: existing Evaluator
priority first; then untested binding, modal support fraction, supporting window
count and how frequently the alternate setting appeared in distinct recorded
transport executions. Familiarity is a developmental tie-break, not estimated
information gain or game reward. This modest task-specific proposal adapter is
the new connection; a broad autonomous hypothesis generator is deferred.

For **full** `body-fire-bootstrap-20261001-020552`, only the NE group meets these
criteria: samples 18 and 24 on provisional candidate 146 reported
`signed_command_response`, under FIRE NW and SE respectively. That observed
2/2 mode becomes the expected result; it is not an encoded prediction target.
Every proposal is traceable to those immutable E/E source rows and their original
`agency.jsonl` line, hash, timing, displacement and class/identity uncertainty.

| BODY from evidence | FIRE alternative | Jointly tested in supporting group? | Distinct recorded uses of FIRE state | Initial Evaluator priority |
|---|---|---|---:|---:|
| NE | NONE | No | 7 | .65 |
| NE | E | No | 4 | .65 |
| NE | N | No | 2 | .65 |
| NE | S | No | 2 | .65 |
| NE | SW | No | 2 | .65 |
| NE | NE | No | 1 | .65 |
| NE | W | No | 1 | .65 |
| NE | NW | Yes | 4 | .52 |
| NE | SE | Yes | 1 | .52 |

MemoryFormer assigns novelty/significance to untested combinations; initial
Evaluator usefulness/significance priority is .65 versus .52 for retests.
The narrow selector resolves the seven .65 ties using the documented evidence
rank, selecting NONE because its recorded state frequency is 7. **Evaluator did
not magically discover neutral FIRE's utility.** It ranks evaluated memories;
the adapter generates alternatives and resolves this tie. The evidence supports
testing a hypothesis, not certifying its generalization.

[The full concrete example](return-path-real-example.json) includes all nine
proposals, supporting IDs, alternative ranks, selected memory ID and pre-game
prediction. It is a real-evidence proposal/commitment demonstration; that intended
demonstration game was not launched, so its resolution is explicitly unresolved.
The next physical run creates its own fresh commitment. A data-perturbation test changes recorded BODY,
FIRE familiarity and observed verdict, and the adapter selects SE/N/wrong_way
instead: neither direction, FIRE state nor expected reason is a selected constant.

## Scope and safety of the action change

One experiment per attempted game; no blind schedule forcing it to run. UNKNOWN
SELF, expired horizon, identical baseline action, existing evade/clear intent,
occupied route or existing arena bounds can leave it unattempted. The generic
occupancy check uses existing movement geometry/clearance, not enemy semantics.
No new SELF gate or association pass is introduced. FIRE remains available during
the existing pre-certification bootstrap. A rejected/malformed plan retains the
normal policy and surfaces its reason in the report.

No database, memory lookup or prediction serialization runs between camera
observation and control dispatch. Live work is one bounded geometry check and
small existing step metadata; all persistence/consolidation is between games.
This small opt-in path's Pi timing cost is **not yet measured**. Baseline runs
without a plan retain controller decisions. Existing report provenance marks
dirty worktrees; the local `run_camera.py` modification is untouched.

## Bounded unattended operation

Developmental mode accepts **3–5 total attempts** and at most 120 gameplay seconds
per attempt. The child process has an additional 120-second bound for startup,
calibration, probes and finalization; timeout stops the session. TCP disconnect
uses the existing Zero transport's neutral-release behavior. Between-game
failure/interrupt is surfaced, pending commitment is marked unresolved where
persistence remains available, and no further START occurs.

The existing confirmed-game-over restart guard remains authoritative. TIME LIMIT,
SELF loss, failed calibration, UNKNOWN screen or uncertain end does not authorize
a next START. The runner may stop after one attempt instead of completing three.
This is intentional; actual 3-game Pi completion still requires reliable terminal
evidence. No new terminal classifier or blind START behavior was invented to pass
the demonstration.

Every attempted game has visible score evidence, SELF status, attempted experiment,
prediction ID, resolution, diagnostic belief/memory change and selection reason.
`session.json` also preserves complete plans/alternatives, per-game processing,
E/E paths, seed processing and stopped/unresolved reasons. Each game and its IDs
remain separate. No justified proposal is valid: that game uses the existing
policy, and no prospective experiment is fabricated.

## Demonstration and validation

- Full supplied real archive processed through E/E, Reflection, existing
  MemoryGateway/Evaluator, Meditation and proposal ranking: nine alternatives,
  NE/NONE selected from evidence; about 7.29 seconds between-game work on the
  development host (not a Pi performance claim).
- Real response/familiarity excerpts provide deterministic regression tests,
  labeled excerpts with original run/revision/line/hash provenance. The full
  archive, including its failures and 400-vs-888 discrepancy, was also processed.
- The **actual `play_robotron.main`** runs against a deterministic camera/controller
  test world: a real-evidence-derived memory changes exactly one action versus
  the logged baseline; new observations resolve the genuine pre-game prediction
  as supported. Controller/camera release, provisional semantics, generic IDs
  and baseline integration tests still run.
- Three unattended **synthetic transport episodes** exercise the real marathon,
  E/E, reflection, memory selection, commitments, resolutions and feedback. This
  proves orchestration/behavioral return plumbing, not physical Pi completion or
  Robotron improvement.
- Tests cover supported/contradicted/unresolved, no proposal, UNKNOWN, immediate
  policy priority, supersession causing a different next experiment/exclusion,
  and no second START at an unverified boundary. Existing complete suites remain.

Still unproven: next physical episode executing/resolving the selected plan;
three unattended physical games; accurate score changes; reliable semantic
consequences; improved SCORE. No Learning Executive, strategy rules, projectile
labels, broad causal optimizer, remote-instruction executor or bulk policy update
was added.

## Next Pi experiment

Stop any preview server and start from attract mode with an unobstructed view.
This command automatically processes the seed and each subsequent attempt; Alex
does not manually invoke E/E, Reflection, Meditation, consolidation or selection.

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git fetch origin &&
git switch feature/agency-first-self &&
git pull --ff-only origin feature/agency-first-self || exit 1
python -m pytest tests -q || exit 1

dev_root="robotron-runs/development-test-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$dev_root"
set -o pipefail
PYTHONPATH="$PWD" python -m experiments.ppal.marathon_robotron \
  --developmental --max-games 3 --game-seconds 60 --retry-wait 3 \
  --focus 1.30 --arm --root "$dev_root" \
  --seed-episode robotron-runs/body-fire-bootstrap-20261001-020552 \
  2>&1 | tee "$dev_root.console.log"

for agency_log in "$dev_root"/development-*/game-*/agency.jsonl; do
  [ -f "$agency_log" ] || continue
  python -m experiments.ppal.replay_tracking "$agency_log" \
    --output "${agency_log%/agency.jsonl}/tracking-replay.json"
done
tar -czf "$dev_root.tar.gz" "$dev_root" "$dev_root.console.log"
```

Return `robotron-runs/development-test-<timestamp>.tar.gz`, even if the session
stops early. Retain the original seed archive: E/E references it by hash instead
of copying its pixels/logs into the new session. Normal selected memories use
the existing MARM outbox/Evaluator; per-game summary embeds enough selected
proposal/evaluation provenance for review without needing a remote MARM service.

Final complete suite: **321 passed in 21.32 seconds**. Two successive fresh-output
full-archive passes completed. An earlier development pass reported SQLite
`SQLITE_READONLY_DBMOVED`: its open database file had been replaced externally.
Line tracing and subsequent runs did not reproduce that replacement; its cause
is not established. Failed artifacts were preserved. No retry that discards or
rewrites committed evidence was added; a persistence failure stops the marathon
and is reported rather than silently continuing.

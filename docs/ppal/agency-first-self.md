# Agency-first SELF: implementation and next live experiment

**Updated after the first Pi run:** see [motion-tracking-repair.md](motion-tracking-repair.md)
for the current tracker, diagnostics and test commands. The acquisition principles
below remain; the old 24-frame diagnostics and independent location association
were superseded by the shared motion-aware tracker.

Armed `play_robotron` discovers SELF over every generic visual detection. A taught
PLAYER score is not an admission requirement. Unarmed preflight still reports
appearance/center proposals without issuing controls; it does not prove agency.

`agency.py` accepts track positions and the BODY vector responsible for each
observation interval. `robotron_agency.py` supplies Robotron stick mapping and
conservative `SpriteTracker` association. `PersistentSelfTracker` remains the
location tracker after identity is established. `WorldState.player` remains a
required position, and uncertain observations never construct a planning world.

Acquisition taps E, neutral, W, neutral, S, neutral, then (if necessary) N,
neutral, E, neutral, W, neutral. Each pulse is 60 ms, both sticks center at its
end, and firing is disabled during discovery. Acquisition requires at least
three signed responses, two different directions, a reversal, two stops,
confidence >= .72, and a >= .18 lead over the runner-up. These values are
parameters and need live calibration. Scores are evidence strength, not
probabilities. An equally controllable pair remains UNKNOWN.

Normal gameplay movement updates agency, including diagonal movement and STAY.
Wrong-way/off-axis motion and nonresponse lower confidence. One blocked command
can be tolerated after a strong lock. Sustained contradiction triggers bounded
reacquisition. Occlusion retains belief briefly but never supplies a stale
position to planning. New track IDs must earn evidence themselves; they do not
inherit authority from proximity. The runner test includes a respawn elsewhere.
Explicit death/world resets can clear the generic component; the live runner
uses disappearance/reacquisition because it has no reliable per-life death signal.

Neutral observations distinguish continuing followers from a stopped body.
`indirect_score` records neutral continuation or motion toward previously known
SELF; this is descriptive evidence, not proof of a learned mediated causal
relationship. Coherent global movement across >=3 tracks causes abstention and
weakens existing identity. There is no camera-motion compensation or learned
latency model. First post-pulse frames supply endpoint displacement; buffered
camera frames and ambiguous/merged visual regions remain important live risks.

Recent manual focus, startup calibration, screen classification and robust
legacy episode-end challenge code remain. The legacy appearance challenge can
corroborate game state, but cannot authorize SELF. Generic acquisition failure
never counts as game-over proof. Existing robust terminal rejection still uses
its separate eligible appearance challenge; this distinction is deliberately
retained from the integration branch, not broadened to arbitrary UNKNOWN blobs.

## Evidence

* `agency.jsonl`: sample ID, SELF/leading/runner-up IDs and confidence, command,
  displacement, directional agreement, contradictions, indirect evidence,
  event, global-motion flag and measured observation interval.
* `latency_seconds` is null: endpoint frames cannot measure exact onset latency.
* `agency-*.png`: up to 24 diagnostic normalized frames with generic track IDs,
  evidence scores and green confirmed SELF / yellow competitors.
* `report.json`: agency log reference, diagnostic frame index, per-action agency
  snapshot and existing provenance, review frames and episode-end evidence.

Taught recognition and center proposals remain available. Causal labels are
not automatically promoted into human-confirmed sprite knowledge. Diagnostic
frames can support later appearance learning after the live identity is checked.

## Next Raspberry Pi test

Use one bounded game before running a marathon. On Charlie:

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git status --short
git fetch origin
git switch feature/agency-first-self
python -m pytest tests -q
mkdir -p robotron-runs
run_dir="robotron-runs/agency-first-$(date +%Y%m%d-%H%M%S)"
set -o pipefail
PYTHONPATH="$PWD" python -m experiments.ppal.play_robotron \
  --seconds 20 --focus 1.30 --arm --output "$run_dir" \
  2>&1 | tee "$run_dir.console.log"
tar -czf "$run_dir.tar.gz" "$run_dir" "$run_dir.console.log"
```

Stop if `git status` shows source changes you need to preserve before switching.
The documented backup and simulation log need not be deleted. Reuse the focus
value that produced the best current image if it differs from 1.30. Use
`--recalibrate` if the viewing position changed; saved calibration remains the
existing default, not proof that a moved camera is aligned.

Return the `.tar.gz` and your observed official score. Describe whether he moved
and fired, whether the green SELF was actually the player, and what happened
at death/respawn. A phone video is useful if convenient; there is no new continuous
video recorder in this change. Score remains unmeasured until supplied by a
reliable source. Synthetic success is not live success or evidence of improved
learning, and this change does not turn the fixed policy into an adaptive learner.

## Validation

Baseline: 180 existing tests passed with localhost mock-controller access.
Final integrated suite: 214 tests passed (34 new cases); `git diff --check` and
the live runner CLI import/help check also passed.
New tests cover appearance/center confounds, tied responders, delayed followers,
neutral continuation, mines, occlusion, new IDs/crossings, death/reset/respawn,
reversal, unknown control data, global motion, reinforcement and contradiction.
The armed runner is exercised with a deterministic fake camera/controller,
including a wrong PLAYER appearance, a respawn elsewhere and camera failure.
No independent camera recordings were present in the checkout, so validation
against recorded real play remains pending alongside the live test.

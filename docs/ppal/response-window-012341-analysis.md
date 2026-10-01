# response-window-20261001-012341: agency works, policy deliberately idles

Next experiment is superseded by [BODY/FIRE exploratory bootstrap](body-fire-bootstrap.md).

This archive ran 4e29db2. Alex observed a small rightward step after an initial
death, then stillness and further deaths. The logs explain this without assuming
that successful SELF acquisition means successful autonomous play.

## Exact observed behavior

Fresh calibration succeeded at 7.7px jitter. Agency acquired **track 22** at
sample 14 (.74 confidence, runner .18), bound it to SELF, and began the 20-second
policy window. It lost confirmation at sample 32, then reacquired **track 225**
at sample 48 after one missed policy observation. The new explicit response window
therefore works on real Pi evidence, not only the previous offline counterfactual.

The run executed **40 policy decisions plus one reacquisition tick**. Every one
of those 40 decisions is **STAY / NONE**, reason `no current rescue target`.
The small visible step is consistent with discovery/recovery probes, not a normal
movement decision. No policy firing occurred. Controls were receiving precisely
the idle actions the policy chose; this archive is not evidence of ignored normal
movement commands. Physical deaths beyond the logged loss are Alex's observations;
the system did not individually identify/count all of them.

There were zero recognized rescue targets in all 40 decision worlds. Known threats
were present in 14 of them, but none triggered the existing close-threat branch.
The policy's remaining branch was rescue-only: no rescue means hold. UNKNOWN
objects were omitted from the planner entirely. Over all 77 samples, semantic
labels were 1,457 UNKNOWN / 1,569 detections (92.9%), 83 grunt, 14 red circular
enemy, 14 mine and one player. This does not mean the camera failed to see those
objects or that all UNKNOWNs are enemies; their physical tracks exist.

Exact tracking replay reproduces **77 samples / 1,569 detections / 246 IDs**,
zero assignment mismatches. There is no new evidence here requiring another
association algorithm or lower SELF confidence gates. Uncertain semantics remain
a separate limitation. After death, a stationary associated identity cannot be
certified forever from stillness alone; subsequent motion evidence and current
physical continuity remain important. No death rules were hardcoded in tracking.

## Score is now independently useful

Initial retained raw HUD frames read **200**; baseline 200 is accepted at sample 2.
The observer accepts **300 / +100** at sample 52 and retains 300 to sample 77.
The final full-camera review JPEG visibly shows 300, and an offline reader returns
300 at confidence 1.0 with P2=None. Final score therefore has independent pixel
support. There is no justification to credit the idle policy with kills/rescues or
claim the precise event that earned the increase; probing, rescue contact and
other transitions require their own causal evidence.

All 77 score samples were processed, zero errors/drops. Background processing
was 0.940s total, ~15ms maximum. Score remains observational and does not select
or gate any control, SELF decision or episode termination.

A retention limitation remains in this archive: only the first 16 score originals
were saved, so the accepted change's **exact sample-52 raw HUD** is unavailable.
The final frame corroborates its ending value, not its precise onset. The repair
now retains first 16 samples, up to 16 later accepted-change samples and the final
sample, bounded to at most 33 originals. Extra retention happens in the existing
background worker; encoding still occurs after controls close. Omitted changes
are counted if the budget is exceeded. Score recognition/temporal thresholds,
P1/P2 independence, monotonicity and UNKNOWN behavior are unchanged.

## Narrow repair: agency must not depend on successful semantic recognition

`WorldState.unresolved` now carries current unlabeled physical objects, with the
same generic `sprite_<track ID>` IDs and positions used for known roles. SELF is
excluded. A later semantic class change does not rename the physical object.
Shadow prediction preserves these objects and their motion across role changes.
No second live tracking or association pass is introduced.

The existing rescue and close-threat tactics remain. When no rescue is available,
the hindbrain chooses a bounded open-space step using route and endpoint clearance
from recognized threats and unresolved occupancy. UNKNOWN does **not** become
hostile, safe, rescuable or a shooting target. Firing may target the nearest
recognized threat even when it lies beyond the old panic radius. With no known
threat, firing remains NONE. Genuine non-alive worlds still hold controls neutral.
This is a basic control fallback, not score-driven strategy, a learned consequence
model or a guarantee of collision-free movement. A nearby family member can be
missed as a rescue while its class remains unresolved.

The next report includes unresolved counts, planner object IDs/positions by role,
intent and planning mode so decision reasons are directly reviewable. All camera,
tracker, agency/probe timing, controller pulses, SELF loss/recovery and game-state
classification are unchanged. `run_camera.py` is untouched.

On the exact **recorded** 40 decision worlds, the repaired policy requests
movement in 40/40 and firing in 14/40. These are offline decision checks on fixed
old worlds, not a dynamic counterfactual: they do not predict survival, points or
what the enemies would do after those movements. Discrete 80ms neutralized pulses
and observation cost still limit duty cycle; this idle-policy archive cannot
establish how adequate that cadence is for sustained movement. The next run
must measure that under actual non-idle commands before another timing repair.

## What earlier repairs did and did not establish

| Evidence | Conclusion |
| --- | --- |
| Original play-024128 / a70149c | Swallowed background/fragmented player histories motivated the candidate and generic association repair |
| Repaired tracking-034659 / a7a5ab2 | Likely player continuity improved; shifted response supported fresh sensor capture |
| tracking-score-232827 / 4ffb951 | False unmatched ambiguity and wrong HUD geometry were demonstrated separately; live timing still needed a response window |
| exposure-010300 / 2188d5a | Calibration/color improved; player 117 persisted but second-frame response was discarded |
| Current response-window-012341 / 4e29db2 | Real acquisition and reacquisition succeed; final HUD 300 is supported; normal policy chooses only idle actions |

Thus the current failure is downstream of successful agency: semantic filtering
and a missing no-rescue tactic. Stable SELF is necessary but does not by itself
make the old rescue policy actionable.

## Validation and one next experiment

**300 tests passed.** New regressions use all 40 actual planner worlds, verify
movement without semantic promotion, geometry bounds, no shooting at UNKNOWNs,
non-alive neutrality, unchanged physical ID/motion across semantic role changes,
actual final HUD 300 and late-change/final raw retention. Existing armed runner,
delayed-response, exact historical replay, score and tracking tests pass.
Broad semantic recognition and broad HUD reliability remain incomplete; older
score-corpus UNKNOWN limitations are unchanged. No long marathon is justified yet.

Release the preview camera, retain this unobstructed framing and start in attract
mode. Run once, with a 20-second policy window after acquisition:

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git fetch origin &&
git switch feature/agency-first-self &&
git pull --ff-only origin feature/agency-first-self || exit 1
python -m pytest tests -q || exit 1
mkdir -p robotron-runs
run_dir="robotron-runs/open-space-$(date +%Y%m%d-%H%M%S)"
set -o pipefail
PYTHONPATH="$PWD" python -m experiments.ppal.play_robotron \
  --seconds 20 --focus 1.30 --recalibrate --arm --output "$run_dir" \
  2>&1 | tee "$run_dir.console.log"
if [ -f "$run_dir/agency.jsonl" ]; then
  python -m experiments.ppal.replay_tracking "$run_dir/agency.jsonl" \
    --output "$run_dir/tracking-replay.json"
fi
tar -czf "$run_dir.tar.gz" "$run_dir" "$run_dir.console.log"
```

Return **robotron-runs/open-space-<timestamp>.tar.gz**, even on failure. Observe
actual movement/firing, identity loss/recovery, deaths and official score. The
next record must distinguish selected actions from delivered movement and
consequences. Score readability remains unnecessary for play to continue.

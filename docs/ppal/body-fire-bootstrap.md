# BODY/FIRE exploratory bootstrap

The preceding [response-window live run](response-window-012341-analysis.md)
proved BODY acquisition/reacquisition and then revealed an idle policy. Its
40 normal actions were STAY/NONE. "No rescue target" meant **no family member
was recognized**, not a policy prohibiting rescue. Most objects were visible
but semantically UNKNOWN. The repaired open-space fallback retains those objects
as occupancy and makes behavior possible without lowering class thresholds.

Alex also identified a genuine limitation: the available FIRE actuator was not
being explored during bootstrap, and fully certified BODY identity was required
to begin normal play. Certification was a manually chosen heuristic with three
hits, multiple directions, reversal, stops and separation—not a learned theorem
about what evidence Charlie requires. Those diagnostics should not all be a
prerequisite for collecting ordinary experience.

## Existing plumbing versus missing evidence/learning

Available now: independent BODY/FIRE vocabulary including simultaneous actions,
controller send/ACK/pulse/neutral timing, fresh camera observations, one generic
physical tracker with births/misses/paths/ambiguity, raw arena pixels and raw HUD
score evidence, all on the monotonic timeline. No second tracker is needed to
record anonymous FIRE-related physical effects.

Missing: **real FIRE observations in these current live runs**; reliable retention
and association of fast/thin effects; causal differentiation of FIRE-related
births from unrelated births; an uncertainty-aware model of launch/render latency;
reverse-trajectory origin estimates and their coincidence with a BODY hypothesis.
The current detector rejects components smaller than 8 pixels or 3px in either
dimension, and observation cadence/travel gates may miss fast projectiles. Those
limitations must be measured on actual FIRE evidence before changing segmentation
or speed limits. A commanded FIRE direction alone is not observed projectile
motion, and a new nearby track alone is not a certified projectile.

The proposed multi-direction reverse-ray convergence is a useful causal
hypothesis. We have **not** implemented a fixed Robotron projectile model or
invented FIRE corroboration from the BODY-only archive. Establishing thresholds
and declaring combined localization proven without FIRE data would be pre-solving
what Charlie should instead investigate. There is no new FIRE-origin gate.

## Minimal, explicitly experimental mode

`--bootstrap-body-fire` enables the next bounded investigation:

1. One FIRE-only pulse, with BODY neutral, records two fresh effects observations
   as unmeasured BODY evidence. FIRE is exercised before certified SELF exists.
2. BODY direction probes may fire simultaneously in separately commanded
   directions. Both actuator commands, observation phases and controller timing
   are retained with generic births/trajectories and raw pixels. No sprite
   appearance, hue or enemy rule determines agency.
3. A unique current BODY candidate with two directional response hits, existing
   separation and no contradictions can enter ordinary play **provisionally**.
   It need not first satisfy full certification. This is an explicit experimental
   heuristic, not a claim of combined BODY/FIRE causal confirmation.
4. Ordinary movement keeps testing it. A contradictory provisional response,
   unresolved tie, missing identity or global motion withdraws the hypothesis.
   Existing full BODY confirmation can still be earned during ordinary play.
5. When no recognized shooting target exists, the experimental open-space
   fallback explores N/E/S/W FIRE commands alongside movement. It does not relabel
   UNKNOWN objects as enemies or interpret shooting as beneficial by definition.

The records distinguish `controlled_track_id` and `identity_status`
(provisional/confirmed/unknown) from `agency.self_track_id`, which remains None
until the original full confirmation conditions are met. Terminal output calls
a provisional location a **hypothesis**. Ambiguous evidence remains UNKNOWN.
Score channel P1 remains explicit and independent of this status.

Baseline mode remains available without the flag for comparison. The one generic
tracker, per-frame association, score worker, camera controls, pulse bounds and
termination logic are preserved. `run_camera.py` is untouched. Score remains the
official performance metric and observational evidence; it does not drive policy.
The fixed FIRE exploration schedule is a data-collection policy, not learned
strategy or a hardcoded claim about environmental consequences.

This is deliberately not yet FIRE-only SELF localization. The new run should
show whether generic birth/motion evidence can support origin convergence, whether
combined responses reject misleading BODY candidates, and what sampling plumbing
is actually missing. No additional elaborate SELF gate is introduced to pass it.

## Validation and next run

**304 tests passed.** New tests verify independent and simultaneous actuator
commands, provisional gameplay before full certification, online confirmation,
ambiguity/contradiction withdrawal, UNKNOWN-preserving FIRE exploration and the
actual armed runner under delayed rendered response with experimental mode.
These tests verify plumbing and status handling; they do not prove projectile
origin inference or live FIRE consequences. No hardware FIRE archive exists yet.

Use exactly one next run, not the earlier no-flag command. Begin in attract mode
with the same unobstructed camera framing and the preview server stopped:

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git fetch origin &&
git switch feature/agency-first-self &&
git pull --ff-only origin feature/agency-first-self || exit 1
python -m pytest tests -q || exit 1
mkdir -p robotron-runs
run_dir="robotron-runs/body-fire-bootstrap-$(date +%Y%m%d-%H%M%S)"
set -o pipefail
PYTHONPATH="$PWD" python -m experiments.ppal.play_robotron \
  --seconds 20 --focus 1.30 --recalibrate --bootstrap-body-fire --arm \
  --output "$run_dir" 2>&1 | tee "$run_dir.console.log"
if [ -f "$run_dir/agency.jsonl" ]; then
  python -m experiments.ppal.replay_tracking "$run_dir/agency.jsonl" \
    --output "$run_dir/tracking-replay.json"
fi
tar -czf "$run_dir.tar.gz" "$run_dir" "$run_dir.console.log"
```

Return **robotron-runs/body-fire-bootstrap-<timestamp>.tar.gz**, including on
failure. The policy window is 20 seconds after obtaining a current hypothesis;
bounded preflight and probes add time. Observe actual movement, firing/projectile
visibility, provisional/confirmed transitions, deaths and official score. The
point is to collect action/consequence evidence, not declare understanding in
advance. Do not require score or FIRE recognition for continued play.

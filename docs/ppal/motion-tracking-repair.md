> Historical first-run diagnosis and repair. The separate second-run analysis and capture repair are in [second-pi-run-and-capture-timing.md](second-pi-run-and-capture-timing.md).

# First Pi agency run: diagnosis and tracker repair

Source: `play-20260930-024128`, running `a70149c`. The recorded knowledge hash
matches the checkout. Its dirty-worktree flag alone does not identify what was
dirty. It failed before planning (`ticks: 0`), after twelve movement/neutral
observations. This result has no measured score.

## What the run establishes

* East produced displacement `(6.640625, -1.041667)`, direction agreement `.987920`.
  Alex physically observed the actual player move. Controls are reaching the game.
  The log alone does not prove that every command-correlated track is the player.
* Candidate counts changed from 13 to 33; many were UNKNOWN. Confidence peaked
  at `.28`, so the `.72` agency gate correctly abstained.
* The original candidate mask was `max(R,G,B) > 145`. The blue screen background
  itself sits near that threshold: median blue is 143 in `startup-000.png`.
  The detector yielded only three regions in that original frame, including a
  `(5,5,635,475)` region with 143,782 pixels. It swallowed sprites and supplied
  a spurious center at `(50,50)`. Other startup frames alternate between large
  merged regions and many background fragments. Transition animation is visible.
* The old association used only last-position distance, a seven-unit gate and
  comparisons against all local alternatives, including already-explained rivals.
  There was no velocity prediction. Ordinary movement could thus become new IDs.
* Observations were sparse endpoints. The logged command/read/detection intervals
  were `.137` to `.194` seconds; PNG encoding between observations was outside
  those intervals and added further unobserved time. Exact total frame spacing
  and sensor exposure times were not recorded. The tracker was not being reset
  on every probe; churn arose within a persistent tracker.

Therefore this is both a candidate-generation problem and a temporal-association
problem. The proposed list of IDs is not a proven player lineage. Some matching
responses are small centroid jitter on nearly stationary objects, and followers
also respond in superficially similar directions. No blind agency stitching or
lower confirmation threshold is justified.

## Repair

Candidate segmentation uses local per-channel contrast against a 31-pixel median
background, retaining bright colored sprites (including blue) while rejecting
smooth screen illumination. Large borders/transition components are excluded
rather than assigned a misleading center. The existing taught feature vectors
and examples are unchanged. In the original startup frame this exposes 23 local
regions instead of three and removes the whole-screen region; this is not a
claim that all 23 are physical sprites or that startup animation is gameplay.

`SpriteTracker` now maintains position, filtered velocity, elapsed-time history
and changing semantic observations. It uses a constant-velocity prediction,
plausible travel gates, soft box-size costs and a penalized position fallback for
stops/turns. It performs one-to-one minimum-cost assignment over the whole frame.
An alternate whole-world assignment within `.5` cost is ambiguous, including
three-object cyclic ambiguities. Involved old IDs are quarantined; unresolved
successors receive fresh IDs. A growing missing interval cannot make forcing a
far-away match preferable to leaving the old object missing.

A small Hungarian solver avoids a new scipy dependency. Dual lower bounds skip
unnecessary alternate-world solves. In the limited 12-frame endpoint replay,
median association time here was roughly 7 ms, with a maximum near 26 ms. These
are host measurements, not Pi frame-rate guarantees; per-sample processing time
is now logged so the Pi result can expose any slowdown.

Live discovery, quiet startup observations, normal gameplay and recovery all feed
the same generic tracker. `PersistentSelfTracker` binds/follows already-assigned
IDs rather than repeating association on the same frame. Gameplay targets and
threats use `sprite_<track_id>` directly; a label/role change does not rename the
physical object. UNKNOWN processes still retain trajectories in the generic log.
The old semantic tracker remains available to other callers, but does not run a
second association pass in armed `play_robotron`.

Agency remains subordinate to neither appearance nor arbitrary ID continuity.
A unique nearby successor of previously confirmed SELF may receive a bounded
prior only after its own direct response. It inherits **no** hits, stops or
reversal facts and must still satisfy the original confirmation requirements.
Genuine crossings with multiple equally plausible successors do not get that
shortcut. This is complementary protection, not a substitute for generic tracking.

Manual focus, calibration flags, screen-state classification, bounded control
pulses and the separate robust legacy terminal challenge remain. Tracking loss
or generic discovery failure never becomes a new game-over rule.

## Evidence, replay and limits

The first run's 12 endpoint lists are committed as a geometry fixture, plus one
original unannotated startup PNG. The lists have rounded centers but no boxes,
pre-command anchor or exact capture timestamps. With equal dummy box sizes and
intervals estimated from the reported control/read durations, the old tracker
creates 131 IDs from 272 detections; the new one creates 105. The isolated visible
stationary object near `(33.5,83.3)` now keeps one ID. This is partial evidence,
not a replay of the physical player, and not proof of live acquisition success.

Next-run `agency.jsonl` records every processed observation, including pre-command
anchors, detector index→track assignments, centers, original boxes/pixel counts,
soft class scores, processing-completion monotonic time, tracker configuration,
velocity predictions, costs, margins, rejection counts/nearest rejected choices,
created/matched/missed/ambiguous/expired events, agency evidence and lineage
proposals. Margins can be conservative lower bounds; they are not probabilities.
Exact sensor exposure/onset latency is still unknown. `tracks.json` contains
trajectories and changing label histories.

Up to 96 unannotated normalized playfield frames and 24 annotated diagnostics are
buffered in memory; images are encoded after controller closure. Later samples
still have complete numeric tracking inputs even after the image cap. This avoids
making diagnostic image saves part of the movement experiment's observation gap.

Exact tracker replay (no camera or controller):

```bash
python -m experiments.ppal.replay_tracking "$run_dir/agency.jsonl" \
  --output "$run_dir/tracking-replay.json"
```

This should report `assignments_match: true` with the same code/configuration.
The replay CLI explicitly rejects legacy logs that lack complete inputs.
Matching replay output establishes reproducibility, not correct physical identity.

## Next bounded Raspberry Pi experiment

Do one game before any marathon. Keep the same physical view if it has not moved.
If the camera moved, add the existing `--recalibrate` option to the live command.
`1.30` is the requested focus from the previous run; use the known best current
focus if that differs.

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git status --short
git fetch origin
git switch feature/agency-first-self
git pull --ff-only origin feature/agency-first-self
python -m pytest tests -q
mkdir -p robotron-runs
run_dir="robotron-runs/tracking-repair-$(date +%Y%m%d-%H%M%S)"
set -o pipefail
PYTHONPATH="$PWD" python -m experiments.ppal.play_robotron \
  --seconds 20 --focus 1.30 --arm --output "$run_dir" \
  2>&1 | tee "$run_dir.console.log"
python -m experiments.ppal.replay_tracking "$run_dir/agency.jsonl" \
  --output "$run_dir/tracking-replay.json"
tar -czf "$run_dir.tar.gz" "$run_dir" "$run_dir.console.log"
```

If source changes prevent a fast-forward, preserve them and report the Git
message; do not reset or delete them. Existing untracked backup/log files need
not be removed. Return the `.tar.gz`, observed official score if a real gameplay
run happened, and whether the green SELF box followed the actual player. Note
whether the probes ended in normal movement/firing and what happened at respawn.
If acquisition still fails, the full archive is valuable even without a score.

Validation: 244 tests pass, including 30 cases added in this repair. Coverage
includes many moving objects, sparse/unequal intervals, stops/reversals, followers,
resolved crossings, unresolved merges/cyclic ambiguities, no old SELF-ID reuse,
soft label changes, same-frame binding, exact replay, candidate background
rejection, real-run fixtures, and armed runner respawn/controller cleanup. Real
camera acquisition and physical identity accuracy remain pending the next test.

## World-model boundary for later work

Physical track identity, semantic class, behavioral state and threat/reward role
remain separate concepts. Class changes are observations attached to the same ID,
not commands to destroy its history. Large unresolved geometric changes can still
require new identities; this tracker does not claim to solve every transformation.
A track creation is an observation hypothesis, not proof of a physical birth, and
expiration is loss of visual evidence, not proof of death.

Alex's supplied game context motivates future learning from these histories:
independent eight-direction projectile streams; shaping pursuit into interception
lines; Hulk push/deflection and projectile blocking; persistent generators and
nearby descendant births; Brains interacting with and transforming family;
and distinguishing hostile contact/death from family contact/rescue/score reward.
None of these rules is encoded into association. The logs preserve raw persistence,
label changes, positions and observation events so later interaction models can
compare alternative causal explanations. Luring, projectile effects, generator
prioritization and transformation learning are deliberately outside this repair.

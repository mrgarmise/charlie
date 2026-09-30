# Analysis and repairs from tracking-score-20260930-232827

This archive ran `4ffb951`, the fresh-exposure implementation with passive score
instrumentation, and ended before normal autonomous gameplay: SELF acquisition
failed, policy ticks were zero, and controls closed neutral. Alex independently
observed the actual player move left/right/down, then stand still and die through
respawn. No normal planner score can be claimed. Score increases remain reward evidence
even when their preceding action is unknown; the log does not invent attribution.

## Separate comparisons

| Evidence | Original play-20260930-024128 / a70149c | Prior tracking-repair-034659 / a7a5ab2 | New tracking-score-232827 / 4ffb951 |
| --- | --- | --- | --- |
| Player continuity | Fragmented histories and swallowed-background candidates motivated repair | Likely player ID 96 retained over all probe endpoints | Likely player ID 9 retained across samples 6–15; reappearance at 18 is new ID 258 after death/transition |
| Direct control evidence | At least an east response; physical movement observed | Motion appeared almost entirely in following neutral samples | East/west/down now earn correctly signed command evidence; residual motion remains in neutral |
| SELF outcome | UNKNOWN, zero policy ticks | UNKNOWN, zero policy ticks | UNKNOWN, zero policy ticks |
| Timing provenance | Endpoint duration; exposure onset unavailable | Cached-frame phase pattern strongly implicated | Same-request sensor/exposure metadata; exposures start 4–64 ms after execution return |
| Score | Unmeasured | Unmeasured | 18 passive observations, all unresolved with the saved geometry |

The contrast-based candidate detector no longer swallows the whole blue arena
as one sprite. The repaired association maintains this likely player during the
initial control experiment. It does not mean every ID is a correct physical
object, or that all fragmentation has been solved.

## Why 660 detections became 259 IDs

Exact original replay matches **18 samples, 660 detections, 259 created IDs** with
zero mismatches. The original source/settings remain reproducible through the
legacy association version.

- Initial sample 1 creates 20 IDs.
- Startup/transition sample 2 has 127 regions and creates 110 IDs.
- Transition sample 16 has 101 regions and creates 87 IDs.
- Sample 17 has 62 regions and creates 13 IDs.
- All remaining frames together create 29 IDs.

Those three dense frames account for **210/259 (81%)** of creations. The recorded
originals show visual transition/fragmentation; new regions cannot be equated to
new physical enemies. Fan edges/occlusion and the wrong crop contaminate candidate
geometry, but the fan does NOT hide the central likely player during the initial
probe endpoints and does NOT cover the HUD.

A separate implementation bug inflated ambiguity events: the Hungarian matrix
let all tracks exchange identical unmatched columns. Alternate solutions could
permute these dummy assignments, quarantining unrelated invisible identities.
New version 2 gives each track its own unmatched column and excludes rows whose
real edges cannot beat unmatched cost. It retains globally optimal one-to-one
physical assignment and abstains at actual unresolved crossings.

On the identical recorded detections, version 1 emits 168 ambiguity events and
259 IDs; version 2 emits **23 ambiguity events and 258 IDs**. This is a repair of
false ambiguity and unnecessary solver work, NOT elimination of flash fragments.
Host replay was about 2.4 seconds for legacy association versus about 0.26 seconds
for the initial private-dummy version; this is not a Pi speed guarantee. Pi
association in the original run peaked at 2.089 seconds in sample 17. The next
run retains full processing timings so the actual benefit can be measured.

Logs now record association_version=2; replay interprets older absent versions
as version 1. No second association pass is introduced.

## Why responsive movement did not become SELF

ID 9's east displacement at sample 7 is (+.9375,-.10417); sample 8's neutral
endpoint still changes (+.70313,+.3125). West at sample 9 changes
(-1.17188,-.20833); neutral 10 changes (-.39063,0). Down at 11 changes
(-.07813,+.41667); neutral 12 changes (0,+.52083). Each neutral motion exceeds the
unchanged .35 stop gate and removes the .18 hit confidence. Subsequent north/east
samples are nonresponse or off-axis near death/transition. Thus three early
signed responses never accumulate sufficient stops/confidence.

Camera metadata shows genuine new exposures after execution return, including
66.655 ms exposure time, roughly 67.106 ms frame duration, and lens position 1.30.
The first cached-frame defect is improved. This archive does NOT identify whether
remaining endpoint residual is game/transport/display response delay, animation,
rolling exposure, or a combination. Foreground median/mean anchor experiments did
not remove the measured residual, so moving centroids or lowering identity gates
would be unjustified.

A bounded **neutral handoff observation** now follows each movement endpoint.
It goes through the SAME generic tracker with command=None, so it neither earns
a stop nor receives a contradiction. The next fresh neutral interval is measured
normally with all original stop, reversal, direction, lead and confidence gates.
This avoids asserting that delayed response is itself evidence of failed agency.
It does not hardcode a time delay or relabel earlier commands. A continuing
follower still fails the measured neutral test. Actual Pi acquisition remains
unproven; continued motion in that second neutral interval will still abstain.

Armed startup can proceed to agency after three spatially stable generic views,
without waiting the entire center/appearance watch merely because the player is
not at the old crop's center. This readiness never declares SELF and does not
filter candidates by taught identity. Every physical identity still needs probes.
Deadlines remain checked before further pulse/handoff observations.

## Independent score failure

The archive says calibration_mode=saved. Its full-camera images show a materially
changed view: arena starts near raw (525,70), the right/bottom arena corner is
clipped, and the fan hides lower-left geometry. The saved calibration used by the
repository maps the HUD reader ABOVE the actual score. Rectifying with that
geometry yields a strip of wall/bezel with confidence zero. This explains the 18
unresolved readings: no errors or dropped samples were reported. HUD worker cost
was 0.161 seconds total, max 0.019 seconds; there is no evidence it caused the
multi-second association stalls.

All 16 saved full-camera PNGs were inspected. Samples 17/18 have score records but
no saved full-camera PNG; do not claim visual validation of those two. The saved
HUD shows preceding score 1900 in sample 1, new-game zero in 2–4, and 100 in 5–16.

Manually estimated border geometry is useful ONLY for diagnostic HUD replay;
it is not trustworthy automatic full-board calibration and is not promoted to
the live calibration. Correcting that geometry exposed another bug: horizontal
morphological closing joined the serif 1 to the following 0, and seven-segment
classification read 100 as 200. The repair preserves horizontal character gaps,
closes only vertical stroke gaps, recognizes the photographed central-stem serif
1, preserves digit confidence through whole-word recognition, and rejects weak
5/9 ambiguity and truncated left fragments. Hue/saturation are never used.
Inferred 7 retains reduced confidence.

With diagnostic geometry, all 16 originals now yield their visible numbers.
Temporal replay with confirmed baselines yields UNKNOWN on initial 1900,
confirmed zero at sample 3 and **+100 accepted at sample 6**, then stable 100.
Baseline confirmation is enabled only for the live observer; generic tracker
API defaults remain compatible. This prevents one old pre-START display from
locking a new episode at its higher score. Missing frames do not reset state;
accepted values remain monotonic. There is no score-to-policy feedback.

Older labeled raw JPEG corpus validation improves from 3/14 to **4/14**; the
remaining ten return UNKNOWN. Brightness/shape robustness is still limited.
The new 16-frame result is diagnostic validation on an estimated geometry, not
proof of general real-camera performance or correct automatic preflight.

## Tests and next experiment

Full suite: **284 passed**. New regressions cover exact historical replay,
actual-vs-dummy ambiguity, all new-version recorded inputs, delayed neutral
handoff with a continuing follower, full-camera zero/100 reader inputs,
pre-START baseline confirmation, and rejection of the obstructed/clipped full
board. Representative camera fixtures are JPEG reencodings of the original PNGs;
original PNGs were used separately for diagnostic validation.

`run_camera.py` is untouched. The one generic tracker and passive score worker
remain separate. Report now includes exact calibration corners/output dimensions;
score evidence includes handoff phase and latest controller timing context.

Before ONE new game: remove the fan and re-aim/back up the camera until ALL FOUR
arena corners and the HUD fit in the raw image. The current archive is sufficient
for diagnosis; no repeat of the obstructed configuration is needed. Use explicit
fresh calibration in the next command. If geometry fails, return its archive and
stop; do not bypass calibration with the old saved crop.

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git fetch origin &&
git switch feature/agency-first-self &&
git pull --ff-only origin feature/agency-first-self || exit 1
python -m pytest tests -q || exit 1
mkdir -p robotron-runs
run_dir="robotron-runs/tracking-hud-fix-$(date +%Y%m%d-%H%M%S)"
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

Return `robotron-runs/tracking-hud-fix-<timestamp>.tar.gz`, including on failure.
Observe actual player tracking, normal movement/firing after discovery, deaths,
and the official score. The 20-second policy window starts after acquisition;
setup/probes add time. No score recognition is required to play.

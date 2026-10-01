# exposure-calibration-20261001-010300: stable player, discarded delayed response

The archive ran 2188d5a. Fresh calibration succeeded (six stable views, 6.8px
jitter), then discovery failed. There were 27 observations, zero normal policy
ticks and no confirmed SELF. Controls closed neutral. Alex's glasses observation
is useful appearance context; the failure here is not loss of the player ID.

## What exposure and tracking actually improved

The pre-START sweep selected -3 EV and locked actual exposure/gain. Its evaluated
-3 frame used 20.9ms exposure and ~1.50 analogue gain, versus 66.7ms / ~15.75 at
0 EV. Before lock, AE adjusted the selected setting again: subsequent gameplay
requests report ~28.9ms / ~1.50. This distinction is visible in the metadata,
not concealed behind a claim that the requested EV was a fixed shutter value.

During the sweep, locally contrasting detail's clipped-channel fraction declined
from 65.5% to 18.3%; fully white-clipped fraction declined from 31.7% to zero.
These are changing attract-scene observations, not a controlled radiometric
experiment. Original RGB now visibly retains sprite/face colors. AWB remains
automatic; reported blue gain is still ~3.5–3.9 and accurate color calibration is
not established. Fresh geometry and readable full-color evidence are established.

Exact replay reproduces **27 samples / 646 detections / 140 IDs**, zero mismatches.
**132 IDs exist before the first command**: 76 births in transition sample 3,
19 in sample 5, and other initial/settling samples. Only eight additional IDs
appear during the six movement/neutral probes. Physical births cannot be inferred
from these transient detection regions. There are 20 ambiguity events; association
peaks at ~54ms, versus the earlier run's 2.089s peak on different inputs. This is
a useful observed improvement, not a controlled Pi benchmark.

The visually central, command-responsive player is **track 117 continuously from
sample 6 through sample 27**. It is not fragmented across the discovery experiment.
The score worker processed all 27 samples, zero errors/drops, total 0.236s and
maximum ~10ms, in its separate background worker. Score does not gate SELF.

## Why a continuous, responsive player earned zero command hits

Every movement's first fresh post-pulse image still shows the previous position.
Every second image shows the corresponding action. The old protocol judged the
first image and marked the second `neutral_handoff_unmeasured`, discarding the
actual response. Neutral endpoints thereafter are stationary within the gates.

| Command | First endpoint / discarded second endpoint | Player displacement at second endpoint from pre-command reference | Subsequent neutral motion |
| --- | --- | --- | --- |
| E | 10 / 11 | (+1.016, 0) | (+.078, 0) |
| W | 13 / 14 | (-1.484, 0) | (0, 0) |
| S | 16 / 17 | (+.078, +2.396) | (0, 0) |
| N | 19 / 20 | (0, -1.667) | (0, +.104) |
| E | 22 / 23 | (+1.016, -.312) | (0, 0) |
| W | 25 / 26 | (-1.484, 0) | (0, 0) |

Coordinates are normalized arena units. First endpoints are roughly 86–116ms
after controls-ready ACK timing; second endpoints are 321–351ms after it. Fresh
sensor requests cannot guarantee that the TV has rendered the action yet. The
record brackets response observation but cannot isolate RetroArch/input/display
latency or identify its exact onset. This timing repair is justified by **this
run's six consistent response pairs**, not the first run's missing timing data.

The implementation now records the first endpoint as unmeasured and evaluates
the second endpoint against explicit pre-command positions. It records window
origin/end times, command, intermediate frame and reference positions. An identity
absent from the intermediate frame is excluded: no motion evidence is accumulated
across an occlusion. The following STAY interval remains a separate stop test.
All confidence, separation, hits, reversal and stop gates remain unchanged.

Normal policy action feedback uses the same bounded two-endpoint measurement;
otherwise its first unchanged frame could immediately discard the acquired
identity again. This adds one observation to movement feedback, with measured
window cost; it does not extend the command pulse or choose another action.
There remains exactly **one generic association per consumed frame**. No second
tracker, association rerun, sprite-role gate or fixed-color SELF template exists.

Offline replay of the actual recorded input pairs through the new live discovery
code confirms ID 117 after E/W/S and the third stop, at sample 18. Its first
qualified snapshot is sample 17, confidence .74. Replaying all six directions
as an offline counterfactual yields six hits, six stops, zero contradictions,
confidence 1.0. This is not a claim that the archived live run acquired SELF;
it did not. The next Pi run must validate the changed protocol and policy feedback.

## Separate score failure and repair

All 16 retained full-camera HUD originals visibly show **100**, outside the
arena. Fresh calibration now supplies the correct geometry. The first purple
100 produced a .90-confidence proposal; later dim cyan digits were erased by the
fixed maximum-channel >=200 cutoff. Temporal tracking correctly refused to accept
a baseline from that one isolated proposal, so all 27 accepted scores remained
UNKNOWN. There was no score-worker exception and no dependency on SELF failure.

The reader retains its conservative primary path. When that path finds no number,
a bounded relative-intensity fallback requires the **same confident digit string
at three distinct thresholds**. It uses shape and maximum-channel luminance,
never hue, and abstains on disagreement. This avoids choosing a convenient
threshold: individual bad thresholds on this run can confidently misread 100 as
300. No policy receives score reward.

On the 16 original PNGs, the revised reader yields **100 at .90 confidence in
16/16**, with absent P2=None. Temporal replay confirms baseline 100 on the second
observation and creates no fabricated +100 reward: the run has no observed zero
baseline or score increase. Older labeled real-camera corpus remains **4/14
correct, 10 UNKNOWN**, no new incorrect accepted number. The validator therefore
still exits nonzero. Digit 7 still lacks a real-camera example and retains reduced
confidence. Broad reader reliability is not claimed.

## Glasses and historical comparison

The tracked player's head/face region changes orange/cyan/purple/blue across
facings/animation. These captures do not establish that one hue or eyewear pattern
uniquely distinguishes it from every other sprite. Such temporal appearance can
be useful soft metadata for future association/occlusion handling. It should not
replace physical identity or action-contingent SELF evidence. No glasses-specific
tracking rule is needed to repair this run: ID 117 already persists.

| Run | Established failure or improvement | Status now |
| --- | --- | --- |
| play-024128 / a70149c | Background-swallowing candidates and fragmented player histories | Contrast detection and generic association repair addressed these demonstrated defects |
| tracking-repair-034659 / a7a5ab2 | Likely player retained; response shifted into neutral endpoints | Fresh sensor capture added based on that second-run evidence |
| tracking-score-232827 / 4ffb951 | Player persisted initially; residual neutral motion, false unmatched ambiguity, incorrect saved HUD geometry | Private dummy assignments and neutral handoff added; this run demonstrates handoff was not yet sufficient |
| calibration failures / bce4e95 | No agency reached; good final PNG detectable, earlier views missing | Exposure preflight and complete attempt evidence now produce successful calibration |
| exposure-010300 / 2188d5a | Player 117 persists, color retained; response discarded in unmeasured second frame; dim HUD erased | Explicit response window and conservative dim-HUD fallback repaired; live confirmation pending |

## Validation and one next experiment

Full suite: **295 passed**. New tests preserve exact latest/historical association
replay, reproduce the old failure and new discovery using actual recorded pairs,
exclude identities missing mid-window, exercise delayed render through the real
armed runner and policy feedback, and confirm dim raw HUD reading/baseline and
threshold-disagreement abstention. run_camera.py remains untouched. Score remains
passive, non-gating and separate from perception/agency/planning/termination.

Release the camera preview server; keep this unobstructed view. Begin in attract
mode. Run exactly one 20-second policy experiment, with fresh camera preflight:

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git fetch origin &&
git switch feature/agency-first-self &&
git pull --ff-only origin feature/agency-first-self || exit 1
python -m pytest tests -q || exit 1
mkdir -p robotron-runs
run_dir="robotron-runs/response-window-$(date +%Y%m%d-%H%M%S)"
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

Return **robotron-runs/response-window-<timestamp>.tar.gz**, including on failure.
The 20-second policy window starts after discovery; bounded setup/probes add time.
Observe whether normal movement/firing starts after acquisition, whether SELF
persists, and the official score. No score recognition is required to continue.

# Observational score integration

The agency branch merges score branch `72f4958` with the physical-tracking repair
`a7a5ab2`. One generic SpriteTracker association pass remains authoritative.
Score never enters the world state, policy, SELF gates, or episode-end observer.
`run_camera.py` is untouched.

After tracking and agency telemetry are recorded, a nonblocking bounded queue
receives an independent copy of the full camera frame. The worker uses
RobotronScoreSystem with independent P1/P2 channels and explicit SELF=P1.
Unreadable images and exceptions produce unknown visual evidence while retaining
the last accepted monotonic belief. A fresh run/START creates fresh score state;
respawns and missing reads do not reset it. No additional new-game START is sent
inside this runner. No score recognition is required for gameplay.

`score.jsonl` links capture monotonic timestamps and agency sample numbers to
observed/accepted scores, read and accepted confidence, deltas, preceding action
and agency command, worker cost, copy/enqueue cost, and errors. Positive deltas
are temporal reward evidence only: confirmation latency, skipped samples and
multiple actions make single-action causal attribution uncertain. Baselines are
not rewards. `report.json` records accepted official score, channel summary,
worker timings, dropped samples and errors. Sixteen full camera PNGs are buffered
for HUD review and encoded only after controls/camera close. Existing normalized
tracking originals, exact replay inputs, and agency trajectories remain intact.

The queue may drop HUD samples rather than wait for the reader. Camera copying
and background CPU contention are not free; measure the recorded costs and
tracking capture cadence on Pi. Worker shutdown is bounded after neutralization;
`worker_finished=false` means score evidence may be incomplete.

## Validation and limitations

Full suite: 272 passed. Worker tests verify exceptions become unreadable evidence
and a blocked reader causes sample drops without blocking submission. Existing
armed runner tests still validate acquisition, respawn, shared physical IDs and
controller/camera cleanup. Synthetic HUD tests now pass after fixing overlapping
segment samples and grouping separated/merged glyph components. Recognition uses
brightness and geometry, never hue; inferred 7 retains reduced confidence.
Score channel windows exclude adjacent life icons.

All 14 original labeled full-camera JPEGs were retrieved. The repository's saved
calibration does not match this older camera view. Using a calibration located
from the visible border in raw_004, regression gives **3/14 passed**: raw_004 and
raw_005 read 8400; raw_051 reads 9500. The other eleven return None, rather than
incorrect numeric proposals. The real-camera reader is therefore NOT proven
across the corpus, especially later dim/pink score frames. This integration does
not claim reliable score measurement yet. Pixel threshold and geometry remain
limitations for future score-reader work; seven has no real camera exemplar.
These old frames and their experimental calibration are evidence, not a change
to the live playfield calibration. Preserve a current camera view or explicitly
recalibrate before the next game.

## Next Pi experiment

Keep local modifications; never reset or discard files. A failed fast-forward
must be investigated before running. The gameplay limit is 20 seconds after SELF
acquisition; bounded startup/probes and cleanup are additional time.

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git status --short
git fetch origin
git switch feature/agency-first-self
git pull --ff-only origin feature/agency-first-self
python -m pip install pytest || exit 1
python -m pytest tests -q || exit 1
mkdir -p robotron-runs
run_dir="robotron-runs/tracking-score-$(date +%Y%m%d-%H%M%S)"
set -o pipefail
PYTHONPATH="$PWD" python -m experiments.ppal.play_robotron \
  --seconds 20 --focus 1.30 --arm --output "$run_dir" \
  2>&1 | tee "$run_dir.console.log"
python -m experiments.ppal.replay_tracking "$run_dir/agency.jsonl" \
  --output "$run_dir/tracking-replay.json"
tar -czf "$run_dir.tar.gz" "$run_dir" "$run_dir.console.log"
```

Return exactly the resulting `robotron-runs/tracking-score-<timestamp>.tar.gz`,
even on failed acquisition. Include observed official game score and whether
SELF remained on the real player and moved/fired. The primary experiment remains
physical ID persistence and agency; compare raw HUD, score evidence and action
timestamps secondarily. Replay matching demonstrates reproducibility, not truth.

## Newly returned pre-integration live run

`tracking-repair-20260930-034659` ran a7a5ab2, with the expected local dirty
worktree. It failed SELF acquisition, recorded 20 agency samples and zero normal
policy ticks. Exact replay matches 591 detections and 173 created IDs. Most
creations occur during startup: sample 3 has 148 detections/127 creations; later
association briefly costs 0.35–0.71 seconds on Pi. These are diagnostic costs,
not score-reader overhead (the score integration was not present).

The center candidate visually consistent with the player keeps ID 96 from
samples 8 through 20. East-command sample 9 remains at (61.5625,50.4167), then
neutral sample 10 moves east to (62.65625,50.625). West sample 11 is effectively
unchanged, then neutral sample 12 moves west. South sample 13 is unchanged,
neutral 14 moves down; north 15 unchanged, neutral 16 moves up. The same pattern
repeats for east/west. Agency confidence for ID 96 consequently collapses under
continued-during-neutral penalties. This is strong evidence of observation/action
phase misalignment, not fragmentation of this likely player during the probes.
It does not establish whether camera buffering, transport latency, or another
capture/actuation delay is responsible. Do not weaken agency identity gates to
hide the timing problem. A follow-up capture-timing repair should precede another
armed experiment; score remains observational during that repair.

Alex observed 1200 official points later in the game. Since normal policy ticks
are zero, those points cannot be credited to Charlie's normal planner. Probes did
send movement commands, so this is not evidence of no actuation whatsoever.
Pi tests did not execute because pytest was absent; install it and explicitly
stop on test failure before arming. The next command below guards that condition.

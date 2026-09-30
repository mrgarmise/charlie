# Calibration failures, 20261001-002127 and 002659

Both archives ran bce4e95 and failed in fresh calibration. Both report zero
agency samples and zero policy ticks; score is **unmeasured**, not an observed
score-reader failure. No movement is expected because neither reached probes.
There is no new evidence here against SELF, association or capture timing.

## What the actual images demonstrate

The first, skewed image ends the arena's right edge almost at the camera boundary
and contains the fan. The strict full-border check rejects that saved image.
The second, good-view image contains all arena corners and the HUD. **The existing
locator accepts its final saved PNG**, including with OpenCV 4.10.0 / NumPy 2.2.4,
matching the Pi's versions. Approximate existing detector corners are (158,156),
(882,80), (987,573), (167,688). Therefore it is incorrect to diagnose the second
failure as simply missing corners or a consistently rejected final view.

The old preflight needed six agreeing views but saved only the final image and
the last rejection reason. Earlier failures, jitter, or scene transitions cannot
be reconstructed from these archives. The last rejection text could remain stale
after a later successful detection. We have not relaxed the six-view criterion.

RGB clipping is real: within the geometrically normalized arena interior, about
59% of locally contrasting detail pixels have at least one channel >=250 and
43% have all channels >=250 (using the revised detector's geometry; exact
fractions vary slightly with crop). Large parts of the room are also bright.
This confirms color loss in camera output, but the archive contains no exposure,
gain or AWB metadata for setup. It does **not** establish whether gain, exposure,
AWB, TV emission or a combination caused the clipping. Lost channels cannot be
restored by recoloring the PNG.

## Separate from earlier tracking findings

| Run | Demonstration | Outstanding question |
| --- | --- | --- |
| Original play-024128 / a70149c | Background swallowed as sprite; fragmented player histories | Addressed by contrast candidates and the generic association repair |
| tracking-repair-034659 / a7a5ab2 | Likely player 96 continuous through probes; response shifted into neutral samples | Fresh-exposure capture added based on this evidence |
| tracking-score-232827 / 4ffb951 | Likely player 9 continuous in samples 6–15; signed responses but residual neutral motion; 210 of 259 IDs born in three dense transition frames | Neutral handoff and false dummy-assignment ambiguity repaired in bce4e95; live confirmation still pending |
| Both new calibration runs / bce4e95 | Neither reaches agency or score observations | Calibration stability and camera color preservation must be validated first |

Detailed exact replay, score diagnosis and exposure/onset analysis remain in
[tracking-score-232827-analysis.md](tracking-score-232827-analysis.md). No further
agency timing change is justified by these two calibration-only runs.

## This repair

- Before START, fresh recalibration performs a bounded 0, -1, -2, -3 EV camera
  sweep. Measurements use local RGB detail inside a complete detected arena,
  not bright room pixels. It retains the least negative exposure with low
  clipping, adequate detail and meaningful improvement over baseline. Without
  supported controls or usable geometry it retains default automatic exposure.
- After selection, actual exposure time and analogue gain can be locked from
  the selected fresh-request metadata. AWB stays automatic; there is no known
  neutral reference to justify forced white balance. Same-request telemetry now
  includes analogue/digital gain, color gains, color temperature and AE lock.
- Calibration lines now include local RGB contrast, and border support uses
  positive channel contrast against both neighboring sides. White and blue can
  have equal HSV value despite a strong RGB edge. Complete geometry and color
  consistency still matter; incomplete/blank/striped gameplay borders remain
  rejected. No pixel coordinates are hardcoded.
- All attempted full-color frames are retained as setup-attempt-NNN.png, with
  timestamp, capture metadata, detected corners, jitter or failure reason in
  setup-attempts.json. The terminal failure reason reflects the latest accepted
  view when applicable. exposure.json and report.json record the sweep.

All exposure search, file writing and extra border detection occur in preflight,
before agency acquisition. Sprite candidates, the single generic association
pass, SELF gates, movement/firing, replay and passive ScoreTracker are unchanged.
No score feeds the policy. run_camera.py is untouched.

## Validation and limits

**289 tests passed** with OpenCV 4.10.0 and NumPy 2.2.4. New regressions use the
actual lossless good-view PNG, verify corner recovery at original and reduced
brightness, saturated-blue/white border contrast, bounded selection and RGB
retention, missing geometry fallback and hardware control/AWB isolation.
Existing rejection, tracking, agency, timing, replay and score tests also pass.

Reduced-brightness fixtures test detector robustness; they are not recovered
color or proof of hardware exposure optimization. The EV sweep is a conservative
heuristic over a changing attract scene, not calibrated radiometry. Multiple
requests let controls propagate; actual metadata is retained without claiming
perfect AE convergence. A locked attract-screen exposure may not suit every
later scene. AWB correctness remains unproven. The new good-view PNG's visible
200 still returns UNKNOWN in an offline HUD read; camera improvement is not a
claim that this glyph is fixed. Next hardware evidence must validate all of this.

## One next experiment

Release the preview server's camera; retain the good-view framing with all
corners and HUD visible. Start from attract mode so exposure preflight costs no
player lives. Do not reuse the old obstructed calibration.

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git fetch origin &&
git switch feature/agency-first-self &&
git pull --ff-only origin feature/agency-first-self || exit 1
python -m pytest tests -q || exit 1
mkdir -p robotron-runs
run_dir="robotron-runs/exposure-calibration-$(date +%Y%m%d-%H%M%S)"
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

Return **robotron-runs/exposure-calibration-<timestamp>.tar.gz**, even on setup
failure. This includes every preflight view and setting, agency/replay if reached,
raw HUD evidence and score log if observed. The policy window remains 20 seconds
after acquisition; preflight and probes add bounded setup time. One run only.

Camera control reference: Raspberry Pi's official [Picamera2 manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf),
ExposureValue, AeEnable, ExposureTime, AnalogueGain and capture-request metadata.

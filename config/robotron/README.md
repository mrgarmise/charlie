# Screen geometry

playfield-20260926.json was measured from camera-mBPTGSQy, a 1280x720
physical-camera capture supplied September 26. Corners are TL, TR, BR, BL;
output is 640x480. This is playfield geometry only, not a detection profile.
Score and wave text lie outside this crop; a future HUD reader must use a
separate region of the original camera frame. Do not apply the synthetic HUD
profile to this crop.

Keep the camera and display in the same positions. Moving either requires
recalibration. Remove the ornament overlapping the bottom edge. Inspect the
benchmark's playfield.png to confirm the crop still matches all four borders.

Stop camera previews, then run `bash setup/benchmark_robotron_pi.sh` on the Pi.
The bundle contains raw.png, playfield.png, and timing.json. It never connects
to the arcade. Timing excludes network, controller, action pulses, and browser
rendering. Without --profile it has no object detector: results are a baseline,
not evidence of live gameplay speed. The local synthetic smoke test does not
measure Pi performance.

For a faster preview, run:

```
.venv-robotron/bin/python -m experiments.ppal.eyes.serve_eyes --source pi --bind 0.0.0.0 --fps 20 --calibration config/robotron/playfield-20260926.json
```

The target rate is a ceiling, not a guarantee. Use only one preview browser tab.

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

## Draft real-camera sprite detector

`sprites-draft.json` contains nine small sprite examples from timing-QSsAxcb8's
physical camera image. Labels were assigned visually and need user review.
The detector groups bright pixels with OpenCV, compares normalized shape/color,
and keeps low or conflicting matches unknown. It does not cover all animations,
waves, overlaps, explosions or screen transitions. Match similarity is not a
probability. No online learning or temporal tracking is added by this detector.

The source frame yields one player candidate, two human candidates, 27 threat
candidates and 16 unknown regions. This is a fitting check, NOT accuracy on
unseen images. Replay of the earlier 12-frame camera-mBPTGSQy capture shows
missed player/human appearances and some false threat matches. It is not ready
for autonomous control. These failures are why observations cannot produce a
WorldState, even if someone removes the profile's draft flag. The live runner
also rejects this profile format; use the observation tools only.

On the Pi, stop the preview and run `bash setup/observe_robotron_pi.sh` while
playing manually. It records 60 raw/annotated frames and per-frame capture,
vision, and save timing. It uses robotron-runs/playfield-current.json when
available; otherwise the latest measured geometry. The resulting detection
archive lets us inspect mistakes and measure the actual Pi processing cost.

For labeled live preview:

```
.venv-robotron/bin/python -m experiments.ppal.eyes.serve_eyes --source pi --bind 0.0.0.0 --fps 20 --calibration robotron-runs/playfield-current.json --profile config/robotron/sprites-draft.json
```

## Per-recording setup (current default)

All three Pi recording scripts now use --auto-calibrate rather than a saved
camera position. The same open camera is warmed up for exposure/autofocus,
then twelve frames are checked for a complete high-contrast colored border.
Line support on all sides selects the best rectangle; a six-pixel maximum
corner deviation rejects a view that has not settled. This is geometry
estimation, not proof of focus or sprite accuracy. Strong reflections, border
animations, steep angles and partial occlusion can require another attempt.

Each output directory contains calibration.json, setup-raw.png,
setup-border.png, setup-playfield.png and setup.json. A failed setup records
setup-failed.png and an explanation and aborts before the recording. The
recording commands never send controller inputs. The camera may be moved
between runs, but this version does not track drift during a recording.
Keep the whole game border visible and reasonably steady for that short run.

Automatic exposure remains enabled by the camera defaults; setup allows it
to settle. The draft sprite classifier still needs validation under changing
illumination. Automatic geometric calibration does not make its current color
examples lighting-invariant. The playfield crop excludes score/lives; keep the
original camera images for eventual HUD processing.

Validation: located the playfield in both saved camera positions, rejected the
blank TV capture, and passed synthetic geometry/color and blank-frame tests.
Pi runtime and new lighting conditions still need live verification.

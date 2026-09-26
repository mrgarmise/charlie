# First Robotron session on Charlie Pi 5

The `feature/charlie-memory` branch combines the PPAL-7 snapshot with durable
memory, the revisable memory evaluator, head-search recall, and the experiment
runner. PPAL-7's newer hindbrain and dense logging are retained; PPAL-0's
`--memory-log` / `--marm-outbox` options are preserved.

## Install

Use a terminal on the Pi 5 (desktop/VNC or SSH), logged in as `five`.
Use a separate checkout so existing Charlie configuration stays available:

```bash
git clone --branch feature/charlie-memory https://github.com/mrgarmise/charlie.git ~/charlie-play
cd ~/charlie-play
bash setup/install_robotron_pi.sh
```

If `~/charlie-play` already exists, inspect it before changing it; do not delete
it to make the clone command succeed. The installer uses Raspberry Pi OS's
camera/vision packages and a dedicated environment with system packages visible.
It runs offline tests and does not start camera capture or send game controls.

## Capture what Charlie sees

Aim the Arducam at the whole Robotron playfield. Stop any existing Charlie
camera preview/tracking process so the camera is free. Have Robotron running
on the Zero and play manually while this captures twelve frames:

```bash
cd ~/charlie-play
bash setup/capture_robotron_pi.sh
```

Upload the printed `robotron-runs/camera-....tar.gz` file for inspection.
Raw frames, annotated views, and detection reports are included. Initially
zero player candidates is expected: no real-game color profile exists yet.
This script sends no controls. Each invocation creates a new capture folder.

The Pi source converts the existing camera wrapper's BGR array into RGB for
Pillow. Picamera2 calls this array format RGB888 despite its BGR byte order:
https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf

## Calibrate and review

Use the Pi desktop/VNC for the click tools (stop any other camera process).
Replace CAPTURE below with the actual directory just printed:

```bash
source .venv-robotron/bin/activate
python -m experiments.ppal.eyes.calibrate CAPTURE/raw_000.png --click --output robotron-runs/playfield.json
python -m experiments.ppal.eyes.profile_builder robotron-runs/playfield.preview.png --click --output robotron-runs/colors.json
python -m experiments.ppal.eyes.run_readiness --source images --input CAPTURE --calibration robotron-runs/playfield.json --profile robotron-runs/colors.json --frames 12 --interval-ms 0 --output robotron-runs/review
```

Inspect every annotated frame, including different sprite colors and positions.
A color profile is only a candidate detector, not a validated Robotron model.
Only mark `draft: false` after the detections are reliable. Flashing sprites,
overlap, attract mode and explosions may require better detection before play.

## Supervised controls and play

Select SOLO on the Zero for both sticks under Charlie's control. While watching
the game, test one bounded pulse from the Pi (substitute an IP if mDNS fails):

```bash
python -m experiments.ppal.run_arcade_probe --connect --host charlie-arcade.local --move E --fire NONE --duration-ms 100
```

Confirm visible movement and stopping. TCP acknowledgement alone does not prove
RetroArch's joystick bindings. Then, with reviewed calibration/profile:

```bash
python -m experiments.ppal.run_closed_loop --mode camera --arm --host charlie-arcade.local --calibration robotron-runs/playfield.json --profile robotron-runs/colors.json --max-steps 20 --duration-ms 100 --remember --log robotron-runs/first-play.jsonl --preview-dir robotron-runs/first-play-views --preflight-dir robotron-runs/preflight
```

Three camera preflight frames must pass before controls connect. Actions pulse
and center before the next frame; Ctrl-C closes and neutralizes the controller.
Choose new log/preview paths for subsequent sessions to preserve earlier evidence.

## What learning is ready

Dense session evidence is recorded. `--remember` sends the session summary
through Charlie's evaluator to the local durable MARM outbox, even with MARM
offline. Simulator and camera evidence are labeled separately, and each session
has a unique ID. Session completion is not credited as policy improvement.

The PPAL shot-model training/adaptation tools currently operate in simulation.
Real score/lives templates, verified outcome readings, and comparable live trials
are still required for trustworthy real-game adaptation. Synthetic checkpoints
cannot arm the live player. Missing HUD means unknown reward, not zero reward.

MARM server installation and the sync timer are a follow-up integration task;
queued memories survive until it is available. See `memory/README.md`. The timer
alone does not launch MARM. Automatic Robotron policy changes from recalled
memories are not implemented in this release.

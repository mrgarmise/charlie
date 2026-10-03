> Archived PPAL-7 package notes. For this combined branch, use
> [the Pi 5 installation guide](docs/robotron-pi-start.md). Do not extract the old
> ZIP over this checkout; it would replace the memory-enabled demo runner.

# Charlie PPAL-7: ready for a supervised hardware check

This is a complete snapshot of PPAL-0 through PPAL-7. It adds a bounded
camera recording/audit tool, a draft color-profile builder, and a controller
bridge matched to the **current** `controller.py` and `launcher.py` supplied
on September 25. Their TCP server accepts newline-delimited commands on port
8765 and replies `OK`/`ERROR`. The current controller supports absolute
stick positions such as `LS_DOWN_LEFT`, `RS_UP_RIGHT`, `LS_CENTER`, and
`RS_CENTER`. It also retains the older `LS_LEFT_DOWN`/`LS_LEFT_UP` commands.
The bridge uses absolute positions by default, pulses for the requested
30–500 ms, then centers both sticks before reading the next frame. A lost
connection and normal close send `NEUTRAL`. This checks the command contract,
**not** whether RetroArch has mapped the virtual device in the running game.

## Install on Mint or Charlie Pi

From the root of the Charlie repository, extract this entire snapshot:

```bash
cd ~/charlie/charlie
python3 - <<'PY'
from pathlib import Path
from zipfile import ZipFile
with ZipFile(Path.home() / "Downloads/Charlie-PPAL-7-complete.zip") as archive:
    archive.extractall(".")
PY
python3 -m unittest discover -s tests -v
```

The included Python needs `numpy` and `Pillow`. Camera capture on the Pi
uses Charlie's existing `vision.camera.Camera` wrapper. `--click` profile
and calibration tools additionally use Matplotlib; calibration optionally
uses OpenCV for true perspective correction.

## Work we can do without the arcade

```bash
python3 -m experiments.ppal.run_arcade_probe --move SW --fire NE
python3 -m experiments.ppal.eyes.run_readiness --source synthetic \
  --frames 3 --interval-ms 0 --output ppal_synthetic_audit
python3 -m experiments.ppal.run_closed_loop --max-steps 15
```

The first prints `LS_DOWN_LEFT`/`RS_UP_RIGHT` and sends nothing. The second
saves `raw_*.png`, `view_*.jpg`, individual state JSON, and `readiness.json`.
The third still runs the full toy arena with a disconnected recording sink.

## Once the screen and camera are available

On Charlie's Pi with the Arducam aimed at an active Robotron screen:

```bash
python3 -m experiments.ppal.eyes.run_readiness \
  --source pi --frames 12 --output ppal_real_capture
python3 -m experiments.ppal.eyes.calibrate \
  ppal_real_capture/raw_000.png --click --output ppal_playfield.json
python3 -m experiments.ppal.eyes.profile_builder \
  ppal_playfield.preview.png --click --output ppal_robotron_draft.json
python3 -m experiments.ppal.eyes.run_readiness \
  --source images --input ppal_real_capture \
  --calibration ppal_playfield.json --profile ppal_robotron_draft.json \
  --frames 12 --interval-ms 0 --output ppal_real_audit
```

The color tool asks for three interior pixels each for the player, a human,
and a threat. Its JSON is explicitly a **draft**. Review every annotated
frame: sprites flash, overlap, and change color. Adjust the thresholds and
set `draft` to `false` only after the real-frame detections are reliable.
The audit never connects to the controller. If you obtain a real score/lives
template reader, pass it as `--hud-profile`; otherwise rewards remain unknown.

To check the Zero-side command path once you can watch the TV:

```bash
python3 -m experiments.ppal.run_arcade_probe \
  --connect --host ARCADE_IP --move E --fire NONE --duration-ms 100
```

The launcher can reply `OK` even when RetroArch does not recognize the
virtual joystick. Confirm that one 100 ms command visibly moves the player,
then that movement stops. If the older launcher is still installed, the
probe accepts `--protocol legacy`.

The closed loop's `--arm` path requires camera mode, an explicitly reviewed
real profile and calibration, a bounded step count, and a three-frame
camera preflight. It refuses synthetic or draft profiles and PPAL-5/6
synthetic checkpoints. During the preflight it saves views in
`ppal_live_preflight`; if player/human candidates are unreliable, no arcade
connection is opened. Keep early runs supervised and short.

No Robotron camera frames, RetroArch button acceptance, or real-game rewards
were available for this package. They remain the concrete hardware checks.

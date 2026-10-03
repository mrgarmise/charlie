# Live Robotron connection

This adapter follows the Charlie Arcade camera-only contract. The Pi Zero
accepts persistent TCP commands on port 8765 and replies only OK/ERROR. Those
acknowledgments do not prove RetroArch recognized the buttons. Observations
come from the Elegoo camera pointed at the physical display.

`ArcadeController.execute(Action(...))` maps PPAL's N/NE/E/etc. movement to
LS positions and firing to RS positions. `RobotronSession.step()` returns a
camera frame after a bounded controller pulse, neutralizing controls before
waiting for vision. Disconnects, rejected commands, and camera errors end the
session. The existing Zero launcher also neutralizes on disconnect. Do not run
multiple clients against the same virtual controller during a trial.

## First live check

On Charlie, position the camera so the entire Robotron playfield and score are
legible. Start Robotron using the normal launcher/human controller, then run:

```bash
python3 -m experiments.robotron.capture --host ARCADE_ZERO_ADDRESS \
  --output /tmp/robotron-camera-001 --seconds 15
```

This records physical camera frames without moving or firing. Use the human
controller during the clip to show the title/start screen, gameplay, scoring,
and a life loss. For a short virtual-controller check, use a separate directory:

```bash
python3 -m experiments.robotron.capture --host ARCADE_ZERO_ADDRESS \
  --output /tmp/robotron-controls-001 --seconds 5 --move E --fire N --pulse 0.2
```

Only one initial pulse is sent, followed by neutral observation. Defaults use
`http://192.168.4.1:81/stream`; change `--camera-url` if needed. The machine
running this command must reach both the camera and the Pi Zero. Existing
OpenCV/numpy camera dependencies are required. Received-frame timestamps are
not exposure timestamps and do not measure camera latency.

## Remaining before autonomous learning

The controller vocabulary was verified against the supplied
`controller-current.py` / `launcher-current.py` and the arcade repository's
README. No Zero-side changes are required. A live camera/control recording is
still required to verify RetroArch bindings and calibrate playfield/HUD reading.

This is the live I/O adapter, not a completed visual Robotron player. A visual
observer must decode player/targets/threats and validated score/life/rescue
outcomes. Camera pixels alone do not currently populate PPAL WorldState.
Unknown outcomes must remain unknown rather than be counted as zero.

The paired comparison runner also requires a verified reset implementation.
This adapter refuses `reset(seed)` because the existing arcade protocol offers
no state restore/verification, and similar camera frames cannot certify
identical hidden game state. Randomized whole-game trials from visually verified
new-game starts will need a suitable unpaired experimental design, or a
separately authorized operator-side reset fixture. Emulator state must not be
silently fed into Charlie's policy.

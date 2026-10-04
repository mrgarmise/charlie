# CAL-1 integrated normal-brain release

Parent: `f5bc3955bfacddca3445eb218fbff2d51de0caba`, independently observed on
`feature/active-vision` before cloning and again before publication. The release
identifier is the commit containing this report. ALA-2's branch was not changed.
Physical execution authorization for this Work session was **false**.

This release implements the normal Pi/Pico integration. **Native Pi/MicroPython
acceptance and physical envelope qualification remain pending.** The existing
Pi staging checkout and installed Pico were not accessible from this workspace;
neither was modified. Do not mistake host simulation for commissioning.

## What changed

| Components | Result |
| --- | --- |
| `main.py`, `hardware/calibration_service.py`, `hardware/calibration_behavior.py` | Normal-brain capability on the existing UART and perception ticks; Executive selection, automatic experiment selection/evaluation, durable observations and resumable developmental bookmarks. No new learning scheduler, camera process or PWM controller. |
| `hardware/scene_response.py`, `vision/stimulus.py` | Distributed background optical flow on the existing raw frame, excluding the tracked target. Gray source frames and artifact/capture hashes are preserved. Digital framing output is exposed separately; physical evidence always uses raw frames. |
| `vision/detector.py`, `attention/manager.py`, `behaviors/track.py`, `motion/controller.py` | Existing YuNet face selection available on the Pi camera; off-scale framing and bounded visual reacquisition share the installed motion authority. Fixed a pre-enter target being erased. Normal Pi main leaves the separate ELEGOO sidecar off unless explicitly configured. |
| `rp2040/calibration.py`, `rp2040/servos.py` | Brain-driven protocol alongside the retained legacy protocol; independent qualified paths need no GP10 contact, each unexplored increment requires one consumed contact, and exact camera-supported return paths can be retraced. No return path becomes a qualified operating region. |
| `rp2040/main.py`, `rp2040/display.py`, `rp2040/commands.py` | Persistent calibration notices under existing text/feedback priorities; brain connection, reviewed starting pose, GP10 direction, moving/observing, saved/fault states. Watchdog and sole ServoController ownership retained. |
| `hardware/rp2040_controller.py`, `stimulus/keyboard.py` | STOP/SESSION acknowledgments required before reporting connection; `c` requests calibration and `v` confirms a displayed, independently reviewed starting pose. Headless stdin EOF no longer spins. |
| `hardware/neck_calibration.py` | Automatic camera-supported combined grids can produce CANDIDATE profiles; original frame hashes are checked during derivation and qualification. Simulation remains inadmissible for activation. |
| `tools/update_charlie.py` | One pinned Pi/Pico release procedure with automatic snapshots, byte integrity checking and rollback. Installed wiring/configuration, support libraries, profiles, markers and original evidence remain unchanged. |
| `tests/test_brain_calibration.py`, `tests/test_cal1_release.py` | Real Pi main, UART parser/handler, firmware state machine and deployment flow exercised with simulated hardware and service/filesystem adapters. |

The shipped `rp2040/motion_profile.py` and `config.py` were not changed. No physical
profile, electrical clearance, GPIO permission or powered-start review was
invented. Existing GP4/GP5 motion ownership and disabled Head B behavior remain.

## Operational behavior

The first bounded calibration session observes both axes and a combined grid.
It produces immutable provisional observations and, when complete/consistent,
a conservative candidate profile. Repeated calls consult compatible durable
bookmarks and advance to bounded boundary-ray exploration. Each outward ray
reserves its complete supported retreat within the session budget. Missing
permission stops the extension and permits another experiment or retreat.
Timeout records distinguish missing permission from confirmed operator intent;
neither is interpreted as a mechanical hard stop.

The existing Learning Executive selects an eligible reflected calibration
project using externally supplied supervision, electrical clearance and execution
authorization. It retains the resulting candidate/paused disposition. An
unfinished qualification request remains open; candidate generation does not
resolve it or authorize deployment. No winning Robotron strategy is supplied.

Normal Active Vision attempts bounded digital framing first. Residual error
selects a small physical correction from the profile's observed response model,
inside its polygon/margins/rates. The next raw camera observation must support
that movement before another command. A finite sweep supports target reacquisition.
Unexpected pose/ownership, missing background evidence or inconsistent response
stops motion conservatively and preserves uncertainty and alternative causes.
Tracking failure is not labeled a confirmed mechanical fault.

An invalid calibration does not disable passive perception. The normal
application starts without physical authorization after deployment. All
qualification, selection, authorization and startup checks remain separate.
Robotron's existing primary ownership/stationary-neck path is retained; its
camera or controller is not duplicated, and gameplay was not initiated.

## Powered startup: the specific unresolved condition

The supplied mission reports installed CAL-1 firmware, detected GP10 permission,
one consumed 0.5-degree pan increment and ignored unauthorized contacts, followed
by `charlie_cal1_004` aborting before confirmation. These are **operator-reported
commissioning facts**, not independently observed here. The movement path is
established; actual displacement, smoothness and full clearance are not.

The reported jerk during late servo-power connection makes the initial powered
pulse unqualified. This release removes routine `external_power_off` from the new
brain path, but does not silently assume a physical start pose. A commissioning
or qualified profile needs an independent `powered_start_review` containing the
reviewed pose, reviewer, evidence and `powered_initialization_verified=True`.
The reviewer must differ from the live confirming operator. `v` confirms the
displayed pose once, without power cycling; no camera estimate is called a
measured servo position. A missing review displays `START POSE UNVERIFIED` and
constructs no PWM. Existing legacy verification remains available unchanged.

The field `powered_start_review` is a physical-evidence input, not a template
to fill with asserted truth. No such review is supplied by this release.

## Offline acceptance

| Requested behavior | Executed coverage |
| --- | --- |
| Normal brain initiates calibration; successive movements; automatic observation | Actual `main.py` -> shared frames -> service -> real UART/handler/state machine -> simulated PWM/camera; calibration resumes tracking |
| GP10 only for unknown extensions; withheld permission; retreat | No first PWM without consumed contact, no replay, no outward movement when withheld, exact supported retreat, qualified path without GP10 |
| Normal viewfinding and off-scale correction | Bounded motion after digital range exhaustion, camera response/health evaluation, qualified transition retained |
| Display/brain status | Existing Pico scheduler/display regression suite, persistent status implementation, acknowledged STOP/SESSION connection |
| Persistence/reuse | Immutable frames/observations/candidates and SQLite requests survive restart; bookmarks consulted on later sessions; no pending permit restored |
| Existing features and ownership | Existing calibration, firmware, watchdog, heartbeat, command, Active Vision and Robotron regressions retained |
| No unqualified activation | Simulated candidates rejected; missing startup review/authorization constructs no PWM; independent profile activation unchanged |
| Cohesive release/rollback | Fake Pico filesystem and systemd flow verify original configuration/evidence/library bytes, dependencies-before-main upload and automatic rollback after partial failure |

Final counts, exact source hashes, environment and failed/intermediate attempts
are recorded in `validation-cal1-brain.json`. Torch-dependent ALA tests are
explicitly skipped when Torch is unavailable. No native test is claimed.

## One later authorized deployment

Use the full published commit SHA from the completion message as `RELEASE`.
This is a procedure, **not execution authorization in the current mission**.
From the existing Pi staging checkout:

```bash
cd /home/five/cal1-integration-stage
git fetch origin feature/active-vision
git show "$RELEASE:tools/update_charlie.py" | .venv/bin/python - --cal1-release "$RELEASE"
```

The helper creates the pinned release automatically, keeps the staging checkout
and original evidence, stops the normal service, obtains maintenance STOP,
preserves the Pico filesystem, updates application dependencies before main,
checks transferred/preserved bytes, and starts the **normal** Charlie service.
Motion authorization is off. It preserves or creates `charlie.service` and its
existing unrelated settings, uses the existing Pi virtual environment and
selects the existing face detector. No support-library/configuration overwrite,
manual backup, temporary calibration firmware, GPIO probe or physical checklist
is part of this procedure. A source-level Python application update does not
replace the MicroPython runtime.

Ordinary startup thereafter is `sudo systemctl start charlie`. The helper's
`--dry-run` only prints the plan, with no service/UART/git mutation. Native
service startup, camera ownership and Pico timing still require observation.
A transport write alone is no longer reported as an acknowledged brain link.

For separately authorized assembled, powered commissioning, stop the service
and run its same normal application interactively:

```bash
sudo systemctl stop charlie
CHARLIE_NECK_MOTION_AUTHORIZED=1 CHARLIE_NECK_SUPERVISED=1 CHARLIE_VISION_TARGET=face \
  /home/five/cal1-integration-stage/.venv/bin/python \
  "$HOME/.local/share/charlie/releases/$RELEASE/main.py"
```

Use `c` to request/repeat calibration and `v` only when the reviewed starting
pose is actually confirmed. Thereafter Charlie selects and evaluates movements;
the operator supervises proposed extensions through GP10. Ctrl-C stops the
normal application. The helper does not fabricate profile review/configuration
or clear old quarantine markers. Existing offline profile tools remain the
independent qualification/metadata-selection interface; calibration requests
do not require reflashing the application.

## Remaining physical acceptance

1. Qualify the powered starting pulse/pose and smoothness in the existing assembled
   configuration; this addresses the reported jerk, not a repeat of basic GP10
   detection or the established motion path.
2. Observe actual camera response/settling on focused small movements, then only
   genuinely unverified boundary and combined-axis clearance extensions. Keep
   the independent physical cutoff available; GP10 is not an emergency stop.
3. Independently qualify/select the resulting physical profile and demonstrate
   normal autonomous tracking/reacquisition, real display/UART cadence and restart
   behavior. Existing electrical and profile safety gates cannot be invented or
   bypassed by software; resolve a specific remaining condition if one is blocked.

No firmware was deployed, no servo moved and no physical policy/gameplay was
activated in this Work session. CAL-1 is not declared physically complete.

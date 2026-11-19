# Visual embodied learning • offline research
Charlie estimates which bounded servo response delay best predicts marker motion. A dog adapter uses the existing FNK0050 MuJoCo environment. An analytic two-axis rig uses the same experiment selection, pixel estimator, UEL evidence journal and validation code. The twin describes a particular simulated joint response; other joints and mechanical properties remain open questions.

## Review baseline

| Asset | Inspected source or observation | Qualification |
|---|---|---|
| Charlie default source | master 57e07eb850b139eda6a5f1a930cc0ef7b5bf5f18 | Source only |
| Universal learner | Drafts #40, #41, #42. This branch extends #42 at cf0842efeaeea4862abdbf46c33977adfc48aa3b | Journal, profile, inquiry registry, experimental evidence and response baseline reused |
| Dog | main 38ca17d8a1799b51c207f0a8cec3a16b28e46931; simulator #1 2d6af9192a69868454f260e8cb3851c98727e623; integration draft #3 c2b2ba71502824a5fe5580c89d1e6253af72d655 | Existing Gym, XML, gait seed, IK, fall and joint constraints; newer local Pose Lab campaigns unavailable in this checkout |
| Physical dog priors | Operator-reported 588 g, hip spans 136 and 75 mm, roughly 90 mm clearance | Kept separate from simulated dimensions. No physical calibration, ordering or firmware changes |
| Charlie Pi | Reported Pi 5 8 GB, IMX708, Hailo-8L 13 TOPS, HailoRT 4.23.0 | No Pi, native drives, HEF inference, or thermal/power telemetry in this experiment |
| Elegoo | Existing Charlie camera owner supports MJPEG, and #30 contains a separate S3 integration | Identity, electrical interface, mounting, host, clock and firmware of the proposed second camera remain unobserved |
| Operational approval | Historical stationary revisions f3304c5, d3dca90 and 72cd9e4; manual 90-second foreground boundary | No runtime checkout accessed. Research branches do not change service, motion or deployment files |

## Data and authority

~~~mermaid
flowchart TD
  H["Optional human or LLM text"] --> Q["UEL question ranking"]
  Q --> S["Allowlisted simulation"]
  S --> C["Projected images"]
  R["Local replay and calibration"] --> P["Pixel tracking"]
  C --> P
  P --> F["Bounded fitting"]
  S --> F
  F --> V["Held-out validation"]
  V --> M["MuJoCo skill practice"]
  V --> J["UEL evidence journal"]
  M --> A["Operator review file"]
~~~

The graph ends at files. The physical mock raises on every call, including expired or forged tokens. Simulation scripts import no live owner or actuator transport. A hypothesis string reaches a report only. Original evidence and rejected policies remain available. The bench uses newly generated visual fixtures, with no external image or model assets.

| v1 object | Implementation and interpretation |
|---|---|
| BodyDescription / Trajectory | Named ordered joints and observed marker, baseline fingerprint, metric world, commands and simulated IMU. Dog links, ranges, inertias, materials and envelope come from the fingerprinted XML and DogEnv; the analytic rig has a 0.1 m arm. Physical topology, mapping, mass and dynamics remain presumed. |
| CameraSource / Camera | Synthetic, local recording, primary or Elegoo role. Intrinsics in pixels, distortion, world-to-camera R and t in metres, profile and clock provenance. Physical roles consume recordings through the same decoder. |
| Observation batch | Family, seed and ordered optional features. Covariance is isotropic sigma² I in px². Missing and occluded joints have no estimate. SQLite stores sampled PNGs with SHA-256, command, simulated IMU, truth for evaluation, frame index and synthetic monotonic time. Unmeasured wall time and supply fields are null. External records declare exposure times and content hashes. |
| ExperimentProposal | Objective, predicted effect, eligibility, required review and command timeline. Simulation probes use waveform, seed, grid and delay; stationary physical proposal contains zero commands. |
| TwinCandidate / ValidationReport | Small exhaustive parameter grid, Huber loss, baseline, fitted observations, alternatives and independent validation ID. Data units, extraction uncertainty and baseline must agree. Report contains pixel residuals at each detected sample in time order, interval coverage and trajectory-level bootstrap. |
| MotionSkillCandidate | Content-addressed validation parent, mode, individual seed, delay, initial pose, energy proxy, peak FL clearance, tilt margin, simulation acceptance and hardware_accepted=false. |

## Offline walkthrough

Use isolated checkouts of both research/visual-twin branches. Python 3.12.14, NumPy 2.3.5, OpenCV contrib headless 5.1.0.95, MuJoCo 4.0.1, Gymnasium 1.4.0 were exercised on x86-64 Debian. The CPU rig needs NumPy, Pillow and OpenCV contrib. The dog needs both research checkouts plus MuJoCo and Gymnasium. Prepare a wheelhouse matching the OS, Python and architecture before offline use. Keep existing environments untouched. For Mint or Pi create a separate venv and install the applicable packages with pip --no-index --find-links /path/to/wheels. Native ARM wheel and camera compatibility still need verification. System licenses include Apache-2.0 for OpenCV and MuJoCo source, MIT for Gymnasium, BSD for NumPy and the Pillow project's license. Respect the existing dog LICENSE.txt / NOTICE.md, including CC BY-NC-SA constraints. No accelerator model or weights are distributed.

From the Charlie checkout, assuming sibling directories named charlie and dog:

~~~sh
export PYTHONPATH="$PWD:$PWD/../dog/research/fnk0050-sim"
python -m research.uel.visual demo /tmp/rig-run --body rig
python -m research.uel.visual demo /tmp/dog-run --body dog
python -m research.uel.visual inspect /tmp/dog-run
python -m research.uel.visual recording research/uel/visual/evidence/recording.json
python ../dog/research/fnk0050-sim/visual_video.py /tmp/dog-sequence
python -m research.uel.visual recording /tmp/dog-sequence/recording.json
python -m research.uel.visual.evaluate /tmp/new-dog-benchmark --body dog
python -m pytest -q research/uel
python -m pytest -q ../dog/research/fnk0050-sim/tests
~~~

The demo prints the qualification digest. Supply it to the following commands. The review command writes a standalone HTML page. Practice emits a skill collection ID for exact headless replay.

~~~sh
python -m research.uel.visual compare /tmp/dog-run "$qualification"
python -m research.uel.visual review /tmp/dog-run "$qualification"
python -m research.uel.visual practice /tmp/dog-run "$qualification"
python -m research.uel.visual replay-skill /tmp/dog-run "$skills" stand --index 0
python -m research.uel.visual propose /tmp/dog-run "$qualification" --hypothesis "A moving camera could explain the shift."
~~~

To select an earlier candidate, pass its qualification digest. There is no global current model or promotion pointer to undo. To pause, place a file named CANCEL in the session directory; remove it to resume from verified journaled frames. Keep the same software and fixture settings for resume. Each cycle has a finite trial/optimizer grid (five delays), a default 60-second capture deadline, an 8 MB journal quota and a 16 MB directory admission check for new lineage objects. Local replay bounds frames, compressed bytes and decoded resolution. Archive one session directory with its IDs, or start a fresh one. Cumulative archive retention is an operator decision. No service installation.

## Field calibration and later qualification proposal

1. First proposed observation: immobilize and de-energize the dog, secure a fixed external camera, and image a ruler and measured rigid checkerboard. Mark board origin, normal and axis directions. Fix focus, zoom, image size and pose for the session. Check the floor plane and a second known length. Record observer position, clock source and exposure/receipt distinction. Do not infer metric depth from a single unscaled silhouette.
2. Measure printed square and marker sizes. Tape light removable markers to a fixed body panel and a visible rigid leg segment. Check unloaded clearance through the intended range separately before any powered test. Avoid contact surfaces, joints, wires, and the battery. Capture varied tilted board poses that cover the frame, plus one fixed world image. Command syntax: `calibrate OUTPUT --camera primary --pattern 7 5 --square-m 0.024 --world-id floor-board --world-image world.png board-*.png`. Replace the illustrative square size with the measurement.
3. For the optional second view, record its actual model, host, connector, power, driver, frame size, format and timestamp source. Measure its extrinsic pose against the same oriented board at the same scale. Use shared visible time events across the capture interval and test an independent ruler point in the overlap. An ambiguous board orientation can pass a reprojection check. Recalibrate when moved or refocused. Camera shake, blur, rolling shutter and autofocus changes need checks in actual footage. The translation-only anchor diagnostic rejects inconsistent planar shifts; rotation or a moving tracking head requires measured per-frame poses.
4. For offline replay see evidence/recording.json. Add a second source with camera_id elegoo, backend elegoo_optional, its own calibration and ArUco marker ID (field `aruco_id`). Missing calibration produces independent 2D. For metric pairs provide `world_references` with three independent noncollinear measured points (world_m and per-camera pixels), then add `sync_events` as corresponding ordered clock events in seconds. Supply exposure times. Gates cover clock fit, skew, transform, parallax, positive depth and reprojection. Use an identified marker in overlapping frames. The silicone/appearance/detector assumptions of the synthetic fixture have no physical validation.
5. To test imported, command-aligned files run `fit-recordings OUTPUT --body dog TRAIN.json HOLDOUT.json` (options may precede positional inputs). The recorded-train test shows the complete experiment metadata including frame, baseline, fixed camera, marker, command units and timestamps. Physical camera records use an explicit ArUco ID. Fit accepts only matching commands from the bounded family catalog; markerless silhouettes are lower-confidence observational evidence.
6. Any future powered probe requires a separately approved target-specific envelope, supported body and mechanical clearance, confirmed ordering and neutral, accessible independent power cutoff, independent watchdog, fall and brownout protection, good batteries, and current/thermal checks. Camera feedback alone cannot stop unsafe motion. Recovery and complex maneuvers remain simulation-only. First review action is the stationary observation in step 1.

Calibration and hardware reference material: [OpenCV calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html), [ArUco](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html), [Raspberry Pi accelerator documentation](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html), [MuJoCo documentation](https://mujoco.readthedocs.io/).

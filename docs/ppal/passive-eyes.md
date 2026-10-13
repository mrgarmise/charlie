# Charlie Eyes: passive observation and Mint launcher

Implemented against `feature/agency-first-self`, baseline `0bd08c1`.
The viewer is display-only. It neither starts games nor supplies actions, identity,
score, calibration or project-selection evidence back to Charlie.

## Audit and transport choice

The old `eyes.serve_eyes` constructed its own PiCameraSource and performed a read
inside every browser stream loop. It is a direct preview, not a passive subscriber;
using it during play risks camera contention and extra captures. It remains
available for its original use, but the new launcher does not invoke it.

The repaired player already has owned full RGB PIL frames in ObservedCamera, a
corrected playfield image, and measured generic SpriteTracker/AgencyTracker
snapshots. Original evidence images are buffered until controls close; tailing
those files cannot supply timely live pictures. A shared raw array would add
buffer lifetime/copy complexity, while an unbounded stream queue adds latency.

Chosen transport:

1. ObservedCamera offers its existing owned raw frame reference. No extra read.
2. After the existing association/agency observation, the player offers the same
   raw frame, existing crop and snapshot. After an ordinary action completes,
   it offers existing action/intent/transport evidence.
3. A **one-slot replaceable queue** retains the newest offer. No RGB copying,
   image encoding, filesystem access, network request or acknowledgement occurs
   in submit. The queue's brief in-process synchronization has measured overhead;
   “nonblocking” does not mean literally zero CPU cost.
4. A best-effort worker publishes at **3 FPS maximum**, only with recent viewer
   demand. JPEG display copies are at most 800×600, quality 65; original frames
   and full RGB evidence are never modified.
5. A single latest JSON/JPEG bundle is atomically replaced in a private runtime
   directory, normally under XDG_RUNTIME_DIR (RAM on typical Linux desktops),
   otherwise `/tmp/charlie-eyes-UID`. Storage and pending frames remain bounded.
6. A separate loopback HTTP process reads the latest bundle. Browser polling is
   sequential at about 3 FPS; slow clients cannot build a producer backlog.

No extra detector, classification, tracking, association, focus optimizer or
semantic interpreter is in the viewer. JPEG encoding uses existing Pillow, HTTP
and launcher use the standard library, and SSH/browser are existing desktop tools.
There is no streaming framework, second tracker, systemd unit or permanent server.

Detached workers encode **zero** images. Their periodic demand check and queue
submission still have a small cost, separately reported. Worker/output failures
drop display evidence and never determine gameplay eligibility or termination.

## Views and uncertainty

- **Raw frame:** the full existing camera field of view, display-scaled/compressed;
  not just the arena crop. Color is retained.
- **Tracking view:** existing corrected playfield, existing physical track IDs and
  boxes. Green solid SELF means the published identity status was confirmed;
  amber dashed SELF means provisional. Other tracks are blue without enemy/rescue
  assumptions. UNKNOWN does not become a candidate labeled as SELF.
- **Decision/evidence:** phase, identity status/confidence, agency evidence,
  commanded action and actual local transport record. A displayed action can
  occur after the displayed image's capture; adjacent evidence is not causation.
- **Learning:** current project context when provided by the existing marathon,
  including a project without a selected experiment; existing experiment plan
  when available. Missing context is null, not an invented goal or conclusion.

Both capture and publication freshness are checked. A frame older than two
seconds, a changed/closed owner, or a connection failure clears displayed imagery
and overlays and reports unavailable. Old frames are not presented as live SELF.
Overlay boxes use crop pixel coordinates; raw/crop timestamps come from the same
existing capture. Up to 128 existing detection boxes are displayed, with omitted
count explicit. The viewer does not alter canonical logs or tracking thresholds.

## Camera ownership and idle preview

`vision.Camera` now holds a cooperative Linux camera lease for its lifetime.
This covers new PiCameraSource consumers and the existing main physical camera
wrapper. A second owner fails before opening Picamera2. An active process that
does not publish passive evidence is shown as unavailable; the viewer never
falls back to another capture beside that active owner.

The launcher-owned viewer can open **one idle direct preview** when the lease is
free. It uses the existing Camera wrapper, BGR-to-RGB conversion and JPEG display;
it supplies no identity/tracks or control evidence. HTTP client count does not
create additional cameras. Preview demand expires after two seconds without a
client, and closing the launcher explicitly ends the remote server.

An active owner requests priority only during **camera initialization**, before
any capture/agency probe/gameplay action. The idle server receives a release
signal, closes the camera, and unlocks. Active initialization retries the lease
for at most one second; it never opens a second capture to work around a failure.
This is a bounded startup handoff, **not** a wait added to frame, planning or
controller execution. `camera_lease_handoff_seconds` records its cost. A hung
preview/driver yields a clear startup failure rather than weakening safety.

Camera cleanup now calls Picamera2 stop **and close**, releasing the device even
if stop fails. Initialization failures release the lease. Stale PID files do not
establish ownership: the viewer checks the actual lock. Legacy processes started
before this update may lack the lease; driver ownership errors produce unavailable
and back off, never successful parallel capture. Update/restart those processes
for cooperative handoff support.
Unavailable observer storage does not gate the active camera: it retains its
original libcamera ownership behavior. Idle preview never bypasses a missing
lease. Existing-owner refusal remains a refusal, not a storage-error fallback.

## One-time setup

Update the Pi checkout normally, preserving local work:

```bash
cd ~/Projects/charlie
git fetch origin
git switch feature/agency-first-self
git pull --ff-only origin feature/agency-first-self
```

On **Mint**, update its checkout and install the menu launcher:

```bash
cd ~/charlie/charlie
git fetch origin
git switch feature/agency-first-self
git pull --ff-only origin feature/agency-first-self
python3 setup/install_charlie_eyes_mint.py --host five@charlie
```

Use `five@charlie.local` instead if that is Mint's working Pi address. The default
remote repository is `~/Projects/charlie`, interpreter `.venv/bin/python`.
The installer accepts `--project` for a different path relative to the Pi home.
Python 3, an installed Firefox/Chromium browser, OpenSSH and Tk are sufficient on
Mint; the Pi uses its existing camera/Pillow environment.

Find **Charlie Eyes** in Mint's application menu, right-click → **Add to panel**.
Click it to open a dedicated browser window. Closing that window closes SSH input,
which shuts down the remote viewer and releases its idle camera. No recurring SSH
or systemd commands are required. An SSH key/passphrase or first-host confirmation
may appear in a desktop authentication dialog; secrets are not saved by this app.
Native ssh-askpass is used when installed, otherwise a temporary Tk dialog.

Port **8767** is retained: HTTP binds only the Pi's loopback, and the launcher
forwards Mint's `127.0.0.1:8767` over SSH. It does not expose a new public LAN feed.
An existing preview/tunnel occupying that port must be closed; the launcher does
not silently kill it. Another launcher instance fails clearly rather than
creating another camera or replacing an existing browser session.

Gameplay starts through its unchanged authorized command. Keep the viewer open
to observe; camera handoff/passive attachment happens automatically. Removing or
closing the viewer does not stop an active game. Removing the desktop entry and
`~/.local/share/charlie-eyes` uninstalls the Mint launcher; no service is installed.

## Timing measurements and validation

The [recorded benchmark](passive-eyes-benchmark.json) runs the actual calibration,
taught candidate generation, **one** VisualAgency tracker/agency pass and normal
Forebrain/Hindbrain computation over a real archived frame. Planning uses the
archived explicitly provisional world interpretation, not a newly certified SELF.
Attached mode consumes real JPEG bundles over HTTP at 3 FPS. Three randomized
rounds, two seconds per condition, were measured on this execution host:

| Mode | Mean processing FPS | Mean frame-to-action-ready | Median FPS | Median action-ready |
|---|---:|---:|---:|---:|
| Publisher absent | 17.17 | 60.40 ms | 19.21 | 52.07 ms |
| Viewer detached | 19.06 | 52.59 ms | 19.67 | 50.84 ms |
| Viewer attached | 18.62 | 54.03 ms | 19.53 | 51.20 ms |

Attached versus detached mean: approximately **2.3% lower throughput / +1.43 ms**;
median: approximately **0.7% / +0.36 ms**. Individual trials vary substantially;
the absent-publisher condition also had an unusually slow trial. Do not interpret
the baseline reversal as an improvement or claim zero overhead. Mean submission
cost was about 51–55 microseconds. Detached publication count was zero; attached
rounds received 4–6 current JPEG bundles over HTTP.

These are **offline host measurements**, not live Pi camera/gameplay/controller
latency measurements. No physical Pi or Mint session was available here. The
cloud browser blocked the loopback test URL (`ERR_BLOCKED_BY_CLIENT`), so browser
visual QA on the actual Mint remains unverified. HTTP, data, markup and lifecycle
tests passed; this limitation is not represented as successful native GUI testing.

Repeat the same bounded, non-armed benchmark on the Pi with an available archive:

```bash
python -m experiments.ppal.eyes.benchmark_passive \
  robotron-runs/body-fire-bootstrap-20261001-020552 \
  --seconds 3 --rounds 3 --output robotron-runs/passive-eyes-benchmark.json
```

Actual play now logs `viewer_state` (worker demand status/check timestamp) and
local `control_execution` in ordinary steps, plus publisher/drop/encoding costs
and camera startup handoff time in report.json. A viewer closed/opened during a
bounded run permits observational comparison without another camera:

```bash
python -m experiments.ppal.eyes.compare_passive_runs "$run_dir/report.json"
```

This reports actual capture-to-controller-start latency and ordinary action
cadence for attached/detached samples. It excludes inadequate timing/UNKNOWN and
does not claim remote display onset. Demand status is sampled every 333 ms and
expires after two seconds; transition periods and changing scene/agency difficulty
confound causal conclusions. Missing timing remains null. Physical comparative
validation and native Mint window-close behavior still require Alex's machines.

Tests cover latest-only replacement, provisional/null SELF, zero detached
encoding, worker failures, active-owner refusal with no second capture, actual
process-level priority handoff, stale owner/frame rejection, raw-read reuse,
clean camera/lease cleanup, HTTP streaming, remote stdin-EOF shutdown, Mint menu
installation and launcher/browser-close→SSH EOF lifetime. No changes were made
to `experiments/ppal/run_camera.py`, controller commands, preflight criteria,
SpriteTracker, AgencyTracker, SELF gates, score interpretation or restart safety.

Validation: **376 tests passed**, including 12 passive-observer/launcher/timing
tests and all existing tracking, agency, score, startup, replay, memory and
project regressions. `git diff --check` passed.

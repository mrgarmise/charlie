# Protected SELF observation window correction — October 24

Runtime pin: `c8db98768776bb43141530f90d331c0222f273eb`.
Tree: `3d1064d050f3786da38b46013c2ec90fce598338`.
Direct parent: PR #9 `02f5c945627dfd7b2945cd27936b4df3bd9678d1`.
Published and tested local source/test/fixture trees match exactly.
The existing controller interface and visual-readiness fixes remain included.

## Confirmed cause

Original report:
`/home/five/charlie-native-trials/visual-readiness-20261024-6ajF25mY/development-20261024-224738/game-01/report.json`.
The report already retains the originating error in `performance.stream.error`:
`critical capture window overflow; no frames silently discarded`.
Acquisition reached 655 frames at **77.36277629689837 fps**, with 636 ordinary
history evictions, 18 retained frames and 66,355,200 accounted bytes. Sensory
preflight was usable; no ordinary gameplay decisions or completed games exist.
This is a protected-window capacity defect, not a camera/focus/readiness failure.

1280x720 pixels at the existing conservative four-byte accounting require
3,686,400 bytes/frame. The unchanged 64 MiB ring fits **18** frames: about
0.23 seconds. SELF's synchronous 60 ms pulse plus **250 ms** post-pulse interval
already needs about 25 frames including its independent baseline, before wire
latency. Waiting until the whole interval ended before releasing the pin made
successful acquisition predictably exhaust memory.

The [authentic report and provenance](../../../tests/fixtures/native-causal-overflow-20261024/provenance.json)
remain byte-identical. Its regression reconstructs the original 655 acquired /
636 evicted / 18 retained counters exactly without hardware.

## Implemented correction

Only three runtime files change: `observation_stream.py`, `shot_capture.py` and
SELF's replay cleanup in `robotron_agency.py`.

- Keep the sole continuous camera producer, 24-frame count limit and **64 MiB**
  ring. No inference, encoding, storage or journal work runs on that producer.
- Run the existing bounded controller execution on a joined worker while the
  caller drains protected exposures **in order**, including the pre-command
  baseline. Do not replace protected frames with newest-only sampling.
- Transfer complete lossless pixel writes to one append-only `frames.raw` file.
  Only then acknowledge/release that frame's RAM protection. Commit the entire
  bounded file with fsync before successful causal replay. This preserves the
  existing distinction between accepted bytes and durable completion; no
  pre-fsync causal acceptance is claimed.
- Retain the full declared post-pulse interval. Controller completion sets its
  exposure-time cutoff; slow disk/replay processing cannot extend protection
  into unrelated future camera frames. Post-cutoff ordinary evictions remain
  explicitly counted. Untransferred protected-frame overflow still fails closed.
- Bound each archive to **128 frames and 256 MiB**, with a **2.5 s** collection
  deadline or the caller's earlier deadline. Load/hash-check one original at a
  time during the existing SELF algorithm. The index holds metadata, not an
  expanding list of full-resolution images. Accounting includes partial writes;
  disk limits and the existing resource stops remain in force.
- Keep sensor timestamps/sequence identities, RGB/mode/size, per-frame pixel
  hashes, baseline, exact transport action/release timestamps and independent
  observations. The existing movement/neutral response protocol and shot-origin
  inference are unchanged; collection is not SELF qualification.
- On cancellation/error, cancel and join the controller worker, interrupt a
  blocked socket when necessary, neutralize/disconnect, atomically release the
  pin and retain available originals. Invalid manifests identify the original
  exception, traceback, camera root cause, last successful metadata, worker
  state and any explicitly unarchived sequences. Partial evidence never becomes
  an accepted causal window.

Native files live in the existing episode's `causal-windows/window-*/` evidence
root. Each archive has one closed pixel file and a `manifest.json`; its entries
specify offsets/lengths, capture metadata and pixel hashes. Raw records are a
four-byte big-endian JSON-header length, UTF-8 header, then unmodified image bytes.
Failed windows retain their available originals and explicit invalid status.
Successful originals remain evidence, not live scratch buffers. Standalone tests
without an episode recorder use temporary storage and clean it on close.
There is no extra capture owner or background acquisition/inference queue.

Focus 2.0, exposure, CAL/Active Vision handoff, camera ownership, controller
LEASE/local and server deadmen, thermal/resource limits, recording, START/terminal
rules and learning integration are unchanged. No camera retry loop, servo motion,
calibration movement, firmware or policy activation was introduced.

## Verification

**155 passed in 104.02 s**, no failures/skips ([full relevant output](tests.txt)).
Focused capacity / streaming SELF / supervised controller: **50 passed in
28.67 s** ([output](capacity-tests.txt)); selections overlap and are not summed.
The new module contains **14** regressions, including full-resolution paced
77.36 fps streams with 60 ms and 400 ms pulses, complete sequence/pixel retention,
slow consumers, real SELF replay and replay failure, cancellation, unchanged
64 MiB accounting, explicit archive exhaustion, genuine ring overflow,
partial disk failure, capture timeout, stale metadata, safe admission and pixel
integrity. Existing readiness, recording, session lifecycle, supervisor, native
runner and agency-boundary selections pass too.

Development failures are retained. [Per-frame fsync experiment](initial-per-frame-fsync.txt)
failed because each fsync took about 80–90 ms on this host: it could not drain
77 fps. The final design commits the bounded file once before replay.
[Initial integration](initial-integration.txt) had 143 passes and one synthetic
fixture error: it replayed a previously observed baseline with a wall-clock
tracking timestamp. The corrected test uses the actual ObservedCamera
independent-delivery/timestamp guard; production tracking semantics were not
weakened. Source whitespace, Python compilation and handoff shell syntax pass.

These are device-free software results, not a successful native game, score,
SELF acceptance, E1/P1/I1 or learning-performance claim. No physical retry was
required before implementing the defect correction; none was performed.

## Minimal pinned installation

With gameplay stopped, run in the existing Charlie Pi checkout/environment:

```bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
charlie_release=c8db98768776bb43141530f90d331c0222f273eb
test -z "$(git status --porcelain)"
git fetch origin refs/pull/9/head
git merge-base --is-ancestor "$charlie_release" FETCH_HEAD
git switch --detach "$charlie_release"
test "$(git rev-parse HEAD)" = "$charlie_release"
test "$(git rev-parse 'HEAD^{tree}')" = 3d1064d050f3786da38b46013c2ec90fce598338
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" \
  /home/five/Projects/charlie/.venv/bin/python -m pytest -q \
  tests/test_causal_window_capacity.py tests/test_supervised_controller.py -p no:cacheprovider
```

Expect **27 passed**. These use synthetic cameras, fake wire endpoints and the
archived report; they do not open physical devices. Existing origin must remain
`mrgarmise/charlie`. Do not reset local edits. No pip or controller-service update
is needed. No raw failed observations, historical notebooks or learning stores
are replaced.

The existing bounded integrated launch is unchanged except for the pin and fresh
run root. From the same stopped-game ordinary terminal after installation:

```bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
test "$(git rev-parse HEAD)" = c8db98768776bb43141530f90d331c0222f273eb
test -z "$(git status --porcelain)"
test -f /home/five/.local/share/charlie/development/learning-evidence.sqlite3
charlie_run=$(mktemp -d /home/five/charlie-native-trials/causal-window-20261024-XXXXXXXX)
PYTHONPATH="$PWD" CHARLIE_CONTROLLER_LEASE=required \
  /home/five/Projects/charlie/.venv/bin/python -m experiments.ppal.marathon_robotron \
  --arm --recovery-trial --developmental --learning-projects --ala-learning \
  --max-games 2 --qualified-games 2 --focus 2.0 \
  --root "$charlie_run" \
  --learning-root /home/five/.local/share/charlie/development \
  --campaign-notebook /home/five/.local/share/charlie/development \
  --project-evidence /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3
```

No physical launch, deployment or service action was performed here. Native
storage throughput and useful SELF/gameplay on this pin still need observation
in the existing bounded run; software regressions cannot establish those
outcomes. Storage that stalls beyond the finite runway still stops safely with
original diagnostics. No additional physical qualification project or trial is
introduced as a prerequisite for this software fix. Keep PR #9 draft/unmerged.

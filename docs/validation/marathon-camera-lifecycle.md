# Marathon camera lifecycle — release acceptance pending

Base: `a785c9f745bd0645dd01ac70af3beb5a8d44d37b` on
`feature/native-marathon-restart`. Implementation branch:
`feature/marathon-camera-lifecycle`. October 11, 2026, UTC.

## Correction and ownership

The old marathon started a player subprocess for every game. Each subprocess
opened and calibrated the camera. In the user-reported native session
`development-20261011-192041`, game one ended independently, but game two's
repeated preflight timed out before playable gameplay. Its 78 frames are
failed-attempt evidence, not a completed second game. The human-observed score
800 is not a replacement for the unavailable machine score.

The CLI now supervises a **whole marathon worker** through the existing progress
watchdog. That worker owns one lazily opened `CameraSession`. The first episode
uses the existing sensory preflight on current observations. Later episodes
borrow the same live hardware and in-memory calibration. They keep fresh frames,
separate capture origins, separate control/agency journals, independently closed
controller connections, and independently drained recording/score writers.
A borrower cannot close the hardware. The owner closes once on normal exit,
error or interruption, before the offline learning handoff. Posttest uses a new
owner and new preflight. No saved calibration is loaded or reapplied.

`play_robotron.main(argv, camera_session=..., progress_path=...)` is the small
reusable player entry point. Standalone player invocation retains its existing
separate watchdog and fresh preflight. The existing injected marathon-driver
interface remains available for controllerless tests.

The native working `preflight.py` is unchanged. Its SHA-256 is
`8cd902f89603394fe3e492370e37f88854ee8d2e0904b49bdc2ee03aca665bb8`.
**It currently hardcodes a 2.0 diagnostic starting position.** This inherited
native camera behavior is deliberately preserved; no claim of a new automatic
focus repair is made here. CLI focus defaults remain `None`, never 1.30.

## Visual failure / CAL contract

Ordinary fresh observations feed `LiveViewMonitor`, including during agency
recovery. It retains the existing major border-loss/excessive-clipping checks
and adds a conservative relative border-detail symptom. Recognized terminal,
attract and ambiguous non-gameplay pages reset these symptom streaks. A lost
SELF does not request CAL, and duplicate timestamps cannot increase support.
This is a symptom monitor, not a physical viewpoint estimator: unknown pages
cannot independently establish camera movement or a failed geometric fit.

Persistent measured degradation or camera capture failure neutralizes controls,
records a `charlie-cal-recovery-request-v1`, marks the live owner invalid, and
stops the affected episode. The replaceable `request_recovery` outbound function
returns `status: unavailable`, symptoms separately from hypotheses, the episode
and live-session identity, requested evidence and `physical_authorization: false`.
No servo, firmware, RP2040, CAL-1 or policy activation interface is called.
There is no silent midgame recalibration. Recording failures retain their own
failure classification rather than being treated as a camera recovery service.

## Durable episode evidence

Existing `EvidenceJournal` transactions append `game_completion` records to
`<learning-root>/game-evidence.sqlite3`, normally
`/home/five/.local/share/charlie/development/game-evidence.sqlite3` for play-first.
This extends the existing journal format; it is not a replacement memory store.
The payload schema is `charlie-game-completion-v1`.

Each record retains the capture/content/manifest identity, original paths and
artifact hashes, marathon path, checks, timing, control/agency references,
start and terminal evidence, camera report, score observations and provenance,
experiment identity and notebook/context references. Media stay in their
original episode directory. Do not remove those directories merely because
references have been committed.

Classification:

* `completed`: established player gameplay, sealed recording, successful player
  return and the unchanged independent terminal/restart checks all pass.
* `invalid`: a confirmed camera/CAL or recording invalidator.
* `incomplete_unverified`: all remaining attempts, including missing reports.

A complete recording receipt alone, START acknowledgement, Python process launch,
SELF loss, diagnostic timeout or preflight failure cannot qualify a completed
game. OCR scores remain explicitly not independently verified; missing scores
remain missing. These records do **not** establish physical score improvement.
Idempotent finalization reuses a journal record; conflicting aliases are blocked,
and identical content with a different origin cannot become a second completion.
Earlier commits survive later errors and interruption. New invalid/unverified
records retain diagnostics but do not enter the qualified-game learning handoff.
Historical captures/journals are not rewritten or retroactively requalified.
Legacy reflection behavior remains available for sessions lacking these new
classification records.

`--max-games` is an attempt cap. Optional `--qualified-games N` is a completion
target within that cap. Counts and `target_met` are separate. An unverified
boundary still stops further START, even when the target has not been met.

## Host validation

All controller/camera acceptance tests here are explicitly software fixtures,
not physical experience. The real-player regression executes two simulated
playable episodes, independent terminal detection, SELF acquisition, separate
recording sealing and durable completion, while asserting one open and one
preflight. Its camera-failure variant preserves completed game one and marks
only game two invalid with unavailable CAL.

Results: 89 final focused tests passed (120.63 seconds), then 18 final
lifecycle/evidence tests passed (10.03 seconds). The serial broader run had
901 passed, 15 failed and 21 skipped (239.97 seconds). All 15 failed cases
match independently rerun failures at the untouched exact native baseline:
14 autofocus cases and one geometry-jitter expectation. Broader regression
preceded final focused hardening; the final changed paths were rerun afterward.
An initial overlapping run was contaminated by ownership-lock contention;
it is not acceptance evidence. Exact commands, environment, timestamps,
source hashes, JUnit hashes and failed cases are in
`marathon-camera-lifecycle-tests.json`. Tests do not weaken the native camera code. The baseline's
`FocusSource` host fixtures lack the `read_fresh()` method now required by the
native autofocus implementation; those pre-existing failures remain visible.
The geometry replay fixture also assumes jitter 8, while the preserved native
configuration uses 12.

Changed files: `camera_session.py`, `cal_recovery.py`, `game_evidence.py`,
`live_view.py`, `play_robotron.py`, `marathon_robotron.py`, the new
`test_marathon_camera_session.py`, the relevant no-midgame-recalibration assertion
in `test_robotron_autofocus.py`, and these two validation documents.

## Guarded Pi preparation — no gameplay or deployment performed here

Do not overwrite `/home/five/charlie-restart-recovery`. First inspect its HEAD,
status and worktrees, and preserve any new modifications:

```sh
cd /home/five/charlie-restart-recovery
git rev-parse HEAD
git status --short
git worktree list
mkdir -p /home/five/charlie-recovery-backups
git diff --binary > /home/five/charlie-recovery-backups/native-before-camera-lifecycle.patch
```

Copy any untracked local camera backups separately; `git diff` does not include
untracked files. Do not stash, reset or delete evidence. Confirm the baseline
identity is the exact commit above, or investigate subsequent work before any
integration. Fetch the published feature and create a separate worktree:

```sh
git fetch origin feature/marathon-camera-lifecycle
git log --oneline a785c9f745bd0645dd01ac70af3beb5a8d44d37b..FETCH_HEAD
git diff a785c9f745bd0645dd01ac70af3beb5a8d44d37b FETCH_HEAD -- experiments/ppal/preflight.py
git worktree add -b native-camera-lifecycle-validation /home/five/charlie-marathon-camera-lifecycle FETCH_HEAD
cd /home/five/charlie-marathon-camera-lifecycle
python3 -m pytest tests/test_marathon_camera_session.py tests/test_marathon_deferred.py tests/test_restart_discovery_evidence.py tests/test_recording_handoff.py tests/test_robotron_startup_boundaries.py tests/test_progress_supervision.py -q
```

Verify the fetched SHA against the published handoff. Empty preflight diff is
required. Check any native camera resource owner before camera-only testing.
Do not execute an armed command until the user separately authorizes supervised
native gameplay. No installed service or other worktree is changed by preparation.

Rollback is to stop the new process through the existing operator STOP/neutral
path, verify controller and camera release, and use the unchanged original
worktree at `a785c9f...`. Retain all newly generated evidence and journal records;
rollback does not delete or reset the development notebook.

## Release-blocking supervised acceptance

After separate authorization, with physical motion disarmed and no learned-policy
activation, the normal three-game command is:

```sh
python3 -m experiments.ppal.marathon_robotron --arm --developmental --learning-projects --play-first --max-games 3 --qualified-games 3 --learning-root /home/five/.local/share/charlie/development
```

No obsolete focus argument is supplied. The unchanged native preflight behavior
above still applies. Verify all of the following with original capture evidence:

1. One camera initialization and one successful current-view preflight.
2. Actual playable game one, causal SELF acquisition, independently confirmed end.
3. Evidence-based restart permission; **actual playable game two**, fresh camera
   observations and new causal SELF acquisition using the same live session.
4. Independently confirmed game-two ending and distinct sealed original package.
5. Separate completed records for both games in the durable journal; missing
   scores remain missing. No game-two calibration or camera reopening.
6. Game three follows the same rules. Three qualified games are required, not
   three attempts or three START commands.
7. Camera release precedes existing offline Executive/Reflection/Meditation work.
   Inspect `reflection-progress.json`: `checkpointed` or `yielded` does not prove
   substantive meditation completed. Resume with the existing offline interface:

```sh
python3 -m experiments.ppal.marathon_robotron --reflect-session robotron-runs/ACTUAL_PRETEST_SESSION --developmental --learning-projects --play-first --learning-root /home/five/.local/share/charlie/development
```

After substantive offline learning is evidenced and posttest is separately
authorized, invoke the normal command again. It creates a fresh camera session
and independent preflight. Compare independently qualified episodes, plans,
notebook revisions and score evidence. No six-game or learning success is
claimed before those observations. Exercise operator interruption and native
thermal/resource limits; do not create a new system supervisor.

Native tests and supervised game-one-to-game-two gameplay acceptance are pending.
No live gameplay, START, servo movement, camera-only native test or deployment was
performed in this Work session. Original native session artifacts were described
by the user; they were not available here for independent reinspection.

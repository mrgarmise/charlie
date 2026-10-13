# Progress-aware marathon handoff — 2026-10-11

Base: `9eeba7ca2ed69a412ab39b7f03c292842103edc6`, directly on
`feature/marathon-camera-lifecycle`. Separate branch:
`feature/progress-aware-marathon-watchdog`.

## Finding and correction

The former `finalizing` watchdog compared elapsed time with phase entry, imposing
an unconditional 90-second finalization cutoff. The handoff performs several
full, independent capture checks. Hashing, original-observation binding checks,
and fsync exposed no work progress. The code establishes this failure mechanism;
it does not establish exactly which operation was interrupted in native session
`development-20261011-203343`. That original session is unavailable in this host
checkout. Its score 900, 636 artifacts and 26.3-second verification are user-supplied
observations, not new independent measurements.

The independent parent now times inactivity between increasing work counters.
Timestamp writes, repeated counters, phase-entry resets within processing, and
invalid counters do not count. Actual completed work increments the counter:
1 MiB hash chunks, completed hashes, verified journal records, checked observation
bindings, synced artifacts and completed handoff operations. Publications are
coalesced to at most four per second within long loops, with operation completion
published immediately. There is no timer or background heartbeat. A blocked hash
read, fsync, SQLite commit or writer join eventually stalls. The unchanged normal
90-second inactivity allowance applies; total productive finalization has no new
wall-clock cutoff. Existing explicit offline budgets still apply.

Pending operation names identify score evidence processing, capture validation,
completion journal commit, session write, and restart checks. Supervisor JSON
retains `last_progress.operation`, `last_work`, counters, reason and reap status.
Repeated verification passes are retained; no integrity guard is cached or skipped.

An fsynced session bookmark saves the successful worker return code before heavy
handoff. Interrupt cleanup preserves that known code instead of unconditionally
substituting 130. Interrupted live episodes still receive 130. Completion records
remain immutable and idempotent; conflicting records remain errors. Interrupting
handoff stops further gameplay regardless of successful reconciliation. Originals,
score qualification, causal SELF, independent restart authorization, camera reuse,
CAL gates and physical authority are unchanged. The native preflight SHA256 remains
`8cd902f89603394fe3e492370e37f88854ee8d2e0904b49bdc2ee03aca665bb8`.

Changed implementation files:
- `experiments/ppal/progress_supervision.py`
- `experiments/ppal/marathon_robotron.py`
- `experiments/ppal/play_robotron.py`
- `experiments/ppal/progress_evidence.py`
- `experiments/ppal/game_evidence.py`
- `experiments/ppal/score_observer.py`
- `memory/episode_identity.py`

New regression file: `tests/test_progress_handoff.py`. Results and exact commands
are recorded in `progress-aware-marathon-watchdog-tests.json`. Tests use accelerated
clocks or explicitly simulated capture/control fixtures. They are not native games.

## Guarded native preparation (not executed here)

Preserve the existing worktree, camera edits and all untracked files. Do not reset,
stash or copy over the running installation. Stop any existing worker through the
normal operator STOP path and verify camera/controller release before native tests.

```sh
cd /home/five/charlie-marathon-camera-lifecycle
git rev-parse HEAD
git status --short
git worktree list
git fetch origin feature/progress-aware-marathon-watchdog
git diff 9eeba7ca2ed69a412ab39b7f03c292842103edc6 FETCH_HEAD -- experiments/ppal/preflight.py
git worktree add -b native-progress-watchdog /home/five/charlie-progress-watchdog FETCH_HEAD
cd /home/five/charlie-progress-watchdog
python3 -m compileall -q experiments/ppal memory/episode_identity.py
python3 -m pytest -q tests/test_progress_handoff.py tests/test_progress_supervision.py tests/test_marathon_camera_session.py tests/test_marathon_deferred.py tests/test_recording_handoff.py tests/test_restart_discovery_evidence.py tests/test_episode_identity.py tests/test_buffered_recording.py tests/test_score_observer.py tests/test_score_review_queue.py tests/test_score_feedback_learning.py
```

Verify FETCH_HEAD against the published commit identifier and require an empty
preflight diff. Use the Pi's established dependency environment, not a replacement
camera installation. Run tests serially: the existing gameplay resource lock is
shared. These commands do not deploy a service, send START or move servos.

For read-only verification of the failed native package, set its actual preserved
path, then run this from the new checkout (no camera or controller opened):

```sh
export CHARLIE_DIAGNOSTIC_GAME=/actual/preserved/path/development-20261011-203343/game-01
python3 - <<'PY'
import os,time
from pathlib import Path
from memory.episode_identity import inspect_capture
root=Path(os.environ['CHARLIE_DIAGNOSTIC_GAME']);count=[0];start=time.monotonic()
def done(event):
    count[0]+=1
    if count[0]%100==0:print(count[0],event,flush=True)
identity=inspect_capture(root,on_progress=done)
print('capture',identity['capture_id'],'manifest',identity['manifest_id'])
print('artifacts',len(identity['artifacts']),'checkpoints',count[0],'seconds',time.monotonic()-start)
PY
```

Retain original artifacts, journals, session/supervisor JSON, hashes and this output.
Do not rewrite historical session status or invent a successful worker return code
for old evidence. Existing `preserve_game` can reconcile an interrupted completion
only with established original report/return-code provenance; conflicting finalized
records are preserved and require diagnosis.

## Separately authorized supervised acceptance — release blocker

Live gameplay remains unauthorized by this task. Only after separate authorization,
with servo/physical CAL disarmed and operator STOP available, use the existing
normal command from the new worktree:

```sh
python3 -m experiments.ppal.marathon_robotron --arm --developmental --learning-projects --play-first --max-games 3 --qualified-games 3 --learning-root /home/five/.local/share/charlie/development
```

Verify one camera initialization/preflight, playable game one, independent terminal
evidence, productive postgame checkpoints, durable completion and session update,
then independently authorized START and **actual playable game two**, fresh camera
observations and causal SELF. Verify game two's independently confirmed ending and
separate completed evidence. No second calibration is permitted. Issuing START,
printing GAME 2, or passing these tests is insufficient. Continue to game three
only through existing guards. Camera release must precede offline Executive work.
Preserve pending/negative score findings; no OCR result establishes improvement.

Rollback: stop and neutralize the new process, verify camera/controller release,
return to the unchanged `/home/five/charlie-marathon-camera-lifecycle` baseline.
Keep all new evidence and development journals. No installation files or existing
worktrees need replacement for this validation. Do not delete the new worktree
while evidence or unmerged native modifications remain there.

Remaining risks: progress publication and additional fsync have native filesystem
costs not measured here; any single operation exceeding 90 seconds without a
completed-work checkpoint still safely stalls. Native tests, original-session
replay and supervised playable game-two acceptance are pending. This report claims
no fresh Pi validation, gameplay completion, score improvement or deployment.

## Host results

Final focused run: **116 passed, 1 skipped**, 34.64 seconds.
Serial `tests/` run: **912 passed, 15 failed, 21 skipped**, 230.928 seconds.
The 15 failed cases exactly match the published baseline failure set: fourteen
obsolete autofocus fixtures lack `read_fresh`, and one geometry fixture expects
8-pixel jitter while the preserved native configuration uses 12. These camera
files and assertions were not changed. Repository-wide discovery additionally
stopped with six collection errors in legacy Pico/native camera scripts and an
import collision; no complete repository-wide green result is claimed.
Compilation and `git diff --check` passed. The final focused rerun includes the
additional progress-owner/offline-units regression added after full collection.

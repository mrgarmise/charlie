# Prompt Robotron terminal recognition and restart

Base: `3723132e0a7643d24b7670c202aba0f4a1acee12` on
`feature/progress-aware-marathon-watchdog`. Separate implementation branch:
`feature/prompt-terminal-restart`.

## Investigation

Existing functionality was recovered from `episode_end.py`, `robotron_screen_state.py`,
`robotron_agency.py`, `play_robotron.py`, the marathon and their regression suites.
Relevant history includes `c940dd8` (episode end/optics), `6ddba67` (independent
boundary corroboration), `c97e497` (recorded screen/startup discovery), `ca7bc48`
(qualified causal discovery failure), `a785c9f` (native integration), `9eeba7c`
(single-camera lifecycle), and `3723132` (completed-work watchdog).

The former visual rule waited for eight consecutive non-gameplay observations,
plus rankings and a later attract/startable streak. A gameplay-looking attract
sequence could reset that evidence; recovery could continue indefinitely. Logo
recognition required an optional operator reference. Startup could attach to a
moving demonstration rather than start the next game. Score instrumentation fed
all agency frames, including attract demonstrations, into the same score tracker.

The current user-reported native observation (1100, SELF loss, high scores/title,
demonstration reacquisition, later 1300, operator interruption) has not been supplied
as an original capture package here. Those scores are not independently verified
or corrected by this repair.

## Implementation

- Extend the existing episode observer: three fresh strong postgame pages after
  three fresh gameplay observations establish a persistent transition. Require
  acknowledged START or confirmed causal SELF entry evidence. Strong rankings
  require both existing recorded Heroes/All-Time heading thresholds; a title
  requires a hashed complete-logo match. A single page, repeated timestamp, blank
  frame, unsupported heading, elapsed deadline or moving sprite cannot qualify it.
- Retire agency and tracking identity at verification, including inside probe
  observation. Suppress further agency probes after positive terminal suspicion.
  Gameplay-looking demonstrations cannot clear the verified transition or create
  a new SELF in that episode.
- Normal loss gets three seconds of causal recovery, then neutral fresh terminal
  observations. At twenty seconds unresolved loss stops as `OBSERVATION UNCERTAIN`,
  with an unknown/unverified boundary. Initial discovery also has a twenty-second
  upper bound. These are declared operational investigation limits, not game-over
  evidence, proof of pulse effectiveness, or a gameplay-duration cutoff.
- Separate independent completion qualification from START permission. A verified
  completed package can be journaled even when no startable screen is available;
  that package cannot authorize START. Prompt completions collect three subsequent
  fresh startable/title observations while neutral, within a bounded 20-second
  wait. Preserve legacy proof rules for historical packages.
- The marathon passes the sealed previous episode via `--restart-from` for game
  two onward. The real player independently verifies it, rejects demonstration
  attachment, waits for three fresh recognized startable/title frames, sends
  **one START**, then requires three fresh gameplay observations. No retry START
  is sent when acknowledgement or visual commencement fails. Existing first-game
  startup exploration is preserved.
- Score processing has separate gameplay and non-gameplay trackers and labeled
  original log rows. The completed report selects only supported gameplay snapshots
  at/before its frozen camera timestamp; retain the final gameplay image even if
  the last diagnostic image is later. Deferred score review excludes non-gameplay
  rows. Missing/unreadable scores remain unresolved; the score is still a reading,
  not an independently qualified complete-game SCORE certificate.
- Preserve watchdog checkpoints, immutable journals, episode identities, duplicate
  rejection, one camera/preflight per marathon and camera release before learning.
  No physical/CAL authority, camera geometry or gameplay policy is changed.

## Authentic pixel evidence and limits

Existing native fixture `tests/fixtures/robotron-calibration-20261011/exposure-ev-3.png`
comes from `development-20261011-001506/game-01`, unchanged from the original upload.
SHA256: `1a6c37eb4084b306ade3cc3957312db563fbc9e5d71690cf51fd70eb69a7739c`.
Its complete ROBOTRON/2084 logo supplies a derived binary recognition mask in
`config/robotron/screen-labels/title-anchor.json`, with source, crop, dimensions,
compression, integrity hash and threshold. This image is a recognition anchor,
**not held-out native acceptance**. Reconstructing its crop reproduces the mask.

Existing October 1 full-camera regression fixtures provide recorded high-score,
instruction and gameplay pages, with provenance in
`tests/fixtures/robotron-screen-states/provenance.json`. Pixel replay validates
those saved observations; simulated temporal order, controllers and scores do not
become authentic game outcomes. The latest native run remains uninspected.

## Changed files and tests

Implementation: `episode_end.py`, `robotron_screen_state.py`, `play_robotron.py`,
`marathon_robotron.py`, `game_evidence.py`, `score_observer.py` under
`experiments/ppal`, plus the title-anchor JSON. The existing camera session,
preflight, CAL recovery and progress supervision modules are byte-unchanged.

New tests: `tests/test_prompt_terminal_restart.py`. Extend the existing shared-
camera two-game fixture to put an autonomous demonstration inside second-game
startup. Update three older agency integration regressions which demanded more
than sixty seconds of unresolved agency search: they now require an unverified
stop before a delayed terminal page, consistent with this mission. Existing rapid
respawn, causal identity, controller/camera failure and cleanup tests remain.
Exact commands, result counts, failure cases, environment, source and JUnit hashes
are in `prompt-terminal-restart-tests.json`.

## Native Pi preparation — no deployment performed here

Keep `/home/five/charlie-marathon-camera-lifecycle` and its local edits unchanged.
Inspect all current state; preserve untracked backups separately. Do not reset,
stash, reinstall the arcade, or relocate persistent development evidence.

```sh
cd /home/five/charlie-marathon-camera-lifecycle
git rev-parse HEAD
git status --short
git worktree list
git fetch origin feature/prompt-terminal-restart
git diff 3723132e0a7643d24b7670c202aba0f4a1acee12 FETCH_HEAD -- experiments/ppal/preflight.py experiments/ppal/camera_session.py experiments/ppal/cal_recovery.py experiments/ppal/progress_supervision.py
git worktree add -b native-prompt-terminal-validation /home/five/charlie-terminal-restart FETCH_HEAD
cd /home/five/charlie-terminal-restart
python3 -m compileall -q experiments/ppal
python3 -m pytest -q tests/test_prompt_terminal_restart.py tests/test_robotron_agency_integration.py tests/test_marathon_camera_session.py tests/test_robotron_episode_end.py tests/test_restart_discovery_evidence.py tests/test_progress_handoff.py tests/test_progress_supervision.py tests/test_score_observer.py tests/test_score_review_queue.py tests/test_score_feedback_learning.py tests/test_recording_handoff.py tests/test_robotron_recorded_screen_states.py
```

Match FETCH_HEAD to the published implementation SHA. The safety/camera/watchdog
file diff must be empty. Run tests serially with the Pi's established environment;
they simulate controller interfaces and do not authorize live commands. Replay any
new native originals read-only using their existing calibration and retain source
hashes, capture timestamps, classification and uncertainty. Do not teach a new
positive reference from an unqualified ambiguous page just to pass acceptance.

## Release-blocking supervised acceptance

No live gameplay, camera-only native operation or servo movement is authorized by
this repair. After separate supervised gameplay authorization, physical CAL/servo
movement disarmed, known camera ownership and operator STOP available:

```sh
cd /home/five/charlie-terminal-restart
python3 -m experiments.ppal.marathon_robotron --arm --developmental --learning-projects --play-first --max-games 3 --qualified-games 3 --learning-root /home/five/.local/share/charlie/development
```

Observe and preserve:
1. One successful native preflight and camera session; actual game one with causal
   SELF and supported gameplay observations.
2. SELF loss; prompt recognition of repeated high-score/title evidence, identity
   retirement and neutral controls. No time-derived completion; unsupported imagery
   at twenty seconds must stop unverified.
3. Frozen game-one score image/timestamp. Later attract values stay separate.
4. Completed sealed package and durable journal record, then fresh startable screen
   and exactly one START in the next episode's control evidence.
5. **Actual playable game two**, causal SELF and fresh observations on the same
   camera/calibration; its independently supported ending and separate completed
   package. Starting a process, printing GAME 2, or acknowledgement alone does
   not pass. No game-two preflight or camera reopening.
6. Library/arcade/controller protocol unchanged; no servo/CAL movement. Camera
   release precedes offline learning. Record native CPU/capture cadence and any
   missed/unknown headings; title matching generalization/performance is pending.

Rollback: operator STOP/neutralize, verify camera/controller release, return to the
unchanged previous worktree/commit. Keep every new original package, score row,
journal and failed investigation. Do not truncate databases or rewrite historical
report scores. No service or installed arcade changes are required for this test.

This is host-tested software preparation, not native acceptance or demonstrated
Robotron score improvement. The release remains open until supervised game-one
completion → actual playable game two → independently confirmed game-two completion.

## Host result receipt

Focused regression run: **124 passed**, 112.09 seconds. Final serial host `tests/`
run, including the subsequently added durable-completion/no-permission regression
and final guards: **925 passed, 15 failed, 21 skipped**, 231.095 seconds. The failure
set exactly matches the published baseline: fourteen autofocus fixtures lack
`read_fresh`; one geometry fixture expects 8-pixel jitter while preserved native
configuration uses 12. No camera thresholds or tests were altered to hide them.
Compilation and `git diff --check` passed. No fresh Pi test is claimed.

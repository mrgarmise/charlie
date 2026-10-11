# Native Robotron terminal investigation repair

Status: implemented for host validation; **pending native Raspberry Pi acceptance**.
Base: `9e423e982a2f9b9a244c7126543fb4b04debb465`, published
`feature/prompt-terminal-restart`. This isolated branch preserves that worktree.
No live gameplay, servo movement, CAL activation, deployment, or notebook edits
were performed. The base's 91 native tests are user-reported historical evidence,
not validation of this repair.

## Authentic evidence and diagnosis

Source: supplied `charlie-terminal-restart.tar.gz`, SHA-256
`5e95637c06ace5faa826d97a22b38c6d6e2aa8b9f84b7d23ebdd050f5076f33f`.
Original episode: `robotron-runs/development-20261011-221727/game-01`.
Capture identity:
`capture:4b5feb18af64c2d54065b4dc45b005205dfdd3b6f043e2ba6892034e0b97f0b6`.
Original journal and capture seal were verified through existing read-only
interfaces. The source report records the base revision and a clean native tree.
Original artifacts remain unchanged. Derived masks in tests retain source image
hashes, observation IDs and exposure timestamps. They are diagnostic features of
one episode, never new independent experience.

The original result was `OBSERVATION UNCERTAIN`, ticks 8, no confirmed ending,
`unverified_episode_boundary`, zero qualified games. Fresh observations reached
the recognizer; this was not a camera outage. The 20-second recovery timer
expired without a positive terminal transition. The baseline classifier matched
high-score headings and Robotron's complete logo, but had no central GAME OVER
word matcher. Visual inspection of original captures 152, 153 and 154 shows
GAME OVER inside a uniform yellow gameplay border. The preserved baseline
classified all three as gameplay, retaining sprites as active-field evidence.
The new matcher identifies the complete words instead of treating the border
as sufficient. No previous label, border or geometry threshold was relaxed.

| Original event | Monotonic exposure/time |
| --- | ---: |
| START transport acknowledgement | 15798.224070728 |
| First ordinary action | 15818.111348947 |
| REACQUIRING transition | 15822.692590049 |
| Recovery start inferred from recorded batch deadline | 15822.713142799 |
| GAME OVER capture 152 | 15839.329036 |
| GAME OVER capture 153 (reference) | 15840.236423 |
| GAME OVER capture 154 (third fresh page) | 15840.790938 |
| Original recovery deadline | 15842.713142799 |
| Original stopped process | 15843.715817372 |

Read-only replay confirms the transition at 15840.790938, 1.922 seconds before
the original deadline. Keep the 20-second limit. Captures 155 and 156 are a
wipe and blank/striped transition, not supported START permission. There is no
postgame instruction screen in the supplied original sequence. Replay explicitly
returns `start_authorized=false`. It does not rewrite or upgrade the original
completion record. Earlier successful session `development-20261011-203343` is
not in the supplied originals; its claimed success cannot be independently
compared here.

The single reference is capture 153. Captures 152 and 154 are temporal holdouts
from the same episode, with similarities 0.9906 and 0.9933. Gameplay negatives
120/145/151, wipe 155 and blank 156 score below 0.31. Similarities are not
probabilities. Different native installations/episodes still require acceptance.

A second code defect allowed a recovery deadline check to beat terminal evidence
already confirmed inside a frame batch. Terminal confirmation now takes priority.
Quiet investigation previously spent four more sprite/association frames per
iteration and classified the same camera observation more than once. It now
uses the already delivered fresh frame, while a narrowly scoped memo reuses only
an identical camera observation ID/timestamp/calibration identity. New frames
are always classified; returned diagnostics cannot mutate cached results.

The original OCR report says 800; the inspected late original camera image shows
700. This is unresolved score-quality evidence, not permission to replace the
recorded score or claim improvement. Existing last-supported-gameplay freezing
and separate later attract readings remain intact.

## Startup and learning scheduling

START write to first ordinary action took 20.014 native seconds. SELF discovery
alone took 14.225 seconds; the post-exploration candidate watch took about 3.235
seconds. Reuse the existing three fresh commencement observations only while
recent and ordered, requiring another fresh positive frame. Stale or contradictory
views discard that prior. Missing candidate counts remain null, never fabricated.
The center-spawn prior changes initial candidate ordering only. No causal response,
reversal, neutral, confidence, separation or identity requirements were weakened.
There is no demonstrated native startup speedup yet.

Both in-process and supervised-parent automatic scheduling now require at least
three qualified completions, target satisfaction, a successful final block state
and camera cleanup. An incomplete play-first CLI block exits 2 and does not
schedule between-block meditation. Explicit unarmed `--reflect-session` remains
available for a separately requested diagnostic investigation. A qualified block
uses the existing offline Executive once, after camera release. A subsequent
separately authorized three-game invocation creates a fresh camera session.

## Changed files

- `robotron_screen_state.py`: complete recorded GAME OVER matcher and current-observation memo.
- `episode_end.py`: accept that positive page through the existing temporal rule; concise diagnostics.
- `play_robotron.py`: persist source-bound diagnostics, avoid redundant quiet batches, prioritize confirmed endings, reuse recent commencement evidence.
- `robotron_agency.py`: explicit center candidate-order hypothesis, unchanged causal qualification.
- `marathon_robotron.py`: independently check the new positive page and gate scheduled learning.
- `config/robotron/screen-labels/game-over-anchor.json`: hashed native reference and calibration.
- `tests/fixtures/robotron-terminal-221727/features.json`: provenance-preserved diagnostic masks.
- `tests/test_native_terminal_forensics.py`, `tests/test_marathon_camera_session.py`: focused regressions, all controllerless.
- `tools/replay_robotron_terminal.py`: read-only original-capture replay with external output.
- This report and validation receipts: commands, results, hashes and limitations.

`preflight.py` SHA-256 remains
`8cd902f89603394fe3e492370e37f88854ee8d2e0904b49bdc2ee03aca665bb8`.
Camera lifecycle, CAL stub and watchdog source files remain byte-identical to the
base. Gameplay/controller protocol and learned-policy activation are unchanged.

## Native validation and reversible integration

These commands prepare an isolated validation worktree; they do not deploy or
start gameplay. Confirm the published branch SHA against the delivery receipt.
Stop if the native source worktree contains changes; preserve them rather than
resetting or copying over it.

```bash
cd /home/five/charlie-terminal-restart
git rev-parse HEAD
git status --short
git worktree list
git fetch origin feature/native-terminal-forensics
git rev-parse FETCH_HEAD
git diff 9e423e982a2f9b9a244c7126543fb4b04debb465 FETCH_HEAD -- experiments/ppal/preflight.py experiments/ppal/camera_session.py experiments/ppal/cal_recovery.py experiments/ppal/progress_supervision.py
git worktree add -b native-terminal-forensic-validation /home/five/charlie-native-terminal-forensics FETCH_HEAD
cd /home/five/charlie-native-terminal-forensics
PYTHON=/home/five/Projects/charlie/.venv/bin/python
"$PYTHON" -m pytest -q tests/test_native_terminal_forensics.py tests/test_prompt_terminal_restart.py tests/test_robotron_recorded_screen_states.py tests/test_robotron_startup_boundaries.py tests/test_ppal_agency.py tests/test_marathon_camera_session.py tests/test_marathon_deferred.py tests/test_progress_handoff.py tests/test_progress_supervision.py tests/test_restart_discovery_evidence.py tests/test_score_observer.py
"$PYTHON" tools/replay_robotron_terminal.py /home/five/charlie-terminal-restart/robotron-runs/development-20261011-221727/game-01 --output /home/five/charlie-terminal-replay-221727.json
```

Replay refuses output within the original episode or overwriting an existing
output. Expected: 65 post-START observations; first terminal 15840.790938; START
not authorized. Run the broader native suite too, separating known preserved
camera-fixture failures from new failures. Do not declare new native acceptance
from host tests or this replay.

Only after separate supervised gameplay authorization, with servos disarmed,
use the normal application (the command below was **not executed here**):

```bash
cd /home/five/charlie-native-terminal-forensics
PYTHON=/home/five/Projects/charlie/.venv/bin/python
"$PYTHON" -m experiments.ppal.marathon_robotron --arm --developmental --learning-projects --play-first --max-games 3 --qualified-games 3 --root /home/five/Projects/charlie/robotron-runs --learning-root /home/five/.local/share/charlie/development
```

Observe and preserve: genuine gameplay/causal SELF in game one; independently
confirmed ending; fresh startable observations authorizing exactly one START;
**actually playable game two** using the same camera; game-two SELF and confirmed
ending; separate immutable qualified records; three qualified completions;
camera release; one scheduled offline phase through the normal Executive. No
servo movement. An unverified ending must stop further START and scheduled
meditation. A later authorized three-game block uses a new invocation/camera.
Never count launches, attempts, demonstrations, replay or simulated tests as
completed games.

Rollback: stop the new process using the existing operator STOP, verify neutral
controls and camera release, then use the unchanged previous native worktree.
Do not reset learning notebooks, journals, game evidence or camera configuration.
No running installation was changed by this work.

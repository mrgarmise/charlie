# Robotron campaign and retained Executive handoff

This branch extends integrated `master` `bcf8082f6319c63c4bd6bcceeab5faea37241654`. It merges the read-only E1 probe lineage ending at `9152ee0`; the information-yield estimator remains **shadow only**. Best of Charlie and all historical branches remain intact. This is software development, not native installation or ALA-2 acceptance.

## Implemented path

`python -m learning.campaign` is a phase adapter over the existing marathon, watchdog, recording journals, Reflection and normal `DevelopmentLifecycle`. It does not select hypotheses, implement a second Executive, generate arbitrary code, reset history or confer candidate authority.

The adapter freezes source/configuration identities and the operator-confirmed original notebook. The first three-game block uses the frozen baseline. Completed blocks release the camera before existing bounded reflection and Executive investigations. The original notebook's immutable records are transferred into the existing marathon project projection before the next block; outcomes return through the established reflection handoff. The existing Executive/Evaluator can then choose its eligible actuator-response experiment. A transfer preserves record identities and is not new independent experience.

Normal campaigns support 3–100 total games in blocks of at most three (`--games 10` gives 3+3+3+1). Expansion beyond three requires original three-game lifecycle checks plus the operator's explicit observation attestation. The final partial block is baseline-only. None of these counts certifies scores or learning. An incomplete block stops the campaign; no additional game or automatic meditation is scheduled for that block.

An existing Charlie-originated `gameplay_experiment_proposal` can instead commission its exact one-game baseline acquisition. Its question, candidate identities, measurements and original proposal are retained. Delivery is idempotently linked to the original project and explicitly awaits independent measurements. Observing a game cannot itself qualify identities/trajectories, run an unqualified candidate, resolve the hypothesis or satisfy E1/P1/I1. Existing acquisition and motion-corpus qualification must admit those measurements before the original temporal experiment can execute.

The offline cycle now gives predictive-usefulness feedback only for supported/contradicted predictions. Unresolved results remain durable findings/dependencies, without false negative credit. Historical feedback is preserved unchanged; this correction applies to subsequent resolutions and is not retrospective learning acceptance. Repeated exhausted evidence remains held by the existing Executive.

Explicit `--learned-policy` now reaches the marathon's player. The existing physical qualification/activation/rollback checks run before every episode; an offline grant cannot be upgraded by gameplay permission. The campaign freezes that separately approved manifest. This branch activates no policy, and does not automatically replace a frozen manifest with a new candidate.

## Authority, STOP and recovery

`prepare` is offline and does not arm anything. `arm` is an explicit operator command with a bounded duration (up to 24 hours), game count, frozen source, notebook, proposal and optional already-qualified policy. Native camera/controller/start/restart preflight remains mandatory inside the existing player. The grant permits Robotron controller activity only; no servo, firmware, downloads, game switching or candidate deployment.

The parent checks revocation/expiry before worker launch and each watchdog poll (normally 0.2 seconds), independently of child heartbeats. Revocation uses the existing process-group stop, grace/escalation and controller cleanup. Hardware neutrality and failure latency still require native verification; a host test is not a physical measurement. Permission expiry is loss of operator authority, not an analysis cutoff. No healthy game receives `--game-seconds` or a campaign processing deadline.

A durable launch intent precedes START. If the campaign process disappears while a block may have played, restart marks it blocked and does not replay START. Preserve and reconcile that block's original progress, supervisor, session and completion records before preparing another campaign. Offline reflection may resume without arming. Camera, CAL-1, servo authority, terminal recognition and progress-watchdog source are unchanged.

The original notebook's `offline.lock` excludes a simultaneous Executive writer while gameplay uses that notebook. The campaign uses its existing JSONL memory and SQLite Evaluator, rather than the unrelated default memory directory. Release the existing application-owned Executive cleanly before campaign operation; this command does not stop services for you. All original notebooks, archives, October 9 failures and candidate identities remain in place.

## Authentic evidence checked offline

The October 16 overnight and diagnostic archives were recovered unchanged. They contain original record exports, logs and continuity reports, not the full original runtime memory evaluator or original camera/trajectory artifacts. The before/after copies were reconstructed only for read-only analysis; they are not replacement native notebooks.

The existing E1 probe examines 3,247 original records and 585 additions across 19 shared projects. The outcome ablation changes **zero scores and zero eligible decision evaluations**. Six provenance-only changes do not constitute decision influence. E1 remains NOT YET DEMONSTRATED.

The preserved proposal `97f90b0167670c30404e4cb8fdc16e6daacead326ae50105125c6fc7f5b64c65` belongs to project `aef1dd40685d65655699145b7e6105b2af15b5db18589de7aa58c7c713ac3a9c`. Its original question concerns independently qualified held-out temporal motion error. Offline preparation resolves that request to the one-game acquisition adapter without an authority file or physical execution. It still requires hash-bound independently reviewed identities, measured board trajectories, 150 ms ±25 ms adjacent horizons, validation plus three unconsulted final experience groups, occurrence boundaries and independent score annotation. A new game alone cannot satisfy all of those requirements.

See `native-e1-replay.json`, `authentic-pathway.json` and `authentic-dependencies.json`. Source digests are retained in the dependency receipt. Exported private history and full archives are not copied into this branch.

## Native preparation — operator execution only

Use the published commit in the handoff. Keep the installed Best of Charlie release and original notebook. The following creates a separate worktree and never installs firmware or switches the running release:

```bash
REPO=/home/five/Projects/charlie
REVISION=<published-commit-from-handoff>
git -C "$REPO" fetch origin
APP=/home/five/charlie-campaign-validation-$REVISION
git -C "$REPO" worktree add --detach "$APP" "$REVISION"
PYTHON=/home/five/Projects/charlie/.venv/bin/python
STATE=/home/five/.local/share/charlie/development
cd "$APP" || exit 1
"$PYTHON" tools/charlie status
"$PYTHON" tools/charlie readiness
"$PYTHON" tools/inspect_developmental_progress.py --help
"$PYTHON" -m pytest -q tests/test_gameplay_campaign.py tests/test_ala_diagnostics.py tests/test_marathon_camera_session.py tests/test_marathon_deferred.py tests/test_progress_supervision.py
```

Confirm installed/running identities, original notebook, camera/controller ownership and a clean shutdown of notebook writers. Use the established `tools/charlie --state "$STATE" backup ...` and `verify-backup` before native execution. Do not overwrite/restore the original state from the read-only exported copies. Set `REPO` and `PYTHON` to the verified local checkout/environment if they differ from these historical paths.

### First supervised three-game qualification

Preparation is still unarmed:

```bash
CAMPAIGN=/home/five/charlie-campaigns/first-three
"$PYTHON" -m learning.campaign prepare "$CAMPAIGN" --notebook "$STATE"
cat "$CAMPAIGN/campaign.json"
```

The next commands are the operator's explicit arming action; they were **not** executed by Work:

```bash
"$PYTHON" -m learning.campaign arm "$CAMPAIGN" --hours 1
"$PYTHON" -m learning.campaign run "$CAMPAIGN" --arm
```

From another terminal, immediate disarm requests the existing safe worker shutdown:

```bash
"$PYTHON" -m learning.campaign disarm "$CAMPAIGN"
```

Acceptance requires witnessing three genuinely playable games; correct SELF rather than demonstration sprites; independently supported endings; one START for each restart; one camera qualification reused across the block; separate sealed captures/completion records; supported final score measurements; camera/controller release before offline work; and a successful STOP/neutrality check. Independently annotate the last supported gameplay score, not a later attract reading. Score qualification is separate from lifecycle completion. Record observations, source/configuration identities, source hashes, relevant native timings and failures.

Resume yielded offline work with `run "$CAMPAIGN"` **without** `--arm`. A blocked/ambiguous gameplay attempt does not resume automatically. The existing `--reflect-session` path remains available for explicitly reviewing partial diagnostic evidence; it must not relabel an incomplete game.

### Execute Charlie's retained request

After independent inspection of the current original notebook, prepare the exact existing proposal (do not supply a human replacement hypothesis):

```bash
EXPERIMENT=/home/five/charlie-campaigns/temporal-observation
PROPOSAL=97f90b0167670c30404e4cb8fdc16e6daacead326ae50105125c6fc7f5b64c65
"$PYTHON" -m learning.campaign prepare "$EXPERIMENT" --notebook "$STATE" --proposal-id "$PROPOSAL"
# Only the operator can grant and exercise this physical capability:
"$PYTHON" -m learning.campaign arm "$EXPERIMENT" --hours 1
"$PYTHON" -m learning.campaign run "$EXPERIMENT" --arm
```

This executes at most one baseline game and resumes the existing acquisition/Executive work offline. It does not authorize listed candidates to control the player or manufacture the independent measurements. The durable delivery record retains exactly which measurement prerequisites remain unsatisfied.

### Expand only after native reliability qualification

```bash
TEN=/home/five/charlie-campaigns/ten-games
QUALIFIED_SESSION=/absolute/path/to/the/reviewed/three-game/session
"$PYTHON" -m learning.campaign prepare "$TEN" --notebook "$STATE" --games 10
"$PYTHON" -m learning.campaign arm "$TEN" --hours 2 \
  --reliability-session "$QUALIFIED_SESSION" --observed-native-three
"$PYTHON" -m learning.campaign run "$TEN" --arm
```

Do not use `--observed-native-three` for software fixtures or unreviewed runs. Expansion rechecks the original sealed completion records, a clean common source revision, the reused camera session and verified fresh restarts. Existing offline resource/thermal bounds apply. The loop may yield for missing evidence or resources; that is not successful learning. Hundred-game scope is supported as 33 three-game blocks and one final baseline game, but remains unauthorized/unqualified until the native progression is accepted.

For a separately qualified physical PPAL candidate, prepare a **new** frozen campaign with `--policy /absolute/qualified-manifest.json`. The existing candidate-specific evaluation, physical readiness, explicit deployment authority, operational shadow and rollback must already pass. Gameplay arming does not provide any of those approvals. Record the actual policy identity and decision traces from subsequent games.

## Learning and closure report

| Gate | Result | Evidence / outstanding requirement |
|---|---|---|
| E1 | NOT YET DEMONSTRATED | Authentic overnight ablation found no outcome-dependent valuation effect; prospective retained-outcome decision and causal control still required |
| P1 | NOT YET DEMONSTRATED | Authentic transitions, persistent learning update/reload and comparable subsequent PPAL decision ablation still required |
| I1 | NOT YET DEMONSTRATED | No candidate activated; independently qualify, authorize, integrate and demonstrate downstream use with rollback |
| Gameplay reliability | NOT YET DEMONSTRATED natively | Three genuine consecutive games, automatic restarts, separate endings and native STOP/neutrality |
| Performance | NOT YET DEMONSTRATED | Freeze code/policy/experiment identities and independently compare complete-game scores; no timed partials |
| Autonomy | Software controls only | Host tests establish orchestration mechanisms, not unattended native success |
| Original ALA-2 obligations | OPEN | Original Pi notebook acceptance, October 9 failure preservation, distinct identity continuity, authentic next investigations and every governing acceptance gate remain open |

After the baseline, let the existing Executive choose its question and experiment. Record what it knew, the authentic new experience, retained update, later comparable decision, and the causal control. Repeat for PPAL separately. A higher score, delivered observation, completed campaign, code repair, new proposal or shadow result cannot replace those evidence chains. Do not declare ALA-2 complete.

## Recovery and rollback

Disarm first and wait for confirmed worker/controller/camera cleanup. Keep the campaign directory, notebook and every partial recording. The installed release was not modified by these worktree commands. Return to the previously verified installed release through its existing immutable-release rollback procedure; do not reset history or restore the notebook blindly. Any separately activated candidate is revoked through the existing `CapabilityDeployment.rollback` boundary, not by editing its manifest. A revoked grant/candidate requires fresh explicit authority.

## Validation

Final counts and exact runtime file hashes are in `validation.json`. The initial broad test attempt was interrupted after encountering a shared gameplay ownership lock; its incomplete output is retained separately and is not a successful test receipt. Subsequent scoped/full runs use isolated test temporary directories with all ownership guards intact. Software fixtures are explicitly labeled and never qualify native gameplay, learning or scores.

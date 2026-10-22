> **2026-10-21 authority update:** [Standing operator authorization](../../OPERATOR_GAMEPLAY_AUTHORIZATION.md)
> now covers ordinary Robotron gameplay and qualified adaptations until revoked.
> The historical separate-approval instructions below are preserved as the prior
> runbook; they do not require renewed permission within that grant. Host safety,
> phase review and independent technical qualification remain mandatory. These
> old baseline commands do not select a newly qualified learning attachment;
> see [current integration status](../experience-action-20261021/README.md).

# Separate operator trial — prepared, not executed

No command in the physical-trial sections below is authorized by the software
integration mission. An operator must explicitly approve the exact scope after
host checks and unresolved software/environment checks are resolved. No learned
policy, neural model, Hailo detector or firmware is activated by these commands.

## Freeze an isolated installation

The frozen runtime is `2d75f5ae6bab1b9912f8905dec9a6777c799eac0`.
Use a **new** directory; never reset/clean an original worktree. Git transport
was unavailable in Codex; the GitHub connector published the branch instead.
In an ordinary operator terminal with repository access:

```bash
TRIAL_SHA=2d75f5ae6bab1b9912f8905dec9a6777c799eac0
TRIAL_DIR=/home/five/charlie-native-trial-20261021
PYTHON=/home/five/Projects/charlie/.venv/bin/python
git -C /home/five/Projects/charlie fetch origin integration/native-marathon-20261020
git -C /home/five/Projects/charlie worktree add --detach "$TRIAL_DIR" "$TRIAL_SHA"
cd "$TRIAL_DIR"
test "$(git rev-parse HEAD)" = "$TRIAL_SHA"
test -z "$(git status --porcelain)"
```

Documentation and receipts live at the integration branch head; this runtime
commit deliberately precedes that documentation-only commit. Verify the runtime
and config hashes against tested-source-final.json in the published report.
Do not substitute FETCH_HEAD or the moving branch head silently.

Run the device-free suite through the report's bwrap launcher with
`CHARLIE_AUDIT_CODE="$TRIAL_DIR"`. It hides physical devices and preserves
ordinary-terminal socket access if that host permits it:

```bash
CHARLIE_AUDIT_CODE="$TRIAL_DIR" bash /home/five/charlie-native-integration-evidence-20261020/sandbox.sh \
  -m pytest -q tests -p no:cacheprovider
```

Do not replace failed network tests with mocks or run arbitrary root-level
legacy hardware tests. Missing Torch/Node/archive checks remain explicit skips;
optional neural training/export is not required for the fixed-reader trial.
No package installation, camera diagnostic or controller connection is performed
by these preparation instructions.

## Operator prerequisites and monitoring

Before authorization, identify the real host processes/services and their exact
checkout/interpreter. Independently establish that no previous gameplay, camera,
controller, offline worker or Hailo client owns the devices. Codex's private PID
namespace cannot establish this. Preserve existing partial sessions before any
operator-directed owner shutdown. Confirm physical emergency stop and neutral
release procedures without relying on the Python supervisor as the emergency stop.

Require a visible correctly framed display, unobstructed full HUD, unchanged
manual focus 2.0, verified controller endpoint/firmware identity, available disk
space, writable separate trial-output directory and authentic existing learning
notebook. Do not load a saved calibration or move a servo. The existing player
must independently pass current-view preflight and controller acknowledgment.
If any prerequisite is unavailable, do not arm. Passive camera activation also
needs its own approval; it is not needed to rerun device-free tests.

Record continuous host temperature, throttling flags, CPU/RSS for the identified
worker tree, free memory/disk, and camera/controller ownership alongside trial
progress. A final-temperature sample cannot replace this trace. Use the ordinary
host `vcgencmd get_throttled` and `/sys/class/thermal/thermal_zone0/temp` where
available. If telemetry/ownership cannot be monitored, defer the trial.
Stop at >=75C, throttling, unbounded RSS/queue growth, unsafe disk pressure or
loss of the physical stop path. The offline recovery rule (<65C for 5s) is not
permission to automatically resume interrupted gameplay.

The existing performance and stream reports distinguish captured exposures,
ordinary skipped frames, processed observations and meaningful supported-SELF
decisions. Record camera-to-decision age, each processing stage, command submission,
acknowledgment and release brackets separately. Display response latency remains
unknown unless independently measured. Targets include meaningful 8–12 Hz and
fresh accepted decisions <=250ms old; any failure is reported without changing
timestamps or allowing stale commands.

## First separately approved physical scope: Game 1 -> Game 2

Approve up to two complete games with the existing policy, no model/policy
activation. The CLI below also seeks completion of Game 2; it does not substitute
a timed partial second game for completion. A confirmed playable Game 2 after a
sealed Game 1 establishes only the transition, even if Game 2 later fails.

Only after separate explicit approval:

```bash
cd "$TRIAL_DIR"
"$PYTHON" -m experiments.ppal.marathon_robotron \
  --arm --developmental --learning-projects --play-first --baseline-only \
  --observation-block --max-games 2 --qualified-games 2 \
  --root /home/five/charlie-native-trials/transition-20261021 \
  --learning-root /home/five/.local/share/charlie/development \
  --campaign-notebook /home/five/.local/share/charlie/development \
  --project-evidence /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3
```

Use a fresh output directory for each newly approved attempt. Omit all diagnostic
game-duration limits, projectile-SELF flags, deployment authority and learned
policy/semantic flags. The two-game observation block does not schedule automatic
three-game meditation or qualify a six-game campaign.

Independently verify: acknowledged authorized START; fresh playable screen and
causal SELF; bounded normal actions; genuine positive terminal transition;
report.json return status and source-bound recording completion; stopped score
and recording writers; unique capture/content identities; the same uninterrupted
camera-session ID across games; fresh postgame start permission; a new acknowledged
START and independently supported Game 2. A demonstration sprite, lost SELF,
zero reserve icons or elapsed time cannot satisfy any missing boundary.

Inspect session.json, both original report.json files, capture-origin.json,
capture-manifest.json, recording-state.json, source journals, agency.jsonl,
terminal observations, completion record IDs, score originals and the complete
thermal/resource log. Review scores independently by channel and exact visible
string. A human score label does not certify the terminal boundary.

## Later separately approved scope: three -> meditation -> three

Do not run this because two-game software fixtures passed. First accept the
actual native Game 1 -> 2 evidence and review every blocker in the report.
Authorize block A independently, retaining the frozen runtime:

```bash
"$PYTHON" -m experiments.ppal.marathon_robotron \
  --arm --developmental --learning-projects --play-first --baseline-only \
  --max-games 3 --qualified-games 3 \
  --root /home/five/charlie-native-trials/block-a-20261021 \
  --learning-root /home/five/.local/share/charlie/development \
  --campaign-notebook /home/five/.local/share/charlie/development \
  --project-evidence /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3
```

The existing orchestration releases the camera before offline Reflection/
Meditation and only schedules it after a qualified target. Require three distinct
complete authentic games and `target_met`, no cleanup errors, a checkpointed
reflection-progress.json, exact source episode references and retained state IDs.
If reflection yields, resume the **same** session offline; do not start another
physical block or fabricate replacement evidence:

```bash
"$PYTHON" -m experiments.ppal.marathon_robotron \
  --reflect-session /absolute/path/to/block-a/session \
  --learning-root /home/five/.local/share/charlie/development \
  --campaign-notebook /home/five/.local/share/charlie/development \
  --project-evidence /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3
```

Replace the session placeholder with the original path recorded in session.json.
No --arm is permitted for this resume. Verify checkpoint status and retained
reload through the existing journal/Executive interfaces. Learning claims still
require controlled E1/P1 comparisons; a saved meditation alone is insufficient.

After independent review and separate block B authorization, repeat the exact
three-game command with a fresh `block-b-20261021` root. Keep --baseline-only;
this intentionally avoids extra actuator experiment selection. Do not use a
six-game campaign grant to bypass the review boundary or activate learned policy.
Only three authentic completions before and three after checkpointed meditation
may establish the requested sequence. Performance remains a separate frozen
baseline comparison, and I1 needs independent qualification/authorization.

## Stop, evidence preservation and rollback

Stop immediately on uncertain geometry/focus, stale/reordered exposure, stream
critical overflow, lost supported SELF beyond bounded recovery, unexpected
attract-player reacquisition, missing command/release acknowledgment, writer or
seal failure, resource limits or monitoring loss. Existing bounded recovery is
not permission for repeated START attempts on an unknown episode.

For an ordinary stop, interrupt the supervised parent from its foreground
terminal (Ctrl-C); it signals/reaps its owned child and retains an unverified
boundary. Verify actual neutral/release acknowledgment and child termination.
Use the independent physical stop immediately for urgent risk. This session has
not issued a neutral command or touched the controller. Never SIGKILL a broad
name match or assume a stale PID identifies the current owner.

Preserve all reports, partial directories, source images, journals and monitoring
logs. Never automatically rerun a blocked/playing campaign. Reconcile evidence
before another separately approved attempt. No notebook restore/reset is part
of rollback. Stop/reap the identified owner and choose a fresh checkout of prior
PR #5 `7dcea80cd6a6448a7c13f8b83179435c049d7b3c` or the preserved native
`73169db9ad2648ca7e4088979d22905900052c6a`; preserve newer evidence and keep
firmware/packages unchanged. Physical gameplay on the rollback version also
requires authorization.

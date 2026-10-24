# October 24 supervised controller interface correction

Runtime pin: `00458579b0fdb5dd81fe5bf6ccaa7d93d8308dbc`.
Tree: `86a10bbaf89c4602c436e5c81e1e184d6dd2f942`.
Direct parent: published PR #9 head `bb39d17207ef4b8877b5f8c3e8e847f874ffc2fe`.
Only runtime source change: `experiments/ppal/progress_supervision.py`.
One new regression module: `tests/test_supervised_controller.py`.
The local staged tree independently matches this published runtime tree exactly.

## Cause and correction

[Operator report](https://github.com/mrgarmise/charlie/pull/9#issuecomment-6389509637):
SELF discovery failed before transport dispatch with
`TypeError: SupervisedController.execute() got an unexpected keyword argument 'cancel_event'`.
This was a published software interface regression, missed by the earlier 84
checks. Camera/focus changes or another physical test cannot repair it.

`_call`, `execute`, `_command` and `close` now accept and forward positional and
keyword arguments unchanged. Existing controller-phase entry, failure tagging,
return values and finalizing/perception restoration remain intact. No transport,
server lease/deadman, cancellation, timeout, neutralization or supervisor guard
was disabled or changed.

The regression runs the actual `VisualAgency.discover -> capture_window ->
SupervisedController.execute -> ArcadeController.execute` chain with synthetic
frames and an in-process wire. It checks success, an already-set cancellation
event, cancellation after firing submission, wire rejection and cleanup. Other
cases check expired deadlines, finalizing restoration, lease renewal, stale/current
deadman generations, keyword forms of action/duration/command, backend-specific
arguments and return values, and joined lookahead workers on success/camera failure.
The real `ArcadeController` retains its keyword-only `cancel_event` and `deadline`.
`DryRunController`, `RecordingSink` and `TCPCommandSink` keep their own supported
interfaces: the supervisor does not suppress unsupported argument errors.
`renew_lease`, attributes and other non-overridden methods retain direct delegation.
These are the PPAL proxy interfaces used at this boundary; unrelated legacy
Robotron controllers are not substituted for the PPAL transport.

## Verification

ARM64, Python 3.13.5, existing Python environment, isolated temporary learning
state and home; no devices or physical controller service contacted.

- [Before](before.txt): initial ten new tests all fail on unchanged published
  source, including the exact reported `cancel_event` exception through SELF.
- [Broader run](after.txt): 148 passed, 19 failed, 4 errors in 12.44 s.
  Every failure/error is `PermissionError: [Errno 1] Operation not permitted`
  at local TCP socket construction. These are retained as unavailable checks.
- [Final eligible run](eligible.txt): **150 passed, 16 deselected in 11.96 s**.
  Includes all 13 final new regressions, supervisor/process cleanup, SELF capture,
  native runner, recovery entrypoint, final-image recovery, combined integration
  contracts and device-free controller sandbox guards. The 16 deselected cases
  are the socket-dependent cases in `test_controller_sandbox.py`; the socket
  transport/client files are omitted from this final eligible selection.
  Overlapping run counts are not summed.
- `git diff --check` for source and handoff files, Python compilation and both
  handoff scripts' `bash -n` pass. Raw pytest trace whitespace is retained.
  The exact launch arguments parse successfully with execution intercepted immediately
  after argument parsing, before runtime; the hidden `--campaign-notebook`
  argument is verified too.

Final eligible command, from the checkout with isolated test state:

```bash
python -m pytest -q tests/test_supervised_controller.py \
  tests/test_progress_supervision.py tests/test_agency_stream_engine.py \
  tests/test_native_robotron_trial.py tests/test_recovery_entrypoint.py \
  tests/test_final_image_recovery.py tests/test_native_integration_contracts.py \
  tests/test_controller_sandbox.py \
  -k 'not forbidden_commands_never_reach_wire and not repeated_buttons_combinations_and_release and not stopped_caller_hold_lease_neutralizes' \
  -p no:cacheprovider
```

## Pinned installation on Charlie Pi 5

With gameplay stopped, run in an ordinary Pi terminal as `five`. This reuses the
existing checkout/environment and preserves the retained learning databases and
original failed session. There is no pip reinstall or controller service update.
[install.sh](install.sh) contains the exact commands:

```bash
bash docs/validation/controller-interface-20261024/install.sh
```

For an older checkout without that new document, use these self-contained commands:

```bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
charlie_python=/home/five/Projects/charlie/.venv/bin/python
charlie_release=00458579b0fdb5dd81fe5bf6ccaa7d93d8308dbc
test -x "$charlie_python"
test -z "$(git status --porcelain)"
PYTHONPATH="$PWD" "$charlie_python" -c 'from learning.cycle import gameplay_active; assert not gameplay_active(), "Stop active gameplay before updating"'
git fetch origin refs/pull/9/head
git merge-base --is-ancestor "$charlie_release" FETCH_HEAD
git merge-base --is-ancestor bb39d17207ef4b8877b5f8c3e8e847f874ffc2fe "$charlie_release"
git switch --detach "$charlie_release"
test "$(git rev-parse HEAD)" = "$charlie_release"
test "$(git rev-parse 'HEAD^{tree}')" = 86a10bbaf89c4602c436e5c81e1e184d6dd2f942
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" "$charlie_python" -m pytest -q \
  tests/test_supervised_controller.py -p no:cacheprovider
```

Require 13 passed. An error ends the block; do not reset edits or remove
cancellation/supervision to proceed. The repository's existing origin must be
`mrgarmise/charlie`. The exact detached pin stays fixed if PR #9 advances.

## Existing bounded integrated launch

After installation, the existing two-game recovery invocation is unchanged except
for the runtime pin and fresh run directory. Standing gameplay authority and the
existing lease service/emergency stop remain applicable. This software repair does
not require a new physical qualification project or repeat physical test.
[launch.sh](launch.sh) contains these commands; do not execute it in this software
repair session:

```bash
set -euo pipefail
cd /home/five/charlie-native-lease-trial
test "$(git rev-parse HEAD)" = 00458579b0fdb5dd81fe5bf6ccaa7d93d8308dbc
test -z "$(git status --porcelain)"
test -f /home/five/.local/share/charlie/development/learning-evidence.sqlite3
charlie_run=$(mktemp -d /home/five/charlie-native-trials/controller-interface-20261024-XXXXXXXX)
PYTHONPATH="$PWD" CHARLIE_CONTROLLER_LEASE=required \
  /home/five/Projects/charlie/.venv/bin/python -m experiments.ppal.marathon_robotron \
  --arm --recovery-trial --developmental --learning-projects --ala-learning \
  --max-games 2 --qualified-games 2 --focus 2.0 \
  --root "$charlie_run" \
  --learning-root /home/five/.local/share/charlie/development \
  --campaign-notebook /home/five/.local/share/charlie/development \
  --project-evidence /home/five/.local/share/charlie/development/learning-project-evidence.sqlite3
```

The pin contains the runtime/test correction. This later documentation commit
adds only receipts and handoff files; it is not required at runtime. Read/copy the
commands from this PR when using the detached runtime checkout. Software tests,
source/tree identity, script syntax and CLI flags were verified here; the install
and launch were not executed on the Pi. No new gameplay, physical success,
learning qualification, E1/P1/I1 or completed-game claim is made. Original outcome
remains zero confirmed games. Keep PR #9 draft and unmerged.

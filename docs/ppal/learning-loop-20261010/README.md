# ALA-2 learning-loop continuation: Guide/Home boundary

Base remote branch `feature/agency-first-self` was independently verified at
`6ba21fb9b56e492a85bf3b7fc2e9b5fb63ab9789` before editing. Work is isolated in a
new detached worktree; previous implementation/worktrees and original evidence
are retained. This checkpoint is incremental implementation, not ALA-2 completion.

## Confirmed defect and repair

The existing shared `ControllerSandbox` rejected Guide+Back but allowed Guide
alone. `BUTTONS` exposed Guide to Forebrain exploration. Both text TCP clients
already routed raw commands through this sandbox; the alternate Robotron client
also ignored `Action.controls` before sending sticks. Guide alone could therefore
reach RetroArch, and forbidden combined actions could be silently ignored.

Guide/Home and all recognized aliases now fail before any write, including DOWN
and UP state transitions. Guide is removed from exploratory input choices.
Committed held states are validated and rejected states cleared; existing held
state is validated before subsequent commands, with NEUTRAL retained as recovery.
Both normal/alternate gameplay clients reject Guide-bearing Actions before any
stick output. The dry-run controller validates the same controls. The JSON bridge
already permits only move/fire controls and rejects arbitrary Guide fields.

This changes Charlie's output only. The physical Xbox GUIDE+BACK behavior in the
separate arcade launcher is unchanged. Right-trigger and higher-level restrictions
remain in force. No game-switching, deployment, firmware or movement is introduced.

## Validation and limitations

Host: x86_64, Python 3.12, existing isolated test environment, no connected camera,
RP2040, arcade or physical controller. New cases cover 11 aliases, all three press/
release representations, both TCP Action paths, speculative chooser, dry-run,
corrupted held state and neutral recovery. All legacy permitted input tests remain.

Focused command:

```bash
/workspace/scratch/a5d7375d8e4e/ala-loop-env/bin/python -m pytest -q tests/test_controller_sandbox.py tests/test_ppal_arcade_transport.py tests/test_robotron_exploration.py
```

Result: **87 passed**, 10.06 seconds. [Raw output](guide-focused.txt).
The maintained regression command `/workspace/scratch/a5d7375d8e4e/ala-loop-env/bin/python -m pytest -q tests` passed **845 tests, 21 skipped in 198.62 seconds**. [Raw output](guide-regression.txt).
Unqualified repository-root collection was also attempted and failed during
collection of legacy manual/Pi scripts (`machine`, libcamera, desktop dependency
and module collision); it is not a passing check. Its exact output is preserved
in [root-collection-failure.txt](root-collection-failure.txt). No successful
hardware connection or physical execution occurred. Regression validation is
restricted to the maintained `tests/` directory rather than those manual scripts.

Native access attempt:
`ssh -o BatchMode=yes -o ConnectTimeout=5 five@charlie 'uname -m'`
returned hostname resolution failure. No new native Pi acceptance is asserted.
User-supplied checkpoint labels do not replace observed native validation logs.

## Remaining active mission

Acquisition still needs broader, incremental question-driven historical inspection.
Retained motion dependencies combine exploration with fresh final evaluation
requirements; these must be separated without weakening candidate qualification.
The normal Executive must decide whether unresolved evidence merits a bounded
proposal, retain it in existing status/journal, and proceed with other work.
Authentic host-copy continuation can test available preserved experience; the
latest native notebook and archives remain inaccessible here.

Physical gameplay, servo movement, flashing and persistent physical policy
activation are unauthorized. ALA-2 remains open until independently measured
complete-game Robotron SCORE improves against the frozen baseline through
Charlie-originated learning. This safety repair does not establish improvement.

## Incremental historical discovery

Existing acquisition now retains hash-bound score, controller, event, planning and annotation row references even without images. Request text selects relevant evidence kinds; it does not create or rank projects. Rows remain unqualified reports, including tracker beliefs. Original image qualification and final evidence requirements are unchanged.

Durable discovery receipts contain filesystem change stamps, permitting unchanged diagnostic inspections to be reused after restart without rehashing or decoding images. These stamps are cache invalidation, never measurement proof; independent qualification still verifies original hashes. Missing or changed referenced artifacts invalidate the receipt. Each turn inspects at most 128 changed episodes; cached episodes no longer prevent later episodes from being reached. Lightweight report-path enumeration and metadata checks still occur.

Host command: `python -m pytest -q tests/test_request_source_discovery.py tests/test_acquisition_investigation.py tests/test_ala_acquisition.py`. [Focused results](history-focused.txt). Fixtures cover missing/corrupt inputs, changes, original request identity, nonfinite timestamps, provenance, restart, request-driven filtering and advancement beyond the processing bound. No authentic independent measurements or native acceptance are established by these fixtures.

# Reproduction boundaries

Use a new output directory and isolated learning copies. The recorded harnesses
contain exact local paths and refuse to overwrite their initial state. They are
evidence of these runs, not installation or physical-play scripts. Later stopped
attempts retain their logs and state; they are not silently replaced by a fresh
notebook. `--offline`/no deployment authority remains mandatory.

The normal application and existing lifecycle acquired the report contexts and
ran Reflection/Meditation/Executive/Evaluator work. The controlled continuation
froze the acquired corpus to isolate decision influence. See `run_recovery.py`,
`checkpoint_recovery.py`, `resume_checkpoint.py`, and `e1_reload.py`. The ordinary
Executive owns questions, proposals, choices, predictions and conclusions in
each harness. The small scoped ablation is explicitly read-only.

## Tactical recovery and PPAL controls

Run from the separate code worktree with its normal Python environment. Obtain
the six journal paths from `tactical-recovery-strict.json`; they are preserved
source files, not six newly played games. Repeat `--journal` for each path:

```sh
python tools/recover_tactical_feedback.py \
  --journal /preserved/origin/session-evidence.sqlite3 \
  --write-ledger /new/isolated/tactical-diagnostics.json \
  --report /new/recovery-report.json
python tools/replay_retained_tactics.py \
  --journal /preserved/origin/session-evidence.sqlite3 \
  --ledger /new/isolated/tactical-diagnostics.json \
  --report /new/replay-process-1.json
```

Repeat the replay command in a second process with another fresh report path;
compare the JSON bytes/digest. Source journals with SQLite sidecars require a
quiesced complete snapshot first. Report and ledger must be distinct, outside
source episode directories. The replay receives historical interpreted worlds;
it does not initialize a camera, controller or a physical policy.

## Checks actually run

```sh
python -m pytest -q tests
python -m learning.readiness --output /new/disarmed-readiness.json
git diff --check
```

The final native full suite used `taskset -c 0-2` so the offline learner's final
CPU remained separate. Its 34 socket failures are sandbox restrictions, not
passing tests. Do not run repository-root legacy hardware/manual test modules.
Focused tests cover tactical qualification/reload/CLI boundaries, serialization,
ordinary lifecycle/projects/Evaluator/PPAL, immutable session receipts and the
category index's read-only legacy-source behavior.

All source data, raw copies, the complete notebooks and failed attempts remain
under `/home/five/ala2-recovery-20261019`. The repository contains compact reports,
hashes and trace artifacts, not a replacement operational notebook. Original
Mint-image comparison, exact October 9 native acceptance and independently
qualified complete-game comparison remain separate original obligations.

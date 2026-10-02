# Progress-supervised Robotron episodes

Normal gameplay no longer has an elapsed-game-duration cutoff. An armed player
runs under an independent parent watchdog and continues while observations and
completed perception/action cycles progress. Robotron's existing confirmed
terminal rule is still the only authorization to start another marathon game.

## Physical evidence audited

Both supplied developmental archives were inspected separately, including their
reports, session summaries, journals, challenges and saved final camera views.
The compact extract is [progress-supervision-evidence.json](progress-supervision-evidence.json).

| Archive | Old stop | START write → first ordinary action | Journal commit span | Boundary finding |
|---|---|---:|---:|---|
| development-20261002-003511 | TIME LIMIT, 20 seconds | 6.408 seconds | 65.069 seconds | Ordinary actions still occurring; no confirmed terminal evidence |
| development-20261002-005944 | TIME LIMIT, 120 seconds | 6.585 seconds | 991.880 seconds | Instruction/attract page recognized repeatedly, but terminal corroboration was unmet |

In the larger archive, reacquisition rows at gameplay-relative times 92.930,
94.566, 96.459, 98.559, 101.030, 103.481 and 105.400 seconds report STARTABLE
instruction headings and consecutive non-gameplay streaks 4 through 10. The
saved final full-camera frame visibly shows the Robotron instruction page. Thus
this was not simply a failure to recognize the page. Three appearance challenges
at 59.382, 83.797 and 113.480 seconds had **zero attempts**, no eligible candidate,
and no confirmed response. They were inconclusive, not rejected causal probes.
`EpisodeEndObserver` therefore had no corroborating agency failure and could not
confirm game over. Later UNKNOWN classifications also broke the consecutive
screen streak. No subsequent START was authorized.

This change deliberately does not relabel an ineligible challenge as a failed
experiment. The unresolved return-to-attract case now stops as observation
uncertainty rather than running indefinitely. Improving autonomous recognition
of that boundary still requires stronger terminal corroboration. Neither SELF
loss nor an instruction page alone is newly declared proof of game completion.

The journal's physical timestamps support the reported long postgame wait: its
first and last commits span 16 minutes 31.880 seconds. Repeated artifact loading
and hashing, repeated unindexed prediction queries, and consideration of
impossible track-pair links caused avoidable offline work. These paths have been
optimized without changing the replay model or proposal/ranking rules.

## Stop paths and independent supervision

| Condition | Behavior | Another START? |
|---|---|---|
| Healthy extended survival | Continue, regardless of game age | No |
| Existing confirmed terminal evidence | GAME OVER; process episode through existing learning path | Only after successful processing and the existing restart check |
| Temporary camera read exception | Retry up to three reads from the same owned source; record failures | No |
| Repeated/stale exposure or stuck capture | Parent stops child as observation failure | No |
| Sustained inability to recover actionable SELF | Neutral observation/reacquisition; after 60 seconds continuously unresolved, OBSERVATION UNCERTAIN | No |
| Stuck/rejected controller transport | Existing socket bounds and neutralization; parent independently detects a stuck operation | No |
| No completed perception/action or neutral-recovery cycle | Parent detects cycle stall | No |
| Child hang | Interrupt, then terminate/kill and reap if needed | No |
| Explicit diagnostic duration | DIAGNOSTIC LIMIT, not normal game completion | No |
| Offline processing stall/budget exhaustion | Stop marathon; retain journals, commitments and partial outputs | No |

Default progress allowances are 10 seconds without fresh exposure/capture or
controller-operation completion and 30 seconds without general/cycle progress.
Startup calibration continues to use its existing bounded preflight machinery;
fresh observations during startup do not consume a game-duration allowance.
Finalization has a 90-second allowance after controls are closed. Offline work
has a 60-second progress-silence allowance and a separate 300-second work budget.
These are failure/work allowances, not healthy-game lifetime limits.

`Progress` publications come from completed real operations, not a timer thread.
Repeated sensor timestamps do not advance freshness. The parent reads atomic
small status files; it does not capture images, run tracking, classify objects or
control the arcade. A supervised controller wrapper records operation boundaries
without changing command vocabulary, durations, START sequence or acknowledgments.
Controller pulses remain 30–500 ms at the transport, with the player's unchanged
30–200 ms ordinary pulse option. Socket timeouts, stick centering, neutral close,
and Zero-side neutralization on TCP disconnect remain intact.

Player `report.json` includes progress counters, publication cost, failure kind,
and diagnostic-limit provenance. Parent evidence lives next to the run directory
as `<run>-progress.json` and `<run>-progress-supervisor.json`; marathon roots
naturally include these files. `agency.jsonl`, score and diary evidence remain
unchanged in role. `steps.jsonl` additionally preserves completed player rows
before final-report creation. The redundant in-memory agency-row list was removed;
tracking IDs, trajectories and report contents retain their existing semantics.

## Between games

Normal and developmental runners now share the existing between-game path.
Normal mode retains its existing policy and saved-calibration behavior; it does
not automatically enable BODY/FIRE bootstrap or experiment selection.
Developmental mode retains its existing chooser, project context, provisional
SELF, bootstrap and experiment mechanisms. No learning goal or action hypothesis
was supplied by this repair.

The default physical runner invokes existing import, prediction resolution,
derivation, Reflection, Evaluator/MemoryGateway/MARM, optional Learning Executive
updates and Meditation inside an isolated worker. It uses the same durable
memory, commitments and project journals. Parent connections observe committed
worker changes. Stage starts and completed journal operations provide inspectable
progress; `between-game.json` includes stage timestamps. Processing failure ends
the campaign conservatively.

Interrupted runs without a finalized report can be imported as hashed
`partial-episode` manifests with UNKNOWN outcome/boundary. A torn final JSONL line
is retained in the hashed original and indexed as unreadable; it is never turned
into a valid observation. Predictions lacking resolving evidence remain unresolved.
No partial specimen becomes confirmed game-over evidence.

The existing START classification and `safe_to_restart` rule are unchanged:
return code zero, GAME OVER, confirmed game-over state, the original persistent
non-gameplay-plus-no-controlled-SELF rule, at least eight consecutive observations,
at least one rejected agency challenge, and a positively recognized STARTABLE or
TERMINAL screen. Calibration failures, UNKNOWN, respawn, interrupted processes
and diagnostic limits do not pass this check.

## Performance and regression evidence

The larger archive's optimized offline pipeline completed in **14.673 seconds**
on the Work host. All **10,812 ordered diagnostic resolutions** exactly matched
the archived timestamp, verdict, reason and error. Meditation's history, all
**372 merges**, and quality summaries also matched exactly. The timing comparison
is between different machines and does **not** establish the new Pi duration.
That replay benchmark omitted project portfolio consolidation; isolated-worker
tests separately exercise existing project and memory updates across processes.

Optimizations are phase-local verified artifact snapshots, indexed observation
horizons and resolution lookups, and a temporal onset index for Meditation's
candidate links. Original byte hashes and change detection remain required.
No new tracker/association pass or interpretation machinery was introduced.

Regression coverage includes the real player loop with extended simulated
survival and no diagnostic deadline; a confirmed GAME OVER; fresh/stale exposure;
recoverable camera exceptions; controller stalls; a child that ignores interrupt
and termination; cleanup/reaping; uncertain boundaries; partial ingestion; offline
work budgets; and isolated durable memory/project updates. Existing startup,
tracking, agency, score, replay, learning and passive-viewer tests are retained.
Full regression: **393 passed**. Final focused player/supervision/startup checks:
**36 passed**. The simulated tests do not
demonstrate a new physical multi-game campaign.

## Next physical run

Use the current agency branch and omit `--game-seconds`:

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git fetch origin
git switch feature/agency-first-self
git pull --ff-only origin feature/agency-first-self
python -m pytest tests -q && PYTHONPATH="$PWD" python -m experiments.ppal.marathon_robotron \
  --developmental --learning-projects --max-games 3 \
  --retry-wait 5 --focus 1.30 --arm
```

Return the complete `robotron-runs/development-<timestamp>` directory as a tarball,
including game progress/supervisor files and all between-game worker outputs.
The run is bounded by three attempts and progress/uncertainty/work supervision,
not by healthy-game age. It may stop after the first attempt if a genuine episode
boundary cannot be confirmed. Ctrl-C remains available and preserves evidence.

`--seconds` remains a player alias of `--diagnostic-seconds`; marathon
`--game-seconds` remains an explicit diagnostic option. Existing scripts that
supply them still stop intentionally, with DIAGNOSTIC LIMIT evidence. Omit them
for normal gameplay. `--processing-budget` controls offline work only.

## Physical follow-up

See [physical-learning-audit.md](physical-learning-audit.md) for the b9624ce
physical findings. Productive offline work now yields/resumes at durable units;
inactivity remains independently supervised. Positive gameplay → rankings →
instruction/attract evidence adds corroboration when no SELF probe is eligible.
UNKNOWN never authorizes START.

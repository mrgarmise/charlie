# ALA-2 resource efficiency milestone — 2026-10-08

## Verified source and hardware limits

Remote feature/agency-first-self was independently verified at
99d561382a0a55d0dc2bb4dea4b511350c8cdae5, tree
42360481b1a24f0386a45fd067c4f1c4acac6d44, before edits. Other worktrees,
firmware, calibration profiles, production notebooks and captures were untouched.

The supplied native status log is preserved verbatim (36,083 bytes, Library
libfile_60ab5761235c8191a122de55b86059e6, Pasted text(20261008-014710).txt),
SHA256 d8d50cbe0d7dcfc161c51dc8f7e1c47177ebf462a8a59841af9a8ebac3c8206a.
It does not provide a current complete hardware/resource inventory. Pi 5,
four cores, 8 GB, microSD, Python 3.13, approximately 73 C and single-core
utilization are user-reported observations, not fresh remote measurements.
No Pi command connection is exposed in this session.

Host: x86_64, Python 3.12.14, Linux 6.18.44. Cgroup CPU quota 800000/100000;
memory limit 8,589,934,592 bytes; nine visible CPUs. The candidate development
process is constrained to two permitted CPUs. Host thermal sensors are unavailable;
this is reported as unknown, never as evidence of a cool Pi. No hardware operated.

## Measured bottleneck and correction

The actual normal main.py --offline was profiled with the authentic October 4
play-20261004-205356 capture directory. Original tracks SHA256:
b7364b69c6cc80b4f5bbb88951f7f6c88713d003312308ece0a21751ec77c685.
It has 951 raw fragments and 4,532 retained observations. Frozen inventories
are embedded in each benchmark JSON. Historical tracking and score claims
remain unverified; these captures are not fresh independent final evidence.

The baseline's ten-second meditation slice spent 9.779 profiled seconds in
yield_for_primary and 9.742 in gameplay_active. Path.glob visited/matched
process-directory entries on every pair pulse. This was repeated bookkeeping,
not productive trajectory analysis. A direct scandir probe alone advanced more
work but still spent most of the slice repeatedly probing processes.

The existing Executive now uses ResourceGuard for cooperative resource checks.
Ownership is checked at turn entry and at most every 50 ms during analytical
pulses. Each pulse still checks the original wall deadline; no timeout was
increased or removed. A newly appearing gameplay owner is detected on the
first pulse at/after the polling interval. This is a polling bound, not a hard
real-time response guarantee or a gameplay latency acceptance threshold.
The existing PPAL path never calls this guard or Meditation.

Normal startup options: --learning-cpu-cores (default 2), --learning-memory-mb
(default 768), --learning-temperature-c (default 75). CPU affinity and numerical
library thread budgets apply only in the existing development process; nice=10
remains. The thermal default is a conservative configurable development budget,
not a measured Pi optimum or independent hardware readiness qualification.
Resident-memory/temperature pressure yields the turn and retains its checkpoint.
It does not count as three failed investigations, grant authority, or spin up
another scheduler. Unknown thermal availability is exposed explicitly.

Status reports CPU time, resident/peak memory, configured budgets, temperature
availability and ownership-check count. Analytical progress reports completed
iterations, reconstruction cursors and retained plausible links, explicitly
separate from qualified learning. Corrupt checkpoints appear unavailable in
status while the original source/integrity gate still rejects them. Resource
implementation and budgets participate in durable resumption dependencies.

## Comparable host evidence

Three alternating unprofiled baseline/candidate one-turn trials used the same
source, ten-second slice, initially absent state, .05-second interval and no
deployment grant. Three final candidate repeats include the final status and
resource-dependency reporting changes. Some trials overlapped host regression
work; distributions and whole-system per-core counters are retained rather than
attributing unrelated CPU usage to Charlie. This is host evidence, not Pi speed.

| Normal one-turn trials | Wall seconds | CPU seconds | Completed iterations |
| --- | --- | --- | --- |
| Baseline 99d5613, three trials | 13.102–13.347 | 13.084–13.338 | 0 each |
| Final resource-aware, three trials | 4.959–5.647 | 4.913–5.551 | 5 each |

Final candidate peak RSS: 168,480,768–168,570,880 bytes; baseline:
168,415,232–168,656,896. Storage block counts and per-core whole-system busy
percentages are in the raw reports. They are not microSD latency measurements.
All source inventories remained unchanged; independently qualified findings=0.

A twelve-turn baseline completed five iterations in 93.982 wall/93.354 CPU
seconds. A clean twelve-turn candidate completed the same five in 30.923
wall/30.321 CPU seconds, with consistent checkpoint/result content. Both final
scientific result digests match:
fd385a3d9e9a8ed7800c73fd909c39b1072ee9aeca44dd3b02f62fff71213336.
The result contains the same unverified tracks, quality, merges and history.
Neither run qualifies an operational improvement or complete-game score gain.

One earlier longer candidate run returned this scientific result but retained
a four-iteration checkpoint alongside a five-iteration result. It is preserved
in perf-m1-guard-complete.json and treated as **inconclusive**, excluded from
the successful comparison. Its cause is unresolved. The profiler now explicitly
reports checkpoint_result_consistent; this failure was not rewritten or hidden.
Further native consistency verification is required before claiming Pi acceptance.

Full offline suite: 593 passed, 20 skipped in 107.02 seconds. Focused lifecycle,
resources and continuity: 57 passed in 33.57 seconds. A subsequently added profiler
fixture check passed separately; it confirms normal entry-point use, integrity
reporting, zero physical authority, and refusal to overwrite prior evidence.
Nineteen skips require Torch; one requires unavailable original October 1
collision captures in this host. Initial resource namespace/status test failures
are retained; /proc/self fixes namespace-safe RSS, and status no longer masks
the original checkpoint integrity exception.

A separate copy of the authentic retained 1,144-record notebook ran three normal
turns. The strict validator preserved every original document, commitment time,
checkpoint and commission, adding only one implementation-dependent waiting
record. Restart evidence is attached separately. No source history was reset,
fabricated, or counted as another independent experience.

## Guarded native measurement

First update the existing checkout with the exact published SHA accompanying
this milestone, then use the existing guarded acceptance script. No --arm or
--allow-offline-improvements belongs in this procedure.

```bash
cd /home/five/charlie-ala2-bae659f60b0e
release=<exact-published-40-character-SHA>
bash tools/update_existing_ala2_pi.sh "$release" &&
bash tools/accept_episode_identity_pi.sh "$release"
```

For reproducible native profiling, preserve the production notebook and use new
benchmark output directories. The profiler invokes the normal main.py, selects
no agenda itself, emits no controller commands and refuses an existing output.

```bash
python=/home/five/Projects/charlie/.venv/bin/python
root=/home/five/Projects/charlie/robotron-runs/play-20261004-205356
git worktree add --detach /home/five/charlie-ala2-profile-baseline 99d561382a0a55d0dc2bb4dea4b511350c8cdae5
"$python" tools/profile_development.py --repo /home/five/charlie-ala2-profile-baseline --episode-root "$root" --output /home/five/ala2-profile-baseline-01 --turns 12
"$python" tools/profile_development.py --episode-root "$root" --output /home/five/ala2-profile-candidate-01 --turns 12
```

Repeat with new numbered directories and comparable thermal/load conditions;
never delete failed trials. Do not mix profiled and unprofiled timings. Collect
uname, Python/OS versions, available affinity/CPU quota, RAM, filesystem/storage,
vcgencmd measure_temp and get_throttled when available, and normal status resource
samples before/after. Retain unavailable interfaces and raw current flags rather
than assuming reported hardware health is still current. Check identical source
inventories, final scientific digests, stage counts and checkpoint consistency.
Use tools/inspect_developmental_progress.py and the existing strict restart
validator around the persistent notebook. Native responsiveness, power/thermal
behavior and performance remain pending; no claim of native acceptance is made.

## Next optimization boundary

Re-profiling shows checkpoint serialization and acquisition now dominate much
of the remaining cost. Candidate pair calculations are independent and could
use bounded pure workers; ranking, merging, checkpoints, commissions, evaluation
and agenda decisions must remain parent-owned. Workers should be admitted only
after their measured serialization/startup/memory overhead justifies concurrency.
No parallel work was introduced merely to fill cores in this milestone.
ALA-2 remains open: independently verified complete-game score improvement is UNKNOWN.

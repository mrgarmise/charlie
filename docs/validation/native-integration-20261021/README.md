# Native marathon integration — October 20–21, 2026

## Decision and candidate

A coherent **software integration candidate** is prepared. Physical Game 1 ->
Game 2 reliability and the six-game target remain NOT YET DEMONSTRATED. Hardware
readiness remains blocked by device/host visibility and restricted socket tests.
Nothing was merged into production, installed as a service or physically activated.
No model was trained. The ALA charter and acceptance standard govern all claims.

Canonical branch: `integration/native-marathon-20261020`. Frozen remote runtime object:
`2d75f5ae6bab1b9912f8905dec9a6777c799eac0`, parent PR #5
`7dcea80cd6a6448a7c13f8b83179435c049d7b3c`. Local tested runtime:
`6a46319` in `/home/five/charlie-native-integration-20261020`.
The local parent is the preserved text reconstruction described in the prior
native audit, not the remote Git ancestry. Publication overlays 58 reviewed files
onto the exact remote PR #5 parent. These files have identical Git blob identities;
all runtime/configuration source hashes are frozen in `tested-source-final.json`.
Documentation/receipts may advance the branch without changing that frozen runtime.

Native environment: Raspberry Pi 5 ARM64 Linux 6.18.50+rpt-rpi-2712,
Python 3.13.5, original `/home/five/Projects/charlie/.venv/bin/python` runtime,
OpenCV 4.10.0. No packages were installed. `requirements-neural-score.txt` remains
an optional upstream **host engineering** specification, not Pi installation
instructions. Torch/ONNX/export availability and actual HEF/model identity are
not inferred from fake-SDK tests. No private Mint corpus, weights or partitions
were accessed. The fixed HUD reader remains the live default; optional neural
and detector adapters are unqualified and never selected by marathon commands.

## Inspected sources and feature inventory

Fresh GitHub metadata confirmed these heads before integration. No source PR
branch was updated by this mission.

| Source | Exact inspected head | Integration decision |
|---|---|---|
| PR #5 | 7dcea80cd6a6448a7c13f8b83179435c049d7b3c | Native base: camera, gameplay, lifecycle, reserve support and recovery reports |
| PR #8 | b4f258853964edbc3e442f9332675d5ebd7007e9 | 34 selected source/test/tool files; original downloaded blobs verified; joint import/admission corrections below |
| PR #7 | 83112b4b9d20f97178a6494f09f48713d4210344 | 16 selected files plus session-import repair; local 365bc84 tree equals published 93846db3ac9641414396724b567effb480211fb4 |
| PR #6 | ab58a3d3d3f83a44e77184d329f0e28c1f9cbda8 | Five observation-only tools/modules and regression tests; common Hailo admission added; no live backend selection |
| PR #3 | b1d1ef14fd9100a34a94519305db802c2b75d66e | Existing review/import/feedback architecture retained; newer PR #8 interfaces supersede an indiscriminate overlay |

| Capability | Present and integrated | Tested evidence | Installed / qualified |
|---|---|---|---|
| Camera lifecycle/preflight recovery | CameraSession, borrower isolation, current-session calibration, invalidation | Existing lifecycle and preflight regressions | Candidate only; running host identity/ownership unknown; live transition pending |
| Continuous frames / controller overlap | PR #5 producer, bounded ring/pins, exposure freshness, main-thread perception lookahead | Stream/overflow/cancellation/timing regressions; six saved-frame native benchmark | No deployment; live capture age and 8–12 meaningful Hz unmeasured |
| SELF / respawn reacquisition | Signed response, reversal/neutral controls, existing track recovery; center is ordering prior only | Agency/projectile/attract and simulated playable-game regressions | Physical identity, respawn and score benefit unqualified; projectile SELF opt-in remains off |
| Terminal/restart | Positive page evidence, temporal confirmation, later restart permission, fresh START acknowledgment | Original terminal-camera replay and controlled two-game lifecycle | No authentic qualified new completion or Game 1 -> 2 transition |
| Watchdog | Completed-work progress, bounded recovery, out-of-process cleanup | Progress/handoff/interruption regressions | Live host process reaping and neutral hardware acknowledgment pending |
| Thermal/resources | Existing offline 75C suspension, below-65C recovery for 5s; bounded camera/recording queues | Existing thermal tests; read-only native thermal/environment sample | Offline controls do not establish live thermal supervision; external monitoring required |
| Score evidence | Fixed HUD + phase-separated temporal tracker; original photos/reviews retained; optional neural proposals | Label/geometry/hash/abstention/reload and score-worker tests | Neural recognition NOT qualified; independent final score review required |
| Shared Hailo ownership | Existing Admission now also wraps optional detector VDevice lifetime | Fake-SDK and cross-client exclusion/failure-release tests | Process-local only; no physical Hailo or cross-process ownership qualification |
| Durable completion / identity | Existing source seals, capture/content identity, writer barrier, append-only completion journals | Recording/identity/duplicate/interruption regressions | Source validation is not independent physical score certification |
| Offline meditation / retained learning | Existing Executive/Reflection/Meditation interfaces plus PR #7 projections and tactical diagnostics | Fresh-process E1 control and two identical P1 replays | Candidate state copies only; original acceptance and I1 remain open |
| Reserve icons | Existing inactive reviewed-count support + source-bound ROI diagnostics | Controlled support semantics; two original photographs inspected | No independently reviewed count corpus or detector; not a marathon prerequisite |

Older dirty agency-recovery and camera-calibration worktrees were inspected, not
merged wholesale. Their fixed focus, response windows, stop checks and preflight
configuration already exist in the PR #5 base. The 12-pixel geometry-jitter
configuration is inherited, not newly relaxed here. Their diffs match the prior
recovery backups. Original main, score-sampler, learning-recovery and audit
checkouts remain unchanged; see `preservation.json`.

## Implemented integration corrections

1. PR #8's newer inspect_robotron_score.py had lost PR #7's immutable session
   import receipt cache and SQLite-sidecar rejection. Restore both while retaining
   exact `00`, invalid-`0000` rejection, review supersession and original pixels.
   Before reconciliation: three import regression failures. After: checks pass.
2. ScoreObserver retained every processing-time float indefinitely. Bound those
   samples to 2,048 while preserving whole-game count, total and maximum. Replace
   repeated 256-element gameplay-history list copies with a bounded deque. Reject
   geometry submission after close. Both new regressions failed before repair.
3. PR #5's player submission now forwards existing capture metadata and explicit
   exposure/read-completion basis to the PR #8 observer interface. This does not
   activate the optional reader or manufacture exposure timing.
4. Optional PR #6 detector inference now uses PR #8's existing shared admission
   object before creating VDevice. Resource denial or memory pressure cannot
   silently trigger CPU fallback. Mutual exclusion is nonblocking and respects
   suspension; errors release ownership. This does not preempt in-flight work or
   exclude external processes. Existing .85/.25 neural gates and decoder edges,
   HEF identity/preprocessing and required-Hailo semantics remain unchanged.
5. PR #7's indexed category projections and bounded retained tactical diagnostic
   interface are included. Ordinary player construction still does not pass the
   experimental memory into physical policy; no I1 claim follows.

## Native measurements

Six hash-matched October 17 saved playfield frames, four passes, single-thread
BLAS/OMP, actual Pi CPU: legacy classification median **77.41 ms**, batched
classification **70.45 ms** (about 9% lower); full terminal classification
**212.10 ms** versus hypothetical supported-SELF scheduler **2.44 ms**.
These reproduce benefits already in PR #5, not new physical throughput gains.
No archived photograph establishes supported SELF for that benchmark. Native
camera cadence, frame drop/age, display latency and sustained meaningful updates
remain unmeasured. See `integrated-native-replay-cost.json`.

On a read-only copy of the authentic overnight notebook, the included Executive
category projection returns exactly the same ordered 45 context IDs and 45
meditation-result IDs. Baseline full observation decoding: **1.284 / 1.269 s**;
category lookup: **0.201 / 0.202 s**. The byte hash is unchanged. This is a native
projection cost comparison, not a learning or independent experience gain.
See `query-benchmark.json`; no original read-only journal was migrated.

Actual background score-worker ABBA control, 6,000 synthetic unreadable 4x4 images
per arm, mocked HUD but real queue and append-only log: timing retention falls
6,000 -> 2,048; measured retained Python memory falls **373–406 KB -> 243 KB**.
Wall times overlap (**2.46–2.49 s before; 2.38–2.46 s after**). Claim bounded
instrumentation memory, not a demonstrated perception/control speedup. No error
or dropped sample occurred in those controls. See `score-benchmark.json`.

Unsuccessful/restricted checks remain visible: first integration tests exposed
three dropped receipt/sidecar protections; both score-boundary regressions failed
before repair. A fake-SDK fixture bypassed the new constructor and initially
lacked admission; its setup was corrected to exercise the real contract. A first
attempted full run and a parallel lifecycle run shared a disposable gameplay
lock directory and were interrupted after cross-suite lock conflicts. Their
logs remain as invalid harness runs, not product qualification. The launcher now
creates a distinct home/state/temp root for every invocation. No guard was disabled.

## Lifecycle and evidence acceptance

| Transition | Current implementation / evidence | Remaining acceptance |
|---|---|---|
| Ready -> START | Current calibrated startable pages, controller readiness and actual transport acknowledgment | Host controller identity and physical START/display causality |
| START -> gameplay/SELF | Fresh commencement evidence plus independent agency tests | Authentic native SELF; expected position is never identity |
| Supported play -> loss/respawn | Fresh observations, bounded neutral recovery and causal reacquisition | No independently qualified individual-life sensing or respawn timeline |
| Play -> terminal | Positive GAME OVER/postgame evidence on ordered fresh observations | Existing original failed episode is not retroactively upgraded |
| Terminal -> sealed completion | Recording completion/manifest/source identity; report consistency and journal commit | New authentic complete-game evidence, independent score/channel attribution |
| Completion -> next START | Prior durable barrier, later startable evidence, new acknowledged START; single camera owner | First authorized Game 1 -> Game 2 trial |
| Attract demo -> SELF | Retired episode cannot resurrect; new game requires new evidence | Physical demonstration rejection |
| Three complete games -> meditation | Camera/controller/writers close first; scheduled_learning requires qualified target; normal Executive handles checkpoints | Authentic three-game input set and completed meditation receipt |
| Meditation -> next block | Retained state reload, new bounded block and fresh camera session | Separate operator approval; no experimental policy activation |

Timeout is a failure/safety stop, never a game completion. Unknown/partial sessions
are preserved. No source report was rewritten to convert replay into acceptance.
The original terminal episode is replayed read-only through the existing tool;
source seals, frame identities and observations remain bound to originals.

Reserve audit: the two historical source photographs are hash verified. A small
sprite-shaped HUD mark is visible beside the score in one; the corresponding
area appears empty during gameplay in the other. This is visual investigation,
not independent count adjudication or a death/respawn sequence. A diagnostic
P1 reserve ROI hypothesis `[179,48,300,92]` is separate from score crop
`[64,0,179,96]`; it is NOT a qualified calibration and is not used at runtime.
Unknown counts remain null. No recognizer was trained/activated and no score ROI
was changed. Zero reserves can mean the final active life. Reserve observations
never establish terminal state, SELF, START or controller authority.

## Learning and original evidence

E1: prior scoped recurrence learning reproduced on the integrated Executive.
Fresh-process actual evaluation with identical 19 alternatives: **2.0 -> 1.5**;
scoped ablation: **2.0**. The winner remains unchanged. This resolves recurrence
of score-review uncertainty, not the cause of score-reading errors.

P1: the same preserved authentic six-origin tactical ledger yields 99 contexts,
**96 changed numeric valuations / 84 changed diagnostic preferences**. Two fresh
process outputs are byte-identical. All returned actions remain unchanged.
Retrospective diagnostic adaptation is distinct from prospective performance.

I1: **NOT YET DEMONSTRATED**. No candidate activation or downstream physical
policy influence occurred. Independent complete-game performance: **NOT YET
DEMONSTRATED**. Original October 9 notebook acceptance, unavailable/partial
recordings, independent Mint comparison and remaining original ALA-2 obligations
remain open. No software test count closes any of these gates.

Original notebook remains byte-identical:
`7c942b2a5977142ba093bfe2b2238d8d37573438e55b9c8cab5f566bb44ae6ae`.
Full isolated state and original journals are retained locally. Replay readers
were bound read-only; new reports and copied-state selections were written only
to this mission's evidence directory. Duplicate source copies are not new games.
No authentic new game identifiers or completion seals were created by this mission.

## Tests, reproduction and blockers

The preserved full run finished with **1,465 passed, 36 failed, 26 skipped** in
744.75 s. Of those failures, 34 are sandbox socket denials; two are the fixture
issues described below. Final per-test failures/skips are in `test-report.json`.
The full native suite uses read-only code/library binds, synthetic device nodes,
private process namespace and per-invocation state. It intentionally cannot touch
physical controllers or cameras. Full native source is frozen by
`tested-source-final.json`; the earlier interrupted runs are excluded.

Run `bash /home/five/charlie-native-integration-evidence-20261020/sandbox.sh
-m pytest -q tests -p no:cacheprovider` for the same device-free environment.
Launcher, replay wrappers, benchmark harnesses, source manifests and compressed
results are included here; full copied notebooks and multi-megabyte replay traces
remain under `/home/five/charlie-native-integration-evidence-20261020`.

Direct bare TCP socket creation outside the inner bwrap and the previous native
full suite fail with EPERM. The current environment exposes no video/media,
controller or Hailo nodes and only its private PID namespace. No eligible less
restricted execution route is available. Do not weaken socket tests or report
blocked checks as passes. Re-run socket-dependent cases in an ordinary operator
terminal using the isolated synthetic-device launcher before any physical trial.

Remaining blockers: authoritative host installation/process/device identity;
exclusive camera/controller/Hailo ownership; blocked socket tests and optional
runtime/archive checks; live focus/framing/freshness; meaningful observation
rate and control/release/display attribution; physical SELF/respawn/attract
qualification; genuine sealed Game 1 -> 2 completion; continuous temperature,
throttling and memory monitoring; independent score review; three-game mediation
inputs and checkpointed retained outputs; qualified I1 and original ALA-2 gates.

See [operator commands and stop conditions](OPERATOR.md). This candidate is
prepared for software review and a gated operator trial, not a hardware-ready
or marathon-success declaration.

## Upstream reports

- [PR #5 native audit](https://github.com/mrgarmise/charlie/blob/7dcea80cd6a6448a7c13f8b83179435c049d7b3c/docs/validation/native-marathon-20261020.md)
- [Recovered session](https://github.com/mrgarmise/charlie/blob/7dcea80cd6a6448a7c13f8b83179435c049d7b3c/docs/validation/session-recovery-20261020.md)
- [PR #8 crop/CTC report](https://github.com/mrgarmise/charlie/blob/b4f258853964edbc3e442f9332675d5ebd7007e9/docs/neural-score/CROP-DIAGNOSTICS-20261020.md)
- [PR #7 native learning recovery](https://github.com/mrgarmise/charlie/blob/83112b4b9d20f97178a6494f09f48713d4210344/docs/ppal/ala2-experience-recovery-20261018/native-20261019/README.md)
- [PR #6 observation bridge](https://github.com/mrgarmise/charlie/blob/ab58a3d3d3f83a44e77184d329f0e28c1f9cbda8/docs/hailo-observations/README.md)
- [PR #3 score-feedback recovery](https://github.com/mrgarmise/charlie/blob/b1d1ef14fd9100a34a94519305db802c2b75d66e/docs/score-feedback/REPORT.md)


## Resumed October 21: exact stopping point and completion

The October 20 session stopped after the runtime object was created on GitHub,
before its integration branch, draft PR, final evidence bundle and two local
fixture corrections were published. GitHub returned 404 for the intended branch
at resumption; no successful branch publication was assumed. All 58 runtime
publication blob IDs match the remote runtime tree
`fb84172ac8bdc604be59ca6d0c759c043503340c` exactly. PR #5/#8/#7 heads are unchanged.
Eight preserved worktrees retain exactly their recorded HEADs and status.

The full run's two non-socket failures were SQLite startup under a 50 ms test
flush deadline and synthetic exposures outrunning the evidence writer. The
preserved corrections initialize SQLite normally before applying the flush
limit, and pace causal integration fixtures on durable writer completion.
Production deadlines, queues and overflow guards are unchanged. Original full
failure receipts are retained. The corrected 18-test recording group and
32-test agency group passed before interruption; a resumed 12-test recording
check passed in 2.13 s. These are focused results, not a rewritten all-green
full-suite claim. The isolated lifecycle run's three socket failures also remain
in the bundle. No long suite or learning replay was restarted.

`tested-source-final.json` identifies the original full-run source;
`tested-source-resumed.json` identifies the final fixture-corrected source.
The frozen runtime in OPERATOR.md is unchanged; use the integration branch for
corrected tests and receipts. The operator must resolve the 34 blocked socket
checks in the device-free launcher before physical trial consideration.

Readiness: software integration is reviewable; native physical Game 1 -> Game 2
is **NOT READY pending the stated host, device, software and evidence gates**.
Scoped historical E1/P1 diagnostic evidence is preserved. I1, independent
complete-game performance, original mission obligations, six-game marathon
success and ALA-2 closure remain unestablished. Reserve icons remain supporting
evidence only: zero reserves can mean Charlie is playing his final life.

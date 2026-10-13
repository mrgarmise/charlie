# Charlie ALA-2 thermal recovery engineering report

Date: 2026-10-12 America/New_York (2026-10-13 UTC). Scope: operational suspension/recovery only. Native deployment, original notebook modification, physical gameplay, servo commands, firmware changes, candidate activation and branch merging were not performed.

## Governing sources and integration base

The attached `ALA_LEARNING_CHARTER.md` and `ALA2_ACCEPTANCE_STANDARD.md` were read before implementation. Their authentic-experience, independent qualification, provenance, authorization, rollback and separate Executive/PPAL causal obligations remain in force. The October 9 failure and original persistent notebook were not rewritten or reclassified.

Dedicated branch: `feature/ala2-thermal-recovery`, based on published acceptance head `4bca038591a586c70a7f97f50f1af25ef42f6794`. Ancestry checks verify that it contains native installed `6ba21fb9b56e492a85bf3b7fc2e9b5fb63ab9789`, acceptance checkpoint `84de3ffedf5d25d82268b1b1ffe14447dd6b84a8`, and agency branch head `708a1f6b5177497f4e765dd1900fa8407d266d8c`. No work from either history was discarded. Published implementation: `1895bc7b92b92b8b53add5abc16631e9be22c7e4`. Local code commit: `58392cf57cbbb916819e7a768eb72360bfb94097`; source tree: `221cf5de3f1faa0e78a4801c097ebc514ce22fd0`. GitHub publication uses the connected repository account; published commit metadata may differ from the local author while the entire tree is verified identical.

## Original mechanism and the hour-long run

The installed guard raises generic `ResourceUnavailable` on temperature >=75°C. The lifecycle yields/checkpoints, but the run loop increments its turn counter for every refusal. It has no latched cooldown, hysteresis, stabilization or automatic wait/resume. Four immediate refusals can exhaust four turn slots without any Executive progress. Missing sensors were previously accepted without a thermal check. The old worker supervisor probes resources only on increasing child progress, allowing stalled work to defer resource checks.

The provided native run preserved 3247 original records and appended zero, retained 19 projects/36 commissions/18 blocked items, found no runnable work, and ended `yielded_without_progress`, with steady state unestablished and physical authority false. Its thermal reason agrees with the installed thermal-violation path. **No incident temperature, timestamped transition trace, per-stage duration, or profile was supplied.** Later 52.7°C and `get_throttled=0x0` do not establish earlier temperature or throttling.

The approximately one-hour duration remains unproven. The old loop does not contain a cooldown sleep; ordinary 0.05s intervals across four slots contribute about 0.15s. The 2-second experiment budget is not a whole-turn or constructor deadline. Constructor/final status reconstruction, evidence acquisition, full-file SHA reads, archive/session verification, retained meditation checking, SQLite/project projections and fsync can run outside it. The supplied inventory lists a 1.9GiB archive and additional larger worktree archives; only explicitly configured roots are read, so other archive sizes do not prove this invocation visited them. With no appended records, costly retained-state/status work before a refusal is also possible. Current profiling can distinguish these costs, but cannot retroactively identify the original cause. The repair adds bounded cooperative deadlines plus an operator outer timeout; it does not claim to have diagnosed or eliminated every filesystem/projection latency.

## Architecture and changes

| File | Change and rationale |
|---|---|
| `learning/resources.py` | Typed thermal/memory interruptions; <=75°C ceiling; injected sensors/clock; persistent latch interface; strict <65°C stabilization; resource re-admission; invalid telemetry conservative handling. Cached refusals remain refusals. |
| `learning/lifecycle.py` | Same Executive lifecycle; lightweight separate telemetry; retain latch across restart; acquisition boundary checks; thermal-only polling; attempt/progress/poll counters; bounded wall/cooldown deadlines; cancellation and signal-handler restoration. |
| `learning/cycle.py` | Resource checks before candidate work/evaluation and unconditional offline child resource polling via existing supervisor. Original plans/checkpoints/chooser remain authoritative. |
| `experiments/ppal/progress_supervision.py` | Optional offline `on_poll` admission/cycle checks; interruption uses existing stop/reap path even without child progress. Physical callers retain default behavior. |
| `main.py` | Configurable cooling/stabilization/deadline arguments passed to existing application worker; no new scheduler or physical capability. |
| `tests/test_thermal_recovery.py` | Deterministic sensor/clock tests, real Executive checkpoint restart controls, worker-reaping, telemetry deduplication, bounded collector and no-hardware controls. |
| Existing resource/stall tests | Thermal release now explicitly waits stabilization; injected meditation preemption targets meditation instead of newly guarded acquisition. Assertions about original identities and non-stall behavior remain. |
| `tools/observe_development_thermal.py` | Bounded read-only actual-sensor/status collector; no heating, scheduling, evidence fabrication or physical imports. |
| `docs/ppal/thermal-recovery.md` | Operational behavior, accounting, limits and exact operator staging/copy/validation commands. |

Before: generic resource refusal -> waiting -> slot consumed -> stopped when requested count expires. After: thermal violation -> durable latch/checkpoint -> suspension/cooling polling -> eligibility after stable <65°C -> memory/ownership admission -> retained Executive resumes. Reheating interrupts again. Other resource refusals, missing evidence, invalid meditation and worker failures do not become thermal recovery. Normal unbounded operation has no default cooldown expiry. Bounded runs use 300s wall / 120s continuous cooldown defaults and terminate explicitly if either expires.

All expensive work already in a monolithic filesystem/hash/evaluation call cannot be interrupted at an arbitrary instruction safely. Construction, final status folds and fsync can overrun a cooperative deadline. Existing supervision polls every 0.2s and may require its existing signal grace periods to reap a child. The outer native `timeout` is the hard validation boundary; a forced kill does not establish a clean shutdown. This distinction is part of the handoff, not hidden behind a unit-test claim.

## Deterministic evidence ledger

All injected temperatures and fixture gameplay data below are **controlled software inputs**, not authentic Pi observations or new learning evidence. `test-results.json` and compressed JUnit reports provide commands, exact outcomes, identities and provenance.

| Control | Baseline / retained update / later result |
|---|---|
| Thermal boundary | 60°C admits work; exactly 75°C latches; cached checks cannot return a false clear. |
| Hysteresis | 70°C and exactly 65°C retain suspension; 64°C starts stabilization. Oscillation to >=65°C resets it; two stable seconds in the injected-clock fixture release once. Production default is five seconds. |
| Reheat | 75°C immediately after release re-latches; oscillating temperatures do not rapidly cycle. |
| Telemetry loss | Missing, NaN, infinity, negative, out-of-range, Boolean/string, or reader exception suspends; loss during cooling resets stabilization. ARM Linux cannot opt out. |
| Memory / gameplay controls | Memory refusal is typed and never becomes cooling; stable cooling with exhausted memory remains eligible but latched. Gameplay takes priority and resets cooling verification. Neither permits false recovery. |
| Retained investigation | Heat is injected after the first actual reconstruction pair in a fixture. A durable checkpoint retains neighbor=1 and the original context/commission. Five further hot turns change no journal documents and no checkpoint bytes. |
| Restart causal control | Reopening at 70°C remains latched; reopening below 65°C alone still waits. Only after the injected stable interval does the same work/commission complete through existing Reflection. Every pre-interruption record remains byte-identical; commission/result counts are one each. Original input bytes remain unchanged. |
| Same-process continuation | A thermal-preempted Executive attempt is followed by polling and a successful retained attempt under one lifecycle object; two actual attempts use one nonthermal slot, no duplicate commission/result, no activation. |
| Bounded / shutdown | Polls consume no slots or productive turns. Cooldown and wall deadlines terminate at injected times. SIGTERM during unbounded suspension stops in <=0.1s sleep granularity, retains latch, restores handlers; cancellation bypasses cache. |
| Stalled child | A child with no progress report is stopped/reaped on the second resource poll; supervisor records resource preemption and unverified boundary, not a scientific result. |
| Deduplication / safety | Repeated identical hot polls append no redundant operational events and no journal records. Thermal-only controls retain physical_authorization=false, controller_writes=0 and no camera/controller/gameplay module initialization. Observer never writes the notebook or overwrites prior observations. |

`productive_turns` uses the existing Executive's committed-progress indicator. It can include software checkpoint advancement, and is not proof of E1 or P1 learning. Operational temperature records remain outside the scientific journal; existing checkpoint/yield receipts report real interruption of fixture work and preserve content-addressed deduplication.

## Validation environment and limits

Host: Linux 6.18.44 x86_64/glibc 2.39; Python 3.12.14; pytest 9.1.1; NumPy 2.5.4; Pillow 12.3.0; OpenCV-headless 5.0.0.93. Torch is unavailable. No Pi, camera, servo or working controller device was used. **976 passed, 21 skipped, zero failures in 249.24s** in the final comprehensive software regression. The separate thermal/stall controls passed **43 tests in 12.68s**. Exact final summaries and skip reasons are in `test-results.json` / retained regression output.

Initial unrestricted repository collection failed with six existing errors: MicroPython `machine`, the `behaviors` package conflict affecting `test_mobile_track.py` and `tests/test_memory_recall.py`, and absent `libcamera` for three vision scripts. Collection also attempted to open `/dev/ttyACM0` through a legacy import and failed because the device was absent; no controller command or physical action occurred. Subsequent regression scope is `tests/`, excluding the known collection-blocked memory-recall module; do not run unrestricted repository collection on physical hardware. Nineteen Torch-dependent cases and two original-archive-dependent checks are reported as skipped, not passes. A first software sweep had one obsolete preemption injection failing because acquisition gained earlier resource checks; its intended meditation boundary was fixed and retested.

Focused regressions cover lifecycle, resource, efficiency, profile, meditation yield/restart, stall handling and independent progress supervision. `git diff --check`, Python compilation and CLI help also pass. The full final software regression uses the same committed source bytes. A clean detached checkout of published implementation `1895bc7b92b92b8b53add5abc16631e9be22c7e4` passed **97 focused regressions, zero skips/failures, in 33.32s**. Its complete source tree matches the local tested tree. No desktop result substitutes for native acceptance.

## Acceptance and remaining dependencies

| Requirement | Status | Evidence / dependency |
|---|---|---|
| Automatic recovery implementation | PASS | Source, deterministic controls, regressions; guarded single Executive |
| Same investigation/checkpoint/identity continuity under injected cooling | PASS | Held-hot comparison, same-process resume and restart controls |
| Bounded polling/shutdown/resource separation/safety controls | PASS | Typed constraints, deadline/signal tests, child stop/reap and no-hardware assertions |
| Committed, published dedicated branch | PASS | Implementation published and replayed from clean checkout; exact tree and parent ancestry verified; final report commit in handoff |
| Original one-hour root cause | NOT YET DEMONSTRATED | Missing contemporaneous native timing/profile; bounded-work gap identified |
| Authentic native Pi suspension and recovery | NOT YET DEMONSTRATED | Requires separately approved staging/offline observation on copied notebook; original stays intact |
| Productive original native investigation after cooling | NOT YET DEMONSTRATED | Requires native resource-clear resumption and eligible authentic evidence; blocked work remains blocked |
| E1 Executive adaptation / P1 PPAL adaptation / I1 qualified integration | NOT YET DEMONSTRATED by this repair | Their independent authentic causal controls and guarded integration remain separate ALA-2 obligations |
| Frozen complete-game Robotron improvement / ALA-2 completion | NOT YET DEMONSTRATED by this repair | No gameplay or independently measured complete-game comparison performed |

The precise next actions and required observations are in `../thermal-recovery.md`. Authorize staging/offline validation separately; do not deploy this worker into the normal application, modify the original notebook, merge, deliberately heat the Pi or authorize physical operations implicitly. If no natural thermal trip occurs, retain that negative observation and leave the native recovery gate open. Run continuity inspection on the copied notebook before/after, retain all attempts and inspect candidate/commission IDs, transition times, actual measurements, resource priority and clean shutdown. E1/P1/I1 remain independently governed and open.

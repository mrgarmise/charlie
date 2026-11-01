# Charlie — Objective A v2: Integrate and Deploy Mobile Body in the Normal Runtime

**Revised:** 2026-11-01, after master-integration campaign PRs #17–#24  
**Runner:** Codex on Charlie's Raspberry Pi 5, using a native session with whatever device and loopback access is genuinely available  
**Repository:** `mrgarmise/charlie`  
**Nature:** Narrow continuation and operational integration, not a restart of the master campaign, another dashboard implementation, or a supervised motor trial.

## Execute this mission

Complete the remaining *Objective A* work autonomously to the extent the actual runtime and access allow. The outcome is a **single normal Charlie application**, including its existing AttentionManager, perception, pico:ed object display, developmental Learning Executive, optional Executive review capabilities, shared ELEGOO camera/telemetry, and authenticated local Mobile Body monitoring. Safely integrate the existing implementation, install and observe it in the real normal Pi service if permissible, and publish independently tested corrections. Do not request operator involvement for routine coding/configuration/CI; do not pretend physical tests or privileges were obtained.

**Do not execute the original Objective A handoff unchanged.** It predates the campaign and incorrectly directs development back to PR #16. Preserve that document as history; use this revision for continuation.

## Verified source baseline (refresh before edits)

- PR #17, the canonical capability/mission register, **merged**. `master` was `c53c7e662ececbd8d90c8945f04cddbdf909ace4` at campaign checkpoint; this is historical, not an instruction to reset.
- PRs #18–#23 are an **unmerged, stacked draft runtime campaign**. **PR #23** (`campaign/mobile-review-options-20261101`) at `3b364f9b3eca8ae3348fb5f9eb4eaeb315f32b27`, tree `eb8ea26b8460a3b2f3d6f6dfee93dd9cc347a8de`, is the latest independently validated cumulative implementation at the checkpoint. It includes PR #16's mobile console via PR #21; it also includes earlier #13 shared architecture, stationary evidence recovery (#18), Executive questions (#19), guarded model learning (#20), mission status view (#21), and immutable acquisition subset (#22). PR #23 corrects forwarding of `--human-questions` and `--model-learning` in the *mobile-specific ability entrypoint*.
- **PR #24 is a documentation/checkpoint PR based on master, not a newer runtime.** Read `docs/master-campaign/CHECKPOINT-20261101.md` on #24, but **do not** substitute #24 for PR #23 as the code base.
- At publication, PR #23 passed **two independent full regressions, each 1,719 passed / 27 skipped**, plus 36 real browser/HTTP and 131 canonical conformance tests. Preserve all failures, including local sandbox socket denials and the baseline calibration failure. These tests do not establish installation or hardware acceptance.
- `docs/mobile-console/CAMPAIGN-INTEGRATION-20261101.md` on PR #21 specifically documents reconciliation of PR #16 and authenticated `/missions` / `/api/missions` read-only status. Do not implement duplicate console, mission registry, HTTP listener, or Executive.
- All runtime PRs remain **draft** and inherited source/merge/native/safety holds remain effective. No source from #18–#23 was deployed or merged into master at checkpoint. PRs #13/#16 and their original branches remain intact.

**Cumulative source changes mean this is now chiefly a NORMAL-RUNTIME WIRING + NATIVE DEPLOYMENT mission, not implementation of the Mobile Body UI or the Executive review features from scratch.**

## Previously completed operator evidence — preserve, do not reflexively repeat

The operator reports a recent backup and separate checkout, demonstrated telemetry, and successful object recognition labels displayed on pico:ed. Discover and inspect the actual backup paths, original test receipts, preserved working setup and identity; distinguish established observations from qualifications they do not prove. Do not request the operator to rerun these demonstrations simply because a Codex sandbox cannot see their devices. Keep all original notebooks, recognition evidence, failed records, unknowns and durable safety fault markers unchanged.

## Precise implementation and verification tasks

### 1. Establish the correct source and installed runtime

Audit current `master`, PR #23 tip, PR #24 checkpoint, all relevant worktrees and dirty files, active Charlie processes/services, launch arguments, runtime identity, protected state paths, port 8768, camera/serial owners and backup/new checkout. Treat source and installation as separate facts. Use a disposable branch/worktree **based on the current cumulative PR #23 implementation** for scoped Objective A corrections; preserve all upstream PR heads. If another campaign is actively writing a branch, avoid overlap and record integration provenance.

### 2. Close the *actual* normal-main routine gap

Inspect `main.py`, `learning/mobile_runtime.py` and existing dashboard adapters at the current PR #23 tree. At the checkpoint, `main.py` still has a dedicated `mobile_only` route that runs the dashboard and developmental worker but does **not** construct the normal primary AttentionManager/vision loop. PR #23's “mobile startup integration” refers specifically to forwarding human/model opt-in flags in the mobile ability entrypoint; it does **not** demonstrate removal of that architectural split.

Make the mobile console available from the **same selected normal application runtime** that owns its source publications, normal attention/vision, display and Executive lifecycle. Do not start a competing application, sensor producer, camera, event bus, HTTP server, actuator executor or Executive. Preserve `--human-questions` and `--model-learning` opt-ins as optional, using a single journal/Executive and their existing reviewed semantics. Support compatibility with existing object recognition and pico:ed labels; do not break the operator's proven behavior. Do not falsely claim every optional mode is simultaneously active if upstream startup contracts prohibit that combination; correct eligible software wiring or explicitly report a real incompatibility.

Retain local authenticated `http://127.0.0.1:8768/mobile` and existing `/missions`, `/api/missions`, Abilities routes as applicable, with shared route/server ownership. The hosted owner-private dashboard's navigation is a separate publishing concern and must not block local use.

### 3. Resolve Objective A's seven barriers without touching movement authority

1. **Autonomous movement authorization:** out of scope (Objective B). Do not create self-granted boot licenses, relax `supervised_trial`, bypass physical STOP/uncertainty/local-expiry or manufacture independent evidence. Charlie may run read-only with motion denied.
2. **Read-only telemetry authority:** locate authentic installed-protocol evidence and read-only admission records; reuse applicable ones through existing interfaces. Separate passive UI/read access from drive authority. If genuine protocol/read admission is missing, render that sensor *unavailable* with a reason without blocking camera, UI or Executive.
3. **Real-time safety feeds:** attach existing properly identified passive observations, keeping pan pose, exposure age, obstacle/floor/lateral coverage and motion readiness **unknown** unless independently measured. Do not infer from command ACKs, HTTP receipt age or the scalar ultrasonic range.
4. **Credentials:** provide strong private monitoring credentials, 0600 configuration file, localhost-only server, exact Host/Origin rules. No drive token is needed for Objective A; keep it **absent**. Never log, commit, embed in hosted assets or put credentials in shell history.
5. **Hardware / service startup:** use the *existing reviewed normal Charlie service*, not a second unit. Replace the example service's offline-only/non-restarting defaults only when real system context establishes a safe, motion-denied read-only launch/recovery path. Do not interrupt a moving or uncertain system. Stale boot-bound motion authority must never survive restart.
6. **Codex sandbox permissions:** previous sessions could not create localhost sockets or access camera/Hailo/serial nodes. Determine independently whether the *current* Codex session has these privileges. If not, treat inability to run native HTTP/device checks as an environment restriction, **not** a request to weaken Charlie's movement authorization or generate another software fake. Finish eligible software and provide exact blocked access paths/commands.
7. **Hosted Sites publication:** if the actual private Site project source/publishing capability is available, publish the already-prepared Mobile Body navigation in place, preserving owner audience, other pages and existing functionality; no public motor proxy. Otherwise mark *hosted publication pending* without blocking the local Pi application.

### 4. Native, read-only operational acceptance

Where the real native environment allows, start/observe Charlie's normal application with one dashboard service and **no drive token or motor command**. Verify actual authenticated `/mobile` and `/missions` HTTP responses, rejection of unauthenticated or drive requests, camera ownership and concurrent subscribers, source/generation/frame/geometry matching, stale-overlay clearing, real available sensor telemetry and faults, normal Executive/attention behavior, preserved pico:ed labels, and optional human/model review startup with no unauthorized activation. Compare real measurements and logs against prior valid evidence; do not claim exposure-to-screen latency from Pi receipt timestamps.

Confirm a safe reviewed service restart/persistence configuration, verifying only what can be observed without an unsafe reboot or interruption. Record deployed code SHA/tree, process identity, command line, service name, listener and actual sensor provenance. If the actual Pi process cannot be safely replaced or accessed, do **not** force-restart; label native cutover blocked and give exact operator-only steps, without expanding into a physical trial.

### 5. Tests, source publication and stopping rules

Run focused normal-runtime/browser/auth/Executive compatibility tests and full independent regression/conformance on any **new changed revision**. Do not simply repeat previously successful PR #23 tests and call that new progress. Never delete or xfail failures; retain genuine errors and distinguish sandbox failures from source regressions. Check runtime-hash binding of physical qualifications and preserve original reports; do not rewrite hashes or certifications to match changed source.

Publish reviewed increments on an **additive Objective A continuation branch based on PR #23** (or on a campaign-designated nonconflicting continuation of that exact tested stack), with a new *draft* PR targeting the cumulative stack rather than duplicating the original #16 branch. Do not reapply #10–#16 wholesale, advance older PR heads without coordination, close inherited drafts, merge into master, or override PR-specific no-merge holds. Keep the canonical `release/mission-register.json` and milestone record consistent with actual source/test/installed/native states.

Stop only for a genuine unresolvable environment access barrier, independent safety veto, or required external publishing action. Do not ask for intermediate confirmations on routine software work; accomplish every independent eligible task and describe precisely what is blocked.

## Objective A acceptance — do not conflate levels

**Code integrated** means one normal application/Executive/attention/sensory ownership structure and accessible Mobile Body/Missions routes, independently tested on the *new* source revision.  
**Pi installed/operating** means exact binary/config/service verified live on the Pi, with actual `/mobile` monitor-only server and real available observations.  
**Hosted published** means actual existing private Site was updated through its real source workflow; otherwise separately pending.  
**Physically qualified or autonomous-ready** means NOTHING in this mission: supervised wheel/STOP/braking trials and independent autonomous boot readiness remain the **Cleared Room** and **Objective B** missions.

A final handoff report must identify every barrier 1–7 as addressed/deferred/blocked; exact source and deployed revisions; safe monitored startup; regressions and original evidence; whether the `mobile_only` split was removed or reconciled; current hosted Site status; which existing physical measurements are still usable; and the exact remaining requirements for the later Cleared Room trial. **Run this revised Objective A before Cleared Room**, using the ultimate integrated tested runtime as the physical-trial baseline.

## Source pointers

- https://github.com/mrgarmise/charlie/pull/23 — latest tested cumulative runtime at checkpoint
- https://github.com/mrgarmise/charlie/pull/24 — continuation ledger only; `docs/master-campaign/CHECKPOINT-20261101.md`
- https://github.com/mrgarmise/charlie/pull/21 — Mobile Body and Missions reconciliation
- https://github.com/mrgarmise/charlie/pull/16 — original Mobile Body implementation and acceptance documentation
- https://github.com/mrgarmise/charlie/pull/13 — original shared architecture and safety contracts

**Source facts have historical timestamps. Re-fetch every head at execution; do not use this document as permission to overwrite active worktrees or to claim unobserved operation.**

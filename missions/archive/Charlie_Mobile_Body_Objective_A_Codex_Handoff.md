# Charlie — Mobile Body Objective A: Normal-Runtime Integration and Read-Only Deployment

**Prepared:** 2026-11-01  
**Runner:** Codex **on Charlie's Raspberry Pi 5**, in a native environment with the actual repository, services, networking and available devices.  
**Repository:** `mrgarmise/charlie`  
**Primary work:** existing draft [PR #16](https://github.com/mrgarmise/charlie/pull/16), stacked on existing draft [PR #13](https://github.com/mrgarmise/charlie/pull/13).  
**Historical review points, not permission to assume heads are unchanged:** #16 `9c4d899ff6e60f4e17d8c21cb43f8101fbda6b56`; #13 `097f110fd0c6d321d24024c399d79f0a427bf23c` (observed 2026-11-01). Re-query all heads before edits.

## Operator directive

**Carry out Objective A to practical completion without requesting intermediate operator participation.** This is a targeted implementation, integration, configuration and **read-only native acceptance** mission. Do not produce another architecture proposal or stop after publishing code that is not actually connected to Charlie's normal routine. Continue through eligible code fixes, independent tests, and safe read-only deployment; retain exact evidence and honest distinctions between implemented, installed, running, observed and physically qualified.

The operator reports that **the prior day he made a backup and a new checkout and has already demonstrated substantial telemetry and pico:ed display of recognized objects.** Discover and preserve that actual backup/checkout and existing authentic measurements/receipts. Do not throw them away or make the operator repeat successful tests merely because a different Codex session lacks device access. Inspect evidence before classifying its scope. A previous success is not proof of untested physical braking, STOP or future-boot readiness.

The operator's longer-term intent is a single, persistent Charlie with one Executive and multi-body sensory/motion capabilities. Objective A concerns integrating and operating the **Mobile Body dashboard** in this existing system; autonomous movement policy and new physical qualification are explicitly **out of scope**.

## Precise desired result

Charlie boots/runs his **existing normal `main.py` application** with its normal AttentionManager, developmental Learning Executive, current perception and device ownership, while the same process exposes an authenticated Mobile Body dashboard. The dashboard displays genuine available shared camera frames, recognition metadata/overlays and qualified telemetry without adding a second camera owner, an independently running Executive, or an alternate motor executor. The normal pico:ed object-label behavior and existing abilities remain functional. Monitoring must remain usable with **no drive credential and no physical motion authority**. The application's reviewed startup mechanism must restore the read-only dashboard safely on reboot without silently commissioning hardware or creating a competing service.

The local Pi route is the immediate deliverable: `http://127.0.0.1:8768/mobile`, through the existing loopback-hosted dashboard adapter and private access configuration. The separate owner-private hosted Site is desirable if genuine source/publishing access exists but **must not block local integration**.

## Evidence and instructions to read first

1. PR #16 `docs/mobile-console/{README.md,ACCEPTANCE.md,AUDIT.md}` and existing `setup/charlie-mobile-console.service.example`.
2. PR #13 architecture, integration reports, physical holds, native evidence, and normal `main.py` ownership contracts; inspect PR #10–#12 lineage rather than reapplying already-merged-into-#13 changes.
3. Exact currently installed Pi checkout, yesterday's backup/new checkout, worktree inventory, service startup configs, process/PID/port ownership, camera/serial/Hailo owners, protected learning state and evidence directories, firmware/bridge identities and original receipts.
4. Existing normal `main.py` execution paths and `ui/dashboard.py` / `ui/mobile.py`, `stimulus/bus.py`, `motion/elegoo_executor.py`, `learning/actuator_safety.py`, `learning/deployment.py`, and `learning/mobile_safety.py`.

**Known structural problem to address:** `main.py` has a special `mobile_only` hardware branch that starts the mobile console with a development worker but does not run the full normal AttentionManager/vision main loop. Prefer connecting Mobile Body to Charlie's **real normal app path**, not deploying an isolated Mobile Body mode and treating it as brain integration. Existing flag choices can be mutually exclusive; reconcile the selected normal configuration without disabling prior working capabilities.

## Work program

### Phase 0 — Preserve and discover, without another qualification campaign

- Verify the current PR and branch graph, #13/#16 ancestry and current changed files. Check `git worktree list`, dirty files, remote fetch/auth, release state, active service(s), cameras, port 8768, firmware/bridge/readback identities, saved backup(s), exact normal invocation, prior Pi logs and current state. Do not reset or overwrite active worktrees or notebooks.
- Determine where yesterday's backup and checkout actually are. Preserve original authentic sensor/recognition evidence, earlier failed measurements and durable uncertainty markers.
- Write a small inventory of evidence that is **already demonstrated** versus what has not been established. Treat the operator's observed functioning pico:ed labels and earlier telemetry as starting facts, while verifying whether each existing receipt satisfies the current installed-source protocol and read-only authority rules.
- Inspect the established safety and PR draft/merge holds. Do not merge into `master` or change holds under this mission. Use the existing PR #16 branch or a safely isolated continuation of it, keeping original source and ancestry traceable.

### Phase 1 — Normal-application wiring

- Reconcile #16 with the current #13 implementation/evidence head. Do not create a parallel application, camera producer, sensory bus, web API, Executive, attention manager, or actuator authority.
- Make `--mobile-dashboard` attach to the **single normal application** using its existing shared feeder, StimulusBus, qualified executor and existing dashboard adapter. Confirm the normal Executive, AttentionManager, object recognition, optional face/pet paths, and pico:ed labels remain intact. Do not enable mutually incompatible launch flags blindly; adapt integration safely where appropriate and test the real configuration.
- Preserve all normal manual-control isolation: browser requests travel only through existing qualified executor; STOP priority, deadman/watchdog, stale-frame handling, leases and independent motion denial must remain intact. The local UI may display disabled controls and reasons when physical authority is absent.
- Distinguish display-only dashboard software from physical movement eligibility. The lack of a newly witnessed chassis trial **must not block read-only UI startup** or normal eligible non-motor sensory learning functions.

### Phase 2 — Resolve the authorization barriers appropriate to Objective A

**Barrier 1: autonomous movement authority.** Do **not** rewrite the `supervised_trial` actuator authorization to self-grant motion. A future independent autonomous-readiness architecture is Objective B. Preserve physical holds and the ability to demonstrate disarmed/read-only dashboard operation.

**Barrier 2: read-only telemetry admission.** Inspect the existing read-only telemetry qualification, installed protocol and measurements. Reuse authentic, applicable prior evidence in the existing CapabilityDeployment path if it already satisfies the contract; do not synthesize reports, witnesses, hashes or activation grants. If current read-only authorization cannot be legitimately established, leave that specific sensor unavailable with a truthful reason **while allowing shared camera, UI, and other independent functionality to proceed**. Do not couple monitoring credential availability to drive authorization.

**Barrier 3: real-time safety measurements.** Reuse real source-bound sensory feeds where present. Report unavailable/unknown for unqualified pan position, exposure age, obstacle coverage, floor clearance, blind spots or stale values; do not map command ACK, chassis yaw, camera receipt age or an ultrasonic scalar to evidence they cannot supply. Physical motion remains off. Do not make missing motion-only data prevent ordinary read-only viewing.

**Barrier 4: dashboard credentials.** Establish a private strong monitoring credential using a secure local provisioning mechanism; keep secrets out of shell history, source, URLs, hosted assets, tests and logs. Use reviewed 0600 environment-file storage, exact Host/Origin checks and localhost-only binding. No drive credential is required for success; by default **omit `CHARLIE_DRIVE_TOKEN`**. If a separate Abilities dashboard is enabled, preserve its existing operator token and route on the same server.

**Barrier 5: hardware startup.** Inspect the current service and normal application configuration before making any change. `--offline` is the current safe default; only use a reviewed `--hardware` run when the actual installed setup supports the intended stationary/read-only mode. Do not install the example user unit alongside an already active physical Charlie service. Configure startup persistence and restart behavior without authorizing motion; ensure a reboot cannot revive a stale boot-bound lease/grant.

**Barrier 6: Codex environment restrictions.** Previous restricted runs yielded `PermissionError` creating even loopback sockets and exposed no camera/serial/Hailo devices. First determine whether the **current native Pi Codex process** actually has network socket and device access. If yes, use normal least-privilege access, existing service protocols and passive measurements. If the execution sandbox still blocks essential system calls, distinguish this from Charlie's safety authorization. Do not change motion code to work around sandboxing, and do not falsely claim that fake-wire or synthetic-pixel CI is native acceptance. Complete all eligible software work; report the exact inaccessible command/interface and needed environmental permission if native observation remains blocked.

**Barrier 7: hosted Site publication.** If the actual owner-private Sites source/project helper and publishing privileges are accessible, integrate the prepared `ui/mobile.js`/`ui/mobile.css` Mobile Body route into the **existing** Site, preserving existing pages/data, Abilities route, audience and authentication. Test and publish only through the genuine Site workflow. Never add bearer credentials to hosting source or proxy physical motion through a public Site. If inaccessible, report this as a separate external blocker; it does **not** block the local Pi dashboard or objective completion for local use.

### Phase 3 — Safe native installation and validation

- Use the actual existing normal Pi service/launch path, preserving its process ownership and existing rollback state. Before replacing or restarting an active application, verify that an existing qualified shutdown is safe and will not interrupt active physical movement. If safe stop/replacement cannot be established, do not force-kill, SIGKILL, steal device owners or restart into motion; preserve the working installation and mark native cutover blocked.
- Demonstrate (when permitted) the local authenticated `/mobile` route, monitor-only access and its denial of drive actions. Verify same-origin local access and documented SSH/private tunnel access, not a public interface.
- Verify that the existing one-camera-owner architecture is maintained with concurrent subscribers. Validate source/generation/frame-ID matching, stale clearing, reconnection, bounded history, recognition overlays and measured display FPS/age, explicitly distinguishing Pi receipt timing from unknown sensor exposure timing.
- Verify the normal Executive lifecycle and AttentionManager continue running, and that existing pico:ed object-label output is not regressed. Test available read-only ultrasonic telemetry with physical references when its existing qualified read authority applies, including invalidity/staleness reporting; never issue speculative firmware commands.
- Exercise the normal application's operator controls at the **software/fake-wire level only**. No physical motion command, new firmware flash, arbitrary service replacement or simulated external grant may be used to claim hardware acceptance.
- Install/validate reviewed reboot persistence without silently enabling physical movement. Record actual process IDs, startup args, listening address, source identities, telemetry observations, log paths and version hash. If reboot itself risks disturbing the system, document the staged boot-persistence result rather than rebooting unsafely.

### Phase 4 — Tests, publication, final report

- Run focused tests plus the existing independent regression and conformance suites on the exact implementation revision. Verify normal app + mobile UI behavior with absent/denied hardware as well as permitted sensor paths. Preserve original failures and rejected requests, and repair eligible regressions without deleting assertions or weakening stopping/authority gates.
- Existing qualification records may be runtime-hash bound to source files that this integration edits. Preserve them unchanged. Classify whether integration altered qualified behavior and which qualification records no longer match; never update/report hashes merely to make old certificates appear current. Distinguish a software-only regression pass from authentic physical requalification.
- Publish independently tested scoped increments back to the **existing draft PR #16**, preserving #13 and all other active PR heads. Do not close the PR, force-push, blanket-merge or silently promote to `master`; a separate master-integration mission/PR holds govern final promotion.
- Produce a succinct final **matrix** with states: `SOURCE`, `SOFTWARE TESTED`, `INSTALLED`, `LIVE NATIVE OBSERVED`, `PHYSICALLY QUALIFIED`, `AUTONOMOUS-READY`, `BLOCKED`. Include exact commit/tree/runtime hashes, services and commands, URL, logs/receipts, prior evidence reused and exact remaining blockers.
- End with a short **Cleared Room trial handoff** stating the tested integrated revision, which physical qualifications remain missing, and which existing qualified measurements may be reused. Do not begin physical movement trials as part of Objective A.

## Acceptance criteria / when to claim completion

Objective A's **software portion** is complete when: (a) the dashboard is mounted in Charlie's normal startup rather than an isolated demo; (b) its code retains one sense/executor/Executive ownership structure; (c) the local authenticated view and read-only behavior pass independent automated tests; (d) existing pico:ed/object/Executive behavior regresses neither in tests nor available native checks; (e) physical controls remain denied absent genuine authorization; and (f) tested code/commit and evidence are published to #16.

Objective A's **native deployment portion** is complete only upon observing that the actual selected normal Pi application is running with the local Mobile Body route, and logging the real available camera/telemetry observations and startup configuration. If native permission, protected process ownership, real protocol authority or missing devices block part of this, label that portion **BLOCKED**, not completed. Publish all software progress and the exact restriction instead of stopping prematurely or inventing success.

Hosted Site publication is a separately tracked deliverable, not a prerequisite for local functional deployment. Physical wheels-up/floor-driving/STOP/braking tests, new motor qualifications, operator-supervised movement, permanent autonomous readiness and `master` merge are **not** Objective A acceptance requirements.

## Handoff sequence

**Run Objective A first.** Next, use its exact installed/tested revision to update and execute the previously queued **Cleared Room Mobile Body** physical-qualification mission with the operator present and control of the physical cutoff; reuse already authentic, applicable records. **Objective B** (independently governed autonomous startup/movement readiness without per-boot human prompts) is a later separately reviewed design, validation and implementation mission. A full integrated system should not need a human to decide every permitted activity, but the Executive must never self-certify missing hardware evidence or override independent vetoes.

## Required reporting format

1. **Delivered:** exact normal runtime, routes, credentials provisioning approach (never reveal secrets), operating service and preserved functions.
2. **Verification:** test commands/results, real sensor measurements and observations with source/timing, CI/commit links; say when observations are synthetic.
3. **Authorization barriers:** each of the seven above, labeled addressed / not applicable / blocked / deferred, with evidence and reason.
4. **Remaining for Cleared Room:** only genuinely outstanding physical trials or environment requirements, with existing trials preserved and referenced.
5. **Rollback and PR state:** exact pristine backup/checkout state, new commits, draft PR status, installed version and safe rollback procedure.

No progress checkpoint by itself is the end of the eligible software mission. Continue autonomously across the scope above, stopping only at a genuine independent physical-safety, access or operator-action boundary.
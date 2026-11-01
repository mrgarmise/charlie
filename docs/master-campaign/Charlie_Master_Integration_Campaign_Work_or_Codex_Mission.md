# Charlie — Master Integration and Autonomous Capability Consolidation Campaign

**Prepared:** 2026-10-31 (America/New_York)  
**Target:** `mrgarmise/charlie`, authoritative default branch `master`; related `mrgarmise/charlie-arcade` is separately owned.  
**Recommended runner:** Codex on Charlie's Pi 5 for native inspection and testing; Work or other connected GitHub-capable runner for isolated repository integration.  
**Mission nature:** Real implementation, reconciliation, verification, safe incremental publication, and evidence-backed promotion. Not another architecture proposal; not a blanket PR merge; not permission for unsupervised hardware operations.

## 0. Executive instruction and desired outcome

Integrate **as much safe, tested, valuable Charlie functionality as possible into authoritative `master` and the normal `main.py` runtime**, while preserving Charlie's persistent identity, existing Robotron and learning operation, sensory architecture, original evidence and notebooks, exact hardware gates, and full rollback. Build one cohesive runtime rather than disconnected demos or competing services.

**Prioritize by architectural dependency, user-visible autonomy, confidence and merge risk—not chronological age, PR number, or UI attractiveness.** Work continuously through eligible independent increments. Commit and publish independently tested increments throughout the mission; do not use success at an intermediate phase as a reason to stop. Do not present source publication as native installation or as proof of physical autonomy. Leave only genuinely unqualified hardware/authentic-data gates pending, with exact procedures, artifacts and blockers.

A successful result includes: (1) a verified current branch/commit/evidence inventory; (2) a canonical capability and mission register; (3) the shared sense/attention/action architecture integrated into an offline-safe normal `main.py`; (4) as many additional independently tested capabilities as can be safely integrated; (5) reviewable, scoped promotion PRs and, **only where existing holds and project authorization permit**, merges into `master`; (6) documented source / tested / integrated / installed / running / physically qualified states; and (7) dashboard-consumable status, with origin chats and instruction files when known.

## 1. Authority, preservation and non-negotiable boundaries

- GitHub `master` is authoritative for integrated **source**, **not** a claim about the Pi's running application. Check exact `HEAD`, `origin/master`, tag `best-of-charlie-v0.1.0`, worktrees, dirty files, installed release manifest, running process identity and evidence/note paths independently. Source at preparation time was `bcf8082f6319c63c4bd6bcceeab5faea37241654`; this is a historical pin, not a substitute for refetching.
- Inspect GitHub PR descriptions, review constraints, acceptance contracts, original mission documents and branch ancestry **before** proposing a merge. Preserve all branches, open drafts, commits, reports, CI receipts, original notebook bytes, labels, failed traces and original attachments; do not rewrite shared heads, force-push, overwrite working trees or fabricate evidence.
- A prior explicit **do-not-merge / keep-draft-until-qualification** hold remains effective. This campaign authorizes preparation, testable publication and software promotion where already permitted; it is **not** unilateral authority to waive PR-specific holds, change branch protection, or bypass an operator's required merge decision. Supply a distinct gate for any blocked final merge. The operator's objective is maximum safe `master` integration—not a license to weaken acceptance.
- All physical motion, Robotron controller input, RP2040 servo activity, ELEGOO chassis commands, firmware writes, deployment, model/policy activation and electrical operations remain **off** unless independently authorized and qualified in the existing safety system. Do not replace authentic sensor measurements with zero, commanded state or host-side acknowledgment. STOP, local expiry, watchdog, independent cutoff, source freshness, floor/obstacle controls, runtime hash binding and durable uncertainty all remain independent gates.
- No remote dashboard/web/HTTP component directly controls motors or camera hardware. The dashboard requests are mediated through existing AttentionManager / qualified actuator executors and source-owned feeders. No public motor endpoint, unapproved tunnel, autonomous physical tests, silent mode activation or unbounded service startup.
- Default release to offline/read-only and explicit disarmed hardware flags. Bounded intake/training and native diagnostic reads should not create new notebook writers or alter the original journal. Preserve state backups and test rollback mechanics before release promotion.
- Important: **Software inclusion**, **independent CI**, **native passive observation**, **hardware qualification**, and **learned improvement** are different claims. Preserve all five as separate acceptance dimensions.

## 2. Current topology — observed 2026-10-31, refresh before execution

| PR | Subject | Current relationship / preparation baseline | Integration guidance |
|---|---|---|---|
| [#10](https://github.com/mrgarmise/charlie/pull/10) | Pet observation and guarded following | `feature/mobile-perception-pet-following` @ `9c1319d`; direct ancestor of #13 | Already contained within #13 by Git ancestry; do not reapply wholesale. Real autonomous following unqualified. |
| [#11](https://github.com/mrgarmise/charlie/pull/11) | Shared owner/subscription camera and object-label display | `feature/object-label-picoed-display` @ `a19c908`; ancestor of #12 and #13 | Already contained in #13. pico:ed label output demonstrated earlier by operator; comprehensive native acceptance separate. |
| [#12](https://github.com/mrgarmise/charlie/pull/12) | Canonical sensory contracts, bounded frame history | `audit/shared-sensory-contracts` @ `ae09f52`; direct ancestor of #13 | Already contained in #13. Treat its architecture and conformance contracts as binding. |
| **[#13](https://github.com/mrgarmise/charlie/pull/13)** | **Unified sensing, motion, face, STOP, object demonstration** | `integration/unified-sensory-motion-20261026` @ `097f110`; **67 commits ahead, zero behind `master`** at inspection; contains #10/#11/#12 exact heads | **Primary integration candidate**; latest unchanged implementation tree passed three full independent CI suites, each 1,600 passed / 21 skipped. Examine whole diff and hold/physical gates; do not infer installed qualification. |
| [#16](https://github.com/mrgarmise/charlie/pull/16) | ELEGOO Mobile Body dashboard console | `feature/mobile-body-console-20261031` @ `9c4d899`; stacks on #13 implementation `77d7e34` but **diverges from #13 latest evidence-only head by one commit** | Reconcile its parent with the accepted #13 integrated tree; do not overwrite either head. HTTP/console release and physical drive qualifications differ. |
| [#14](https://github.com/mrgarmise/charlie/pull/14) | Asynchronous human question UI and answer gateway | `feature/asynchronous-human-questions` @ `4bb3bff`; branches from old `master` | Integrate after shared perception/Executive contracts; attach real opt-in producers/consumers, retain atomic attribution and current notebook ownership. |
| [#15](https://github.com/mrgarmise/charlie/pull/15) | Executive-owned model learning and review | `feature/executive-model-learning` @ `d360514`; branches from old `master` | Integrate guarded worker/CLI/shadow paths; do **not** claim authentic model training or activation. Current authentic corpus review/qualification insufficient. |
| [#7](https://github.com/mrgarmise/charlie/pull/7) | ALA-2 experience-to-decision recovery | `feature/ala2-experience-to-decision-recovery` @ `83112b4` | Review its scoped real E1 and diagnostic P1 evidence, transfer independently qualified safe mechanisms without conflating with I1 or complete-game improvement. |
| [#3](https://github.com/mrgarmise/charlie/pull/3) | Score review feedback recovery | `feature/score-feedback-master-integration` @ `b1d1ef1` | Exact original annotations/photographs and qualified consumption still required; safe dormant code can be considered separately from acceptance. |
| [#5](https://github.com/mrgarmise/charlie/pull/5) | Continuous capture and agency-first Robotron | `feature/fast-projectile-self` @ `7dcea80`; open draft, relative to older Robotron branches | **Explicit no-merge hold** in PR; selectively reconcile with authoritative feeder/ownership and original notebook. Do not wholesale merge. |
| [#6](https://github.com/mrgarmise/charlie/pull/6) | Hailo observation-only detector bridge | `feature/hailo-observation-bridge` @ `ab58a3d`; based on #5 lineage | Preserve observation-only role, native Hailo/model qualifications pending; avoid competing camera owners and compute leases. |
| [#8](https://github.com/mrgarmise/charlie/pull/8) | Neural Robotron score reader | `feature/hailo-score-reader` @ `b4f2588` | Keep fixed reader incumbent, neural proposal gated/abstaining; authentic held-out calibration and native HEF tests pending. |
| [#9](https://github.com/mrgarmise/charlie/pull/9) | 3-game / learning / 3-game marathon | `integration/native-marathon-20261020` @ `9ba60e2`; also built on #5 family | Integrate safe offline campaign/state machine when dependencies are stable; actual automatic game/restart remains qualified/authorized only. |
| **Arcade [#4](https://github.com/mrgarmise/charlie-arcade/pull/4)** | Deadman controller lease | **Separate `charlie-arcade` repository** | Coordinate interface/protocol compatibility only; no silent cross-repository merge or physical launch. |

The open-PR audit includes **13 current Charlie draft PRs (#3, #5–#9, #10–#16) plus one Arcade draft PR #4**. Requery before reporting totals; prior status recaps accidentally omitted #5 and #7. PR #2 closed status should be inspected before attributing its implementation.

Essential source documents: `docs/CHARLIE_ARCHITECTURE.md`, `docs/architecture/{RESOURCE_OWNERSHIP,CONNECTIVITY_AND_DEPLOYMENT,CONFORMANCE,AUDIT_REPORT}.md` on #13; `docs/best-of-charlie/README.md` and `release/capabilities.json` on `master`; `docs/mobile-console/{AUDIT,ACCEPTANCE,README}.md`; `docs/human-interaction/{ACCEPTANCE,README}.md`; `docs/ppal/ala2-experience-recovery-20261018/native-20261019/README.md` on #7; original ALA charter/acceptance standard. Use GitHub links and exact commit/tree hashes in reports.

## 3. Integration principles and target runtime

**Existing Charlie architecture is canonical. Do not invent a second platform.**

```text
Pi IMX708 / ELEGOO camera / RP2040 / ultrasonic / remote eyes
   -> one authoritative acquisition/configuration owner PER SOURCE
   -> source registry + immutable timestamped, source-identified publications
   -> bounded subscriber queues / frame history / passive observations
   -> object/pet/face/Robotron/Hailo inference, evidence and memory
   -> existing AttentionManager + LearningExecutive/PPAL + Evaluator/MARM
   -> only qualified actuator executors / STOP and authorizations
   -> pico:ed display, RP2040 servos, mobile chassis, arcade controller

Web UI / local console -> authenticated intent / read-only status -> same
attention/executor path (never a competing camera or motor owner)
```

- Integrate as actual normal `main.py` abilities and configuration, not just importable modules or a sidecar demo. Preserve initial/idle state, normal Executive, safe task preemption/recovery, multi-body identity, single writer and shared source labels. Give each available capability discoverable status: `unavailable`, `implemented-inactive`, `software-integrated`, `native-observed`, `physically-qualified`, `autonomy-demonstrated`, etc. Avoid equating `git merged` with `working`.
- For each source/actuator, enforce exclusive authority, bounded buffering, stale-data rejection, source/boot/generation/hash lineage, fault recovery and fair resource admission. Existing Hailo scheduler is compute, not raw sensing. The source registry is discovery/metadata; it need not carry every byte itself.
- Preserve legacy callers via subscription-backed facades where necessary, with tests prohibiting direct driver opens, duplicate camera ownership and fallback bypass.
- Preserve compatibility with normal Robotron, Active Vision, face tracker, pico:ed display, remote/specialized eyes, learning memory, fallback offline operation and existing stop semantics.
- Do not redesign just for elegance: reuse and repair tested source. No second Executive, event bus, capture owner, web command server, authentication system, model notebook or actuator authority.

## 4. Execution program: dependency-ordered, independently deliverable

### Phase 0 — Freeze truth, inventory and merge gates (required; no code activation)

1. `git fetch --all --prune` only after checking current worktree(s) and authentication; never reset local modified files. Record `git status --porcelain`, `git worktree list --porcelain`, all remote heads/parents/merge bases, current `master`, installed release, `main.py` processes and original persisted notebook identities. If shell authentication fails, use connected GitHub API read/write paths with expected-head checks; don't modify key material.
2. Query **all** open/closed PRs including #3/#5/#6/#7/#8/#9/#10–#16; query `charlie-arcade`. Read current PR bodies for do-not-merge / draft restrictions, baseline CI, review threads and evidence holds. Record which branches are ancestors, which overlap or are divergent, and independent active edits.
3. Establish baseline CI on exact current `master` and matching untouched controls. Preserve known preexisting writer/loopback/float assertions and failures; don't call them passes or casually xfail/delete. Run small focused contract checks, full available host suite and proper CI. Record time/RSS/CPU/temperature where available.
4. Create an additive canonical **mission and capability register** in the repository, preferably backed by existing `release/capabilities.json` plus a new linked mission-index document if needed. Each entry must contain ID, description, original chat title/URL if verified (or `UNKNOWN/PENDING EXPORT`), Library mission filename, Git PR/Linear URL, base/head/target, status dimensions, last tested revision, remaining blockers, dependencies, owner, safe next action, date and evidence links. Do not fabricate originating chat URLs.
5. Establish a release/promotion gate document and baseline matrix showing each existing main feature/function and its non-regression tests. Publish this as a small reviewable documentation-only PR unless existing project controls already have an identical authoritative register.

**Deliverable:** audited branch ancestry graph, zero-loss preservation map, baseline CI receipts, machine-readable master-campaign registry, proposed safe merge sequence and review gates.

### Phase 1 — Main architectural promotion: PR #13 (top priority)

1. Confirm with Git ancestry that current #13 contains current #10/#11/#12, and examine subsequent changes or new heads. Current prepared proof: #13 is a descendant of #10 @ `9c1319d`, #11 @ `a19c908`, #12 @ `ae09f52` and `master` @ `bcf8082`. Avoid applying all three old PRs again.
2. Treat #13 as the primary candidate for a clean `master` integration. Create a **disposable integration worktree**, pin base and candidate. Inspect every changed runtime/motor/firmware/deployment path and all relevant tests; #13's large (~252 files at inspection) diff needs special attention to archived receipts, generated artifacts and source provenance.
3. Prefer the most direct safe promotion: if full reviewed #13 is disarmed by default, respects all existing hold/merge gates and passes fresh full/cross-feature CI against current `master`, make its cumulative source the reviewed promotion. **Do not introduce redundant new architecture or new per-feature copies.** If an unresolved hold or unsafe native activation prevents whole-branch promotion, extract **small, semantically complete** foundation slices with accurate parentage and tests: (a) sensor publication/registry and subscriber contracts, (b) vision/pico labels, (c) AttentionManager+pet observation, (d) qualified executor/STOP/face preflight, (e) optional stationary object demonstration. Each slice must leave normal `main.py` safe and runnable.
4. Non-negotiable conformance: one Pi and one ELEGOO camera owner; independent simultaneous subscribers; source switch without disrupting others; bounded latest/recent history, ordering/restart semantics; single actuator owner and STOP priority; original motor safety gates unchanged; object output and normal Executive/Robotron compatibility. Tests for absent/denied hardware must pass offline. Reconcile #10's latest safety increments; don't regress its rejected invalid braking/travel evidence.
5. On each successful slice: publish exact code+tests+reports to reviewable staging PR(s), run independent CI, verify tree/commit hashes and regression diff, obtain review/required permissions, and only then merge eligible work to `master`. Reconcile old PR #10–#13 statuses only **after** confirmed inclusion, keeping outstanding native-acceptance issues open.

**Software completion:** `master` can start in safe offline mode, publish sources and run existing normal abilities together without competing camera/motor/Executive owners. **Physical acceptance remains separate** (firmware identity, servo/STOP/face, obstacle/floor and real-cat following).

### Phase 2 — Executive and human-learning consolidation (#7, #14, #15)

1. Reconcile #7's authentic scoped E1/P1 results with current master and existing ALA charter. Preserve exact replay/ablation and original notebook identity. Do not claim I1, autonomous real-game improvement or durable policy activation. Integrate reusable verified mechanisms without overwriting journals.
2. Integrate #14's authenticated asynchronous question journal/UI **through the existing Executive and current pet/Robotron evidence opportunities**, with atomic review/acknowledgment and fallible human answers. Ensure actual normal application hook and restart behavior; use opt-in safe web access, no public endpoint and no motor/policy authorization from a human answer.
3. Integrate #15's model-learning task adapters, supervised resource budgets, dataset lineage, guarded evaluation, separate held-out partitions, shadow candidate states and human review without changing incumbent live models. Resolve overlap with #14 on review/question APIs so both use existing durable identities rather than rival systems.
4. Test one **real normal application instance** simultaneously running shared source publication, AttentionManager, Executive selected activity, persistent answers and guarded model-learning review. Use deterministic saved observations for host acceptance; report genuine native/inference outcomes separately. Preserve all evidence; no synthetic labels as authentic truth.
5. Promote safe default-off functionality with exact CI and review. If authentic data/physical devices are unavailable, advance source readiness without pretending complete learning qualification.

**Software completion:** One Executive owns learning priorities and questions; evidence and replies survive restart; candidate learning is integrated but appropriately inactive until independently qualified.

### Phase 3 — Dashboard and console value, without turning UI into an authority (#16)

1. Reconcile #16's source against the **latest accepted #13/master** and its one newer evidence-only head; preserve both. Retain read and drive roles, expiring leases, independent STOP, source match/TTL, stale-data clearance, no motor bypass.
2. Integrate local Mobile Body page through the existing `ui/dashboard.py` adapter. Preserve operator object demonstration and live per-source camera/ultrasonic/recognition status. Use real available observations; show unknown, unavailable or stale for unqualified signals, not synthetic zeros or fabricated FPS.
3. Link the existing hosted owner-private dashboard only through its genuine Sites source/project workflow if accessible; **never overwrite the entire site or silently change audience/access.** If inaccessible, publish the local adapter and a clear pending hosted-site deployment note, preserving exact current site identity.
4. Add a **read-only Mission/Capabilities** dashboard view consuming the canonical registry: status by code/CI/native/acceptance, priority, blockers, PR/Linear/originating chat/Library mission links, last verification and recommended next step. Avoid manual status tables that drift out of sync with GitHub.
5. Keep all driving and remote motor operations unavailable until the existing independent native/physical qualifications and current operator authorization. Verify monitoring works with drive permissions absent.

### Phase 4 — Robotron and model/perception improvements (review individually, not a blanket merge)

1. Evaluate #5 continuous capture/agency-first code as a **conflict-prone** source. Its own PR says not to merge yet. Adapt useful bounded capture/timing/policy work **under the single shared owner** from Phase 1; preserve native timing and original life/SELF safeguards. Obtain explicit resolution of its merge hold before changing `master`.
2. Evaluate #6 Hailo observation bridge as a source-identifying, observation-only subscriber with shared Hailo lease; zero gameplay policy change until authentic calibration.
3. Evaluate #3 safe score-feedback importer/consumer with original October 10 SQLite/photo recovery; no manufactured improvement claims and no changing score truth without independently verified labels.
4. Evaluate #8 neural score-reader pipeline as proposal/abstention only while fixed reader remains incumbent; preserve private corpus and true held-out score acceptance gates. No unqualified model activation.
5. Evaluate #9 3 / meditation / 3 campaign **after** camera lifecycle, terminal recognition, controller readiness and score evidence are proven. Safe disarmed campaign logic can enter `master` independently of permission for physical play. Freeze revisions and collect complete-game evidence; no second writer or unobserved START.
6. Audit separate `charlie-arcade` #4 for protocol compatibility, but do not change its native installed controller or merge across repositories as if one branch.

**Robotron software completion is not performance completion.** Report authentic before/after complete games separately. E1/P1/I1 and independent performance claims each require their own reviewed evidence.

### Phase 5 — Release truth, acceptance ledger, ongoing integration policy

1. Maintain changelog and `release/capabilities.json` with precise merged `master` SHAs, CI tested tree identity, installed/active/qualified states and regression links. Do not silently change the immutable previous release tag; create a new release/tag only under existing release controls.
2. Produce a single release candidate integration plan; check `main.py --offline` (or actual current approved CLI), start/stop, normal Executive, Robotron compatibility, passive vision, correct hardware-denied behavior, cross-PR resource ownership, rollback and unmodified original evidence.
3. Generate one durable mission index used by both GitHub and dashboard; map pending source missions to originating chat titles (known historical list below) and explicit unknown links. Reconcile Linear statuses only with corresponding tested evidence and project conventions. No automatic closure merely because a feature's code merged.
4. Report native Pi read-only observations from actual available access. If remote device nodes/network denied, leave exact native/physical acceptance pending with operator-supervised steps; no vague 'hardware pending' labels where specific dependencies are known.
5. Recommend a policy for future PRs: new feature's normal-runtime registration, ownership tests, integration-base update, required CI, staged merge, registry update and dashboard propagation must be part of definition of done. Keep future work on small reviewable changes to `master` rather than letting months of draft branches accumulate.

## 5. Acceptance matrix required for EACH promoted capability

| Dimension | Required evidence |
|---|---|
| Implemented | Exact source tree, entrypoint, interfaces and explicit optional/default flags |
| Independently tested | Focused tests, full regression CI, unchanged-master comparison of existing failures, failure receipts, environment/version |
| Integrated | Normal `main.py` path demonstrates producer/subscriber/Executive/actuator contract using safe fixtures or disarmed operation, not just unit import |
| Published to master | Actual merge commit/tree SHA on authoritative branch, provenance back to old PR(s), no duplicated ancestry |
| Installed | Actual Pi release manifest exact tree/bytes, not just Git SHA |
| Operating | Actual current PID/start ticks/process/config, representative bounded observation and resource cost |
| Physically qualified | Independently witnessed device/safety/output evidence with exact current runtime/firmware and authorization; never inferred from ACK |
| Autonomous benefit | Verified Charlie-selected decision and retained subsequent action/outcome with appropriate baseline/ablation; distinct from code integration |
| Residual work | Narrow remaining blockers, safe procedure, owner, exact acceptance source, never a vague 'done' |

The operator should be able to answer: **What is in `master`? What can normal Charlie do today without an operator? What has only passed software tests? What is waiting for me at the Pi? Where were the original instructions?**

## 6. Historical origin chat titles to attach to register (not verified URLs)

- `Historical audit status` — Phase 1 dashboard/project inventory, Phase 2 conversation export still pending.
- `Review class progress` — free-drive dashboard request, autonomy/model learning discussion.
- `Integration Incomplete Report` — PR #13 unified sensing and motion continuation and STOP/face milestones.
- `Audit And Publish Corrections` — sensory architecture audit, PR #12.
- `Add Object Recognition Display` — PR #11 object recognition and pico:ed.
- `Implemented Pet Tracking Mission`, `Explore CV Models`, `Robot Navigation Setup` — PR #10 pet-following and mobile multi-body design.
- `Implementation validation mission` — PR #14 asynchronous human Q&A.
- `ALA Work Tab - Autonomy` — Robotron, ALA, Hailo score reader and campaign source discussions.
- `Review Text File` — later object-demonstration/dashboard continuation; exact document contents require original conversation verification.

Related Library files already observed: `Charlie_Project_Audit_Phase1.md`; `Charlie_Unified_Sensory_Motion_Integration_Work_Mission_Reviewed.md`; `Charlie_Sensory_Architecture_Audit_Work_Mission.md`; `Charlie_Pet_Follower_Complete_Integration_Work_Mission.md`; `Charlie_ELEGOO_Pet_Tracking_Full_Work_Mission.md`; `Charlie_Object_Recognition_PicoEd_Display_Work_Mission.md`; `Charlie_Asynchronous_Human_Question_Learning_Work_Mission.md`; `Charlie_Autonomous_Model_Learning_Codex_Mission.md`; `Charlie_Robotron_Authentic_Dataset_Qualification_Codex_Mission.md`; `Charlie_Keyboard_First_Human_Review_Interface_Codex_Mission.md`; `Charlie_Hailo_Score_Reader_Crop_Diagnostics_Work_Mission.md`. **Do not invent chat URLs, completed status, or other Library files; update names after actual discovery.**

## 7. Runner workflow and delivery contract

- Before touching code, reply with the exact latest `master`, current relevant PR heads and ancestry, existing holds, current isolated worktree and first staged promotion choice. Use `git merge-base --is-ancestor`, `git log --graph --oneline`, `git diff --stat`, `git worktree list` and cross-check against GitHub API. If Codex runs on Pi, inspect native installations read-only while respecting device denial.
- For each eligible slice, create a new additive integration branch/worktree, implement/reconcile runtime registration, add regression tests, run independent focused+full tests and CI, publish commit/PR, document relationship to ancestor PRs and remaining native acceptance. **Do not stop after creating documents or running a test suite: continue eligible integration/publishing.**
- Prioritize broad validation on pinned, disposable integration stacks. Do not count a combination passing on an outdated base as assurance of the latest head. Do not disable flaky tests to improve numbers; retain failing records and compare exact unchanged baseline.
- Do not silently commit source onto `master` from an unsafe/uncertain checkout. Merge only after permission, repository protections and all applicable software merge gates; if explicit prior hold remains unresolved, leave a ready-for-review PR and identify the exact approval needed.
- Update mission register after *each* published increment, including rejected or superseded implementation paths. Avoid status drift. If dashboard source is inaccessible, keep its sync step recorded and do not claim site UI updated.
- Deliver a final compact release report: **(A)** `master` before/after SHA; **(B)** PRs merged and capability gains actually integrated; **(C)** source-only PRs/staging branches pending signoff; **(D)** tests/CI/failure receipts; **(E)** installed/running/physical evidence or exact absence; **(F)** next three high-leverage merges and any operator-supervised native acceptance steps; **(G)** exact instructions/chat/index status. Cite actual URLs and SHA/trees.

**Finish condition:** complete every eligible software-only step and publish tested, reviewable increments. Do not declare all Charlie autonomy complete simply because the combined codebase builds or because a historical synthetic demonstration passes.

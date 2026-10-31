# Pet follower completion mission — implementation and acceptance status

**OPEN: safe supervised live-pet following has NOT been demonstrated.** This session completed eligible host integration and published tested increments to existing PR #10, not a new follower application. Native access is unavailable; no motor/camera/control connection, physical trial, firmware change or physical policy activation occurred. Current authorization permits supervised qualification and independently qualified operation, but independent readiness evidence is still required.

Runtime source: 0536888090d47ad382c9d79b9a3dcff1012f24a6 on `feature/mobile-perception-pet-following`, PR https://github.com/mrgarmise/charlie/pull/10 . Base 96e651373e513d24b4163b87c5f85bdd5549cf1d. All old worktrees, Robotron, PR #11, original images/journals and species errors preserved. No AGENTS.md found. Read the mission and audited repository/history before editing; see AUDIT.md.

## Integrated behavior

The existing normal main.py startup now attaches the existing mobile perception/tracker service to the existing AttentionManager and the ONE DevelopmentLifecycle/LearningExecutive. Animal observations become opportunities. The existing portfolio scores its existing projects, uncertainty/history, costs and priorities; another ongoing interest, primary activity or unavailable resource can cause decline/yield. Choices are debounced on track rather than cat/dog label, so class flips do not create an agenda. This is the existing rule-based selector, not learned general intelligence. No hardcoded cat-seen/follow rule or second chooser was added.

The existing CapabilityRegistry exposes pet_observe/pet_follow with body, prerequisites, costs, conflicts, lifecycle and dynamic readiness. `--list-capabilities` opens no devices. `--pet-abilities` uses the same integrated sensing service without an actuator; physical `--pet-follow` additionally requires `--hardware`, independent deployment, current boot/zone/hardware, healthy resources and fresh sensor/scene proof. Old observation flags remain unarmed and old legacy face startup remains intact. Pet service prevents another legacy mobile sidecar from being created on its AttentionManager; cross-process leases cover existing camera/body transports, while the existing Hailo lease remains authoritative.

Existing PetTracker -> MobileNavigator -> MobileExecutionGate is retained. The new bounded adapter sits behind that guard, binds proposals to frame/sensors/pose/target/activation, prevents replay, uses per-direction measured envelopes and rechecks deployment/resources/feed during each <=200ms pulse. Off-axis/unknown camera pose stops and records handoff requirements instead of invoking an unbounded legacy alignment. Relative depth cannot provide metric pet range, free space or stair safety. The native feed must separately prove occupied live animal/proxy, pet-associated range, FOV, corridor, source timing and supervisory welfare/intrusion conditions.

The existing ELEGOO driver/ MobileBase now support bounded forward/reverse/pivot pulses with finite PWM/duration/lease checks, local timer (installed-source verification required), no reconnect/replay after ambiguous motor delivery, STOP on exit, explicit unknown physical consequence and STOP-delivery uncertainty. Unconfirmed STOP prevents another start. Legacy interfaces/fallback remain available to original callers. Ultrasonic querying refuses absent verified installed read-only protocol; no speculative sensor command was sent.

Existing CapabilityDeployment now validates separately evaluated mobile proof and issues/revokes finite boot/zone/body grants in its existing journal. Robotron policy activation rules are unchanged. Proxy grants cannot admit live pets; live-pet grants require proxy evidence; autonomous operation additionally requires witnessed live following/decline/restart-revoke records. Source/runtime/artifact changes revoke applicability. Calibration tooling permits reviewed supervised staged testing without requiring the later completed pet-following trial first; its default is a no-device dry run.

Original observations remain immutable. Separate attention/action/evaluation events distinguish request, decision, proposal, gate, wire, ACK, unknown/measured consequence and learning claims. Existing MemoryEvaluator records abstained/unobserved unless separate frame-bound measurements exist. Reflection, historical evidence review, journal/MemoryGateway and project bookmarks are reused; motion leases/targets are never restored across restart. No learning-derived policy self-certifies motion.

## Published increments

1. `4ecc13e74b6f6ff00238437fa250768edbe4c110` — bounded controller primitives, catalog/deployment boundary and audit; 46 focused checks passed.
2. `b3eab6e7fe89dffed08bf83697bd8bdfa175dbfc` — existing AttentionManager/Executive/lifecycle/capability integration; 72 focused checks passed.
3. `26406297deb26d2755f871fa76ea2c0aae32071a` — safety-feed revalidation, proof/evaluation evidence; 89 focused checks passed; independent GitHub CI passed.
4. `1e6cad5f04b2920fd321f5d390f85dd1e4d3cffa` — body/camera leases, direction-specific qualification and calibration tools; 105 focused checks passed.
5. `b678268c49d7b1f7730508b1f7bc7be23236669f` — proxy/live/operation stages and uncertain-stop latch; 107 focused checks passed.
6. `0536888090d47ad382c9d79b9a3dcff1012f24a6` — recovered native evidence remains available to the same current portfolio; 107 focused checks passed plus authentic historical control. Subsequent commits contain reports/evidence only.

## Independent evidence and its limits

Final focused regression: 107 passed, covering perception/tracking, original mobile face behavior, normal main/restart, whole-portfolio select/decline, higher-priority yield, no-device replay/catalog, proof tampering/reused trials, boot/zone/revoke/expiry, frame/scene/model/pose, during-pulse feed change, STOP uncertainty, body/camera exclusion and conservative evaluation. Compilation and whitespace checks passed. The isolated broad host run on b678268 passed 1,354 tests with 21 skipped and four unchanged Robotron writer-backpressure failures. All four reproduce on unchanged baseline c2ec29e (20 other controls passed). Earlier overlapping runs shared the global gameplay lock and are explicitly excluded from regression qualification; they are documented in validation.json. No Robotron production code was changed to conceal these host timing failures. Final-source independent GitHub CI passed **1,358 tests / 21 skipped** in 366.99 seconds: https://github.com/mrgarmise/charlie/actions/runs/40249483380 . validation.json records the exact revision/environment and limits.

A controlled host replay reuses all 614 original native records, verifies all 9 original encoded/pixel image hashes, retains the same Executive's authentic-evidence-review interest, and declines an animal opportunity while that interest remains active. The independent label review still finds 3 correct species predictions and 6 dog-for-cat disagreements, one correlated source log. No new image exposure/inference, sensor, device connection or movement occurs. Source journal SHA256 612c6146f580d5b5e2f6b1e776d8cdf99f8591704851cf6b37a1225c8d7bf2de is unchanged. See historical-attention.json and reproducible historical_probe.py. This is a controlled historical software decision cycle, not native real-time choice, pet identity recognition, physical following or learned improvement. Private pixels/journals are not published.

The original two-minute stationary 1000-frame/230-observation watcher, 42.2ms median inference, 48.8ms median decode-receipt-to-decision, phone-Nigel detections, almost-immediate wheels-up stop and speed 35/200ms/~1cm floor pulses remain **operator reports**, not newly verified measurements. Total travel is not post-STOP distance; a phone photo is not a live pet. Model/firmware/route paths in the mission are leads to verify natively.

## Milestones and acceptance

| Stage | Implemented and host-tested | Native / physical status |
|---|---|---|
|A ownership/audit|Current repository/history, normal lifecycle/bus/catalog, transport ownership and migration|Pi hostname unresolved; no remote channel/mounted native checkout|
|B bounded motion/sensing|Existing driver pulses/STOP uncertainty/leases, gated sensor query, staged calibration and independent measured envelopes|Installed parser/MCU/bridge, query/reply/FOV, local timer/watchdog, cutoff, stop-distance curve and sensor producer unknown|
|C existing PPAL execution|Frame/pose/sensor/activation binding, during-pulse validation, replay prevention and fail-closed adapter|No physical adapter activation; actual motor consequences unobserved|
|D lifetime abilities|Normal catalog/main/status, invoke boundary, source-specific readiness and fresh leases on restart|Native startup/restart and live concurrent workload qualification pending|
|E voluntary attention|One existing portfolio, choices/declines/yields, competing interest and historical authentic-data control|Natural current live-pet follow/non-follow/preemption not observed|
|F memory/evaluation|Original evidence+labels immutable; real Executive review retained; conservative independent action evaluator; durable bookmarks|No new native causal learning, individual identity, comfort or improved policy claim|
|G0 regression|Focused legacy/noninterference tests, source hashes and CI evidence|Physical original-face/Robotron regression not exercised|
|G1 stationary vision|Same sensor pipeline/normal AttentionManager and fault lifecycle; safe commands supplied|New sustained Pi/Hailo/camera and thermal/capture-timing measurements pending|
|G2 local safety|Source-bound verification and structured trial proof required|Measured STOP/TCP/Pi loss/local expiry/cutoff missing|
|G3 wheels-up|Single bounded supervised test path and direction-specific record validation|Historical pivots only; new instrumented missing aspects pending|
|G4 empty room|Measured speed/time/braking margins; zone/edge/obstacle/welfare gates|Calibrated per-direction stopping/drift/abort evidence missing|
|G5 proxy|Separate proxy-only grant and scene binding|No grounded proxy movement demonstration|
|G6 live cat|Proxy-before-live grant boundary, humane stop requirements, external consequence review|No actual safe supervised pet following; project NOT complete|
|G7 limited operation|Separate operation grant, boot/zone/expiry/revoke and durable history|No qualified release, natural follow/decline/restart acceptance; no whole-house permission implied|

## Exact remaining work

Obtain actual Pi access; verify existing checkout/native artifacts, installed MCU+ESP32 protocol and original motion evidence. Bind/qualify the actual native sensor/timing producer (none can be invented from currently unknown coverage). Execute G1–G4 missing independently measured aspects, then qualified normal-main G5 proxy and G6 real-cat trials in an inspected room with cutoff/witness and voluntary pet exit. Only then admit G7 limited operation and show normal voluntary follow/decline, preemption/restart/revoke and evaluated outcome. Native findings may require further implementation corrections; eligible host implementation is not a claim that unknown hardware interfaces are already integrated. RUNBOOK.md contains precise commands, proof formats, conservative rollback and all blockers. This mission does not merge/deploy over known-good installations or certify a house from one room trial.

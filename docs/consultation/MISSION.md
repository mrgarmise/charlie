# Charlie — Onboard LLM Consultation and Optional Remote Mentor

**Execution handoff for Pi-connected Codex or ChatGPT Work**  
**Prepared:** 2026-11-01  
**Repository:** `mrgarmise/charlie`  
**Status:** mission specification; **no installation, deployment, device test, or source change has yet occurred**.

## Purpose and intended behavior

Give Charlie an always-available, **onboard, offline-capable language-model consultant**. Charlie's **existing Learning Executive**, not the model, decides when a question is justified, what evidence to provide, how to interpret the answer, and whether to investigate further. Answers are fallible **knowledge candidates**, never self-validating truths. Provide a compatible optional second consultant (LAN-hosted model, e.g. Mint; later, explicitly approved OpenAI API) without coupling the learning architecture to one provider.

The first tangible milestone is a real **Qwen3 1.7B quantized model** (or, if resource measurements require, Qwen3 0.6B) serving text-only questions locally on the **Pi 5 (8 GB, Debian 13 ARM64, active cooling)** via Ollama/its HTTP API. No Hailo-8L acceleration is assumed: that hardware serves existing vision work, while this experiment uses CPU inference. A minimal independent, bounded consultant must work before any autonomous integration is enabled.

**Primary requirement:** preserve normal acquisition, Hailo vision, telemetry, dashboard, all actuator authorization/STOP/watchdog boundaries, and the existing single Executive/journal. An LLM cannot itself actuate hardware, grant authority, change policies, or install/train models.

## Verified source and continuation constraints

Before changing code, fetch and verify current GitHub head, installed identity if accessible, active PRs, and the correct development base. The November 1 published integrated runtime is **draft PR #23**, `campaign/mobile-review-options-20261101`, published SHA `3b364f9b3eca8ae3348fb5f9eb4eaeb315f32b27` *at mission authoring*. The source ledger is [PR #24](https://github.com/mrgarmise/charlie/pull/24), `docs/master-campaign/CHECKPOINT-20261101.md` on `campaign/checkpoint-20261101`. Another active draft, [PR #25](https://github.com/mrgarmise/charlie/pull/25), changes pico:ed label font; do not overwrite or entangle it.

The normal Executive integration already provides opt-in `--human-questions` and `--model-learning`; on PR #23 the normal mobile startup forwards both flags to the **same** `DevelopmentLifecycle` and journal. Relevant source includes `learning/lifecycle.py`, `learning/human_runtime.py`, `memory/learning_projects.py`, `memory/human_interaction.py`, `learning/resources.py`, and the normal `main.py` entrypoints. Review these current files and contracts rather than recreating an Executive, new camera owner, second journal, or separate autonomous agent. Preserve all existing draft/no-merge/physical-qualification holds. Create a separate feature branch and draft PR from an independently verified suitable integrated source; do not merge or alter existing PRs to proceed.

## Stage A — Native model feasibility without robot integration

1. **Preflight, read-only:** inspect hardware/OS, current model services, 8-GB RAM availability, disk space, swap pressure, CPU temperature, throttling, load, active vision/learning workload, and current installed revision. Baseline responsiveness/CPU/memory and identify safe operating limits. Confirm active cooling actually functions under load. Do not assume previous source CI proves native installation.
2. **Choose installation:** prefer Ollama's official ARM64 Linux release, installed in a reversible, operator-approved way. Initial service must listen on **127.0.0.1 only**, not a public or LAN address; it must have no browser automation, remote command execution, filesystem access, camera access, or tool-calling privileges. Avoid privileged changes to the existing running service stack; if OS-level installation requires interaction/permission unavailable to Codex, provide a precise native operator runbook and continue with all software-only work.
3. Pull/verify **`qwen3:1.7b`** first if RAM/disk allow; fall back to or compare **`qwen3:0.6b`**. Use short, text-only, non-thinking consultation settings initially, bounded context (start approximately 1–2K tokens), bounded answers (start 128–192 generated tokens), one outstanding inference, restricted CPU threads, and short model keep-alive. Tune based on measurements, not assumptions. Prevent model preload from consuming RAM when Charlie needs it. Do not attempt 4B/8B models as an automatic upgrade.
4. Benchmark cold-load and warmed model with a reproducible ~15–20-question set representing Charlie's actual needs: object recognition ambiguity, persistent cat identity, uncertainty, safe observation experiments, Robotron score ambiguity, what Charlie previously recorded, simple knowledge versus questions needing current web information. Record model version and quantization, time to first answer if measurable, total latency, prompt and generation tokens/sec, answer usefulness, failures, RAM peak, CPU load, temperature/throttling, and service interference. **Do not invent a Mint-vs-Pi speed ratio**; the Mint is not part of this stage unless it is genuinely accessible and approved for a controlled same-model comparison.
5. Repeat a short load test alongside **stationary, authorized normal sensing** if feasible (camera/Hailo and dashboard, no motors); establish whether frames, sensor telemetry, safety watchdog timings, and Executive responsiveness stay within established bounds. Set conservative stop/suspend thresholds. If native sensors aren't accessible, mark this test **PENDING NATIVE**, not passed.

### Stage A gate

Proceed to Stage B integration in default-off/shadow mode only if independent model calls and resource controls work, and no existing functionality is degraded. Native resource qualification is separately required before enabling autonomous consultation during normal real hardware operation.

## Stage B — Add a consultation provider to the existing Executive

1. Implement a compact **provider interface** with a local Ollama text provider, a deterministic fake provider for tests, and an **optional configurable remote provider** (initially another LAN Ollama endpoint). Keep provider selection and network transport independent of the Executive. An external OpenAI API provider can be a separately disabled configuration stub or follow-up; **do not create billing, add a payment method, use personal ChatGPT authentication, or make charged calls without new explicit user approval**. No Work/Codex allowance should be consumed by consultation inference.
2. Explicit opt-in only: initially **no new questions are sent by default**. Integrate at a safe cooperative/low-priority point in the *existing* `DevelopmentLifecycle` and `LearningExecutive`; share one journal, source provenance and interruption/resource guard. Do not block real-time vision or safety loops. Respect the existing human-question gateway and the independent guarded model-learning gates.
3. Questions must originate from independently committed, authentic evidence or an Executive-recognized knowledge gap; no questions from synthetic/demo observations in production. Check existing retained knowledge first, deduplicate/cool down repeated questions, enforce maximum context and prompt privacy, and bound queue length, daily count, wall time, concurrency, retries, and CPU/memory usage. If load or thermal state worsens, suspend rather than starve critical systems. Missing model/provider is a normal recoverable state.
4. Persist an attributed **consultation record**: original question and evidence references, time, request status, chosen provider and model/version, content/response digest, answer, latency and token metrics, confidence/uncertainty *as claims*, and follow-up candidate. Treat LLM answers as **unverified hypotheses**. An answer may prompt further observation, a human question, or a held review; it cannot mark a memory as verified without independent evidence. Make records replayable across restart without duplicate submissions or loss of attribution. Never modify original immutable sensor/gameplay evidence.
5. Implement **optional remote escalation**, disabled by default: use local LLM first; request remote advice only if explicitly configured/authorized and local advice is unavailable or an Executive-selected question warrants more depth. Remote network addresses must be allowlisted/authenticated and secured (VPN/TLS/appropriate access control); don't expose Ollama unauthenticated over the LAN or internet. Avoid automatic transmission of raw camera frames, credentials, private notes, or other personal information. Offline means fully functional local route with no remote requests; a remote outage must not stall Charlie.
6. Provide a simple authenticated/read-only **Questions & Discoveries** status view *if compatible with existing dashboard architecture*: pending/answered/deferred/verified/rejected counts, question text, answer origin (local/remote), latency, candidate evidence and follow-up. Prefer extending existing question UI/status instead of inventing another service. No unreviewed answer may be displayed as established fact.

## Required independent tests

- Default-off/no-model/no-network cases preserve normal startup and existing normal/mobility review options; exactly one Executive and evidence journal. No new camera owner, sensor capture, movement/actuator route, permissions, or firmware changes.
- Local fake server and deterministic payloads: correct model requests, bounded token/context lengths, timeouts, circuit breaker, cancellations, duplicate/cooldown handling, queue/day budgets, malformed JSON or nonsensical answers, stale evidence, restart recovery, model unload, and remote outage fallback.
- Answer cannot activate a model/policy/capability, grant actuator access, supersede authenticated human answers, convert synthetic data into authentic evidence, or overwrite original notebooks.
- Test answers that are incorrect or contradictory and verify retention as **unverified**, with opportunity for evidence-based rejection or revision.
- Run focused tests, relevant architecture/safety contracts and full available independent CI; keep honest failed/skipped/unavailable results. Existing unrelated failures must be preserved and investigated, not suppressed for a green count.
- Any hardware/thermals/latency assertions require actual native measurements. Separate software CI success from real Pi acceptance.

## Publishing, acceptance and deliverables

Publish independently tested increments to **one new draft PR**, referencing this mission, original source SHA, new commits, reproducible commands, exact test counts and native measurements where available. Include:

- A working text-only local inference proof or a precise operator runbook with installation and native verification explicitly pending (whichever is actually achievable).
- Model/version/configuration selection and performance report for Pi idle and stationary-normal-operation, identifying unavailable trials.
- Provider abstraction and default-off integration with existing Executive/journal.
- Safe runtime resource controls, local-only access by default, opt-in remote configuration, and a no-billing guarantee while remote API is disabled.
- Focused and regression test results, safety review, resource interference findings, rollback steps, and clear operator acceptance procedure.

**No claim of complete autonomous learning, native deployment, physical qualification or operational safety without actual evidence.** No movement, motor calibration, GPIO actuation, RP2040 firmware flash, model-learning promotion or release/deployment authority is granted by this mission. If resource limits prevent useful onboard execution, report actual data and recommend a remote LAN model as secondary—not an unapproved hardware purchase.

## Completion definition

The meaningful end state is: a proven local model can answer structured questions on Charlie's own Pi, the existing Executive can consult it when explicitly enabled, its responses become attributed fallible knowledge candidates, no critical robotics behavior regresses, and Charlie can later use an authorized alternative provider without rebuilding the consultation system. Keep genuinely inaccessible native acceptance as an exact, finite checklist.

### Reference documentation

- Official Ollama ARM64 Linux installation: https://github.com/ollama/ollama/blob/main/docs/linux.mdx
- Official Ollama API and runtime metrics: https://github.com/ollama/ollama/blob/main/docs/api.md
- Qwen3 size offerings: https://ollama.com/library/qwen3
- Original integrated runtime: https://github.com/mrgarmise/charlie/pull/23
- Campaign/preservation checkpoint: https://github.com/mrgarmise/charlie/pull/24

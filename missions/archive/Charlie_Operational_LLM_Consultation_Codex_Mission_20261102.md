# Charlie — Operational Local LLM Consultation: Codex Continuation Mission

**Prepared:** 2026-11-02  
**Mode:** Implementation and independent software validation; **NO deployment, promotion, merges, firmware changes, motor commands, or changes to the approved runtime**.

## Objective

Take the already-developed local LLM consultation capability toward **real, bounded, Executive-directed Ollama consultations in Charlie's normal application**, rather than leaving `--llm-consultation` as a permanently inert shadow queue. Implement and independently test the smallest reversible, default-off activation path, then present a precise native acceptance checklist and a separately reviewable promotion candidate. Do not declare live operational acceptance until native tests are actually witnessed and passed.

This is **not** a request to fix Charlie's existing periodic sensing stalls or to develop the whole multi-consultant roadmap. That work is separate.

## Immutable boundaries and source verification

1. Preserve `~/charlie-runtime` **unchanged** at approved SHA `f3304c588a893a953e34e5c4d00bd5f9bfb18f19` and preserve `~/charlie-ops` approvals, evidence, launch scripts, locks and rollback. Do not touch any running operational service or service configuration. Do not grant motion authority, drive the ELEGOO car, move servos, flash RP2040 or replace firmware. No automatic hardware session.
2. Inspect the *actual* GitHub state before editing: `mrgarmise/charlie`, draft PR #27 `feature/onboard-consultation-20261101` (based on draft PR #26/PR #23), current branch SHAs, full diff, accepted tests, and dependent changes. **A discrepancy needs reconciling:** the PR description reports a 2026-11-02 continuation SHA `b0c04ad4c5c6e1f0b2b9fd2e6316af286c36c01f`, but the PR metadata previously reported head `b60f4a5edb3605bac212ce7ed81a1f9b43ba92e5`. Both commits exist. Establish the actual reachable branch state and do not overwrite either continuation or other active PRs.
3. Work on a **new isolated continuation branch/worktree** based on the verified consultation implementation; preserve PR #27 and its evidence. Publish tested increments in a new draft PR or clearly linked continuation without changing the approved operational checkout. Coordinate with the separate runtime-promotion review; do not silently import unrelated mobile monitoring, motion, or unfinished Objective A changes.
4. Preserve the existing shared-sensor architecture: one authoritative physical camera owner, bus subscriptions, Executive as sole consultation decision maker, existing watchdog/resource/STOP gates. Never create a second camera owner or a language-model-controlled actuator path.

## Evidence already obtained on the native Pi 5

- A dedicated sandboxed `charlie-consultant` Ollama service was installed on the Pi 5, bound to loopback, with verified CPU and RAM cgroup limits, no device privileges, no swap, one model loaded maximum, one request at a time. Installed models `qwen3:1.7b` and `qwen3:0.6b`; exact native versions and hashes are retained in the prior operator records. **Reverify the running unit**, not assumptions from this note.
- Approved 90-second stationary recognition baseline: 4.30 observations/sec, frame interval p95 ~271 ms, zero >500 ms gaps. Warm Qwen3 1.7B consultation produced approximately normal sensing (4.27 observations/sec during question, p95 ~272 ms, no >500 ms gaps), no throttling and safe reported resources. This is **an initial coexistence screen**, not a passed complete watchdog/native acceptance.
- Cold 1.7B and cold 0.6B loading produced substantial interference; model loading must **not** occur unpredictably while primary sensing has real-time obligations.
- Later 0.6B warm/idle tests and a no-model-resident control all showed ~10–11-second periodic observation gaps. The **no-model control** had 15 gaps >500 ms, 3.966 observations/sec, p95 ~425 ms; model residency and text generation are **not necessary** for these stalls. The actual root cause remains unknown. Keep separate as a documented baseline/performance issue, do not disguise the gaps or claim an LLM fix.
- Most frame sequence jumps are compatible with the camera reader continuously decoding while a separate feeder/recognition consumer samples frames. `FrameSubscription.read()` uses `get_nowait`; `run_objects` performs synchronous evidence/recognition tasks. This does not prove the source of the stalls. No more open-ended timing experiments for this mission.
- Evidence folders (do not modify):
  - `~/ollama-consultation/benchmarks/stationary-baseline-20261102T192949Z.csv`
  - `~/ollama-consultation/benchmarks/simultaneous-1p7b-20261102T193842Z/`
  - `~/ollama-consultation/benchmarks/warm-coexistence-20261102T194726Z/`
  - `~/ollama-consultation/benchmarks/cold-0p6b-20261102T195208Z/`
  - `~/ollama-consultation/benchmarks/warm-0p6b-20261102T200025Z/`
  - `~/ollama-consultation/benchmarks/resident-idle-0p6b-20261102T200626Z/`
  - `~/ollama-consultation/benchmarks/unloaded-control-20261102T200935Z/`
  - corresponding original `~/charlie-ops/logs/*-stationary.log`.

## Implementation scope — one bounded initial consultant

1. **Build on PR #27, not from scratch.** Retain `learning/consultation.py`, Executive-journal review, evidence attribution, queue/circuit/resource guards, privacy boundaries and tests. `--llm-consultation` presently constructs only a shadow `ConsultationService`; `OllamaConfig` defaults to `keep_alive=0` (allowed max 5s), 30s request deadline. Real transport must require an **additional explicit default-off enable gate** that only works when service identity, operator consent, and native prerequisites are satisfied. A plain `--llm-consultation` must stay shadow-only for backward compatibility.
2. Start with **Qwen3 1.7B only**, text-only, local loopback, no tools, no code execution, no camera access, no direct sensors, no file browsing, no remote fallback and no actuator permissions. The Executive alone selects a supported evidence question and owns the outcome. Responses are append-only **unverified hypotheses** that cannot change physical authority, model policy, deployed code or human-validated conclusions. Preserve independent evaluation and authenticated human correction paths.
3. Implement a **bounded model readiness/residency gate** consistent with the measured loading problem. No cold model load or model switch while an active sensing deadline may be jeopardized; if no already-resident correct model is available, **skip/defer consultation**, rather than forcing load. Prewarming may be qualified before a sensing session or during an independently designated safe idle window, never by bypassing live resource/STOP checks. Reconcile PR #27's 5-second `keep_alive` configuration with the actual safe residency design; bound duration, refresh, unload, outage, restart, fallback and cleanup. Do not permit a forgotten permanently resident model with uncontrolled memory use.
4. Run consultations only from existing independently bounded Executive/development-worker pathways, **never synchronously in camera acquisition, feeder, attention/watchdog or recognition loops**. Ensure one outstanding request, finite queue/time/day limits, cancellation propagation and no auto-retry after unknown completion. A frozen, missing or overloaded model must fail closed, remain visible in status, and leave normal Charlie behavior unaffected.
5. Maintain prompt minimization: submit only bounded, generalized question text derived from admissible retained evidence; no raw images, precise identifiers, private notebooks, human message content, operational secrets or unreviewed executable instructions. Prompt/response are data, not authority. Preserve model digest, uncertainty, answer lineage and immutable receipts.
6. Keep current multi-consultant expansion (0.6B quick agent, question-architect model, coding model, remote host, Mint host, autonomous code promotion) **out of scope**. This milestone is real local consultation by one trusted *transport*, not trust in the model's answers.

## Verification and evidence requirements

- Read-only preflight of existing approved runtime, existing service identity, Ollama model digests, source/PR dependencies, permissions and current baseline. Do not change the service automatically.
- Independently test the software using deterministic fakes and a sandboxed local Ollama endpoint where permitted: gate defaults and explicit consent; ready/not-ready model; cold-load prohibited during sensing; stale question; deadline/cancel; cgroup/resource pressure; journal integrity/replay/rejection; consumer thread isolation; provider failure/restart; one-request budget; privacy filtering; no actuator imports or calls; graceful no-provider/normal runtime behavior; rollback. Retain failures and CI results.
- Produce a **separate promotion/reconciliation manifest** explaining how the minimal consultation change relates to approved `f3304c5...`, draft PRs #23/#26/#27, branch SHAs, dependencies, and files that would be touched. Never promote or cherry-pick into `~/charlie-runtime` during this mission.
- Prepare an exact **finite native acceptance** runbook for operator-supervised stationary Pi testing after software review. Use already-known matched baseline degradation bounds and record dashboard/Executive/telemetry/watchdog latency in addition to frame metrics. Preserve existing stricter guards; stop on any watchdog breach, thermal throttling, ≥70°C, MemAvailable <3 GiB, swap use, load >2, or >10% comparable performance deterioration. Distinguish inherited periodic stalls from new effects; do not declare acceptance from aggregate p95 alone.
- Include rollback: disable the new real-consultation gate; leave shadow-only operation intact; stop `charlie-consultant` if needed without disturbing approved services; retain immutable evidence. Document every untested native claim as pending.
- Publish independently tested code and a report, with a clearly stated end state: **software candidate ready / native acceptance pending / merge and deployment blocked** (unless native acceptance actually occurs under distinct explicit operator authorization later).

## Deliverable

Return concise links to the draft continuation PR, exact commits, tests/CI, implementation and rollback docs, and a minimal ordered list of **operator actions required for native qualification and later approval**. Do not ask the operator to repeat the existing bench experiments unless a specifically identified integration gate cannot be resolved from preserved evidence.
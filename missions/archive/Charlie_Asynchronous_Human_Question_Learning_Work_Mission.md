# Charlie — Asynchronous Human Question-and-Answer Learning Gateway

## Work mission — implementation, testing, publication, acceptance

**Repository:** `mrgarmise/charlie`  
**Intent:** Give Charlie, as one continuing autonomous individual, a safe, asynchronous way to identify information he cannot resolve independently, ask his human for help through a web page, receive an answer later, and incorporate that answer as traceable evidence in his existing learning loop.  
**Scope:** software implementation and independent tests now; Pi-connected and physical acceptance where access is available. No microphone, speaker, general-purpose LLM, cloud subscription, new mobile app, or autonomous motion is required for the initial acceptance.

## 0. Entry checks and concurrency safeguards

1. Inspect the current repository, branch/PR inventory, CI results, deployment configuration, canonical architecture and active integration work **before editing**. In particular inspect the recent shared sensory architecture work (PR #12), Unified Sensory and Motion Integration (draft PR #13), ALA-2/Learning Executive work, pet following (PR #10), Robotron/score-reader work (PR #8), and any later changes; do not assume these references remain current.
2. Identify actual owners of Executive decisions, PPAL/evidence, agency/state persistence, ability registration, interface/server hosting, authentication, sensor observations and answer ingest. Use existing mechanisms rather than creating another Executive, event bus, evidence store or autonomous agent hierarchy.
3. Create a **focused new draft PR/branch** for this bounded capability only if a separate branch is safe; do not alter/overwrite active PR #13 or other parallel work. If a shared contract must change, coordinate through additive, backward-compatible adapters and document the integration dependency. Do not merge/rebase unfinished PRs without explicit authorization.
4. Preserve all original experimental evidence, logs, policy state, confidence values, hardware gating, qualified actuator restrictions and established deployments. No unsolicited hardware motion, flashing, live policy deployment or destructive migrations.
5. Write a short implementation plan and acceptance matrix based on what is actually present. Then **implement** the eligible software; this is not an architecture-only research mission.

## 1. Core behavioral contract

The initiating decision must originate in **Charlie's own Executive and evidence systems**. Do not simulate autonomy by running a canned script that randomly poses questions. Support an initial bounded set of *information needs* (not a library of complete sentences): e.g. conflicting classifications, unknown identity, uncertain result interpretation, contradictory evidence, ambiguous user preference or evaluation goal, and unanswered questions about an observable event. Explicitly distinguish information requests from movement permissions or commands.

A legitimate question must carry: stable ID; originating ability/subsystem; observation/evidence references (and image preview where authorized); candidate interpretations or unresolved proposition; evidence confidence and history when available; why this information matters to a pending decision/learning problem; expected response schema; timestamp; urgency and deferrability; provenance; status and expiration/cancellation policy; and deduplication/cooldown metadata. Do not invent evidence, confidence or knowledge gaps.

Choose whether to ask through bounded, testable policy criteria: unresolved uncertainty of sufficient consequence; alternatives to asking (additional observation or inference); estimated value of information; user interruption budget; recent duplicate questions; outstanding queue; age/staleness of evidence; and Executive activity priorities. Favor deferred asynchronous collection rather than interruptive notifications. The first version can use transparent heuristics; avoid claiming generalized curiosity or arbitrary natural-language understanding where it is not implemented.

The question generator should **assemble grounded questions from typed structured requests**, e.g. `identify_entity` plus the tracked-frame evidence and candidate labels. It is acceptable to have small response templates; it is not acceptable to claim they are open-ended LLM composition. Support expandable question types so future capabilities can participate without hard-coded cross-agent calls.

## 2. First-class human interaction gateway

Build an application-facing **Human Interaction Gateway** with typed API/domain events or the closest suitable existing integration. The Executive submits information needs; a renderer presents them; an answer processor validates and routes answers to the original consumer as **new evidence**, not directly as changed motor policy, retrained weights, authoritative truth, or automatic permission to act.

Provide an asynchronous, persisted question lifecycle, including queued/pending, answered, dismissed/unknown, expired, superseded and failed/retryable states; preserve restart/reconnect correctness, idempotency, explicit ownership, origin references and auditability. Avoid silently losing questions or applying the same answer twice. Define policy for unanswered or contradictory human answers and allow Charlie to continue other activities while waiting. Human answers are source-attributed, fallible observations; allow uncertainty and 'I don't know'.

Add a small responsive web interface, usable from an iPhone and a computer on Charlie's approved network, showing question, context, evidence/image if available, choices, optional free-text explanation, status, and history. Include optional priority filters and a low-noise backlog view. An operator should be able to answer **later**, without real-time connectivity. Use an existing web app/service and security model if practical; otherwise implement a minimal independently contained service with bounded queue, durable storage, validation and clear run/stop instructions. Avoid exposing internal services to the public Internet by default; require suitable authentication/authorization for any non-local access, CSRF protection where applicable, safe input handling and secrets hygiene. Do not invent a public URL or promise remote connectivity that has not been established.

The initial question types should not depend on an LLM. Design a **future optional language adapter** so an LLM could help *phrase* or interpret questions under explicit schema and provenance constraints later. No model can be permitted to grant actuator authority, fabricate observations or silently rewrite memory. Do not add speech features in this PR.

## 3. Integrations and demonstrations

### A. Animal classification disagreement (priority acceptance example)
Connect to Charlie's existing pet/animal tracking evidence if contracts permit. Where the same tracked animal receives conflicting labels (e.g., cat versus dog) and the Executive determines asking is worthwhile, it should generate one deduplicated question with appropriate associated frame/tracking evidence. On human reply, store a provenance-linked label/answer and make it available to the existing evidence review/learning pipeline. Do not immediately retrain the live model or authorize ELEGOO movement. Make sure ambiguous identity, tracker ID churn and stale frames are handled defensively.

### B. Robotron feedback / ambiguous objective (second example)
Support an information request grounded in gameplay evidence, such as an ambiguity in the meaning of a score/terminal outcome or a conflict between explicitly recorded evaluation metrics. An answer should contribute attributed evidence or an optional proposed human preference for subsequent Executive review, not change the live game policy automatically. Use authentic available evidence or deterministic synthetic fixtures; do not claim an unobserved Robotron game was played. Do **not** couple this mission to building a Robotron visual world model—that is a separate subsequent mission.

### C. General API contract
Show that both existing abilities can publish information needs using a shared interface without special-case UI code for each. Demonstrate an unanswered queue surviving a process restart and answers being consumed by the correct requester afterward. Preserve one individual Charlie identity, one authoritative Executive, and the shared learning/evidence architecture.

## 4. Tests and independent validation

- Focused unit tests: information-need detection boundaries, grounded rendering, correct schema, deduplication and cooldown, value-of-information gate, unanswered fallbacks, expiration/supersession, state transitions and conflicting answer handling.
- Contract/integration tests: Executive request → persistent queue → UI/API → delayed operator answer → source-attributed evidence → original learning consumer; cases across cat/dog and Robotron; identity and provenance; restarts and repeated submission.
- Security tests: unauthorized answer attempts, invalid payloads, forged evidence refs, replay/idempotency, cross-site issues where applicable, oversized submissions, dangerous HTML/script content and route restrictions.
- Regression tests of existing Executive/PPAL, shared sensory subscriptions, camera ownership, pet following and Robotron behavior; ensure no actuator commands, unsafe deployments or changes to motor authorization.
- Run independent CI and eligible native/headless tests; report command outputs, precise pass/skip counts, and failures. Do not report hardware or browser usability as verified unless exercised with evidence. If Pi access exists, test persistence and local page access on the actual host, with no motor movement. Include accessible manual iPhone browser checklist when human testing remains necessary.
- Store and publish non-sensitive evidence, screenshots/examples, tests and a compact acceptance report. Do not export personal or sensitive camera footage; use synthetic fixtures for public repository tests and retain any authentic evidence within approved privacy boundaries.

## 5. Delivery and completion criteria

Publish independently tested, coherent increments to the focused **draft PR** as implementation proceeds. Provide a short README/operator runbook covering service lifecycle, local URL discovery, access configuration, troubleshooting, question schema, answer semantics, and safe recovery. Add contract and architecture documentation locating this as an **interface to the existing Executive**, not a new independent brain. Identify dependencies on PR #13 and do not prematurely merge cross-branch work.

**Software acceptance requires all of the following:** (1) a real Executive-derived uncertainty can yield a nonduplicative structured question; (2) it persists unanswered over a restart; (3) the operator can view it and answer asynchronously in a functional browser UI; (4) the answer is validated and recorded with immutable provenance as evidence; (5) the originating learning workflow can consume the result without automatically changing models or authorizing motors; (6) both pet-observation and Robotron examples pass end-to-end using available authentic or explicit deterministic fixtures; (7) regression and security checks pass; and (8) outstanding native/hardware validation is stated precisely.

Do not declare success on architecture docs, mockups, or unit tests alone. If a true live Executive trigger cannot be integrated because upstream PRs are incomplete, implement all eligible interfaces, tests, UI and persisted pipeline; explicitly mark that integration acceptance **pending**, with exact code-level blocker and next action. Keep the PR draft until actual integration acceptance is demonstrated. Do not ask for extra product requirements unless absolutely blocked; use minimal conservative defaults and document them. Do not expand this mission into speech, general LLM autonomy, changing Robotron perception, replacing learning algorithms, or qualifying mobile movement.

## Operator-facing final report

Report the branch/PR and published commits; actual implemented behavior versus mocks; screenshots or location of question-page UI; tests and CI counts; security and privacy protections; per-acceptance-item PASS/PENDING; hardware/phone checks needing operator action; and any impact on existing branches. Explicitly explain **how Charlie decides there is a question to ask** and which parts are heuristics/templates rather than LLM reasoning.
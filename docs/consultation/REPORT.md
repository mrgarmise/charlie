# Onboard consultant implementation and qualification boundary

This is a software implementation with **native inference acceptance pending**.
Normal `main.py --llm-consultation` is an explicit **shadow-only** opt-in; it queues
evidence-backed observation questions without creating a provider or sending any
request. Default startup does not create a consultation service. Real provider
calls are available independently for bounded tests and the native benchmark.
Enabling them in normal robot operation requires the still-missing Stage A native
resource/interference qualification and a separately reviewed enabling change.

The exact development base was independently checked through GitHub PR #26:
`3d8591d8126bf9bc8c49bdddfb80fd7ea5487b98`, tree
`b2eea13b0a795819f5c90d319cd33ee6bb793ef8`. It continues the mission's PR #23
`3b364f9b3eca8ae3348fb5f9eb4eaeb315f32b27`. Local Git objects matched this tree;
Git fetch failed first on SSH system-config permissions, then DNS with an
isolated SSH configuration. GitHub's connector supplied verified head metadata
and publication. Existing PRs, the checkpoint ledger and the separate #25 font
work remain unchanged. This mission uses only new draft **PR #27**.

## Implementation and safety review

- `learning/consultation.py`: typed text-provider protocol, local Ollama provider,
  deterministic test provider and explicit optional private TLS remote provider.
  Literal IPs avoid DNS rebinding; local uses loopback only. Remote requires an
  exact origin allowlist, system-trusted TLS certificate and environment-token
  authentication. Redirects/proxy environment/automatic retries/tools/images are
  absent. No OpenAI API or paid inference implementation exists.
- Requests use non-thinking text, 1024-byte question bound, 1024–2048 context,
  up to 192 generated tokens (160 default), one CPU thread (at most two), zero
  keep-alive (five seconds allowed only for explicit benchmark comparison).
  A spawned HTTP worker bounds full wall time even with a slow-drip server;
  shutdown/thermal/resource checks run every 50 ms. Local and remote attempts
  share a 30-second default total deadline. Server CPU/RSS need the separate
  operator cgroup in OPERATOR.md; client process limits cannot bound Ollama RSS.
- The **same** LearningExecutive checks existing local evaluator knowledge by
  evidence identity before requesting advice. Retained promoted human corrections
  defer consultation. Prior consultation answers are reused by persistent dedup;
  the human gateway remains independent and an authenticated answer before
  submission suppresses model advice. No new memory backend or journal exists.
- Admission requires independently committed observation records, fresh original
  UTC commitment (five minutes), authentic provenance and a recognized uncertainty.
  Mobile observations additionally require the existing acquisition producer,
  an authentic frame and a stable observed track. Score proposals without explicit
  authentic provenance remain ineligible: this PR does not fabricate missing
  qualification. Synthetic/demo flags are rejected. No model can create needs.
- Only a general species/score observation-method question leaves the process.
  No raw frame, private notes, individual name, label, evidence payload, notebook
  contents or credentials enter the prompt. Evidence references remain local.
  Four questions/day and four pending requests are default limits (maximum eight),
  persistent subject dedup and 24-hour cooldown bound interruptions. One request
  is processed per turn, with a 300-second circuit hold after failure. No retry.
- Queue/submission/result/rejection events are append-only in the existing
  EvidenceJournal, retaining source IDs, UTC time, request/response digests,
  provider/model identity, model digest/quantization/server-version metadata,
  text, latency/token metrics, uncertainty disclaimer and follow-up. A crashed
  in-flight submission becomes deferred on restart, never automatically resent.
  Incorrect/contradictory/nonsensical text stays **unverified**. Later independent
  evidence can reject it without changing original evidence or the answer.
  There is deliberately no model-based verification or promotion operation.
- `learning/lifecycle.py`, `memory/learning_projects.py`, normal and mobile
  entrypoints share one Executive/journal and the existing resource/interruption
  guard. No camera/serial/actuator/firmware path changes. Other work retains
  priority. The general resource guard is reused; the independent benchmark also
  refuses system memory/swap/load pressure and requires thermal telemetry.
- Existing authenticated dashboard adds read-only GET `/api/discoveries` and
  `/discoveries`, reading the Executive's atomic status file. The HTML escapes
  answer text, labels it unverified and grants no action. These routes use the
  existing bearer token/Host/Origin restrictions; POST is absent. They start no
  service themselves. For inspection through an existing tunnel, use an HTTP
  client with `Authorization: Bearer …`; no token appears in the URL.

## Validation and provenance

Published increments:

1. `9a79021389e70dbcd1a5ebe777d73b68f3d0d8b9`: providers, records, native
   runbook and independent CI. Local **34 passed / 4 skipped** (socket denial).
2. `d0d3bde241ce78ff01081a1398c808ff378c06fa`: normal Executive shadow
   integration and authenticated status routes. Local focused **47 passed /
   5 skipped**; broader integration **65 passed / 4 skipped** before the added
   dashboard HTTP check.
3. `867c8b7c43ced0ab69f3928896cc09826e79f9a6`: local retained-knowledge
   check and all eight combinations of human/model/consultation startup options.
   Local integration **70 passed / 5 skipped**, conformance **131 passed**.

Final CI results and restricted-host broad failures are recorded below when
complete; no local socket-denial skip is evidence of a working native server.
Private raw logs/JUnit/preflight live in
`/home/five/charlie-consultation-evidence-20261101/`.

Reproduce from the isolated checkout:

```sh
python -m pytest tests/test_consultation.py tests/test_consultation_http.py -q
python -m pytest tests/test_consultation.py tests/test_consultation_http.py tests/test_normal_multi_ability.py tests/test_normal_human_questions.py tests/test_objective_a_normal_runtime.py -q
python tools/check_unified_contracts.py
python -m pytest tests -q --junitxml=consultation-full.xml
python -m tools.consultation_probe --output NEW_PRIVATE_PREFLIGHT_DIRECTORY
```

No hardware is opened by those commands. Tests use fixture evidence and fake
model answers, never native qualification. Real loopback tests run on independent
CI; on this restricted host they explicitly skip after socket creation denial.
The full host suite retains existing socket failures and the previously documented
calibration-completion failure; nothing was xfailed or removed to obtain a pass.

## Native performance report

| Measurement | Evidence / status |
|---|---|
| Host | Pi ARM64, Debian 13.7, 8,255,824 KiB total memory |
| Read-only preflight | 4,941,136 KiB available, zero swap used, ~802 GiB disk free |
| Thermal / fan | Initial sample ~50 C / 3188 RPM; saved preflight 57.3 C / 3244 RPM |
| Throttling / installed live revision | UNKNOWN: `/dev/vcio_gencmd` and systemd inaccessible |
| Model release / quantization / model digest | PENDING NATIVE; no Ollama executable or model installed here |
| Cold/warm latency, tokens/sec, answer quality | PENDING NATIVE; no real model output claimed |
| Peak model RSS / cooling under load | PENDING NATIVE; idle RPM does not prove load cooling |
| Normal stationary sensing interference | PENDING NATIVE; camera/Hailo/serial nodes unavailable |
| Mint/Pi speed ratio | Not measured; no ratio or Mint comparison claimed |

[OPERATOR.md](OPERATOR.md) supplies installation, cgroup, loopback-only service,
18-question cold/warm benchmark, measured-baseline comparison, stop thresholds,
finite native acceptance checklist and rollback. All native rows remain pending
until actual measurements exist. No movement, service replacement, firmware
flash, model training/promotion, release or deployment authority was exercised.

## Preserved investigation of full-suite failures

Independent first-increment run
https://github.com/mrgarmise/charlie/actions/runs/41331655972 completed **1759 passed,
27 skipped, 2 failed** (413.81 seconds); focused transport and 131 contracts passed.
Both failures were in unchanged
`test_resource_pressure_preserves_work_and_recovers[memory/temperature]`.
The new spawn transport causes Python's standard resource-tracker child to persist
until interpreter exit. The old fixture mocked `resident_bytes()` with a zero-arg
lambda, while production correctly calls `resident_bytes(child_pid)` when a child
exists. This exposed a test-isolation defect, not a need to relax child accounting.

An independently isolated **unchanged PR #26 checkout** seeded only the standard
resource tracker and reproduced **2 failures** in 0.72 seconds. The corrected
fixture injects the complete `owned_resident_bytes()` result, keeping its same
900 MiB refusal / 40 MiB recovery assertions. Production `learning/resources.py`
is unchanged. Seeded tracker + all resource and consultation tests now pass
**60 / 5 loopback skips** locally. The original failed CI log and unchanged-base
JUnit are retained privately; no failure was suppressed or xfailed.

The restricted-host preliminary full run retained **1707 passed, 38 skipped,
36 failed, 7 errors**, 502.38 seconds. Its collection preceded the final additional
review tests; it is not an exact final-head count. The 43 failures/errors reproduce
the base environment pattern: 42 socket-creation denials and one existing normal
calibration-completion failure. Independent final CI is required for the complete
software verdict. Raw full XML/log remain in the evidence directory.

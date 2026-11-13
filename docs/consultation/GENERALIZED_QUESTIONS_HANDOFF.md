# Generalized questions and meditation consultation handoff

Development only. Draft PR: https://github.com/mrgarmise/charlie/pull/36,
branch `feature/meditation-questions-20261110`, stacked on #33. Mission is the
revision-3 document in #35 at 16a8f2b. No merge, deployment, hardware operation,
model inference, autostart or operational approval changes were performed.

## Source and publication reconciliation

| Local commit | Published commit | Identical tree / meaning |
|---|---|---|
| d3dca9059233b5f054c4f6f9979085b1422f9674 | ee528a25acf0a683582b44f47f8e3584293a1e11 | 72cd9e4eba5939c181ae88d6ed03d5bbc50527c4; exact approved baseline |
| c9f8acf | d828f0e2a03086ae911997ffd4695035f17522f9 | 41d70366ace5eb4bb0f128098ae9f3f69b8ab585; selector |
| 6bad3dc | a92705b90a5685ce9afdba0e5cc76d13e5f1f8a0 | 1e3221d74d09e17495b01846d66c1b3b40d5ef64; coordinator/policy |
| 032a46d | f637d495a6b814449b7a6b9b1cc103fa35c7f757 | 3afe8872d41805d685dcc8deda10d09f6918d8b2; provider boundary hardening |
| bf0c662 | 561614ddd39789c78fb140d4983275a2cd4c7513 | 9b13c4b45d986cc18a9cab3a9e8d6102ac09c838; current catalog and queue bounds |
| b89adae | 5297498b0305e72c091d4f5fe776dc5e4a3f6181 | 414adc49b3cca3dcc807d784f23f33020be2548c; source-alias write protection |
| cf69dc9 | fad7d16b0d6b2ecc202a3891e868e7f764594922 | 796cf4df99a64ef4485af88af2094e717ba2a7ac; evidence-only handoff |
| 53b5b9b | 6e0a67c0005bcc025e2bb735b6edb60a7e07dc72 | ff24ab01a06898adf1a55d80ca730e59b661a1c5; meditation client-budget admission |

GitHub did not have d3dca905 (commit lookup 422). Shell fetch failed DNS, after
working around an existing SSH config ownership error. GitHub connector publication
created new commits, preserving the exact tested trees and all existing branches.
Baseline differs from #33 in four files: the historical adapter, its tests, and
the already approved RP2040 display fixes/tests. None of these changes was invented
or silently omitted. Approved runtime and qualification checkout remain pinned
at d3dca905 and clean; approved.sha still matches.

## Per-phase status

- A implemented and source-reconciled: QUESTION_SELECTION_ARCHITECTURE.md and
  generalized-evidence/README.md record source/legacy reconciliation.
- B implemented and software tested: typed canonical Reflection investigations,
  immutable read-only discovery/fingerprints, project/human/model answer vetoes,
  deterministic ranking/context, bounded separate queue and CLI. The existing
  300-second current-authentic observation path is preserved in ConsultationService
  and exposed in the catalog by a read-only canonical-queue adapter.
  Historical proposals never become fake current observations. Unsupported schemas
  fail closed; additional producer adapters require explicit reviewed mapping.
- C implemented and fake-provider tested: selectable IDs, existing OperationalProvider,
  runtime exclusion, durable attempt/answer states, truthful admission/submission,
  uncertain-completion latch, answer and pending-evaluation views. The original
  tools/historical_question_qualification.py and operational wrapper are unchanged.
  Generalized manual native acceptance remains pending.
- D coordinator and standing-policy enforcer/protocol implemented and simulated;
  actual Executive reflect_experience checkpoint hook tested. NativeSlotAuthority
  is a precise denying native-guard stub with external dependencies documented in
  GENERALIZED_QUESTIONS_NATIVE_ACCEPTANCE.md. No installed isolated scheduler/issuer
  exists in this development work. Native integration, finite service/prewarm/cutoff
  and authority isolation require separate Pi implementation/qualification. No
  unattended native acceptance is claimed. Default-off source and approved runtime
  prevent accidental activation.
- E focused/source/contract testing implemented; independent GitHub CI and full
  local suite results are recorded in generalized-evidence/VALIDATION.md. Native
  qualification and operational promotion are separate, pending activities.

## Real evidence outcomes

`generalized-evidence/authentic-selection.json` contains original committed times,
source journal fingerprint, question/source IDs, original scopes, prompt digests
and selection reasons for 27 authentic preserved investigations. All 27 were
paused/blocked in the current project ledger and refused. The original journal
hash was unchanged. At least three distinct genuine topics are represented:

- 5524edc23f1affbda1d8a65253b7bd1000e52df6c66661f6d86bf4609a745643:
  temporal estimation; paused and also has a known historical native answer.
- ae34a68462dae3dd17eca801be9a293841e7a3101d5ec1d924f41e7e70c06dd5:
  visual generalization; blocked.
- 52f7dfdc55ed96c6930760a6e33ca076f5e84c780038a3fc23c6d9268c8c2009:
  preserved observation availability; paused.

The archived October journal alone is insufficient: include authoritative project
status and all known human/model answer notebooks. Canonical content integrity
is not a signed statement of real-world truth. Operator source allowlisting and
status/answer completeness remain prerequisites. No hold was cleared, no authentic
question was relabeled eligible, and no fake lineage was published as authentic.

## Operator CLI (source/test work only until native trial is separately qualified)

Run from the isolated reviewed checkout. Explicit source lists avoid private home
scanning. Use a NEW private decision notebook, never an original source path.

```sh
python -m tools.questions list --source /absolute/project-ledger.sqlite3
python -m tools.questions inspect --source /absolute/project-ledger.sqlite3 --id CANDIDATE_ID
python -m tools.questions explain --source /absolute/project-ledger.sqlite3 --id CANDIDATE_ID
python -m tools.questions queue --source /absolute/project-ledger.sqlite3 --notebook /new/private/decisions.sqlite3
python -m tools.questions select --notebook /new/private/decisions.sqlite3 --id CANDIDATE_ID --reason 'offline evidence review'
python -m tools.questions defer --notebook /new/private/decisions.sqlite3 --id CANDIDATE_ID --reason 'wait for qualified meditation'
python -m tools.questions skip --notebook /new/private/decisions.sqlite3 --id CANDIDATE_ID --reason 'operator refusal'
python -m tools.questions show-answer --notebook /new/private/decisions.sqlite3 --id CANDIDATE_ID
python -m tools.questions pending-evaluation --notebook /new/private/decisions.sqlite3
```

Only after an independent one-off safe-idle interval/service and private Admission
are issued for the exact clean candidate revision, the generalized manual command
is:

```sh
python -m tools.questions consult --source /absolute/project-ledger.sqlite3 --source /absolute/known-answers.sqlite3 --notebook /new/private/decisions.sqlite3 --id CANDIDATE_ID --approval /private/one-off-approval.json --runtime-lock /home/five/charlie-ops/runtime.lock
```

This command consumes existing external approval; it cannot approve a trial,
start/prewarm a service, waive Admission or choose a different model. No private
approval contents are printed. It holds runtime.lock through the independently
qualified service cutoff. The unchanged original manual utility remains available.

## Existing-lifecycle integration API and independent policy

After separate backend qualification, the trusted application composition root
may attach a coordinator to its **existing** DevelopmentLifecycle object:

```python
policy = StandingPolicy(enabled=True)  # only independent, accepted configuration
slots = StandingSlotAuthority(policy, independently_owned_backend)
queue = QuestionQueue(separate_decision_journal)
life.meditation_consultations = MeditationConsultations(
    queue, explicit_permitted_journals, slots, enabled=True,
    daily_limit=policy.max_daily, cooldown=policy.cooldown_seconds,
    slot_seconds=policy.max_slot_seconds)
```

Imports are from learning.question_selection, learning.meditation_consultation
and learning.standing_consultation_policy. This example is not executable native
authorization: independently_owned_backend is intentionally not provided by the
Executive. Do not substitute a test Authority for it. NativeSlotAuthority denies
if no authority is supplied. A normal worker has no coordinator by default;
`--llm-consultation` keeps its pre-existing semantics, not standing authorization.

The normal 10-second thinking slice cannot admit a native client requiring
35 seconds of headroom: it defers before service preparation. A separately
qualified meditation profile can use the existing `--learning-budget 60` (or
`budget_seconds=60` at composition). The remaining monotonic client budget is
checked again after source review and service preparation; insufficient headroom
defers without inference. Client and independent service-cutoff budgets remain
separate, and both must fit the qualified primary-free interval.

Queue maintenance runs in bounded offline turns; source hashing/verification has
cooperative primary-work checks. Consultation runs at a saved meditation iteration
boundary, after Executive commission. At most one attempt/commission and external
slot, <=4/day, cooling and an external durable authority budget apply. Calls are
only via OperationalProvider. The native backend must hold exclusion across all
startup/inference/unload/cutoff and handle caller death independently.

## Durable states, failure recovery and limitations

Candidate records retain source identity, original timestamp, scope, score/reasons
and prompt/context version/digest. State events carry candidate ID, timestamp,
attempt ID, commission/slot identity and bounded reason. States are queued,
operator-selected, deferred-to-next-eligible-meditation, rejected,
admission-pending, submitted/unknown (only after provider admission), answer-durable,
provider-cleanup-confirmed, awaiting-evaluation and uncertain-completion.

An interrupted/failed attempt after admission-pending is conservatively latched,
including admission refusal; it is never automatically retried. A crash in any
possible-dispatch or answer/cleanup intermediate state globally blocks new model
work in that notebook. Source changes reject stale queued work; invalid/missing
sources or truncated discovery prohibit execution. The provider's existing
completion-unknown.json latch is never deleted or automatically cleared. Durable
answer write precedes retained(); cleanup uncertainty is not success. CLI skip/
defer/select cannot reactivate terminal or uncertain attempts.

Answers are bounded unverified hypotheses with exact source/question/prompt/model/
service provenance. No command, training, policy promotion or physical authority
consumer exists. Prompt JSON isolation does not guarantee semantic immunity to
injection; lack of execution authority is the enforcement boundary. Qwen may give
off-domain advice and needs independent evaluation. Human answers take precedence
where schema provides exact source links; unmapped schemas are not auto-selected.

Disable by revoking the **independent** policy and setting enabled=False/detaching
the development coordinator after service quiescence. Do not clear uncertain
markers to resume. Preserve notebook/receipt, verify old cgroup empty and review
any later clearance independently. No automatic clearance command is supplied.

The approved camera/Hailo/Pico labels, motion denial, launcher and 90-second limit
were not changed. This is source/hash evidence, not a claim of a new Pi trial.
Manual future promotion/rollback prerequisites and exact network/power conditions
are in GENERALIZED_QUESTIONS_NATIVE_ACCEPTANCE.md. They were not executed here.

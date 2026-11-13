# Charlie's asynchronous human questions

This draft adds an **opt-in interface to LearningExecutive**, not a second brain.
It uses the existing EvidenceJournal for queue, audit, answers and requester review
inboxes. It does not alter GPIO, serial protocols, camera ownership, deployed
software, firmware, motor authorization, PPAL models or historical evidence.

## Start, access and stop

Use a dedicated reviewed checkout and the Executive's existing journal, after
backup. Do not replace any deployed checkout or open personal evidence to a
public service. Requires Python 3.10+ and the repository import path; the service
itself uses only the standard library. Run from the repository root:

```bash
read -rs -p 'Question access secret (at least 32 characters): ' CHARLIE_QUESTIONS_TOKEN
export CHARLIE_QUESTIONS_TOKEN
python -m ui.human_questions --journal /approved/notebook/learning-evidence.sqlite3 --operator alex
```

Open http://127.0.0.1:8787/ on that host. Browser username is `operator`, password
is the secret. Operator attribution is the configured `--operator`; clients
cannot impersonate another source in the form. Keep the token private. Ctrl-C
stops the service and closes the notebook without deleting questions. Restart
with the same journal to recover. A lost response can safely be retried with the
same request ID; a changed replay is rejected. Rotate the token by stopping and
restarting. Previously opened forms then need reloading (CSRF token changes).

The listener **cannot bind non-loopback**. For a computer or iPhone on an approved
network, use an already-approved authenticated SSH tunnel forwarding local port
8787 to Charlie's 127.0.0.1:8787. Open the local loopback address in the browser.
Keep the client tunnel port private. Do not publish or port-forward the service
onto the Internet. Basic auth is acceptable here only because traffic stays on
loopback or inside SSH; no plaintext LAN exposure is provided. A native phone SSH
client/tunnel, credentials and Pi reachability have not been established in this
mission. No public URL exists. An authenticated TLS reverse-proxy integration is
future work and must preserve Host, Origin and access controls.

## Executive integration contract

An existing application-owned `LearningExecutive` can invoke:

```python
from memory.human_interaction import HumanInteractionGateway
questions = HumanInteractionGateway(executive.journal)
result = executive.consider_human_question(
    questions, observation_id,
    reason='Resolve species disagreement before future evidence interpretation',
    consequence=1.0, priority=1, alternative_available=False)
reviews = executive.receive_human_answers(questions, 'pet_observe')
```

`observation_id` must exist in this journal. The example is an API usage pattern,
not a command to run against live hardware. `receive_human_answers` atomically
creates requester-owned `human_answer_review` observations and acknowledgments.
Repeated receipt returns no duplicate. The originating learning adapter can read
these through `journal.category_records('observation', 'human_answer_review')`.
They remain **pending independent review**. No semantic truth, calibrated human
confidence, score certificate, model update or actuator permission is inferred.
If an external consumer uses `results`/`acknowledge` instead, delivery is at least
once; it must deduplicate by immutable answer ID before external side effects.

Two bounded detectors are implemented: PR #13 `mobile_perception` evidence with
a confirmed, unambiguous, observed session track and conflicting cat/dog support;
and existing `score_review_proposal` with reported confidence below .75. Tracker
ID churn never copies a prior answer to another track. Species confidence and
support remain the detector's uncalibrated values, not individual pet identity.
Robotron replies interpret the proposal only; the existing ScoreObserver digit
annotation, independent attestation, partition and candidate qualification
requirements are untouched. A game or real cat is never claimed by a fixture.

The policy asks only when uncertainty × declared decision consequence is at
least .25, priority is at least 1 and no further-observation/inference alternative
is available. It limits pending questions to 32, creation to 8 per rolling day,
and duplicate subjects to a one-hour cooldown (also deduplicated while pending).
Evidence must have a fresh UTC journal commitment (<=300 seconds); source frame
age is checked within the recorded tracker clock. Consequence, activity priority
and alternatives are explicit inputs from the owning Executive caller, not
learned estimates. Questions are always deferrable. No answer means continue
other eligible work and retain uncertainty. Default expiry is one day.

Schema: stable content ID, owner, typed kind, episode/session-bound subject,
proposition, candidates, source IDs, reason, source confidence, UTC creation,
priority/deferrability, response schema, dedup key, cooldown and expiry. Additional
question types can extend `TYPES` and a typed evidence adapter; a future language
adapter may only propose phrasing/structured answers that pass these same
validators. It has no memory-writing or authorization API. Wording currently
uses fixed templates and recorded structured context, with no LLM.

States: pending; failed (retryable); answered; unknown; dismissed; expired;
superseded. Trusted API callers use `transition` with a rationale; the browser
supports choosing a candidate or "I don't know" with an optional explanation.
Expiration is a deterministic projection of the immutable recorded deadline.
A contradiction after an answer is rejected; preserve the old answer and open a
new evidence-grounded, explicitly superseding question after review. Never edit
old evidence or overwrite a human's observation. Failure does not drop a queue
item. Recover SQLite busy/503 with the same request ID and inspect the backlog.

## Security and privacy

All views and writes require a secret, exact loopback Host, no public listener.
Writes require a CSRF token and reject cross-site Origin/Fetch metadata. Payloads
are bounded; only five form fields and known candidates are accepted. There is
no question-submission endpoint, evidence-upload endpoint, arbitrary file route,
JavaScript or camera acquisition. HTML is escaped and CSP blocks script/frames.
Secrets and answers are not request-logged. Images are deliberately not served:
source IDs/history are shown; approval-bound pixel serving is still PENDING.
Do not copy personal camera pixels into public fixtures. SQLite access is local
trusted-operator access; repository Python callers are not an untrusted sandbox.
Keep journal files and backups restricted by normal filesystem permissions.

## Pending integration and operator checks

This branch does not schedule new questions in the normal application yet.
Master lacks PR #13's `learning.mobile.MobileEvidenceAdapter`, `PetTracker` and
shared observation ownership. A separate scratch compatibility checkout tests
the exact contracts without modifying PR #13. After reconciliation, an explicit
opt-in in `MobileEvidenceAdapter.opportunities(observation_id)` can call the
existing Executive, with actual pending-decision consequence/priority/alternatives.
Its current per-track opportunity dedup should not suppress later uncertainty
updates. Scope the journal and session provenance before wiring that call.
Robotron's `ScoreObserver.review_proposal` records in source episode journals;
normal DevelopmentLifecycle uses a consolidated notebook. A reviewed adapter
must consolidate the immutable source reference using the existing consolidation
mechanism, preserving episode lineage and freshness. Do not copy IDs across
journals without their sources. No normal live producer/consumer attachment is
claimed; callable API and deterministic end-to-end tests are implemented.

Manual Pi/iPhone acceptance (no movement):

1. Back up the approved journal; start only the question service in the reviewed
   checkout. Confirm loopback listener and absence of camera/serial opens.
2. Establish an approved SSH tunnel. Check unauthorized access is denied.
3. On desktop and physical iPhone, inspect context/history, choose "I don't know",
   and answer a different synthetic question later. Confirm readable layout.
4. Stop/restart with a question unanswered; reconnect and answer it. Confirm one
   attributed answer and one requester review observation after receipt.
5. Confirm no PPAL model, motor grant, runtime deployment or original evidence
   changes. Record actual host/revision/browser/time and retain non-sensitive
   receipts. Native browser/phone/physical checks remain pending until witnessed.

Tests: `python -m pytest tests/test_human_interaction.py tests/test_human_questions_http.py -q`.
Browser acceptance: install Playwright and Chromium, then set
`CHARLIE_BROWSER_TESTS=1` and include `tests/test_human_questions_browser.py`.
Dedicated CI uploads desktop/mobile-emulation screenshots and JUnit. Emulation
is not proof of physical iPhone Safari usability.

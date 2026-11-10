# Bounded operational consultation candidate

Status: software implementation under independent validation; **native acceptance
pending; merge and deployment blocked**. No approved runtime, approval record,
service, sensor, firmware or actuator has been changed by this continuation.

## Implemented boundary

Normal `--llm-consultation` stays shadow-only. The additional
`--llm-consultation-approval PATH` opts into a single local Qwen3 1.7B transport
inside the existing Executive development worker. The Executive still decides
which authentic retained uncertainty merits a generalized question. Results are
immutable unverified hypotheses; no model, physical authority or human conclusion
is promoted. Existing privacy, queue/day limits, resource checks and review paths
remain in place. Original evidence age is rechecked immediately before submission.

Real calls require a private owner-only, boot/source/service-bound, short-lived
operator approval with a hash of an independently reviewed native prerequisite
receipt. Missing, revoked, stale or malformed approval fails closed. Only the
fixed loopback endpoint is used, with a matching service-owned listening socket,
verified sandbox/cgroup limits, exact model digest/context/version, one loaded
model and finite remaining residency. No prewarm, model switch, lease refresh,
remote fallback or service-control operation is implemented in this path.

**Important limitation:** stock Ollama exposes separate `/api/ps` and `/api/chat`
operations. Inspection is not an atomic no-load guarantee: expiry, runner loss or
configuration changes can occur between them. This implementation therefore
requires an independently designated **safe idle window with no active sensing
deadlines**. It refuses ordinary active-sensing approval. It does not pause sensing
or manufacture an idle window. Concurrent time-critical sensing consultation is
not qualified or enabled by this change. Extending to it requires a separately
reviewed server-side resident-only admission guarantee.

Official API references inspected for this decision:
https://docs.ollama.com/api/ps and https://docs.ollama.com/api/chat . The first
reports loaded models and expiry; the second documents inference and keep_alive.
Neither documents an atomic resident-only precondition. This is a conservative
integration inference, not a claim that client polling prevents a server reload.

## Residency, cancellation and recovery

The runtime accepts only a pre-existing 35–120 second resident lease, exact 2048
context, and a safe-idle approval with 35 seconds remaining. It retains the
existing `keep_alive=0`: each completed answer requests immediate unloading,
then checks `/api/ps` is empty. This deliberately avoids extending PR #27's
five-second configuration cap or leaving a model resident between questions.
A new real question requires a separately qualified prewarm/idle window.

A fixed per-user lock under `/run/user/UID/charlie-consultation` prevents requests
from different notebooks overlapping. Before submission, a fsynced marker records
unknown completion without prompt/answer content. It remains across provider
restarts, timeout, cancellation, journal failure or unconfirmed unload. The marker
is cleared only after the parent durably journals the answer and the child
acknowledges cleanup. No automatic retry or marker deletion after failure exists.

A client disconnect does not prove the server stopped generating. Admission
therefore also requires the existing dedicated unit to have a finite runtime
(maximum 120 seconds), a <=5-second stop timeout, control-group kill, SIGKILL
escalation and no restart. Its conservative process-start-based final cutoff must
fall within the approved safe-idle window. This is a **new native prerequisite**;
we have not changed the user's installed unit or verified that it meets it.
Hard memory <=2500 MiB, zero swap, CPU quota <=1 core, PrivateDevices,
NoNewPrivileges and ProtectHome=tmpfs are checked from service/kernel state.

The provider budget is 30 seconds including metadata and inference, plus bounded
local checks/teardown (systemctl <=2s, throttling query <=1s, Git checks <=2s each,
child termination/join <=2s). These run away from acquisition/recognition. Native
latency measurement remains necessary. Existing watchdog/STOP/resource checks are
called during polling. Native temperature must be known and <70 C, MemAvailable
>=3 GiB, no swap use, load <=2, and no throttling flags. Prior stricter guards still
apply. The service lifetime is the backstop if the client dies or server freezes.

The synchronous mobile-observe/pet capability entrypoints reject the new real
flag. Shadow behavior in those modes is unchanged. Normal application object
recognition/monitoring continues to use the existing separate Executive worker;
no acquisition owner or motor path was added.

## Verification ledger

- First added-test run: 28 passed, 4 failed. All four were test setup errors using
  EvidenceJournal as a context manager. Corrected to `contextlib.closing`; no
  production assertions or gates were relaxed. Raw failure log retained.
- Increment 1 focused: **107 passed**, including 55 inherited tests and 52 new
  activation checks; real loopback HTTP in inherited tests and native fakes for
  approval, cgroups, service identity, cancellation and recovery.
- Architecture contracts: **131 passed**.
- Full local and independent CI: pending at this first checkpoint. Subsequent
  exact commit results will be appended, not silently substituted for failures.

Host is x86_64. `/home/five/charlie-runtime` and `/home/five/charlie-ops` are not
mounted. No actual Ollama endpoint, systemd unit, model, thermal or sensing
acceptance was exercised. Existing Pi measurements in the mission are historical
operator evidence, not new verification. Periodic 10–11-second sensing stalls
remain a separate unresolved issue, including the no-model control. No timing
investigation or claim of an LLM fix is part of this change.

See [native acceptance and rollback](OPERATIONAL_ACCEPTANCE.md) and
[promotion reconciliation](PROMOTION_RECONCILIATION.md) before any native work.

## Second local increment

Added startup/worker isolation checks for every human/model review combination,
actual loopback HTTP ready/cold tests for the operational path, and sanitized
status reasons identifying approval, residency, service, submission or cleanup
refusal. No native state is inferred from a passing fixture.

Focused suite: **114 passed**, two Python deprecation warnings from the test-only
fork seam used to propagate native mocks into a worker while a fixture HTTP server
runs. Production always uses spawn; the warnings are retained, not suppressed.

An exploratory broad run completed **1828 passed / 5 failed / 27 skipped** in
419.23s. The five failures are arcade camera/evidence-writer/terminal tests, listed
in `operational-evidence/exploratory-full.txt`. Some later edits occurred while this
run was active, so it is not an exact-final-commit acceptance run. A clean parent
reproduction and independent clean candidate run are being retained separately.

Publication was rejected twice by automatic approval review. After the first
rejection, the exact remote was checked against the mission and the GitHub
connector confirmed mrgarmise/charlie is public with push permissions. The second
review still requires explicit end-user authorization naming the destination and
source/test/documentation payload. No alternative publishing channel was used.
GitHub CI and a draft PR therefore remain blocked pending that approval. Both
implementation increments are preserved as local commits; there is no claim
that they have been published.

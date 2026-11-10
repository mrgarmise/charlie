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
escalation and no restart. Its conservative activation/process-start-based final cutoff must
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

The cutoff check also rejects randomized extra runtime, notification-based timeout
extensions, non-SIGKILL final signals, and abort-mode stop handling. These properties
must be verified; the client does not equate a requested stop with observed quiescence.

## Cutoff hardening increment

Use the later of unit activation and process start for the conservative service
cutoff. Refuse randomized extra runtime, notification-based extensions, a final
signal other than SIGKILL, and abort-mode timeout handling. These checks prevent
an apparently finite setting from admitting a longer-lived server than the
independent idle window. Native observation is still mandatory.

Final focused source validation: **119 passed**, two retained test-only fork
warnings. The five originally failing arcade cases were rerun on a clean detached
`b0c04ad` parent: **4 failed / 1 passed**. Four failures therefore reproduce without
this implementation. The remaining parameterized case varied; it is not claimed
resolved. Relevant arcade/hardware/vision files are byte-identical to the parent.
Independent broad results and final exact revisions follow in the final ledger.

## Final local validation — 2026-11-08

**Software candidate ready for review / native acceptance pending / publication
and GitHub CI awaiting explicit approval / merge and deployment blocked.**

The three implementation commits are:

- `e2fae66b491b17fa12d2d49148e66f06d21df26e`: bounded activation and initial tests.
- `25a81bc6d385c2b678becc0c09039b43d21fea89`: protocol/startup tests and runbooks.
- `cb4879d7501c6506f1b865c7370fa9112c5dd499`: cutoff hardening; final tested code.

A fresh detached checkout of **cb4879d** completed, sequentially:

| Check | Result |
|---|---|
| Consultation tests | **119 passed**, 0 failed, 7.292 seconds; two retained test-only fork deprecation warnings. |
| Shared architecture contracts | **131 passed**, 2.75 seconds. |
| Full suite | **1846 passed, 27 skipped, 0 failures/errors**, 365.926 seconds. |

The complete full JUnit receipt contains 1873 testcase nodes and includes the last
suite (`test_unified_reconciliation`); its counts agree with those above and the
command exited zero. The raw console capture ends at 73%, so it is retained as
partial console output, not represented as the complete receipt. Compressed JUnit,
raw logs, SHA256 values, commands, package versions and counts are retained in
[the final evidence directory](operational-evidence/20261108/results.json).
The checkout was clean before and after testing. The final evidence commit adds
documentation and receipts only; tested implementation files remain identical to cb4879d.

Workspace maintenance removed temporary logs and packages from the earlier
interrupted session. The source commits and committed evidence survived. The
lost temporary full-run outputs are not counted as completed acceptance. The
fresh results above supersede uncertainty about the current software candidate,
without erasing the earlier preserved failures or claiming their timing behavior
is fixed. No unrelated production code or assertion was weakened.

GitHub CI has **not** run for this continuation, and this session has not created
a continuation PR. Publication remains blocked by automatic approval review,
which requires explicit end-user confirmation naming the public destination
`https://github.com/mrgarmise/charlie` and payload (implementation, tests,
documentation and retained software-test logs). Proposed branch:
`feature/operational-consultation-20261104`; proposed draft base:
`feature/onboard-consultation-20261101`. No existing branch is to be overwritten.

After that approval: publish these increments, open the draft continuation PR,
and inspect independent GitHub CI on the exact published commit. Native steps
remain the ordered, separately authorized prerequisite/idle-trial/review sequence
in OPERATIONAL_ACCEPTANCE.md. No native deployment or promotion is requested now.

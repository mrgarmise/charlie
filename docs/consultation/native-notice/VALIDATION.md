# Software evidence and native limits

Host focused command (Python environment `/home/five/Projects/charlie/.venv`):

```
python -m pytest -q tests/test_brain_calibration.py tests/test_native_meditation.py tests/test_meditation_notice.py tests/test_calibration_integration.py tests/test_consultation_activation.py tests/test_meditation_consultation.py tests/test_object_display.py tests/test_question_selection.py tests/test_historical_question_qualification.py -k 'not operational_protocol_over_real_loopback' -p no:cacheprovider --junitxml=/tmp/pr38-isolated-focused.xml
python tools/check_unified_contracts.py
```

Result: 323 passed, 2 skipped, 2 deselected; unified contracts: 131 passed.
Raw [JUnit](evidence/host-focused.xml), [focused output](evidence/host-focused.txt),
[contract output](evidence/host-contracts.txt). The host restricts one peer-credential
probe; the other skip requires optional authentic private-source inputs. Two
existing real-loopback protocol tests are deferred to independent GitHub CI,
which runs without this exclusion. Kernel flock and SCM_RIGHTS transfer tests
run unprivileged; root/systemd/setns operations are mocked and require native
qualification. No software result is a hardware acceptance receipt.

First published notice increment: remote commit
`4648c3ddf6d64a3570c77f25b2b2fb297c0e1763`, exact tree
`4f1ec694eb8b466f3bec6fc5df15d88560b29365` (local equivalent `acf6039`).
Independent [run 42891092193](https://github.com/mrgarmise/charlie/actions/runs/42891092193)
passed 113 focused tests and 131 contracts; full suite reported 1 failure,
1972 passed and 28 skipped. The failure exposed a legacy calibration display
fixture without the new meditation object. The session handler now checks for
its reset method, preserving legacy displays, and focused CI includes calibration.
Both the failure and repair are retained rather than hiding the failed run.

The scheduler increment receives a fresh full-suite run on GitHub. Final run,
commit/tree mapping and artifact references will be appended after completion.

Approved operational preservation checked read-only:

| Asset | SHA-256 |
|---|---|
| approved.sha | `5022c8cf88b0928d9abea764510d53d10ace5cc570447e7650db406b2cb70e30` |
| start-stationary.sh | `3305e83b84874162578d70f0de276c3dde5a80883261782bf0052db5420bd5e2` |
| run-historical-consultation.py | `3a3956e899c20609a25ef6d63964aa80f9ef7894cd1c93955603c5db62c62a75` |
| original learning-project-evidence.sqlite3 | `93fa829a9e87352105d7e4ee0174b4bdfc9b1b85e67430bfbb8192ca20dc72e4` |

The operational checkout is clean at
`d3dca9059233b5f054c4f6f9979085b1422f9674`. No merge, deployment, firmware
flash, service installation/start or unattended enablement was performed.

Scheduler publication: remote `0c7c7e221fd08b45fede918e14d75bb4ac403961`, local
`2d76a08590dfbf8298dbdf06dc7499050a4dfd2c`, identical tree
`7471705829d15e276228ac13a91a5005e543bc48`. The next hardening increment rejects
unknown/nonfinite inventory validity and scheduled duties before reservation.

Final source hardening also checks legacy display cancellation methods, performs
physical STOP before display housekeeping in the firmware safety exception, and
tests namespace PID binding plus privilege drop before HTTP. These namespace
tests inject syscalls; they do not execute privileged operations.

Deadline hardening publication: remote `47c92204da6be57cee0559c27c16e8d320bf13d6`,
local `40568edd544c8fc6082d0260916bf3ddea3662f8`, identical tree
`d55f15f20d0896d81553d37fe5fe661300c177be`.

## Independent regression investigation

The scheduler increment full suite passed twice at identical tree
`7471705829d15e276228ac13a91a5005e543bc48`: mobile run 43128533044 and
consultation run 43128533062 each reported 2019 passed / 28 skipped. The native
run 43128533085 instead reported one normal-main calibration timeout, with
2018 passed / 28 skipped. This was not dismissed or excluded: an isolated run
on the unchanged PR #36 baseline reproduced it, as did the candidate.
Raw baseline and candidate failures are retained in evidence. The application
fixture had allowed simulated runs to use the shared default neck-state path,
where a safety latch from another simulated campaign could suppress calibration.
The autouse physical-I/O guard now assigns a fresh neck-state path per test.
It never deletes/clears an existing real latch, and real fail-closed behavior is
unchanged. Including all brain/calibration tests now passes 323 host focused
checks. CI focused coverage includes this regression and the full suite stays
unfiltered.

First final-source browser attempt 43129233142 also timed out reacquiring control
in the existing mobile viewport test (35 passed, one failure). Earlier browser
runs passed. Its raw failure is preserved; subsequent exact-head validation is
recorded below rather than silently discarding it.

Pre-isolation source publication: remote
`ce08257746b6c78f1de5a5594c7eefa7bd6988f8`, local
`3889249c4143bef68ccc43677e4b20e681e991c8`, identical tree
`96973dff763bd72cb4e787000bf4f388ee914839`.

## Final source and exact-head checks

Final implementation source, including test-state isolation: remote
`0d58df70f56dd0c4c4dda7e916ba69107bd7c770`, local
`ecb211e44f7369fee27f344cf48871fffee0fa86`, identical tree
`87ff43725135f9886796111f62575e6131940bf7`.
The evidence completion commit only adds documentation/logs/manifests. Its exact
published SHA/tree and final CI conclusions are recorded in the draft PR #38
publication description, avoiding a self-referential commit hash inside a file.
No source after this boundary is excluded from review or testing.

Immediately preceding source `ce082577` independently passed the full suite twice:
2025 passed / 28 skipped, plus 131 contracts. [Consultation run 43129233169](https://github.com/mrgarmise/charlie/actions/runs/43129233169)
retains artifact [13904557736](https://github.com/mrgarmise/charlie/actions/runs/43129233169/artifacts/13904557736),
SHA-256 `0864bc50fbba8350156475ba273ee38f41a58c32e77e3bd520bd9a30b2deeb67`;
[mobile regression run 43129233142](https://github.com/mrgarmise/charlie/actions/runs/43129233142)
retains full-suite artifact [13904916791](https://github.com/mrgarmise/charlie/actions/runs/43129233142/artifacts/13904916791),
SHA-256 `34e8b03ccd63d3f63f4298e25a82de696c122a9e8787cc91b17329280444eeee`.
Its native-focused run passed 309 tests / one optional-source skip, but its full
native job reproduced the shared-state calibration failure. The subsequent
fixture isolation addresses that cause without weakening any production gate.

Post-isolation independent runs (outcomes available through these immutable run
links and final PR checks): [native](https://github.com/mrgarmise/charlie/actions/runs/43130281314),
[consultation](https://github.com/mrgarmise/charlie/actions/runs/43130281356),
[mobile/browser](https://github.com/mrgarmise/charlie/actions/runs/43130281297).
The final evidence-only head also executes the full native workflow; its completed
result must be inspected before reporting completion. Do not infer green status
from these links alone. The final PR description records observed conclusions.
The browser failure's first-attempt artifact remains linked above even if its
retry passes. No tests are removed, marked xfail or automatically retried inside
a test command.

Actual unprivileged `python -m learning.native_meditation.daemon check-config`
refuses with `PermissionError: native issuer requires separate root identity`.
The [raw refusal](evidence/unprivileged-issuer-refusal.txt) confirms that the
ordinary development account does not instantiate a trusted issuer. No native
service or positive privileged operation was attempted. Tests now isolate the
simulated neck-state directory; no real safety latch is deleted for validation.

`evidence/source-manifest.json` records implementation/test/config blob hashes;
`evidence/SHA256SUMS` covers retained evidence. Original source ledgers and
approved runtime assets remain at the preservation hashes above. Native pending
items remain exactly those in the Pi qualification runbook: independently
installed identities/owners, real kernel isolation/cutoff/fault timing, physical
display and firmware acceptance, and an authentic eligible-question trial.

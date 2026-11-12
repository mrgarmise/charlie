# Software evidence and native limits

Host focused command (Python environment `/home/five/Projects/charlie/.venv`):

```
python -m pytest -q tests/test_native_meditation.py tests/test_meditation_notice.py tests/test_calibration_integration.py tests/test_consultation_activation.py tests/test_meditation_consultation.py tests/test_object_display.py tests/test_question_selection.py tests/test_historical_question_qualification.py -k 'not operational_protocol_over_real_loopback' -p no:cacheprovider --junitxml=/tmp/pr38-focused-final.xml
python tools/check_unified_contracts.py
```

Result: 306 passed, 2 skipped, 2 deselected; unified contracts: 131 passed.
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

# Validation ledger (development only)

Final code: local b89adae / published 5297498b0305e72c091d4f5fe776dc5e4a3f6181,
identical tree 414adc49b3cca3dcc807d784f23f33020be2548c.
Catalog increment bf0c662 / 561614dd has identical tree 9b13c4b45d986cc18a9cab3a9e8d6102ac09c838.
Earlier f637d495 / local 032a46d has identical tree 3afe8872d41805d685dcc8deda10d09f6918d8b2.
Logs/JUnit and SHA256 manifest are in host-validation.tar.gz and host/.
No model/service/sensor/hardware operation was performed.

## Host checks

Python: /home/five/Projects/charlie/.venv/bin/python (Python 3.13).
All pytest commands used `-q -p no:cacheprovider` and the named JUnit output.

| Command/tests | Result | Revision qualification |
|---|---|---|
| tests/test_question_selection.py tests/test_meditation_consultation.py tests/test_historical_question_qualification.py | 37 passed, 1 skipped | f637d495 code content, then committed as 032a46d |
| final consultation/generalized/historical tests, excluding the 2 host-forbidden socket tests | 153 passed, 6 skipped, 2 deselected | exact final 561614dd code |
| final explicit authentic source selection test module | 9 passed | exact final 561614dd code |
| CHARLIE_QUESTION_SOURCE=/home/five/.local/share/charlie/development/learning-project-evidence.sqlite3; tests/test_question_selection.py | 5 passed | final pinned code; real private source independently verified read-only |
| tools/check_unified_contracts.py | 131 passed | final code content |
| tests/test_question_selection.py tests/test_meditation_consultation.py tests/test_historical_question_qualification.py tests/test_normal_learning_lifecycle.py tests/test_objective_a_normal_runtime.py tests/test_object_display.py tests/test_camera_sources.py | 167 passed, 1 skipped | earlier development regression sweep; final pinned CI supersedes |
| tests/test_object_display.py tests/test_historical_question_qualification.py | 105 passed | exact approved baseline plus selector-only increment |
| tests/test_consultation* plus then-current generalized/historical tests | 142 passed, 5 skipped, 2 failed | exploratory; both failures are forbidden loopback socket creation |
| tests (full) | 1875 passed, 39 skipped, 38 failed, 7 setup errors | exploratory working tree while implementation continued; NOT final pinned qualification |
| baseline-only test_brain_calibration.py::test_actual_normal_main_runs_calibration_and_resumes_tracking and test_consultation_activation.py::test_operational_protocol_over_real_loopback | 3 failures reproduced | separate clean /tmp/charlie-meditation-baseline at d3dca905 |

The full exploratory failures comprise 37 failures plus 7 setup errors from
`PermissionError: [Errno 1] Operation not permitted` creating loopback sockets, and
one pre-existing simulated normal calibration failure. The calibration failure
was independently reproduced at the unchanged approved baseline. No test was
silently waived or rewritten. The mission's previously reported inherited
calibration failure remains outside this source change; native operation is not
proved by a failing simulation. Initial system-Python contract command failed
because pytest was absent; it was rerun successfully with the project venv.

The final focused suite exercises 500 mixed activity cycles, three distinct
fixture questions/contexts, default off, independent inventory/resource vetoes,
revocation, abrupt reset, global unknown completion, commission/slot replay,
daily/cooling limits, source changes/alias refusal, actual Executive checkpoint
invocation, nested lock/subprocess exclusion, actual OperationalProvider admission
refusal and durable receipt ordering with fake native I/O, deadline expiry and
uncertain cleanup. No timing/deadline result here is native evidence. The private
source test covers multiple authentic topics but correctly refuses held projects;
mock-provider eligibility tests are explicitly fixtures, not invented authentic
measurements. The default skipped test requires the explicit private journal path.

## Independent GitHub validation

Pinned coordinator increment a92705b:
https://github.com/mrgarmise/charlie/actions/runs/42878796091

Provider hardening f637d495:
https://github.com/mrgarmise/charlie/actions/runs/42879617546

Both runners independently passed focused consultation/generalized tests and
131 architecture contracts. Full-suite completion is recorded in the final
publication ledger below. GitHub runs use clean source with normal loopback
permissions; host socket restrictions must not be treated as source regressions.
Native acceptance remains entirely separate.

Coordinator CI 42878796091 completed successfully: 150 focused tests, 131 contracts,
1948 full-suite passes, 27 skips, zero failures/errors. Artifact:
https://github.com/mrgarmise/charlie/actions/runs/42878796091/artifacts/13794535118
ZIP SHA256 ef16787234741a1c0caaf1757950afa4fc0f9739c61278417e84846a95b456e6.
Final catalog CI for 561614dd is recorded in the final publication ledger.

Provider-hardening CI 42879617546 also completed successfully: 156 focused
passes, 1 private-source skip; 131 contracts; 1954 full-suite passes and 28 skips.
Artifact https://github.com/mrgarmise/charlie/actions/runs/42879617546/artifacts/13794995237
ZIP SHA256 4e4299965fd121db8977ef56182f528befa1b83a231f0b2781dc203193afcf35.

Final pinned host consultation/generalized/historical run, with the real source
explicitly supplied and only the two forbidden socket tests deselected:
155 passed, 5 skipped, 2 deselected. The extra skips are host prerequisites, not
rewritten tests. The source-alias negative test proves that a hardlink decision
path is refused before opening any writable notebook; the source hash stays
unchanged. Final exact-code CI and evidence-only publication results are linked
from the draft PR publication ledger; they supersede exploratory host runs.

Final exact-code independent run (5297498b):
https://github.com/mrgarmise/charlie/actions/runs/42881120199
The GitHub run and PR publication ledger provide the final live conclusion.

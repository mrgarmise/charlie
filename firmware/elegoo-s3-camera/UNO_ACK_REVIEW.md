# Owner UNO compatibility review

Baseline: PR #31 commit `74b9cbd69b74f8229adda77d6a44086480f1968f`.
Historical STOP remains **HANDLED — DONE / OK**.
This review used host fakes only. No hardware, UART, flash, deployment, merge,
service activation or motor activation occurred.

## Owner source identity

The owner-provided archive is now available at
`/home/five/charlie-ops/uno-firmware/SmartRobotCarV4.0_V0_20210104.tar.gz`.
Its SHA256 is
`12f9c05c17a54ae1dec25aaedcf1f968551f27c10ab78e25db757884e3d76b48`.
The archive was opened read-only; nothing was extracted over an installed project.
No vendor source was substituted. Availability of this archive does not establish
which bytes are installed on the physical UNO.

Under its doubled `SmartRobotCarV4.0_V0_20210104/` directory:

| Member | Original-byte SHA256 |
|---|---|
| ApplicationFunctionSet_xxx0.cpp | `bbca3edc708fa225292dc820a4b75c9a0200a625eab9a71ee5585d40b3241b64` |
| DeviceDriverSet_xxx0.cpp | `0c1ae9f01d77de41b710bcf797cee88d93833021aba4b7e09fbe0fd7eec0c253` |

`tests/fixtures/owner_uno_provenance.json` binds seven verbatim excerpts to these
members and the archive. Only CRLF normalization was applied. Verify read-only:

```
python firmware/elegoo-s3-camera/tools/verify_owner_uno.py /path/to/SmartRobotCarV4.0_V0_20210104.tar.gz
```

The separately named vendor timer regression remains a historical reference;
the new owner timer and protocol suites execute the supplied modified source.

## Command comparison and corrections

| Command | Owner source behavior | PR31 compatibility result |
|---|---|---|
| N2 | Parser lines1809–1818 selects timed mode, captures time, and emits no immediate ACK. Timer lines1179–1224 checks elapsed **> T**, stops, switches mode, then emits `{H_ok}`. | Existing bounded completion allowance remains appropriate as a software fallback. No increase to N2 T. |
| N21 D1=2 | Lines1497–1524 return `{H_integer}` cm. D1=1 returns `{H_true}` or `{H_false}`. Device driver lines308–328 uses blocking pulseIn with no explicit timeout and caps at150 cm. | Python now accepts only finite integer cm in1–150; zero is unavailable and150 is explicitly marked saturated. It remains obstacle-only data with no target association. |
| N24 | Modified handler lines1901–1912 calls MPU6050_dveGetEulerAngles and emits `{H_yaw}` with two decimals. | Python serializer matches. Non-finite yaw is now rejected. Source support is confirmed; installed capability and transport qualification are separate. |
| N5 D1=1 | Parser lines1837–1844 ACKs immediately. Servo routine lines1323–1329 divides D2 by10; driver lines420–452 clamps its integer step, writes step*10 degrees, calls _delay(500), then detaches. | Legacy pan now reports/sends the representable ten-degree position. Qualified pan rejects nonmultiples of10 before dispatch, preserving the admitted position rather than silently changing it. |
| N1 / N100 | N1 parser emits `{H_ok}` after selecting motor mode; N100 emits bare `{ok}` after replacing the mode. | Existing exact tagged N1 STOP acknowledgement remains required; bare N100 is never N2 completion or physical-stop evidence. Historical STOP stays closed. |

N5 ACK is parser acceptance, **not servo completion**. Its later routine includes
a500ms delay call. The supplied `_delay` calls blocking Arduino `delay(ms / TimeCompensation)`
then resets the watchdog; the header defines TimeCompensation as4 for its altered
Timer0. Thus the source calls Arduino delay(125) for _delay(500), without
servicing the command parser there. Wall-clock timing and the full loop latency
must still be qualified independently. This review does not establish bounded command
execution after a pan, physical STOP latency, or a safe mixed pan/chassis schedule.
The existing executor reports `executed=None` and `physically_observed=None`.
No readiness claim or qualification grant is added by these corrections.

## N2 timing and serial ownership

The original at-T ESP32 N100 could replace timed mode before the UNO's next
strict-after-T iteration, suppressing completion. The existing correction starts
its watchdog after TX completion and uses an independent T+80ms fallback. Only
an exact matching completion at/after T and strictly before fallback retires it
and schedules STOP. Early completion fails closed; expiry closes before processing
late replies. Heartbeats, wrong IDs, bare replies and fragments cannot extend it.
Explicit STOP, disconnect and100ms TX stall retain independent stopping paths.
Pi reserves the existing TX, completion/fallback and STOP serialization horizon
under its wire lock. The80ms allowance is an engineering budget, not a measured
upper bound on the UNO loop; blocking acquisition/servo work may exceed it.
UART enqueue and any serial ACK never prove physical stopping.

Every parsed JSON command assigns shared CommandSerialNumber at line1793 before
dispatch. N21/N24 do not assign a motion mode, but interleaving queries with N2
can relabel its eventual completion; ultrasonic work can also delay stopping.
The candidate bridge therefore still denies both queries, as pinned by the
production command-gate tests. This review confirms source semantics without
introducing query admission, another socket, serial reader, polling owner, or
motion authority. Any future query admission needs serialized pending requests,
exact H correlation, finite bounded validation, STOP preemption, timing bounds,
and installed source/runtime binding through the existing owners.

## Offline evidence

The new Python regressions are run against both the baseline and correction;
the baseline fails on unsupported pan positions, non-finite yaw, out-of-range cm
and saturation reporting. C++ owner fixtures independently execute N2 boundaries,
mode replacement, stop-before-ACK, N21 replies, N24 formatting, and N5
ACK-before-write, truncation and delay invocation (including the original compensated delay helper). All hardware interfaces are
fakes. Fixture provenance verification checks hashes and source membership.

Repeat focused tests:

```
python -m pytest -q tests/test_owner_uno_compatibility.py tests/test_elegoo_command_auth.py tests/test_elegoo_timed_pulse.py tests/test_elegoo_stop_ack_deadline.py tests/test_face_trial_preparation.py tests/test_unified_actuator_requests.py
ASAN_OPTIONS=detect_leaks=0 python firmware/elegoo-s3-camera/tools/host_tests.py --sanitizers address,undefined --no-sockets
python tools/check_unified_contracts.py
```

LeakSanitizer cannot run under the sandbox tracer; address and undefined-behavior
sanitizers remain enabled. The OS-socket bridge suite is attempted separately;
this sandbox denies socket creation at WiFiServer::begin. The eight remaining
suites include deterministic production MotorBridge timing tests without sockets.
Final local results:126 focused Python tests and134 unified contracts passed;
eight C++ suites passed with ASan+UBSan. The25 new Python cases produce13
failures and12 passes against unchanged74b9cbd, then all pass after correction.
Full socket coverage still needs an environment permitting loopback sockets.
No source/runtime qualification from before this change can be reused.

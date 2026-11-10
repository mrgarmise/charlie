# UNO completion ACK and independent ESP32 fallback

Review baseline: PR31 `7e97365b19e5372603c2dc178fff148fc9fdc11c`.
No flash, deployment, merge, service activation, UART hardware access or motor
activation. Historical stock STOP issue: **HANDLED — DONE / OK**; not reopened.

## Source identity — modified archive comparison pending

The owner explicitly identified a separate modified artifact,
`SmartRobotCarV4.0_V0_20210104.tar.gz`, verified outside this workspace at
`/mnt/data/SmartRobotCarV4.0_V0_20210104.tar.gz`. It has not yet been supplied in
this accessible workspace. It reportedly contains Charlie's N24 yaw handler near
line1901. **Do not substitute a vendor ZIP for this modified source.** Exact
modified-source comparison and N24 evaluation remain pending artifact delivery.

For a clearly separate reference regression only, the vendor ZIP at
`/home/five/SmartRobotCarV4.0_V0_20210104.zip` has SHA256
`7a4ab175a8b36df76c8ab981899bd2c6cc923b5c3ed4bd253cf0481342fa10a9`.
Its nested ApplicationFunctionSet_xxx0.cpp has SHA256
`1ba1c11268f3c320090bf9d7bb56bd86c0403fa71b3f90a91781a895903e61ac`;
DeviceDriverSet_xxx0.cpp has SHA256
`ab6fea4596decbeaa989c9c53d2904333c8e4a454a91957979099fe09598340e`.
Hashes are original archive member bytes, including CRLF. This vendor reference
is neither the owner-modified nor installed UNO source.

## Race and correction

The vendor reference ApplicationFunctionSet_xxx0.cpp lines1791–1818 assign a shared CommandSerialNumber
from every JSON H, select the N2 timed mode and record `_millis()`. N2's immediate
ACK is commented out. Lines1179–1226 check **elapsed > T**, stop locally, switch
to programming mode, then print `{H_ok}`. The sketch calls UART parsing before
the timer routine. N100 (lines1906–1912) replaces that timed mode and emits a bare
`{ok}`. Consequently N100 arriving between T and the next timer iteration can
suppress the tagged completion; a bare STOP reply is not N2 completion evidence.
This is a new candidate timing interaction, not the historical stock STOP issue.

Example: closing N2 brace transmitted at50ms; T100; the old ESP32 watchdog queues
N100 at150ms, parsed about160ms at9600baud; the UNO's next timed iteration161ms
then cannot emit N2 completion. With the correction, UNO stops161ms and its11-byte
ACK can finish around173ms before the230ms fallback. Tests also execute the
vendor timer function verbatim (`tests/fixtures/vendor_uno_timer.inc`, normalized
line endings only), with fake time and motor calls, demonstrating stop-before-ACK
and cancellation by a mode replacement. These schedules are fixtures, not physical
latency measurements.

N2 T remains1–200ms. After TX-complete, the independent fallback has a fixed80ms
completion allowance: up to40ms loop/poll allowance plus the maximum37-byte tagged
ACK at9600baud (38.6ms, rounded within80ms). It does not grow with heartbeats,
partial replies or unrelated traffic. A matching ACK arriving at/after T and
strictly before T+80 requests STOP; early matching ACK fails closed. At T+80,
the bridge closes and queues N100 before processing ACKs, preventing a late ACK
from converting timeout to success. Explicit STOP, disconnect, authentication
failure and100ms TX stall retain their independent stopping paths. STOP priority
and retry on UART congestion remain in the one writer. Another motion command
cannot be admitted during the pending pulse.

The 80ms allowance is an engineering budget, not an established worst-case UNO
loop bound. In this vendor source, ultrasonic `pulseIn` has no explicit timeout;
the UNO loop can exceed this allowance. That yields a failed pulse and independent
STOP request, not a longer wait or a claim of physical expiry. An ESP32 UART STOP
cannot guarantee execution by a blocked/broken UNO. Physical qualification must
bound that behavior independently, under separate authorization.

The Pi reserves the worst-case fallback horizon under its existing wire lock:
T+100ms TX confirmation+80ms completion allowance+N100 serialization+40ms poll
allowance. Completion timeout separately allows TX confirmation, ACK serialization
and40ms scheduling. Requested motor duration is never increased to cover serial
latency. Existing exact tagged completion, explicit tagged N1 STOP and durable
uncertainty behavior remain required. Old source/runtime qualification is invalid.

## N21 ultrasonic and N24 yaw through the existing owner

| Request | Vendor reference source | Candidate access decision |
|---|---|---|
| N21, D1=2 | Lines1497–1527 acquire ultrasonic cm and return `{H_integer}`; no motion-mode assignment. DeviceDriverSet lines306–326 use blocking pulseIn and clamp above150cm. D1=1 returns an obstacle boolean, not cm. | Read-only in actuator intent, but not timing-neutral. Preserve the existing Python read_ultrasonic contract. No candidate UART allowlist expansion in this change. |
| N24 | No case24 exists in the vendor reference. The owner explicitly confirms the separate modified tarball implements this handler. | Existing Python yaw() serializer alone does not establish firmware support. Remains unavailable on this candidate pending comparison with the actual modified source and capability binding. |

Both query serializers currently fail closed on the authenticated candidate;
production C++ tests pin their exclusion. No second socket, serial reader,
telemetry service, endpoint, polling loop or motion authority is introduced.
The existing driver RX thread remains the only TCP reply dispatcher and MotorBridge
the only UART writer. Its existing noncandidate N21 regression remains passing.

Any future read-only admission belongs in these same owners, with a separate
exact N21/N24 query allowlist and authenticated transport admission that grants no
motion qualification. It must serialize one pending request and correlate exact H
responses, reject queries during pulses, and prevent new pulses until a bounded
query completes or faults. Even an unknown N24 replaces shared CommandSerialNumber
before its switch dispatch in the vendor source, so interleaving it can relabel a pending
N2 ACK. Read-only ultrasonic work can also delay local stopping. STOP must preempt
queries; queue/rate/time bounds, finite reply validation, source/runtime binding,
freshness and explicit unavailable/unsupported states need tests before enabling.
No cached yaw/range, ACK or availability flag may create motion authority.

## Offline evidence

Local:108 focused Python auth/pulse/STOP/executor/manual-console checks passed;
134 unified contracts passed. Six production C++/source-fixture suites passed with
ASan+UBSan (`ASAN_OPTIONS=detect_leaks=0`, LeakSanitizer is unavailable under the
local sandbox tracer). Deterministic bridge tests cover delayed/fragmented ACK,
missing/bare/wrong/early/boundary/late ACK, live heartbeats, immediate STOP,
disconnect, TX stall and millis wrap. They use an in-memory client transport and
fake UART; no OS socket or hardware is opened. The normal loopback bridge suite
cannot run in this sandbox (socket creation denied); independent CI runs it.

Repeat: `python firmware/elegoo-s3-camera/tools/host_tests.py --sanitizers address,undefined`.
Use `--no-sockets` only in restricted local sandboxes; CI defaults to every suite.
The same bridge regression fails against the original PR31 MotorBridge at the
T boundary and passes against the correction. Independent CI on the published
correction is required in addition to these local
results. Native builds, when run by CI, are build evidence only. No binaries are
published or deployed by this correction.

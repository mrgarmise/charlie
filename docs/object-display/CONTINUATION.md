# Object Recognition continuation

Normal Object Recognition uses Charlie's existing Hailo-8L object model, Attention Manager and pico:ed object-label protocol. Only application-owned feeders open/configure/capture/recover cameras. All camera-facing capability APIs now subscribe to the shared publication. Object mode switches subscriptions, clears stale labels and retains source/timestamp/generation/pixel provenance. Other consumers continue receiving frames without capture duplication or restart.

[Architecture diagram, source files and acceptance-test mapping](ARCHITECTURE.md) · [Machine-readable validation and source hashes](recognition-validation/validation.json) · [Full native software summary](recognition-validation/full-native.txt) · [Final focused summary](recognition-validation/focused-final.txt).

| Validation | Result and scope |
|---|---|
| Native device-free full suite | **1,365 passed, 24 skipped**, 455.06 seconds; no failures. This run preceded the final mobile CLI subscription/poll-accounting refinements. |
| Final focused selection | **97 passed**, including those refinements, owner-only capture, concurrent subscribers, source switching, uninterrupted other-consumer delivery, one-element backpressure, freshness, source generations, isolated provenance, separate-process subscribers, mode startup, existing learning supervision, real label serializer and legacy main startup/cleanup. |
| Final publication subset | **3 passed** after the decode-freshness check. |
| Final existing lifecycle subset | **5 passed**, including primary preemption, existing brain/calibration integration and raw-driver failure cleanup. |
| Display-only CLI replay | Existing CAT/DOG no-device replay retained; actual serializer output is in `recognition-validation/display-replay.jsonl`. |
| Compilation / whitespace | Python compilation and `git diff --check` passed. |
| Installed model identity | Existing manifest's 80-class, 640-input HEF matches installed SHA256 `90e2cdad2875f23fb436ecdba88b4789de3bd8112cdf6b34beb1c8aa9fd7eed1`; read-only inspection only. |

The full suite's 24 skips remain explicit: torch absent (18), Node/browser runtime absent (3), original/archive acceptance artifacts unavailable (2), collection skip (1). One pytest JUnit `record_property` compatibility warning remains. No skipped neural/browser/archive case is represented as executed.

JUnit receipts are losslessly compressed (`*.xml.gz`) with original and compressed SHA256 values in the validation JSON. Earlier failed, sandbox-blocked and interrupted receipts/logs remain preserved. The first full sandbox run had 1,314 passes, 42 failures and 24 skips before corrections; it is not a passing receipt. The interrupted native run stopped after 22 passes/one skip while completing explicit no-device guards. The final suite allows loopback fixtures but rejects unmocked physical camera construction, serial opening and nonlocal HTTP video I/O.

The existing OpenCV preprocessing test now compares float32 values with a 0.0001 absolute tolerance rather than exact equality (`255.00002` is normal interpolation rounding). It retains color/channel/preprocessing assertions. Existing main/firmware/calibration fixtures now inject the application feeder boundary; their motion, STOP, cleanup and interruption assertions remain. Driver tests explicitly test the private authoritative transport with fake dependencies. A camera-lease metadata/unlock handoff race now retries the actual lock briefly; no ownership bypass or weakened motion gate was added.

No firmware or motion implementation changed. No physical camera activation, serial connection, firmware flash, servo/motor movement, navigation or policy activation was performed. Native inference accuracy/latency, thermal behavior, camera configuration and actual display timing remain outside these software receipts. PR #11 remains draft.

For later authorized native operation, use the [normal command and subscription controls](ARCHITECTURE.md#normal-mode-and-provenance). The compatibility subscriber APIs require an existing authoritative publication; they never start a camera as a fallback. A standalone mobile observation command subscribes to the running application's feed. Physical Active Vision retains its actual feeder-role, calibration, firmware and scoped-motion gates.

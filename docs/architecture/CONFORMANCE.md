# Sensory conformance and migration inventory

Contract beneath [Charlie Architecture](../CHARLIE_ARCHITECTURE.md).
Scope: examined PR #11 source, PR #10 current metadata/change inventory and
published branch heads. This is a source/host audit, not an exhaustive historical
conversation audit, installed-service inventory or native acceptance certificate.
The 80 lexical candidate lines in [access-candidates.json](audit/access-candidates.json)
retain exact paths/lines, including comments and legacy examples. Tests are excluded
from that search, but relevant executable tests are mapped below. Dynamic imports,
non-Python binaries and unpublished/native changes require separate inspection.

## Acquisition, consumer and transport inventory

| Paths / sites | Actual behavior at examined PR #11 | Status and remediation ownership |
|---|---|---|
| `vision/camera.py:_PiCameraDevice`; `vision/camera_source.py:_PiCapture` | Private Picamera2 open/lease/capture; same-request pixel/metadata | Shared owner implemented; native capture/clock qualification pending PR #11. |
| `hardware/elegoo_camera.py:_ElegooCameraDevice`; `vision/camera_source.py:_ElegooCapture`; `hardware/camera_ownership.py` | Private HTTP MJPEG reader/recovery, hostname transport lease | Shared owner implemented; receipt age only, exposure age unknown. |
| `experiments/ppal/camera_session.py:CameraFeeder` | Continuous capture, bounded retry/configuration, immutable publish; application lifetime | Host tested; no installed-service claim. Configuration remains actual-role checked. |
| `stimulus/bus.py`; `vision/camera_source.py:CameraSubscription` | Owner admission, independent queues, source switch; audit adds local latest/recent history | Host tested; discovery schema and general modality API still target work. |
| `experiments/ppal/eyes/passive.py`; `passive_viewer.py`; `setup/charlie_eyes_launcher.py` | Asynchronous lossless latest PNG + provenance; viewer/SSH loopback; idle preview uses subscriber facade | Transitional: same-host only, no remote bounded recent history or distributed health directory. |
| `vision/camera.py:Camera`; `hardware/elegoo_camera.py:ElegooCamera`; `vision/tracker.py` | Subscription-only compatibility wrappers; close releases subscriber | Host tested. Width/height request is not independent physical reconfiguration. |
| `vision/stimulus.py`; `vision/detector.py`; `main.py`; `vision/mobile_face.py` | Normal tracking/face interpretation uses feeder publication via adapters | Host tested; native frame/coordinate/model verification pending. |
| `experiments/ppal/eyes/sources.py:PiCameraSource`; `observation_camera.py`; `camera_session.py:CameraSession` | PIL/metadata and borrowed-source compatibility; source wraps subscription; focus requests queue to feeder | Transitional: external consumers require running feeder; remote configuration denied. Native Robotron fresh exposure/focus still pending. |
| `experiments/ppal/play_robotron.py`, `marathon_robotron.py`, `run_camera.py`, `run_closed_loop.py`, `preflight.py`, `capture_robotron_hud.py`, `visual_control_probe.py` | PiCameraSource consumers, not additional Picamera2 owners on PR #11 | Preserve interfaces; verify feeder bootstrap and geometry/focus/freshness before real gameplay. No new gameplay authorization. |
| `tools/benchmark_buffered_recording.py`; `experiments/ppal/eyes/cli.py` | Explicit native/subscription or fixture sources | Distinguish frozen pixels from native acquisition; standalone native mode may be unavailable without feeder. |
| `experiments/ppal/eyes/run_active_vision.py`, `active_vision.py`, `camera_lease.py` | Authorized entrypoint starts application feeder; optimizer subscribes; actual role/lease checks govern focus/motion | Preserve CAL-1 and electrical gates; native acceptance blocked on separately authorized stationary setup. |
| `vision/hsv_test.py`, `test_orange.py`, `test_stimulus.py`; `run_elegoo_head2.py`, `run_elegoo_head2_diagnostic.py`, `experiments/robotron/capture.py` | Legacy camera calls route through compatibility subscriber | Transitional examples: feeder required; some scripts include controller/motion startup. Do not run for this audit. |
| `learning/mobile_runtime.py`, `behaviors/mobile_observe.py`, `vision/mobile_perception.py:MobileFrameSource` | Mobile normal/standalone capability subscribes; model preparation/recording does not own camera driver | Host fixtures only; latest PR #10 changes require semantic reconciliation with PR #11 bus APIs. |
| `vision/mobile_models.py`; `hardware/hailo_session.py`; `vision/object_recognition.py` | Shared source-independent detector/depth adapters; session holds accelerator lease; observations identify frame/model | No fair multi-network scheduler guarantee; model dedup/version fields incomplete. Native Hailo both sources pending. |
| `learning/object_runtime.py`; `vision/object_observation.py`; `attention/manager.py` | Normal Object Recognition publishes to its display-owning AttentionManager and journals predictions | No second serial owner inside that path; default decision-pixel retention missing. Explicit task for runtime owner. |
| `vision/mobile_perception.py:FrameArtifactStore/RecordingFrameSource`; `learning/mobile_runtime.py:EventRetention`; `memory/evidence.py`; `learning/mobile.py`; `memory/evaluator.py` | Bounded selected pixels plus durable journal and independent evaluation | Transitional: no general durable bookmark API or representative/pre-post sampling; audit RAM history is not durable evidence. |
| `learning/resources.py`; `hardware/system.py` | Local thermal/process/CPU/memory polling; fail-closed thermal guard where required | Direct telemetry is intentional current owner, not bus publication; modality registry migration needed. |
| `hardware/neck_health.py`; `rp2040/main.py`, `calibration.py`, `servos.py`, `motion_profile.py` | Health/status, GP10 calibration and gated low-level servo execution | Physical safety preserved, not modified. No generic IMU/range source established. |
| `hardware/rp2040_controller.py`; `attention/object_display_runtime.py`; `hardware/scene_response.py` | Existing serialized RP2040 connection, status and display | Preserve heartbeat/STOP and safety/status priority. Readback firmware identity incomplete. |
| `hardware/elegoo_mobile.py`; `motion/mobile_base.py`; `experiments/ppal/mobile_navigation.py` | Exclusive command connection mediated by control/safety layers | Connection exclusion is legitimate; do not remove independent command gates to share sensing. Latest PR #10 adds substantial qualification gates absent here. |
| `motion/servo.py` | Legacy direct `serial.Serial` adapter; no production importer found in source search | Nonconforming if used as normal runtime. Quarantine/document; do not execute. Migration requires controller-authority adapter, not removal of safety checks. |
| `oldmain.py`; `OldPicoFiles/`; `experiments/ppal/eyes/simulate_active_vision.py`, `benchmark_passive.py` | Historical application/firmware and explicit simulated lease probes | Archive/simulation, not evidence of deployed capture. Never flash legacy files. |
| `experiments/robotron/live.py` | TCP controller port 8765, separate from sensory acquisition | Authorized gameplay authority remains independent; no changes. |

Names alone do not prove nonconformance. `_PiCameraDevice` owning a lease is
correct; `Camera()` in a legacy consumer now subscribes. Hardware-configuring
or motor-command consumers must still pass independent gates. Current PR #10
is not equivalent to the older ancestor in PR #11; source conformance above must
not be misrepresented as acceptance of the combined unpublished stack.

## Testable invariants and acceptance

| Invariant | Repeatable host test / current result | Exact remaining native check |
|---|---|---|
| One physical capture owner despite many consumers | `tests/test_camera_sources.py` owner/concurrent-capability tests | Count native opens and verify physical lease; attach two consumers and close one without interruption. |
| Late consumers get identifiable latest/recent observations | `tests/test_sensory_history.py` | Measure Pi RAM/rate/freshness using both sources; set deployment retention from measured results. |
| Bounded slow consumers, immutable provenance, ordering/faults | Camera/history tests; byte cap, drops, same-generation order rejection and fault invalidation | Long stationary outage/recovery; record generations/drop counters and timestamps. |
| Switching clears labels, keeps original subscriber alive | `tests/test_object_recognition.py` switch/reconfirmation test | Stationary Pi+ELEGOO source switch, independent face/evidence subscriber running. |
| Same inference adapter consumes both sources | Object Recognition fixtures and existing model tests | Hash-bound installed HEF with authentic frames from both feeds; preserve exact source pixels and outputs. |
| Cross-process sharing without second camera | `tests/test_published_frame_subscription.py` subprocess tests | Two real subscriber processes against one native feeder; verify no second capture and boot/age/fault handling. |
| Exact decision evidence and bounded context | Existing artifact/journal tests only; new history does not satisfy bookmarks | Add normal runtime retention/bookmark hooks, expiration receipts and representative sampling before native evidence acceptance. |
| RP2040 single serial owner, prioritized display, STOP/heartbeat/CAL-1 | Existing display/calibration/firmware tests | Separately authorized stationary serial test, firmware readback manifest, electrical isolation and HEAD B lockout proof. |
| Resource outage/thermal does not authorize motion | Existing resource/mobile safety tests; history fault tests | Measure native thermal transitions and fresh recovery; no motor test under this mission. |
| Source discovery across modalities/bodies | Schema documented; general runtime not implemented | Implement adapters/permissions/health for actual installed sources; no imaginary device registration. |

Host tests use synthetic pixels, mocked serial/Hailo and loopback transports.
`tests/conftest.py` blocks unmocked physical camera/serial/nonlocal HTTP access.
Native tests remain pending until independently observed; do not convert source
inspection or historical receipts into claims of current hardware success.

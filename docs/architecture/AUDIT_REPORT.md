# Shared sensory architecture audit — published milestone

The canonical architecture now describes Charlie as one persistent multi-body
individual with independent sensory production, interpretation, cognitive
priorities, evidence acquisition and safety authority. Existing owners and
interfaces were reused. No competing capture manager or replacement application
was introduced.

## Examined source and coordination

Initial published heads: `master` `bcf8082f6319c63c4bd6bcceeab5faea37241654`,
PR #10 `cafe21aa3f6c68080c12a1a5613a92516fdb7167`, PR #11
`a19c90822687739f79f69587302006a1bd6364d4`. PR #11's PR #10 ancestor is
`96e651373e513d24b4163b87c5f85bdd5549cf1d`, so the newest mobility qualification
work is not in the examined PR #11 runtime. Both PR discussions were empty at
inspection. All remote branch heads are retained in
[audit/published-branches.txt](audit/published-branches.txt).

This work uses isolated branch `audit/shared-sensory-contracts` based on PR #11.
Neither PR #10/#11 branch nor another session's worktree is modified. The report
is an audit of published source and available receipts, not unseen unpublished
progress. No native checkout, installed process inventory or live firmware was
available for direct inspection. Earlier original evidence, fixtures, firmware,
motion/control source and historical receipts remain unchanged.

## Findings and implemented correction

PR #11 already centralized Pi/ELEGOO acquisition in application feeders and made
legacy APIs subscription-only. Local subscribers had bounded latest-only queues,
but late subscribers could not query already-produced frames. `stimulus/bus.py`
now retains bounded RAM history, exposes `latest_frame`/`recent_frames`, seeds late
subscribers and rejects same-generation duplicate/regressing frames. Count and
byte caps, eviction accounting, fault invalidation, generation resets and isolated
producer/consumer provenance preserve source identity and freshness. The new
`tests/test_sensory_history.py` uses explicitly synthetic immutable pixels.

Canonical changes: `docs/CHARLIE_ARCHITECTURE.md`,
`docs/architecture/RESOURCE_OWNERSHIP.md`, `CONNECTIVITY_AND_DEPLOYMENT.md`,
`CONFORMANCE.md`, this report and machine audit inventories/validation receipts.
The conformance matrix classifies acquisition owners, wrappers/borrowers,
Robotron/Active Vision/mobile/legacy consumers, Hailo, telemetry, evidence and
serial/motor transports. The candidate inventory contains 80 lexical source
matches; it is not an assertion that every match opens hardware.

Confirmed remaining gaps: general modality discovery, remote clock mappings and
history, fair inference scheduling/deduplication, default exact-pixel bookmarks
in normal Object Recognition, representative context sampling and live firmware
readback manifest. Legacy `motion/servo.py` can directly open serial if invoked;
no production importer was found. It was not executed or substituted into normal
control. The source-defined channels and controlled RP2040 sync/backup/rollback
chain are documented with unknown installed state explicit.

## Validation and evidence limits

Focused repeatable command (run with the isolated host environment's Python):

```sh
python -m pytest -q tests/test_sensory_history.py tests/test_camera_sources.py tests/test_published_frame_subscription.py tests/test_object_recognition.py --junitxml=docs/architecture/audit/focused-tests.xml
```

**29 passed, zero failures/errors/skips**, in 2.37 seconds. The JUnit receipt is
[audit/focused-tests.xml](audit/focused-tests.xml). This includes shared capture,
concurrent/switching consumers, independent subprocess publication, normal
recognition/display/evidence integration and the new history tests. The initial
attempt had 26 passes and 3 failures because OpenCV was missing from the isolated
host environment; installing `opencv-python-headless` resolved those import
failures. No production source was changed to hide them. Python 3.12, pytest
9.1.1, pyserial 3.5, NumPy 2.3.5 and OpenCV 5.0.0 were used.

The broader device-free suite is running at this milestone; its result must not
be inferred from this focused success. `.github/workflows/sensory-audit.yml`
provides independent full-suite CI and retains JUnit output. Host fixtures and
simulations do not establish new Pi/Hailo inference, physical capture, firmware
installation, thermal throughput or safe navigation.

## Remaining acceptance and next safe checkout

Before any native use, semantically reconcile latest PR #10 safety work with PR
#11 subscription work in an isolated integration checkout. Do not deploy this
older stack over the latest pet-following branch. Run the full device-free suite,
then the native matrix in [CONFORMANCE.md](CONFORMANCE.md): one physical capture
owner/two consumers; source-switch isolation; measured RAM/rates/thermal/fault
recovery; authentic frame/model identity on both cameras; durable evidence
bookmark/expiration support; and separately authorized stationary RP2040
readback/heartbeat/STOP/priority tests. Source discovery and evidence contracts
remain partially implemented rather than falsely marked conforming.

This mission authorizes no network/process deployment, firmware flashing,
calibration, physical servo/chassis movement, navigation or policy activation.
None occurred. To undo the audit software, revert its commit(s) in a clean
isolated checkout; no device rollback is required. Preserve both active feature
branches and all original journals before any future reconciliation.

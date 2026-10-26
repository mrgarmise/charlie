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
serial/motor transports. The candidate inventory contains 89 lexical source
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

The full device-free host suite passed **1,373 tests / 21 skipped / zero failures**
in 327.80 seconds, with one existing pytest `record_property`/JUnit compatibility
warning. It ran the published runtime tree (local commit `d25faed`, identical tree
`6ddb926da7fcbbe06bd594e72f2516ccaa6b71ab` to published commit
`ed37a3ac1dd863342b9cce30a60fe98258c4a5e5`). Final test-only strengthening adds
explicit producer-mutation isolation and duplicate rejection after byte eviction;
all 3 history tests then passed in 0.10 seconds. No runtime changes followed the
full run. Full console output and compressed JUnit are retained under `audit/`.
`.github/workflows/sensory-audit.yml` provides independent full-suite CI and
retains JUnit output. Independent [GitHub CI run 40254634149](https://github.com/mrgarmise/charlie/actions/runs/40254634149) passed **1,373 tests / 21 skipped / zero failures** in 354.64 seconds on the published runtime increment. Its exact test summary and source identity are retained in `audit/validation.json`. Host fixtures and
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

## Publication and preservation receipt

[Draft PR #12](https://github.com/mrgarmise/charlie/pull/12) targets PR #11 and
preserves both existing feature branches. Direct shell push lacked authentication;
publication used the connected GitHub service. The published initial commit and
tested local commit have different metadata/SHAs but exactly the same tree.
The final documentation/test receipt is a separate descendant, without runtime
changes. `git diff --check` and local relative-document-link checks passed.
A final read confirmed PR #10 remained at `cafe21aa` and PR #11 at `a19c908`.
No changes occurred under `rp2040/`, `hardware/`, `motion/`, `tests/fixtures/`,
`docs/mobile/` or `docs/object-display/` relative to the examined PR #11 head.

Remaining implementation is intentionally staged rather than hidden behind a
conformance claim: cross-body discovery needs authority/clock adapters for actual
installed producers; remote history needs a qualified bounded remote publisher;
default bookmarks need reconciliation of normal/object and latest pet evidence
retention so preservation failures remain explicit; fair Hailo scheduling needs
native resource measurements. Each is mapped to code and qualification in the
conformance table. None is certified by this RAM-history correction.

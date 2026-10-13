# CAL-1 — Interrupted-session recovery and independent software validation

Date: 2026-10-03. Repository: mrgarmise/charlie. Branch: feature/active-vision.
Recovered published baseline: c467d0af973fbe94705e88cad2a4c056ee401dd4.
Correction revision: the commit containing this report; use its canonical GitHub commit SHA.
Physical authorization: **FALSE**. No Pico flash, servo energization, hardware calibration, camera operation, physical movement, profile activation or Robotron gameplay occurred.

## Recovery findings

The remote branch was independently read through GitHub and fetched with Git. It still ended at c467d0a before this correction; no newer remote commits were present. Two surviving local Charlie checkouts were inspected read-only. The local Active Vision checkout was clean at b29ee2b; the other was a separate learning checkout. No recoverable uncommitted CAL-1 source changes were found in those inspected checkouts. Both were preserved. Their existence does not establish access to all files or in-memory work from the interrupted session.

A new clone was made without hardlinks from the older checkout, its origin set to the existing GitHub repository, the remote fetched and the c467d0a commit checked out separately. No reset, clean, stash or overwrite of prior work was performed.

Published CAL-1 already implemented supervised incremental calibration, persistent immutable profiles, qualification and quarantine, guarded autonomous activation, neck health and blocked Executive recalibration context. The 23-file published change, tests, current motion authority, current CAL-1 instructions and archived simulation were inspected. Software implementation was not restarted.

The old surviving environment had a missing interpreter entry and its binary package import attempt exited 135. This is an environment failure, not evidence of a CAL-1 defect. A fresh isolated environment independently reproduced the original reported results.

## Environment

x86_64 Linux; CPython 3.12.14; NumPy 2.2.4; OpenCV 4.10.0 (opencv-python-headless distribution 4.10.0.84); Pillow 12.3.0; pytest 9.1.1; pyserial 3.5. Torch unavailable.

Environment preparation, outside the repository:
```bash
python -m venv cal1-validation-env
cal1-validation-env/bin/python -m pip install pytest==9.1.1 numpy==2.2.4 opencv-python-headless==4.10.0.84 Pillow==12.3.0 pyserial==3.5
```

The commands below ran from the isolated repository root. Interpreter path was ../cal1-validation-env/bin/python. stdout/stderr and JUnit evidence were retained separately during execution. Times use pytest terminal output; JUnit suite timing differs slightly.

## Executed validation

| State | Actual command | Result |
|---|---|---|
| Original c467d0a | python -m pytest -q tests/test_neck_calibration.py --junitxml=../validation-logs/cal1.xml | 65 passed in 5.08s |
| Original c467d0a | python -m pytest -q tests/test_neck_calibration.py tests/test_active_vision_firmware.py tests/test_head_recovery_lockout.py tests/test_active_vision.py tests/test_passive_eyes.py --junitxml=../validation-logs/integration.xml | 160 passed in 40.04s |
| Original c467d0a | python -m pytest -q -rs tests --junitxml=../validation-logs/baseline-regressions.xml | 609 passed, 19 skipped in 71.30s |
| Added regression before correction | python -m pytest -q tests/test_neck_calibration.py -k invalid_commanded_position | 8 failed, 4 passed, 65 deselected in 0.42s |
| First correction attempt | python -m pytest -q tests/test_neck_calibration.py --junitxml=../validation-logs/corrected-cal1.xml | 6 failed, 71 passed in 5.32s; nonfinite diagnostics could not be persisted as strict JSON |
| Final correction | python -m pytest -q tests/test_neck_calibration.py --junitxml=../validation-logs/final-cal1.xml | 77 passed in 5.07s |
| Final correction | python -m pytest -q -rs tests --junitxml=../validation-logs/final-regressions.xml | 621 passed, 19 skipped in 74.50s; zero failures/errors |

Final full-suite JUnit contains 172 successfully executed cases across the five focused integration files. This is a verified subset of the full run, not a separately timed focused rerun. An intermediate broader run was interrupted after the first correction's focused failures were discovered; it is not counted as a successful validation.

All 19 final skips are missing-Torch coverage in existing ALA foundry/cycle/operational/portable/refinement tests. They are environment limitations, not passing tests. Torch coverage was not run. CAL-1 itself has zero skips.

Other executed checks:
```bash
git diff --check b29ee2b3dc9b2a5c5eb353ee296c270f02601472..HEAD
git diff --check
python -m compileall -q attention behaviors display experiments hardware learning memory motion rp2040 setup stimulus tests tools vision main.py behavior_manager.py
python -m tabnanny rp2040 hardware experiments/ppal/eyes tools/calibrate_neck.py tools/neck_profiles.py tests/test_neck_calibration.py
```

All completed with exit 0. No repository formatter configuration was found; formatting validation here means whitespace/error and indentation checks, not an unexecuted Black/Ruff check. Existing code style was preserved rather than bulk-reformatted. CPython compilation does not establish MicroPython compatibility.

An executed hardware-free archive/gate audit verified:
- Archived calibration JSONL has 44 records and sequential firmware events.
- Its SHA-256 matches both summary and candidate: f5d3dc43f3cc767e9b2a5ca0ba702fac860e56e88091d77bac48af9aadf7c89a.
- All records are simulated; candidate remains CANDIDATE, simulated=true, measured_position=null.
- Shipped profile, commissioning profile, local arm and persistent directory are absent.
- Electrical gate, calibration input and autonomous enable are false.

## Defect, reproduction and minimal correction

Reproduction on c467d0a: prepare a fake 0.5-degree pan move; shift the four observed corners by two pixels; report telemetry pan=NaN, tilt=90, moving=false, armed=true. NeckHealth recorded “movement visually supported,” made zero STOP/revocation calls and did not quarantine.

Root cause: abs(NaN - requested) > tolerance evaluates false. Invalid strings raised TypeError before reaching the existing unsafe path. Missing positions and infinity were also included in regression coverage.

Correction: reject any commanded pan/tilt value whose type is not int/float or is not finite; route it through existing unsafe handling. Invalid values are preserved as explicit repr strings in reported_positions, not invented numeric observations. This avoids writing NaN/Infinity into strict JSON and allows durable quarantine to complete. Existing alternatives and mechanical_fault_confirmed=false remain.

Changed executable file: hardware/neck_health.py only. Twelve parameterized pan/tilt regression cases cover NaN, +Infinity, -Infinity, None, invalid string and boolean. They require STOP, revocation, durable quarantine, preserved uncertainty and refusal of another movement. No authority thresholds, motion profile, GPIO, controller, deployment or learning policy was changed.

No remaining reproduced software defect was found in this bounded validation. This is not a proof of absence of defects.

## Original acceptance audit

| Requirement | Inspected implementation and executed coverage | Disposition |
|---|---|---|
| Versioned durable profiles | ProfileRepository exclusive versions, activation/history and host fsync; RP2040 profile loader; persistent-version/reboot/quarantine tests | Implemented; independently host-tested. Actual Pico filesystem/power-loss durability pending |
| Starting pose vs measurement | operator_confirmed_estimate, measured_position=null; fresh pose/pulse verification and first-PWM test | Implemented; fake PWM tested. Actual alignment/pulse association pending |
| Combined envelope, margins, rates | Convex commissioning region/margin, bounded single-axis increments, conservative observed-grid derivation and immutable qualification | Implemented; math/fake-hardware tested. Continuous mechanical interval clearance pending |
| Fail-closed loading | Missing/corrupt/digest/hardware/unverified/combined-region/qualification rejection; no static fallback; quarantine and running markers | Independently host-tested. Native MicroPython/Pico execution pending |
| GP10 one step | Debounced released HIGH→pressed LOW→released HIGH, prepared step, no held/bounce/reused/stale/between-sample permit | Independently fake-input tested. Real electrical noise/debounce pending |
| Increment confirmation | Fresh initial attestation, clearance proof, visual displacement, stage expiry and no next move before confirmation | Independently fake-hardware tested. Actual supervised observations pending |
| Authority safety | STOP/watchdog/session/epoch/owner/primary/recovery, single PWM owner, GP4/5 only, GP14/15 inactive | Independently fake-PWM/UART/time tested. Physical cutoff/watchdog measurement pending |
| Qualified normal autonomy | Fresh activated qualified profile, scoped Active Vision, visual health, LOCKED resource release, no GP10 at rates 0.5 and 5 | Independently simulated integration-tested. Physical qualification and live operation pending |
| Neck health | Command/view discrepancy, wrong direction, missing evidence, persistent viewpoint shift, alternatives, first-failure STOP/revocation/quarantine, no obstruction retry | Independently host-tested including malformed position fix. Real visual reliability pending |
| Executive/recovery | Existing journal/Reflection/Executive proposal; recalibration remains blocked without supervision/clearance/authority | Independently software-tested. Continuing primary-task health integration is not implemented by this recovery |

The tests contain explicit fabricated physical-shaped qualification documents to exercise schemas. They are test fixtures, not real independently qualified profiles. No simulated evidence qualifies physical movement.

## Remaining acceptance and recommended next procedure

CAL-1 is **implemented, software-tested and independently validated on this host**. It is **not physically demonstrated or fully complete**. ARM64/Pi-native execution and real MicroPython remain unvalidated by this session. Ongoing primary-task health/handoff integration remains a separate documented gap, not authorized implementation here.

Recommended next mission, only after separate authorization:
1. Stage the exact corrected revision in an isolated Pi checkout and run code-only regressions/gate checks; preserve operational checkout, evidence and backups.
2. Resolve Keyestudio shield power/USB topology and verify an independent servo cutoff. Keep Head B disconnected and servo power off.
3. Review actual initial alignment/pulse mapping, combined commissioning region, positive margins and appropriate rate/step bounds. Do not infer them from commanded telemetry or historical unloaded limits.
4. Preserve a fresh full Pico backup; only then separately authorize disarmed firmware maintenance. Confirm no startup PWM and no activation from GP10 alone.
5. Under an explicitly authorized supervised calibration mission, confirm pose/pulse/clearance/cutoff, prepare one step, press/release GP10, inspect movement and record displacement before another step. Real wiring noise, PWM/rate/watchdog and post-STOP stability must be measured.
6. Preserve complete grid evidence and mechanically inspect whole interpolated region. Derive a candidate; require separate reviewer evidence for independent qualification. Test persistence/quarantine/unclean reboot and safe rollback without erasing history.
7. Only after independent physical qualification and separately authorized activation, verify bounded autonomous Active Vision, camera ownership/health checks and resource handoff. GP10 remains calibration-only.

Current CAL-1.md is the detailed future procedure; its physical steps were not executed here. Do not reuse superseded energizing firmware or clear quarantine by selecting an older copy.

## Linear CHA-8 update

Recovered c467d0a without reimplementation; independently reproduced 65 CAL-1, 160 focused, and 609 broader passes/19 expected Torch skips. Corrected invalid/nonfinite commanded-position admission in NeckHealth with 12 regression cases and JSON-safe diagnostic provenance. Final validation: 77 CAL-1 passes; 621 broader passes, 19 Torch skips, zero failures; 172 focused cases included. Compilation/whitespace/indentation, archive hashes and false physical gates verified. Physical authorization remains false; Pi/MicroPython, electrical/mechanical qualification and live health/handoff remain pending. Keep CHA-8 open.


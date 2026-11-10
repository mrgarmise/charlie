# Stock parity follow-on validation — 2026-11-10

BUILD ONLY. No flash, deployment, runtime update, networking change or movement.

- 104 focused Python checks: per-command authentication, qualified executor, manual console, timed pulse and STOP deadlines.
- 31 firmware Python/browser/TLS/enrollment/build-contract checks (real localhost fixtures outside the sandbox).
- Five C++ production suites pass with AddressSanitizer and UndefinedBehaviorSanitizer: framing, auth, power-loss, authenticated bridge and command gate; real host mbedTLS verifies Python-generated command MAC vectors.
- 131 unified architecture/ownership/STOP contract checks pass. No unrelated full Charlie test suite was rerun.
- Native clean OPI and QSPI compilation passes; esptool checksum/hash, S3 header, image slot fit and original partition type/subtype/flags/geometry checks pass.

Both native builds use sketch source SHA256 `011f58cc40b046163e2398d7f785824ef6e1ac78a7b81c8a2503133cc82feed9`, Arduino-ESP32 2.0.17 / IDF4.4.7, CLI1.2.2, GCC8.4 on aarch64. FQBN settings and full image hashes are in [OPI report](stock-parity-evidence/qualified-opi-build.json) and [QSPI report](stock-parity-evidence/qualified-qspi-build.json). OPI:3,154,016 bytes /54461ab297ea8bd231231ca6d14d1b24601e015e6bd4e0034fa4000324d056a4. QSPI:3,152,640 bytes /4d94e2b63d0ef892d73d2b9cd403225c24fbd8e3c176b2d1018d7b86cc2cf3ce. Both fit0x330000. Candidate images remain in the private task toolchain cache; no image is in this PR or CI artifacts.

The first sandbox sanitizer invocation failed because LeakSanitizer cannot run under ptrace; loopback sockets were also denied. Authorized reruns outside the sandbox passed. Firmware suites first reported28 pass/3 skipped under denied loopback; explicit localhost-only rerun passed all31. Initial new-gate host tests exposed mbedTLS major-version enum mismatch in the test shim (fixed by using the production string-based digest lookup), and a test assertion that overlooked Factory status writes (corrected to count STOP frames). Final suites pass. These were fixture/test-development failures, not hardware observations.

Independent GitHub validation links will be recorded after the draft PR run finishes. Native ESP32 images are not executed on host; UART, PSRAM, camera, timing, key storage, task starvation, radio behavior, physical STOP and installed UNO identity remain unverified. The static key/auth policy is a reviewable candidate, not a qualification grant. See QUALIFIED_CONTROL.md and the separate stock-parity audit for NO GO prerequisites.

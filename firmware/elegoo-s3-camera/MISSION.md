# Codex mission — ELEGOO S3 camera-server reconstruction and network integration

**Date:** 2026-11-09  
**Target:** ELEGOO Smart Robot Car V4 ESP32-S3 camera/Wi-Fi/UART bridge for Charlie  
**Scope:** Finish a **buildable, compatible firmware candidate** from an identified source baseline and the already-tested network firmware core. Publish independently tested work in an isolated **draft PR**. **Build-only; no flashing, deployment, merge, live network changes, motor commands, or changes to approved runtime.**

## User decision and objective

The owner explicitly selects this candidate source as the baseline, accepting that it is not proven byte-identical to the firmware installed on the car:

- Source: `UMRoboticsTeam/umrt-outreach-robotcar-wireless`, branch `elegoo-kit-face`, commit **`a92013016d2386cd4ed2e0e7893b018f04b89cfc`**, directory `ESP32_CameraServer_AP_2023_V1.3/`.
- Source browser: https://github.com/UMRoboticsTeam/umrt-outreach-robotcar-wireless/tree/elegoo-kit-face/ESP32_CameraServer_AP_2023_V1.3
- Networking core: Charlie draft PR **#29**, branch `feature/elegoo-firmware-core-20261109`, exact prior head **`b71cd3dd917b83aff3b643795a76dab3ac5b42ed`**, files in `firmware/elegoo-network/`.
- Pi-side peer: Charlie draft PR **#28**, commit `c8a7a8d`, including `docs/elegoo-network/OPERATOR.md`, provisioning protocol, verified discovery and rollback.

**Do not stop merely because source identity cannot be proven identical**. The correct next step is to port and native-build the best candidate, documenting unknown hardware compatibility for physical acceptance. Conversely **do not assert equivalence or flashability** from passing host tests or a successful compile alone.

## Proven hardware facts and private recovery boundary

- ESP32-S3 camera board USB serial VID:PID `303a:1001`, stable USB ID `usb-Espressif_USB_JTAG_serial_debug_unit_30:30:F9:0D:B0:E8-if00`. `/dev/ttyACM0` and `/dev/ttyACM1` can swap. **Never access the RP2040** device, which is separate.
- Flash capacity 8 MiB and PSRAM reported 8 MiB. Do not infer PSRAM interface mode or exact camera pin map merely from these sizes.
- Original full flash image preserved privately at `/home/five/charlie-ops/firmware-backups/elegoo-esp32s3/elegoo-esp32s3-original-20261109.bin`, 8,388,608 bytes, SHA-256 `c196e9077be06b3f61f6acfcf66219fe0535b60ae1d26183c43b2de80ff25c5b`. Independently identical to Mint read. **Do not upload or commit the raw image**; may contain secrets.
- Recorded original layout: bootloader/partition table, NVS 0x9000 size 20 KiB; otadata 0xE000 size 8 KiB; app0 0x10000 size 3264 KiB; app1 0x340000 size 3264 KiB; SPIFFS 0x670000 size 1536 KiB; coredump 0x7F0000 size 64 KiB.
- Charlie has an approved stationary runtime and separate qualified executor. Preserve all safety/qualification constraints. Codex's prior terminal sandbox lacked serial device nodes: **do not waste effort repeatedly attempting hardware access in sandbox**, and do not weaken restrictions.

## Implementation tasks (work to completion where access/toolchains permit)

1. **Reproduce the selected candidate source exactly**, recording upstream commit, original file manifest, and relevant licenses/provenance. Work in an isolated branch based on a reviewed PR #29 firmware-core revision (or make an explicitly documented integration branch). Do not modify PR #28/#29 or other active PR heads in place. Vendor only the required source, with attribution/license compliance; never include any local `charlie_home_wifi.h`, hardcoded home credentials, prototype patch or private firmware backup. The previous hardcoded AP+STA prototype was incorrect and is **not** the integration baseline.

2. **Baseline audit and contract table.** Inspect the source directly: `.ino`, `CameraWebServer_AP.cpp/.h`, `app_httpd.cpp`, `camera_pins.h`, `config.h`, `camera_index.h`, UI and assets. Compare with PR #29's README and PR #28's operator/API contract. Explicitly map:
   - legacy AP / 192.168.4.1 behavior and non-hardcoded initial setup identity;
   - camera init/board pin selection, PSRAM settings, JPEG/MJPEG HTTP route(s), control API and HTML UI; camera port 80 and stream port 81 where supported;
   - actual TCP 100 socket accept/client/close lifecycle, message framing, `{Heartbeat}`, safety/stop format, and `Serial2` UART 9600 baud RX GPIO3/TX GPIO40 as **candidate values to verify**;
   - setup webpage hosting and HTTPS 443 plan, channel conflicts, SPIFFS/embedded asset preservation;
   - device identity, NVS, boot, OTA and partition compatibility.
   Distinguish **observed in source**, **reported observed on car**, **new design requirement**, and **not yet verified**; do not claim matching original source.

3. **Create a complete, independently buildable S3 sketch** from the candidate, wired to PR #29's `NetworkCore.h` and `ArduinoPlatform.h` with real Arduino-ESP32 WiFi/Preferences interfaces. Keep the existing legacy features (camera/video, UI controls, UART bridge, command framing) rather than replacing the working application with a network-only sketch. Design the event loop nonblocking enough to service both networking deadlines and safe-stop heartbeats. Preserve existing motor/serial owner; network provisioning handlers must never write motor UART commands. Replace fragile AP-client-count and TCP disconnect assumptions with real client/session lifetime. Bound JSON, TCP framing, credentials, and timers. Ensure loss of control/heartbeat -> stop through the existing UART writer, and reconnect cannot replay an old command. No unauthorized physical drive behavior.

4. **Integrate authenticated provisioning and recovery AP** using PR #29's protocol; do not silently weaken it for convenience. Provide GET `/v1/network`, POST prepare/confirm and an authenticated browser enrollment flow that genuinely hands its transaction to explicitly authorized Charlie verification. Enforce TLS/pinned cert, per-device randomly provisioned authentication, no hardcoded credentials, no open bearer token over HTTP, no unauthenticated default secret, no insecure TOFU. If this cannot be implemented within ESP32 RAM/flash or the existing camera server, record a concrete resource budget/constraint and implement the closest security-preserving feasible alternative behind an explicit gate; **do not label an insecure implementation production-ready**. Avoid introducing two competing Wi-Fi owners or two independent UART motor writers. Store approved credentials in NVS only after verified target-LAN confirmation; preserve rescue AP, rollback/reboot behavior.

5. **Native compile and artifact analysis.** Try an isolated, reproducible build using documented Arduino-ESP32 2.0.17 **as a candidate, not a proven board match**. Determine actual board FQBN, flash mode/frequency, PSRAM interface, partition layout, bootloader/OTA/security constraints from available nonsecret metadata, source and local read-only tools. Compile from a clean checkout using `arduino-cli` or an equivalent documented toolchain. Record tool versions, exact command/flags, build output, application image size, `esptool image-info`, SHA-256, partition/slot fit and whether the image is genuinely generated or not. Iterate on real build errors until successful where dependencies/toolchain are accessible; no placeholder binaries or fabricated checksums. Keep build outputs off Git unless small reproducible release artifacts are specifically safe and necessary. If native compilation fails due sandbox/package access, supply exact commands to run in the **normal Pi or Mint terminal**; avoid asking Codex to alter sandbox privileges.

6. **Independent verification.** Extend prior firmware host tests with protocol fidelity checks, camera route and UART framing compatibility tests where feasible, actual TCP client disconnect/heartbeat safety tests, AP/STA setup + rollback simulations, bad credentials/power-loss edge cases, and build CI. Run relevant existing host suites, scoped contract/browser tests and reproducible native build checks; avoid spending time rerunning the full Charlie suite repeatedly unless source changes warrant it. Document failures and limits candidly. Review source security, licensing and whether combined network+camera+TLS resource usage plausibly fits 8MiB flash / 8MiB PSRAM; actual radio, TLS load, UART, sensor and movement tests remain native acceptance.

7. **Prepare supervised hardware acceptance and recovery procedure** for a *separate later owner-approved session*. Identify read-only reconnaissance commands and concrete staged acceptance tests to measure current camera routes/stream, UI, port 100 bridge and safe stop **before** flashing, then verify postflash equivalence. Capture rollback strategy using the verified original backup and the real partition layout. Do not propose unsafe blind app-only flashing, rewriting NVS/SPIFFS, or full flash restoration without explicit owner authorization and security/boot checks.

## Deliverables and reporting

- One or more **draft PRs**, with explicit base/head branches and tested incremental commits, linking #28/#29 without merging or rewriting them.
- A source-provenance report; baseline-vs-target behavior/compatibility matrix; full integrated firmware project/sketch; secure provisioning endpoints/flows; automated tests; reproducible native build instructions and build results.
- If a firmware binary is built, give **actual** size/hash/image metadata, compile command, and where it exists; mark **NOT HARDWARE QUALIFIED / DO NOT FLASH**. If not built, give precisely what failed and the minimal next terminal action.
- A precise read-only preflight + supervised physical acceptance + rollback runbook, including the exact camera, stream and UART checks, and every remaining unverified safety gate.
- A concise final report pointing to the new PR(s), commits and evidence, separating **implemented**, **host tested**, **native built**, **native hardware qualified**, **deployed**.

## Non-negotiable guardrails

No `git merge`, operational runtime change, networking change, service restart, ESP32 flash/write, RP2040 interaction, motor activation, or automatic Wi-Fi handoff. No hardcoded passwords, credentials, hardware backups, TLS private keys, or enrollment secrets in public GitHub history. No false statements that a successful compilation proves functional compatibility. Preserve Charlie's approved runtime and all evidence. Continue through eligible implementation rather than stopping at source-provenance uncertainty; reserve genuinely hardware-dependent testing for the supervised session.

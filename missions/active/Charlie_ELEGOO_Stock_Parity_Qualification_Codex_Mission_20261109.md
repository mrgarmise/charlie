# Charlie / ELEGOO S3 — stock-preserving qualification and replacement-readiness mission

**Prepared 2026-11-09.** Use a new isolated development branch and draft PR. **No ESP32 flashing, service restart, deployment, physical motion, Wi-Fi switching, merging, modifications to the approved runtime or original backups.**

## Owner's decision

The owner wants the ELEGOO camera board's AP-only network changed to reliable shared-LAN Wi-Fi *without losing any working feature*. The existing camera, UI, TCP/Arduino bridge and manual drive remain valuable. The user does **not** want a second ESP32 for qualification and accepts that a carefully reviewed first on-device flash will eventually be needed, with the preserved stock image for recovery. They do **not** authorize any flash yet.

An independently built replacement is available in **Charlie draft PR #30** at commit `ea2172ae84f16e7efe9d661301ce649672da69b3`, based on firmware core **PR #29** and Pi provisioning **PR #28**. The OPI/QSPI images have native builds, image geometry validation and host tests but no physical runtime proof. Critical deliberate differences: motor forwarding OFF, legacy motor HTTP 403, changed Factory boot tag. Do not misrepresent this as stock parity. Keep PR #30 draft and unchanged unless making a separately reviewed follow-on branch.

## Newly discovered independent source leads — audit before reinventing

1. **JocelynWordSmith/elegoo-custom-firmware**, https://github.com/JocelynWordSmith/elegoo-custom-firmware . Public custom replacement for ELEGOO Smart Robot Car V4.0 ESP32-S3; README claims PlatformIO-built HTTP camera/control, MJPEG, TCP port 100, STA Wi-Fi and OTA. Also rewrites Arduino UNO firmware, uses **115200 baud and a different command protocol**. This is NOT a drop-in replacement for Charlie's stock 9600-baud UNO, and its published documentation is not independent on-hardware verification. Review code, issues, history and test evidence; use it as source of hardware/PSRAM/OTA/stream comparisons. Do not import its alternate motor protocol or insecure credentials/OTA into our firmware.
2. **UMRoboticsTeam/umrt-outreach-robotcar-wireless**, pinned `elegoo-kit-face` commit `a92013016d2386cd4ed2e0e7893b018f04b89cfc`, `ESP32_CameraServer_AP_2023_V1.3` is the candidate already integrated into PR #30. README identifies ELEGOO ESP32S3 Camera V1.0. Validate changed stock behavior rather than assuming it is exact factory source.
3. **ELEGOO official tutorial**: https://us.elegoo.com/blogs/learn/elegoo-smart-robot-car-v4-0-with-camera-upload-code-to-the-camera-module and https://us.elegoo.com/blogs/arduino-projects/elegoo-smart-robot-car-kit-v4-0-tutorial . These link camera FAQ/source downloads. Investigate whether an *official 2023 S3 camera source* package is obtainable; do not confuse official archived ESP32-WROVER firmware or latest UNO-only repository with S3 source. Record exact provenance/checksum and compiler configuration if found.
4. https://forum.arduino.cc/t/solved-esp32-wifi-not-seen-by-phones-elegoo-smart-robot-car-v4/1017215 documents user compiling/restoring older V4 camera firmware, but is NOT proof for our exact S3.

## Required work

### A. Establish replacement feature parity

- Compare baseline stock behavior based on known successful Charlie ELEGOO manual-driving/MJPEG/recognition results and the owner's existing runtime code, qualifying claims as observed-via-history rather than measured today.
- Audit UMRT source and PR #30 against JocelynWordSmith and any official S3 sources for: actual camera sensor/pinmap/PSRAM mode, HTTP80 routes and UI controls, MJPEG81 path/framerate/headers, TCP100 accept/framing/heartbeat, UART 9600 GPIO3/40, FactoryTest initialization, startup STOP, existing Arduino UNO `N` command semantics, stop behavior, AP identity and rescue flow, credential/NVS partitions, 8MiB flash, security boot/eFuses, USB BOOT mechanism, bootloader and OTA state.
- Make a table with statuses **stock behavior directly measured**, **stock code evidenced**, **ported source evidenced**, **native-built**, **host-tested**, **hardware unverified**, **deliberate regression**. For any missing behavior, propose a security/safety-preserving restoration and implement eligible fixes in a *new* draft PR, with focused tests. Preserve qualified Pi motion-authority gates; do not casually expose unauthenticated legacy motor endpoints or enable forwarding just to claim parity. Where full legacy convenience conflicts with proper safety, propose an explicit authorized qualified-control alternative.
- In particular resolve the production motion architecture: how manual drive remains usable over the new LAN *through QualifiedElegooExecutor* while the replacement firmware retains safe stop and exclusive UART ownership. Decide and test the necessary authorizing mechanism and on-device forwarding gating, without enabling actual motors or flashing. Do not leave motor forwarding permanently unavailable and call the replacement complete.
- Explain whether original factory-ready tag must be emitted and how to preserve required UNO initialization safely.

### B. Exhaust available **non-invasive** evidence before flash

- Review the 8,388,608-byte stock full-flash backup **locally only, read-only** if the accessible environment actually permits, for nonsecret bootloader/app metadata, board/flash interface/security/PSRAM clues, partition/OTA descriptors, version strings and provenance. Never print/commit raw NVS, SSIDs/passwords, tokens, keys, or personal data. Explicitly label what binary inspection cannot reveal.
- Form a concise **read-only live-stock baseline worksheet** using existing Charlie camera owners, approved operational capture paths or supervised normal terminal when needed. Prioritize observations with **no ESP32 reset/bootloader and no motor commands**: camera JPEG/MJPEG/UI endpoints, resolution/headers, TCP protocol if an existing approved client can passively log, AP and stream behavior, existing script/config sources, stock Arduino UNO protocol. Prefer collecting evidence through existing qualified client and subscription owners; avoid parallel camera/TCP consumers and commands that could themselves trigger movement.
- Separate any BOOT/reset/eFuse/security queries requiring a maintenance window; they are **not** authorized as part of unattended Codex.
- Define an objective evidence ledger: item, source, command, observed result, remaining uncertainty, how to test, and pass threshold. No sweeping claim that tests prove hardware.

### C. Actual readiness decision and rollback

- Re-run relevant focused suites, C++ sanitizers, native OPI/QSPI builds (only if changed), image/partition/integrity checks. Inspect pinned Arduino-ESP32 2.0.17 versus available official S3 build settings. Verify the exact candidate image file hashes and private stock backup hash in local normal filesystem *only if available; otherwise mark as operator-check*. Never place binaries or credentials in public Git.
- Assess whether it is possible to determine OPI vs QSPI conclusively without writing firmware; identify the smallest authorized read-only operator action. Do not guess from 8MiB PSRAM capacity.
- Document a realistic first-flash path **for later authorization**: stock backup integrity, preflight, exact selected target and offsets only after security/active slot evidence, preservation of NVS/SPIFFS/otadata, verified UART/stop first, network and camera next, then authorized qualified control, pass/fail/rollback criteria. Do not claim the presence of a backup guarantees successful recovery under every secure-boot or hardware failure condition.
- If stock parity cannot be proven without ever booting replacement on the same board, state that plainly and propose a bounded supervised trial on the existing board **after all eligible offline and stock-live checks**. No second board purchase recommendation; owner specifically declines.
- End with a **GO / CONDITIONAL GO / NO GO** assessment for authorization of that later trial, listing exact blockers, not a generic caution list.

## Outputs

Publish a fresh *draft PR* containing a concise `docs/elegoo-network/stock-parity-review.md` (or similar), a no-flash operator worksheet and report; eligible tested fixes in a separate implementation branch if needed. Preserve original PR #28/#29/#30 and original approved runtime. Include all external source URLs and pinned commits/tags checked. Provide actual evidence links and CI results, distinguish independent external hardware success claims from unaudited README claims, and identify what the user should execute manually in the ordinary Pi terminal if device nodes remain sandbox-hidden.

**Do not spend a mission redoing unrelated full Charlie CI, rebuilding the entire network stack, or trying to circumvent sandbox serial permissions. Do not authorize flash, restart, merge, deploy or physical movement.**

# Source provenance and compatibility boundary

Owner-selected baseline: UMRoboticsTeam/umrt-outreach-robotcar-wireless,
branch elegoo-kit-face, exact a92013016d2386cd4ed2e0e7893b018f04b89cfc,
ESP32_CameraServer_AP_2023_V1.3/. Independently cloned/read at that commit.
https://github.com/UMRoboticsTeam/umrt-outreach-robotcar-wireless/tree/a92013016d2386cd4ed2e0e7893b018f04b89cfc/ESP32_CameraServer_AP_2023_V1.3
Original SHA256 manifest for every source-directory file: upstream-manifest.json.
No installed-source equivalence is asserted. Official WROVER and Arduino-controller
sources from the earlier investigation are not this integration baseline.

Integration base is Charlie PR29 exact b71cd3dd917b83aff3b643795a76dab3ac5b42ed.
Original PR28 c8a7a8d471130e40d9a5ecf827870118f3757b8f provides the pinned TLS peer;
neither PR head is rewritten or merged. New branch feature/elegoo-s3-camera-integration-20261109.
Original mission: missions/active/Charlie_ELEGOO_S3_Camera_Firmware_Integration_Codex_Mission_20261109.md
on missions/library-archive-20261109, copied as MISSION.md with its SHA in REPORT.md.

The fork declares Mozilla Public License 2.0 in its root LICENSE. That full text
is retained in licenses/MPL-2.0.txt. app_httpd.cpp retains its original Espressif
Apache-2.0 copyright/license header; licenses/Apache-2.0.txt provides that full text.
Original authorship comments are retained in adapted camera source. Fork camera UI
assets are retained with their names/attribution and exact hashes. No additional
rights in third-party logos or sensor/model libraries are inferred. Bundled camera,
ESP-DL, TLS and WiFi SDK libraries remain supplied by pinned Arduino-ESP32 2.0.17,
with that distribution's licenses. Corresponding modified source is provided here.

## What is copied or changed

| File | Treatment |
|---|---|
| camera_index.h, camera_index.html, camera_pins.h | Byte-identical to pinned baseline; hashes tested. Compiled UI remains the original embedded gzip asset. |
| CameraWebServer_AP.cpp/.h | Camera/sensor initialization retained; config zero-initialized; networking/AP credentials removed; explicit Arduino include; returns camera availability. Source still selects S3_EYE. |
| app_httpd.cpp | Camera routes/stream/camera controls and embedded UI retained. Unauthenticated /keypress and /json_command remain addressable but return403, with no UART writer. Socket/time limits added. Face enrollment remains RAM-only: original layout has no fr partition, so no new partition or flash-ID write is attempted. |
| Original .ino | Reconstructed as ElegooS3Camera.ino plus MotorBridge: bounded, nonblocking actual-session framing/heartbeat/STOP; separate FactoryTest; no AP station count in motion-session admission. |
| config.h, original AP fields in .h | Deliberately NOT vendored: fork-specific AP name/default password are not production defaults. Original hashes remain in the manifest, without publishing those values again. |
| NetworkCore.h | Exact portable core copy from PR29. |
| ArduinoPlatform.h | PR29 implementation copy, updated provenance comment; same real WiFi/Preferences behavior. |
| New runtime/server/identity/policy/tools | Original Charlie integration code. Networking has one state owner; provisioning never imports or writes the motor UART. |

## Evidence classes and baseline-versus-target matrix

| Contract | Observed in selected source | Candidate behavior | Reported on car / remaining verification |
|---|---|---|---|
| AP | AP-only, fixed subnet192.168.4.1, fork-specific identity/settings | AP+STA; MAC-based stable ID; generated private AP secret from physical enrollment; same recovery subnet by default | Original AP/video/bridge reported working; actual AP settings and association/channel behavior unverified here |
| Pins/PSRAM | CAMERA_MODEL_ESP32S3_EYE: XCLK15, SCCB4/5, D0..D7=11/9/8/10/12/18/17/16, VSYNC6/HREF7/PCLK13; psramFound adaptive buffers | Same mapping/initial JPEG UXGA, two PSRAM buffers, then SVGA; native OPI and QSPI candidates | 8MiB flash/8MiB PSRAM reported; physical mapping/interface mode NOT established by memory size or compilation |
| Camera | HTTP80 /, /status, /control, /capture; MJPEG81 /stream; embedded UI | Same routes/assets; two page sockets/one stream socket; face IDs RAM-only | Native frames/UI/parity, sensor ID, latency, exposure freshness and memory load pending |
| Motor HTTP | /keypress and /json_command directly write Serial2 without a qualified session | Routes return403. Camera /control remains functional. No alternate motor writer or insecure bearer fallback | Deliberate safety hold, not claimed native motor-UI parity |
| TCP100 | Blocking local client; strips insignificant spaces; {Heartbeat}; N100 on disconnect; AP count incorrectly ends STA-only session | One nonblocking accepted client; 256-byte frames;500ms partial-frame deadline;1s heartbeat/4s expiry; reset on close; STOP priority; real session controls lifetime | Wire timing, ACKs, physical stopping, UART congestion and original Arduino semantics need supervised measurement |
| Motion admission | Reference blindly forwards non-heartbeat frames | Default CHARLIE_ENABLE_MOTOR_FORWARDING=0; optional forwarding code host-tested with UART stubs, not enabled in native candidate | Existing QualifiedElegooExecutor and physical authority remain mandatory; no reconnect grants movement |
| UART/factory | Serial2 9600 RX3/TX40; factory tags, WA indicators, GPIO46 | Same candidate pins/rate/tags; one writer; FactoryTest sees explicit session state and AP indication separately | Hardware pin/electrical/LED behavior, exact tag parity and local watchdog still unqualified |
| Provisioning | Absent | TLS443 only; GET/v1/network and POST prepare/confirm, bounded bodies, fixed token comparison, strict Host/Origin, serialized owner queue, ACK before association | TLS/radio load, real netif behavior and CA enrollment require native acceptance |
| Trust | No secure enrollment | Short boot-window physical USB+BOOT authorization; unique name-constrained CA/leaf/token/AP secret; NVS identity; no default secret/TOFU | GPIO0 BOOT access and native USB behavior must be checked before enrollment; no physical enrollment performed |
| Two phase | Absent | RAM pending credentials; target STA socket/SSID/transaction validation before atomic active-record NVS commit; idempotent completed receipt; lease/reboot rollback | Power loss, wrong credentials, AP channel changes and actual primary-network independence pending |
| Storage | Embedded UI; face code requests fr partition | Original six-partition geometry; no SPIFFS mount/erase/write or boot-selection/OTA writer; dedicated NVS namespaces only after authorization | Original table parsed offline; live boot selection, security/eFuses, installed source and current storage unknown |

Private backup independently hashes to c196e9077be06b3f61f6acfcf66219fe0535b60ae1d26183c43b2de80ff25c5b,
8,388,608 bytes. Only fixed nonsecret header fields were inspected: boot e903023f,
app0 e905023f (DIO header,80MHz,8MiB). This does not establish actual QIO boot setup,
PSRAM bus mode, eFuse state, source equivalence or permission to flash. No raw backup,
NVS values, keys or credentials are included in this branch.

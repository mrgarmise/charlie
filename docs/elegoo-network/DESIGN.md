# ELEGOO network implementation and acceptance boundary

Development base: operational-consultation 8d44c81c80024ab0ff9aff9f636859928a5ab45f
(includes manual-drive safety continuation 169cc36). Inventory 2026-11-09:
`~/charlie` absent, `~/Projects/charlie` is older agency work with untracked evidence;
`~/charlie-manual-drive` preserved. Work is isolated in /tmp/charlie-network-provisioning.
Open PRs #3–#27 remain unchanged. The operational branch is newer than #27 and
contains the existing qualified manual-drive stack; no merge is implied.

Stationary approval under ~/charlie-ops/QUALIFICATION.md: no motion authority,
no service/autostart, no automatic source promotion. Approved runtime untouched.
Private 8 MiB backup read-only SHA256 verified against supplied value. Its directory
README is older and says no image exists; this mission does not rewrite that receipt.
No device access or live NetworkManager calls were attempted.

## Component map and contract

- stimulus.bus owns observations; `elegoo-network` is network health, never pose or
  motion authority. Existing MobileConsole.status includes this source automatically.
- ui.dashboard has opt-in `/api/network` status and operation dispatch, within its
  existing Host/Origin/auth/body limits. Mutations need a separate network token
  and a locally armed one-use intent. No raw Wi-Fi credentials enter dashboard APIs.
- networking.service holds at most one local intent and one worker. Nothing starts
  automatically; constructing an adapter does not change networking.
- networking.provisioning separates passive poll/backoff from explicit provision.
  Only provision can call adapter methods; poll cannot switch Wi-Fi or command motors.
- networking.transport separates untrusted DNS-SD/addresses from certificate-pinned
  TLS identity. The enrollment token is sent only after exact certificate pin match.
- networking.adapters uses saved NetworkManager setup profiles and scoped daemon
  rollback checkpoints. python3-dbus is a native OS dependency; zeroconf (0.148.0)
  is an optional discovery dependency. Neither is imported by normal startup.
- Existing camera HTTP 80/MJPEG 81 and qualified TCP 100/UART behavior are unmodified.
  Manager has no executor or motor transport reference. Reconnection cannot resume
  motion. Existing controller heartbeat/STOP gates remain authoritative.

Enrollment: operator physically verifies stable device ID, TLS certificate SHA256
and a freshly generated >=256-bit device token through a separately authorized
USB/physical procedure. Save Enrollment via SecretStore in an owned 0700 directory;
files are 0600, atomic and fsynced. No TOFU or automatic password extraction.
Device identity is independent of IP and source interface; future VPN/relay can
supply an Endpoint behind the same pinned identity without implementing motion.

Protocol v1, TLS 1.2+ port 443, maximum response 4096 bytes:
`GET /v1/network` -> device_id, joined, transaction; authenticated response also
contains ssid for private target verification. `POST /v1/network/prepare` accepts
ssid/password/128-bit transaction/lease_seconds <=90, acknowledges
{accepted:true,transaction}. `POST /v1/network/confirm` accepts transaction only
and returns {verified:true,transaction}. Confirmation requires a fresh target-LAN
probe bound to configured LAN source IP, matching pin, identity, SSID and transaction.
Setup subnet is excluded from LAN discovery. DNS-SD instance is
`<device-id>._charlie-elegoo._tcp.local.`. Candidate and response bounds apply.
No token, SSID, password or arbitrary server error appears in status/telemetry.

Prepare acceptance, target association and verified success are separate states.
The firmware must keep prior credentials/recovery AP until confirmation or bounded
rollback. After process death no device transaction may remain authoritative beyond
its lease. AP+STA shares one 2.4 GHz radio; STA channel changes can move the AP channel,
so setup HTTP loss is expected, never proof of successful target join.

Primary switching is permitted only with allow_setup + allow_primary + separately
acknowledged_disconnect. It deliberately interrupts a management session using that
interface. Secondary names and saved setup profiles are configurable. No new
connections or credentials are passed through shell/argv. Each setup adapter gets
its own checkpoint before activation; rollback must verify its original saved
connection before target verification. An absent secondary is not a prerequisite
failure when primary is explicitly authorized. Restoration failure is a failure,
not provisioning success. Never destroy somebody else's checkpoint.

## Firmware compatibility blocker

Reference UMRoboticsTeam/umrt-outreach-robotcar-wireless `elegoo-kit-face` exact
commit a92013016d2386cd4ed2e0e7893b018f04b89cfc. Reference selects ESP32S3_EYE,
UART 9600 RX3/TX40; camera HTTP80/MJPEG81, TCP100. Its custom AP values are not
production defaults and are not copied. Blocking SocketServer_Test uses local
WiFiClient and AP station count; it would reject a STA-only session. Heartbeat
breaks after four missed intervals and emits N100 stop on session exit. FactoryTest
has no client variable: any naive replacement using that local client there will
not compile. FactoryTest reports AP station status and must be tested independently.
Reference framing strips spaces, recognizes {Heartbeat}, and forwards other braces;
its source is not authenticated provisioning firmware.

Official archived source at elegooofficial/ELEGOO-Smart-Robot-Car-Kit-V4.0 commit
096094e07dc7e5eea8c986986158e2d9111dab64 ships ESP32-WROVER-Camera.zip,
ESP32_CameraServer_AP_20210107. This is not evidence of the installed S3 source.
Official New repo commit 76d82704b20b8b38d3eb874afd865b349cbc1a48 contains Arduino
car-controller code only. Neither establishes installed S3 source/pin/PSRAM equivalence.
Sources: https://github.com/UMRoboticsTeam/umrt-outreach-robotcar-wireless/tree/a92013016d2386cd4ed2e0e7893b018f04b89cfc
and https://github.com/elegooofficial/ELEGOO-Smart-Robot-Car-Kit-V4.0/tree/096094e07dc7e5eea8c986986158e2d9111dab64 .

Faithful firmware replacement is blocked pending matching S3 source and observed
board mapping. The Pi protocol implementation is usable with conforming endpoints,
but installed firmware does not yet implement this API. It is not hardware provisioning.
No ESP32 toolchain is installed; no Arduino image compile/size/checksum is claimed.
Do not flash a reference or host-test executable. Source/firmware qualification is
separate from software validation and must preserve SPIFFS/NVS/partitions.

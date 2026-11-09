# ELEGOO provisioning firmware core — NOT FLASHABLE

This separable firmware-source increment implements a nonblocking two-phase
network lifecycle, a candidate Arduino WiFi/NVS adapter, a setup page, a control-
session guard and an offline image gate. It is **not** a replacement camera sketch.
The matched installed S3 source is an essential unresolved hardware/source boundary.
TLS API/server integration, native Arduino compilation and image generation are
blocked pending that source; no complete firmware or hardware provisioning is claimed.

Reference: UMRoboticsTeam/umrt-outreach-robotcar-wireless/elegoo-kit-face,
commit a92013016d2386cd4ed2e0e7893b018f04b89cfc. Its camera selects S3_EYE,
RX3/TX40 9600, HTTP80/MJPEG81 and TCP100. The fork's custom AP values and UI are
not copied. Its AP-station-count disconnect is wrong for STA-only sessions;
FactoryTest has no access to SocketServer_Test's local client. The blocking socket
loop, unbounded brace buffers and static heartbeat timestamp also need a faithful
reviewed migration. New code is original; no forked camera source is vendored.

Official archive elegooofficial/ELEGOO-Smart-Robot-Car-Kit-V4.0 at
096094e07dc7e5eea8c986986158e2d9111dab64 contains WROVER 20210107, not matching
S3 source. Official New at 76d82704b20b8b38d3eb874afd865b349cbc1a48 contains
Arduino car-controller code. Neither proves installed source equivalence. Preserve
existing camera routes/UI/SPIFFS/UART framing when a matched source is supplied.
No motors, device nodes, NetworkManager or operational runtime are accessed here.

## Host validation

```sh
g++ -std=c++17 -Wall -Wextra -Werror -pedantic -fsanitize=undefined firmware/elegoo-network/tests/core.cpp -o /tmp/elegoo-network-core-tests
/tmp/elegoo-network-core-tests
```

Five scenario groups cover accepted/joined/verified separation, wrong target,
replay/concurrency, lease expiry, old-credential recovery, commit failure, timer
wrap, actual TCP disconnect, heartbeat expiry despite Wi-Fi association, no auto
forwarding after reconnect, and FactoryTest link state independently of the socket
variable. This is callback simulation, not measured UART or physical stopping.
Initial ASan+UBSan run reached LeakSanitizer's sandbox ptrace restriction; standalone
UBSan build/run passes. Hosted CI runs ASan+UBSan independently on Ubuntu.

## Integration contract and remaining build gate

Candidate dependency pin: Arduino-ESP32 **2.0.17**, bundled WiFi/Preferences,
no third-party JSON or crypto dependency. It is a candidate pin, not a proven
compatible toolchain for the installed source. Platform files compile only after
matching source review. `NetworkCore.h` is host compiled independently.

An authorized HTTPS listener must authenticate every API request using a per-device
random enrollment token with constant-time comparison. TLS keys/certificate/token
and recovery AP settings require a separately authorized physical/USB initial
installation, private storage, and out-of-band certificate SHA256 verification.
No unauthenticated enrollment, HTTP bearer fallback, default secret or TOFU.
Do not expose stored credentials or arbitrary exception text. Serve setup.html/js
on HTTPS with no-store and CSP default-src 'self'; frame-ancestors 'none'.
No cross-origin access, query-string tokens, credential logs or debug body dumps.
Rate-limit auth failures and serialize all lifecycle operations on one owner.

Implement the Pi PR #28 contract: GET /v1/network; POST prepare and confirm,
bounded <=4096-byte JSON. Return acknowledgement BEFORE scheduling first tick.
Authenticate and validate transaction/SSID/password/lease before calling prepare.
Status must distinguish active association from transaction join. A confirmation
may call confirm(id,true,now) only when received on the STA target LAN interface,
not on recovery AP. Browser setup cannot independently confirm; it waits for Charlie.
The page's transaction must be provided to an explicitly authorized Charlie verify
operation; automatic browser-only persistence is intentionally unavailable.
The current Pi prepare flow generates its own transaction; browser-to-Pi transaction
handoff remains blocked with HTTPS endpoint integration, not a completed route.

NetworkCore stages credentials only in RAM; active NVS is committed on LAN confirm.
Pending operation expiry or reboot retains old credentials; recovery AP stays up.
ArduinoPlatform stores only its own versioned active blob; NVS provides atomic key
replacement. This is flash persistence, not flash encryption. Review security/eFuse
settings and physical threat model before hardware use. Do not overwrite existing
NVS or SPIFFS. AP+STA shares one radio; target association can move the setup AP's
channel. Lost setup HTTP does not indicate success. Stable ID comes from the
verified device MAC, never AP SSID/IP, with pinned TLS identity; use DNS-SD service
_charlie-elegoo._tcp on port443 after HTTPS initialization. No internet dependency.

ControlSession must be bound to the actual accepted TCP client lifecycle; reset
all parser/heartbeat state at open, close on malformed/oversize data, stop callback
through the EXISTING UART owner, never via a second writer. Invoke tick at bounded
cadence in a nonblocking socket loop, never gate it on AP count or WiFi.status().
No provisioning handler writes motor commands. Existing qualified Pi executor and
independent motion admission remain required. Reconnect only enables fresh
heartbeat processing and never replays a movement. FactoryTest receives explicit
session state separately. Preserve exact {Heartbeat}, UART brace framing and N100
safe-stop semantics only after source and Arduino-side qualification.

After matched-source review, exact local-terminal build template (NOT upload):

```sh
arduino-cli core install esp32:esp32@2.0.17 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli compile --fqbn 'esp32:esp32:esp32s3:FlashSize=8M,PSRAM=opi' --build-path /tmp/elegoo-reviewed-build "$MATCHED_REVIEWED_SKETCH"
python firmware/elegoo-network/check_image.py "$REVIEWED_APP_BINARY"
python -m esptool --chip esp32s3 image-info "$REVIEWED_APP_BINARY"
sha256sum "$REVIEWED_APP_BINARY"
```

FQBN/PSRAM mode must be verified against actual board before using the template;
no settings are inferred from memory size alone. Supply reviewed partitions.csv
only if byte layout matches the installed table. Image gate checks S3 header and
<=0x330000 size; it does not prove source compatibility, valid checksum/signature,
SPIFFS preservation or native safe-stop. No app binary exists so its checksum is
unavailable. There is no placeholder or generated flashable artifact.

Flashing and rollback are NOT authorized. Follow the detailed operator runbook in
Pi PR #28 docs/elegoo-network/OPERATOR.md after separate written authorization.
Exact persistent ESP32 USB identity/MAC and private original backup must be verified;
never access RP2040. App-only flashing cannot be proposed as safe until boot
selection/security/partition compatibility is proven. Full restore would overwrite
NVS/SPIFFS/enrollment and requires its own review. No motion testing under this mission.

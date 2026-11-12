Current follow-on policy and validation: [QUALIFIED_CONTROL.md](QUALIFIED_CONTROL.md). Historical PR30 reports below describe the earlier pinned candidate.

# ELEGOO S3 camera/network integration — BUILD ONLY, DO NOT FLASH

This is a complete candidate sketch based on the owner-selected UMRT S3 camera
source a920130 and the already-tested Charlie PR29 network core. It retains camera
HTTP80/MJPEG81, the embedded UI and UART/TCP100 contracts, and integrates TLS443
provisioning. Source identity with the installed image and physical compatibility
are NOT proven. No hardware qualification, installation or deployment is implied.

See PROVENANCE.md for the file manifest, licenses and compatibility matrix;
REPORT.md for actual builds/tests; ACCEPTANCE.md for the later supervised process.
The original PR28/PR29 heads, approved Charlie runtime and private backup are intact.

## Design and trust

- One NetworkRuntime task owns all Wi-Fi/NVS network transitions. HTTP handlers
  send bounded value requests through queues. The existing NetworkCore separates
  accepted, joined and verified. Association starts only after the response is sent.
  Unacknowledged/unconfirmed transactions expire within their device lease; reboot
  loses pending RAM credentials and retains only previously confirmed credentials.
- One MotorBridge owns Serial2 and the actual TCP client/session. Framing is bounded
  to256 bytes and500ms; UART work per tick is bounded; raw TCP sends are nonblocking.
  Heartbeat is1s, expiry4s. EOF, malformed/oversized/expired framing or congestion
  closes the session and prioritizes N100 STOP. A reconnect resets all parser and
  heartbeat state and cannot replay an old command. AP count never controls safety.
  FactoryTest receives explicit session state and shares the same UART writer.
- Follow-on candidate uses a closed per-command authenticated gate; see QUALIFIED_CONTROL.md. PR30 remains observation-only at its pinned commit.
  Forwarding implementation is compiled/tested on the host with UART capture stubs;
  changing that gate needs separate source review, physical qualification and a new
  runtime/firmware-bound grant. Existing QualifiedElegooExecutor admission is never
  replaced. The old unauthenticated HTTP motor routes return403, deliberately.
- TLS443 uses ESP-IDF's HTTPS server with a physically provisioned per-device leaf
  key/certificate and random bearer token. No HTTP bearer route, default secret,
  network enrollment reset, TOFU or permissive CORS. Host and Origin are checked;
  token comparison has fixed bounds; bodies<=512 bytes, exact schemas and short
  receive/job deadlines. Status exposes only authorized network state, never keys,
  tokens or passwords. Setup is served over verified HTTPS at /setup.
- Initial identity is accepted only through native USB during a60s boot window while
  the candidate BOOT GPIO0 input is held AFTER normal boot. No Wi-Fi, camera or UART
  opens until a valid identity is present. Invalid/unavailable enrollment fails
  closed. Existing identity has no remote reset path. Hardware BOOT wiring/native
  USB behavior must be checked in the separately authorized acceptance session.
- make_enrollment.py generates a per-device name-constrained CA, leaf, token and AP
  secret in a new0700 directory, files0600. The CA private key stays on the operator
  host; only the leaf key reaches the device. The CA is restricted to this device's
  .local name and recovery IP. Verify its fingerprint out of band before narrowly
  trusting it in the browser; never bypass certificate warnings. The Pi uses an exact
  locally enrolled leaf SHA256 pin before sending any credential.
- NVS writes use dedicated charlie-id and charlie-net namespaces. Pending Wi-Fi
  credentials remain in RAM; only a matching confirmed target is stored. Confirmation
  must arrive on the actual STA local socket address, distinct from the recovery AP,
  with matching target SSID/transaction. Duplicate completed receipts can be answered
  without a second write. The recovery AP is not disabled by station loss.

## Endpoints and browser-to-Charlie handoff

Authenticated GET /v1/network returns device_id, joined, verified, transaction, ssid.
POST /v1/network/prepare accepts exactly ssid,password,transaction,lease_seconds1..90;
response is {accepted:true,transaction}. POST /v1/network/confirm accepts transaction
and returns {verified:true,transaction}. Errors contain no request/exception text.
Protocol is compatible with PR28 TLSProtocol at c8a7a8d. Discovery advertises
<device-id>._charlie-elegoo._tcp.local. on443; stable ID is elegoo-<12hex STA MAC>.

Browser setup explicitly initiates a90s attempt and downloads a JSON ticket holding
only device ID, SSID, transaction and lease. It clears password/token fields and
never persists them in page storage. On Charlie, with the reviewed PR28 checkout:

```sh
PYTHONPATH=/path/to/reviewed-peer python firmware/elegoo-s3-camera/verify_ticket.py \
  --ticket /private/charlie-elegoo-verification.json --enrollments /private/enrollments \
  --lan-ip CHARLIE_TARGET_LAN_IP --device-id VERIFIED_DEVICE_ID --authorize-confirm
```

This real verifier discovers on the explicitly selected LAN IP, authenticates using
PR28's private SecretStore/TLSProtocol, validates transaction and target SSID, and
confirms within the device lease. It imports no NetworkManager, camera or actuator
stack. The ticket never supplies a trusted endpoint or certificate. An expired or
wrong ticket cannot commit. The command outputs a sanitized verification receipt;
it does not manufacture a dashboard transaction success. The existing registry can
passively authenticate the online device; no automatic runtime startup/rebinding is
added. The operator must prepare this handoff before initiating the90s browser lease.

AP+STA shares one radio and STA association can move the AP channel. A lost setup
HTTP response is not a success receipt. The legacy recovery subnet is192.168.4.0/24;
a target LAN overlapping it requires explicit reviewed discovery configuration and
native routing acceptance. Never relax the STA-local-versus-AP confirmation check;
identical AP/STA local IPs fail closed. IPv4 target verification is implemented;
IPv6 hardware behavior is not qualified. No internet is required.

## Reproducible native build, never upload

Pinned candidates: Arduino CLI1.2.2; Arduino-ESP32 2.0.17 / IDF4.4.7; bundled
xtensa-esp32s3 GCC8.4.0; bundled WiFi/Preferences/ESPmDNS/esp_https_server/cJSON/camera/
ESP-DL. FQBN uses esp32s3,8M flash, default_8MB overridden by the exact local
partitions.csv, QIO80MHz candidate boot, native USB hardware CDC/JTAG enabled.
Both OPI and QSPI PSRAM variants are built; neither mode is inferred from capacity.
The original image header is DIO80MHz/8MiB, which does not prove QIO boot setup.

```sh
arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install esp32:esp32@2.0.17 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
python firmware/elegoo-s3-camera/tools/build.py --arduino-data /path/to/arduino-data --build-dir /private/build-opi --psram opi --clean
python firmware/elegoo-s3-camera/tools/build.py --arduino-data /path/to/arduino-data --build-dir /private/build-qspi --psram qspi --clean
```

An optional --cli/--config-file selects an isolated installation. The script captures
exact commands/versions, verbose logs, source hashes, binary SHA256, esptool4.5.1
image_info and all six generated partition entries. It refuses source changes during
compile, wrong S3 header, over-slot image or changed geometry. No device/upload flag
exists. Generated bootloader/partition binaries are build byproducts, NOT approved
flash artifacts. NVS/SPIFFS images are never created. Build outputs stay outside Git.
Only build reports/logs are uploaded by CI; no credentials or backup bytes are used.

SDK16-socket budget: camera2 clients, stream1, TLS1; three HTTP listen/control pairs,
TCP listener/client and mDNS leave bounded headroom, not unlimited subscribers.
One TLS connection is documented by IDF as roughly40KiB; TLS task stack12KiB,
network8KiB and bridge6KiB are bounded. Native linker reports static memory, not
actual free heap under camera/TLS/face load. PSRAM buffers and optional face models
need measured native headroom; no peak-heap or safe-stop timing claim is made here.
The core's prebuilt application descriptor labels arduino-lib-builder/IDF4.4.7;
use the generated source hash/commit and file SHA256 to identify this candidate.

## Host and independent validation

```sh
python firmware/elegoo-s3-camera/tools/host_tests.py --sanitizers address,undefined
CHARLIE_PEER_ROOT=/path/to/reviewed-peer python -m pytest firmware/elegoo-s3-camera/tests -q
python tools/check_unified_contracts.py
```

Host bridge tests use real loopback TCP and a UART stub, including the compile-time
forwarding branch; no actual motor command is transmitted to hardware. Browser
fixtures trust only ephemeral test certificates and complete a real download-to-pinned
TLS verification flow. This test-only trust bypass is not a production enrollment
instruction. Independent CI installs Chromium and runs these tests, existing core
regressions/contracts and native builds. Actual radio, TLS heap/load, camera sensors,
UART/Arduino stop behavior and physical movement remain supervised hardware gates.

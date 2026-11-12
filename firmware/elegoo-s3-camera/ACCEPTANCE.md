# Later supervised acceptance and recovery — NOT AUTHORIZED BY THIS MISSION

No command in this document was run against a device. No flash/deploy/merge, Pi
network change, service restart, RP2040 interaction or motor actuation is authorized.
A successful native compile is not a flashability or physical safety certificate.
Keep the original stationary approval and source/runtime-bound motion holds intact.

## Read-only baseline before considering any write

1. Record owner authorization, exact approved runtime/source SHA, qualification and
   independent cutoff. Preserve all running owners/evidence. Identify the ESP32 by
   persistent path only:
   /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_30:30:F9:0D:B0:E8-if00.
   Confirm VID:PID303a:1001 and MAC30:30:F9:0D:B0:E8. Never open the separate RP2040
   2e8a:0005 or a numbered ttyACM chosen by assumption. OS inventory commands such as
   `readlink -f "$VERIFIED_ESP32_PORT"` and `udevadm info --query=property --name "$VERIFIED_ESP32_PORT"`
   read metadata; they are not a device firmware identity receipt.
2. With motors disconnected/electrically isolated and the car off during wiring,
   establish one authorized UART/command owner or passive logic-analyzer observer.
   Do not open a second camera acquisition owner or direct motor transport.
   Record installed AP name/subnet, camera/bridge hosts and network connection UUIDs
   privately. Do not publish Wi-Fi passwords, frames of people or enrollment keys.
3. Through the existing camera owner/subscriber, record current /status, JPEG capture,
   UI and MJPEG81 content type/boundary/resolution/rate/latency. If that owner is stopped
   under separate authorization, example bounded observations are:
   `curl --max-time 3 "http://$VERIFIED_CAMERA_HOST/status"` and
   `curl --max-time 2 -D /private/mjpeg-headers.txt -o /dev/null "http://$VERIFIED_CAMERA_HOST:81/stream"`.
   The expected stream is multipart/x-mixed-replace;boundary=123456789000000000000987654321.
   Test /control using only explicitly selected CAMERA settings. The installed fork's
   /keypress and /json_command may move hardware: never probe them with commands.
   Opening its old UI with keyboard/gamepad input can invoke those routes; isolate
   power and disconnect controllers before an authorized UI observation.
4. Port100 baseline requires exclusive maintenance ownership and isolation. Connecting
   can itself trigger the installed bridge's STOP/factory behavior. Through the existing
   qualified RX/heartbeat owner, record exact {Heartbeat} interval/echo, received frames,
   TCP EOF and stalled-heartbeat behavior. A passive connection may RECEIVE but must
   send no movement frames. Observe actual UART N100 timing with the existing owner or
   a passive analyzer; no second UART writer. Record RX3/TX40/9600 only after physical
   verification; verify Arduino-side N100 semantics and local failsafe independently.
5. Determine installed board/sensor, pin map, PSRAM bus mode, flash boot mode/frequency,
   active OTA selection and security/eFuse state. Memory size alone is insufficient.
   In a separately authorized isolated bootloader maintenance window, read-only storage
   queries may use pinned esptool4.5.1 with --before no_reset --after no_reset and
   --no-stub for chip_id, flash_id, get_security_info. Enter bootloader physically;
   these commands still interact with/reset-sensitive hardware and are not authorized
   now. Do not burn eFuses or use force/security-disable flags. Stop on any mismatch.
6. Verify the original full backup privately:8,388,608 bytes, SHA256
   c196e9077be06b3f61f6acfcf66219fe0535b60ae1d26183c43b2de80ff25c5b. Preserve it
   read-only and make no public upload. Compare current readback only under separately
   authorized maintenance; preserve original and new evidence, NVS/SPIFFS and OTA state.

## Candidate review and staged installation gate

- Review the exact draft PR commit/source hash, toolchain/FQBN, real image-info/hash,
  app slot<=0x330000, original partition geometry and all deliberate behavior changes
  in PROVENANCE.md. Select OPI or QSPI only from actual board evidence. Both binaries
  are unqualified candidates, not a pair to try blindly on hardware.
- Prove bootloader/app ABI, secure boot/flash encryption/secure-version compatibility,
  active OTA slot and original table before deciding what may be written. Generated
  bootloader/table byproducts are NOT permission to replace installed ones. There is
  no safe universal app-only command based solely on app0 being populated. Do not
  merge_flash a whole image, erase NVS/SPIFFS or rewrite otadata by convenience.
- Only after separate written owner authorization define a reviewed flash plan with
  exact device, offset, artifact hash, preserved regions, cutoff and rollback. Execute
  it in the normal Pi/Mint terminal with exclusive ownership; no sandbox bypass.
  No flash command is automatically executed or offered as a blind default here.
- Prepare unique enrollment offline using tools/make_enrollment.py in a private0700
  directory. Verify device ID and CA/leaf fingerprint physically. The CA private key
  stays on the operator host. The device receives only leaf chain/key, random token
  and AP secret through the bounded ENROLL line while BOOT/GPIO0 is held AFTER boot
  during the60s window. Verify GPIO0/USB behavior before this operation. Never compile
  credentials into the app, serve a bearer over HTTP or bypass browser TLS warnings.
  Copy only the private PR28 peer record into its owned0600/0700 enrollment store.

## Post-install acceptance, after the installation gate

1. Keep motor forwarding OFF. Confirm unique identity, recovery AP secret, TLS chain/
   pin and authorized /v1/network status. Unauthenticated/bad tokens, wrong Host/Origin,
   body overflow, malformed/duplicate JSON, wrong cert/ID and HTTP80 provisioning must
   fail. Identity reset must be unavailable over the network. Measure TLS handshake,
   free/minimum heap, task stack headroom and concurrent camera/stream/API load.
2. Verify original camera pins/sensor/PSRAM and real /status/capture/UI/stream parity.
   Confirm original SPIFFS data/table/OTA state remain unchanged. Face enrollment is
   intentionally RAM-only; no fr partition is allocated. Motor HTTP returns403.
3. Verify TCP100 framing and factory tags at9600/RX3/TX40 through the single UART owner.
   Measure disconnect/heartbeat/overflow/partial-frame/congestion STOP and no movement
   forwarding. Reconnect must require fresh heartbeat, clear buffers, retain pending
   STOP priority and never replay an old command. FactoryTest works with no TCP client
   and STA-only client with zero AP stations. Host callback tests do not prove stopping.
4. Provision several2.4GHz networks, with no internet required. Measure prepare receipt,
   target association and independent authenticated target-LAN confirmation separately.
   The browser saves a ticket; explicitly authorized Charlie verify_ticket.py consumes
   it using the pinned PR28 peer. Confirm on recovery AP, wrong SSID/transaction, expired
   lease and overlapping/identical STA/AP addresses must not create a false success.
   Test bad credentials, channel changes, response loss, duplicate confirm, stale IP,
   surprise loss and reboot/power loss before/after atomic commit. Retain recovery AP
   and prior credentials after unconfirmed failure; never infer success from a dropped
   AP connection or internet availability.
5. Use the existing Pi manager's separately authorized dual/single-adapter acceptance
   from PR28. A missing device must only mark offline/backoff; primary UUID/IP/routes/
   DNS and unrelated functions stay unchanged. No automatic startup or disruptive
   recovery. Actual deliberate primary switching needs its own connectivity-loss
   acknowledgement, daemon checkpoint and verified restoration. This firmware mission
   grants none of those live operations.
6. Forwarding/movement is a separate qualification mission. Changing the compile gate
   or reconnecting never creates motion authority. Keep existing QualifiedElegooExecutor,
   source freshness, calibration, independent interlocks and human supervision.

## Rollback — separate written authorization required

Stop the candidate under the approved cutoff/maintenance process and preserve failed
receipts, new private enrollment/confirmed NVS and relevant original state. Verify exact
ESP32 identity, backup hash and security/OTA compatibility again. Full restore at0x0
would overwrite bootloader, partitions, otadata, NVS, SPIFFS and coredump, including new
identity secrets; it is not an innocuous app rollback. An app-only restore similarly
requires proof of the selected slot, compatible original image and security settings.
Define the smallest proven restore plan; do not force a signed/encrypted mismatch or
burn eFuses. Read back and independently verify the authorized restored bytes and
stationary camera/UART safety behavior. Approved Pi runtime/source remains separately
pinned; no reset/clean/merge of another checkout. No rollback was needed or executed
by this build-only mission.

# Operator acceptance — NO FLASHING OR NETWORK SWITCH IS AUTHORIZED

Software only, isolated checkout:

```sh
python -m pytest tests/networking tests/test_mobile_console.py tests/test_mobile_http.py -q
python tools/check_unified_contracts.py
```

Optional development dependencies: Python 3.12, zeroconf==0.148.0 and OS
python3-dbus. Use an isolated venv for zeroconf. Do not install/restart services or
modify approved.sha, runtime configuration, qualification files or firmware under
this mission. No command here should be run against physical hardware until the
corresponding separate written authorization and maintenance setup are recorded.

## Local integration, after source review

Application owns the existing stimulus bus and dashboard. Instantiate
SecretStore(private_directory), TLSProtocol(store), Discovery(zeroconf, lan_ip),
SavedAdapters(DBusBackend(), saved_setup_profile_uuids, Endpoint(configured_setup_ip)),
NetworkManager(bus, discovery, protocol, adapters), NetworkService(manager).
Pass network=service and a separate random network_token to the existing
start_dashboard call. Use manager.endpoint_for(device_id) as a fresh authenticated location hint when
configuring the existing camera/qualified executor owners; never mutate an active
control session or automatically regrant authority on reconnect. No second dashboard process, camera reader, registry or
executor. Do not attach it to startup until native acceptance. The current change
leaves normal startup untouched deliberately; application opt-in is explicit.

A local authorized operator creates NetworkCredentials with getpass (never argv),
creates Authorization(device_id, monotonic()+80, allow_setup=...), then calls
service.arm(credentials, authorization). The opaque handle may be submitted once
via authenticated POST /api/network {operation: handle}. GET /api/network and the
existing Mobile Body shared-sensors view show sanitized state. Primary use requires
allow_primary=True AND acknowledged_disconnect=True; the operator must separately
approve the deliberate management-session interruption. No automatic triggers.
Clear private pending intent by destroying the inactive service; do not persist
Wi-Fi credentials in config files, environment, logs, notebooks or telemetry.

Pre-create saved setup profiles only in a separately authorized maintenance window:
bind the configured adapter; ipv4.never-default/ipv6.never-default yes,
ignore-auto-dns and ignore-auto-routes yes for both, no explicit routes/rules/DNS. Obtain setup AP name and
secret physically; do not copy the fork's settings or assume installed AP identity.
Verify NetworkManager checkpoint support and Polkit scope without granting blanket
root access. Capture original saved profile UUID/IP/routes/DNS before any trial.

## Hardware acceptance sequence, after separate written authorization

1. Resolve the matching installed S3 source, board camera pins, 8 MiB flash/PSRAM,
   PSRAM mode, security/eFuse state, UART RX3/TX40/9600 and partition layout first.
   The official WROVER package is not an S3 replacement. Compare actual camera
   routes and SPIFFS resources. Stop on any mismatch. Never access the RP2040.
2. Use power isolation/free-wheeling/disconnected motors as appropriate, car off
   during wiring; no motion commands. Record independent cutoff and UART owner.
3. Compile matching camera firmware with pinned core/dependencies; retain full build
   output, app binary size/SHA256 and ELF/map. Active app slot is 0x330000 bytes
   (3,342,336). Verify image chip ID and all partition offsets against read-only backup.
   Do not change bootloader, partition table, NVS, otadata or SPIFFS speculatively.
4. Enrollment is a separate physical/USB-authorized act. Generate per-device token,
   TLS key/certificate and recovery AP secret locally; verify device identity and
   certificate SHA256 out of band. Never serve credential forms over unauthenticated
   HTTP, use plain HTTP bearer tokens, TOFU or commit private keys. Browser must
   independently trust the device certificate; never tell users to bypass warnings.
5. Only after written flash authorization: verify exact persistent serial path
   /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_30:30:F9:0D:B0:E8-if00,
   chip ESP32-S3 and MAC 30:30:F9:0D:B0:E8. Do not use numbered ttyACM ports.
   App-only candidate at 0x10000 is permitted only after verifying boot selection,
   compatibility and signed/encrypted image requirements. Proposed command form:
   `python -m esptool --chip esp32s3 --port "$VERIFIED_ESP32_PORT" write-flash 0x10000 "$VERIFIED_APP_BIN"`.
   Variables must refer to reviewed artifacts; this is documentation, NOT authorization.
6. Stationary acceptance: camera 80 and MJPEG81 through existing owner/subscribers;
   serial bridge100 framing/heartbeat; TCP disconnect and heartbeat expiry cause
   independently witnessed safe stop even with STA associated/AP stations present.
   Test FactoryTest separately with no active socket; reconnect must not regain motion.
7. Authorized network trials: LAN already reachable; secondary available/absent/
   unreachable; bad credentials; wrong certificate/ID; loss mid-prepare; AP channel
   change; concurrent requests; stale DNS; device reboot; Pi process death and daemon
   checkpoint rollback; explicit single-adapter fallback; failed restoration. Verify
   original UUID/IP/routes/DNS restored and other Charlie functions remain available.
   Device join is not success until target-LAN identity/transaction/SSID confirmation.
8. Surprise ELEGOO loss must only publish offline/backoff; capture unchanged primary
   UUID/default route and uninterrupted other functions. No internet check is involved.
9. Motion qualification is outside this mission and requires separate supervision.

## Rollback — NOT YET AUTHORIZED

Original image remains private/read-only at the mission backup path, 8,388,608 bytes,
SHA256 c196e9077be06b3f61f6acfcf66219fe0535b60ae1d26183c43b2de80ff25c5b.
Full restore would overwrite NVS/SPIFFS/otadata and new enrollment; assess secure
boot/flash encryption and preserve separately authorized new private state first.
Proposed command form, only after identity/hash/security/physical controls:
`python -m esptool --chip esp32s3 --port "$VERIFIED_ESP32_PORT" write-flash 0x0 "$VERIFIED_ORIGINAL_IMAGE"`.
Do not erase eFuses or use force options. Read back and independently hash, verify
partitions/camera/heartbeat under stationary supervision. Software rollback is
stopping the uninstalled development component and using the unchanged approved
runtime; no reset/clean/merge of another checkout and no service changes.

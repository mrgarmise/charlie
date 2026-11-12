# No-flash stock baseline worksheet

2026-11-10: all live rows below are **pending**, not measured today. No camera/TCP consumers were started. Do not run a new curl capture, open a second stream, connect a second TCP client, press UI drive controls, run discovery or serial auto-detection. Use existing capture/transport owners and their passive subscriptions/history. Redact network identifiers and personal images before publication.

| Owner action, when already running under its existing authorization | Record | Pass threshold |
|---|---|---|
| Read approved.sha and runtime revision in ordinary Pi terminal | Both remain f3304c588a893a953e34e5c4d00bd5f9bfb18f19 | Exact pin match; no promotion/restart |
| Inspect module marking without unplugging/resetting | Board revision and full module suffix, manufacturer datasheet link | Conclusive PSRAM wiring; capacity alone fails |
| From existing CameraFeeder subscription/owner diagnostic | Frame dimensions, timestamps/clock uncertainty, 60s cadence/gaps, JPEG decode success | Stable baseline recorded with one acquisition owner; no invented target fps |
| Inspect owner’s already-held response/status metadata or private historical trace | HTTP80 capture/status, MJPEG81 path/content type/boundary/length, resolution, sensor PID when exposed | Decode/headers consistent; image privacy preserved; no new HTTP control requests |
| View already-loaded stock UI without changing controls | Available control names, selected defaults, UI hash if already cached | Inventory reconciles official vs custom UI; do not send /control commands unattended |
| Existing approved TCP owner’s passive wire history | Heartbeat interval, frame bounds, UART reply tags already received | About1s heartbeat established; no new TCP client or motor/query traffic |
| Inspect existing installed UNO provenance and commissioning files | Exact source/revision, N2 T milliseconds, N1 tagged STOP, N5 position, N100 semantics | Source binding and separately observed physical limits; no motor tests now |
| Review saved normal-boot log if it already exists | PSRAM/sensor initialization, boot reason and partition selection | Explicit mode/security/slot evidence or mark unknown; do not cause reboot |

Read-only ordinary terminal commands that do not open devices:

```sh
cat /home/five/charlie-ops/approved.sha
git -C /home/five/charlie-runtime rev-parse HEAD
sha256sum /home/five/charlie-ops/firmware-backups/elegoo-esp32s3/elegoo-esp32s3-original-20261109.bin
```

The offline comparison tool’s documented arguments accept regular files and source directories. It never invokes serial, Wi-Fi, firmware tools or live endpoints. Do not paste private backup contents or generic strings output into a PR.

**Separate maintenance authorization required:** entering ROM download mode, BOOT+reset, security/eFuse queries, serial opens that might toggle DTR/RTS, downloading stubs or any reset/security/active-slot probe. If device nodes are sandbox-hidden, do not circumvent the sandbox: operator performs only the separately approved maintenance command in the ordinary terminal, retains full output privately and reports the allowlisted security/mode/slot conclusions. No such command was run in this mission.

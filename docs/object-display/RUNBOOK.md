# Object labels to pico:ed

The feature is off by default. It reuses Charlie's existing inference, attention bus, serial owner and display. No additional model, camera read or inference pass is introduced. Recognition means a class hypothesis, not individual pet identity. The .65 confidence cutoff is an uncalibrated conservative starting point; existing lower-confidence native observations may correctly produce no label.

## Safe host verification

From the repository, with its Python dependencies installed:

```sh
python main.py --object-label-replay tests/fixtures/object-display/cat-dog.jsonl
python -m pytest tests/test_object_display.py -q
python main.py --mobile-replay tests/fixtures/mobile/species-loss.json --object-label-display dry-run --learning-state /tmp/charlie-display-smoke --mobile-frames 4
```

These commands use synthetic inputs and fake serial. Replay rejects hardware/real-display options. The CAT/DOG fixture is explicitly synthetic and does not establish real detection accuracy. The captured trace includes the actual host serializer, capability request, CAT, clear, DOG and expiry clear. Firmware tests run the real handler, display renderer and scheduler with fake board/PWM/matrix dependencies and original glyph data.

## Integration and selection

`--object-label-display off|dry-run|rp2040` selects the transport; the default is `off`. Existing main hardware mode reuses Deck.body; it never opens a second display connection. Mobile observation mode optionally attaches one attention sidecar to the same observation producer and exposes all classes from the existing detector metadata. Default mobile behavior retains its original pet-class filter. The original face tracker, camera, chassis/servo authority and learning lifecycle remain in place.

`charlie.object-observation.v1` contains source, frame_id, received monotonic timestamp, geometry, objects (id, label, confidence, box, prominence), and optional attention_target (source/id). Receipt freshness is not camera exposure freshness. Existing PetTracker targets are bound by overlapping boxes. Existing Pi visual targets are bound only to `pi-primary`, using the legacy 1280x720 coordinate space; this mapping never crosses into the ELEGOO source. An explicit attention target wins; otherwise confidence, prominence, label and id provide deterministic ordering.

Policy defaults: three confirmations spanning at least .2 seconds, confidence >=.65, minimum dwell 2 seconds, receipt age <=1 second. Repeated/out-of-order source frames do not count. A maximum of 16 source ordering records and one pending label are retained. Refresh is every 2 seconds without restarting scroll. Fault/loss/staleness clears the object slot; reconnect drops pending selection and requires fresh confirmation. Failed display sends retry at most twice per second. Display exceptions are isolated from existing behavior and shutdown. A firmware TTL clears abandoned labels even if host clear delivery fails.

## Protocol and display priority

The existing 115200-baud locked serial transport handles `DISPLAY_CAPS`, `OBJECT_LABEL <ttl_ms> <step_ms> <TEXT>`, and `OBJECT_CLEAR`. Capability version is `charlie-display-v1`, object_labels=1, width=17, height=7. Unsupported old firmware disables this feature for that link session; there is no generic MESSAGE fallback. Exchanges are bounded to 150ms. Labels are uppercase ASCII letters/digits/spaces, collapsed and capped at 24 characters, with OBJECT fallback. Firmware strictly validates TTL 500..10000ms and step 100..250ms. Default TTL is4500ms and step100ms.

There is one expiring object slot, not a scrolling queue. The renderer uses existing 5x7 glyph pixels on the 17x7 matrix and advances cooperatively through Display.update. It never invokes the vendor's blocking long-string scroll. ERROR/NO_BRAIN override text. Existing text, feedback, capability and progress occupy higher priority than object labels; SLEEP suppresses/clears objects. STOP/IDLE/SESSION clear objects without changing existing authority rules.

## Native qualification and rollback

No physical serial connection, firmware flash, production service change, servo/chassis movement, autonomous navigation or policy activation occurred. Native Pi access was unavailable. Firmware source is implemented but has not been installed. Actual glyph shape, I2C timing, scroll readability, native heartbeat latency, shared Hailo throughput and installed-firmware negotiation remain unqualified.

Do not instantiate RP2040Controller as a supposedly read-only probe: its existing constructor opens/resets serial and sends STOP/SESSION. Do not run tools/sync_rp2040.py without separate authorization. Later native work should first use an isolated checkout and repeat the safe fake-I/O commands above, record Python/Hailo/model manifest/device inventory without opening devices, and obtain authorization before display deployment or real transport tests. Record actual PING/STOP latency during a long label before accepting native scheduling. This mission supplies no physical acceptance result.

Disable with the default `--object-label-display off`; existing behavior is preserved. Existing firmware needs no update when the feature remains off. Any later firmware deployment needs its own known-good backup and explicitly authorized rollback procedure.

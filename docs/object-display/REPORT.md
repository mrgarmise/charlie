# Object recognition / pico:ed implementation report

2026-10-25. Draft PR #11: https://github.com/mrgarmise/charlie/pull/11 . Branch `feature/object-label-picoed-display`, stacked on PR #10 at96e651373e513d24b4163b87c5f85bdd5549cf1d. This preserves the ongoing mobile integration rather than rebuilding on old master. Runtime/test source frozen at19a12fcd27c6173c2809212534c78354eeffa359; CI-only follow-updc8b4a6b3a5e8f7462263e99e40e63491e5479a1.

## Implemented

- Reuse existing Hailo class results, normalized observation events, existing attention target, deterministic fallback, stabilized confidence/dwell/dedup/freshness selection and bounded retries.
- Feature defaults off; no duplicate camera or inference. Optional full existing model class exposure supports PERSON, CHAIR, DINING TABLE, STOP SIGN and other supported classes rather than hardcoded CAT/DOG.
- Negotiate display protocol once per link session, sanitize/cap labels, handle unsupported firmware conservatively and reuse the existing locked serial owner.
- Add one low-priority expiring firmware object slot and cooperative pixel scrolling using the existing font. Preserve status, message, feedback, capability and progress priorities, STOP and heartbeat handling. No vendor driver, scheduler, servo or motion authority changes.
- Isolate display failures from behavior/shutdown, clear on faults/stale input/reconnect, require fresh confirmation after reconnect, and bound refresh traffic.
- Provide a fully isolated no-device CAT/DOG replay that uses real host serialization; real firmware handler/render/scheduler tests use fake hardware. Add dedicated software CI for the stacked feature branch.

Incremental publications: d75f672a2e719ab2ae26a4927935c97ddfe42663 (protocol/firmware),19a12fcd27c6173c2809212534c78354eeffa359 (observation/attention/runtime and tests),dc8b4a6b3a5e8f7462263e99e40e63491e5479a1 (CI). Documentation/evidence follows separately.

## Independent validation

Focused regression:146 passed (object display, active vision firmware, calibration integration, mobile integration, brain calibration). Byte comparison confirms protected face tracker, ELEGOO transports, camera, servo/calibration/motion code, scheduler, vendor glyph driver, firmware sync utility and learning lifecycle files are unchanged from the base; see validation.json.

Full clean-checkout suite: **1,344 passed, 21 skipped**, one warning, in326.56 seconds against frozen source19a12fcd27c6173c2809212534c78354eeffa359. validation.json and host-tests.txt record the result. Compilation and diff whitespace checks passed. No-device application replay and existing mobile replay with the display dry-run both completed. The synthetic replay selects CAT then DOG and clears stale/expired labels; see cat-dog-trace.jsonl.

Benchmark:10,000 synthetic observations over99.99 virtual seconds, one capability query,50 label transmissions and one clear (about.5 label commands/second), zero physical serial calls, camera reads or added inference passes. Host policy p95 approximately3.4 microseconds. This measures fake-I/O policy overhead only, not Hailo throughput, serial latency or LED timing. Full values are in benchmark.json.

Tests cover attention/source preference, arbitrary model labels, confidence flicker, dedup/out-of-order/stale input, bounded failed ACK retries, reconnect, sanitization/injection/bounds, old firmware compatibility, same-label refresh, replacement, priority, expiry, and real firmware scheduling with PING/STOP while scrolling. The diagnostic forbids real serial/socket construction. Injected display failures cannot block existing behavior updates or shutdown.

## Qualification boundaries

All eligible host software work is implemented. Pi-validated: none in this mission. Actual pico:ed LED rendering/scroll readability, I2C timing, native heartbeat/STOP latency, installed-firmware negotiation, shared Hailo/native camera throughput and real classifier accuracy remain open. Native Pi access was unavailable. Existing native evidence and Robotron checkouts are preserved. Synthetic CAT/DOG confidence is not native evidence; labels are class hypotheses and do not identify individual pets. Receipt timestamps do not prove exposure freshness.

No firmware installed/flashed, physical serial connections, servo/chassis actions, navigation/policy activation, production service updates or model downloads occurred. The installed working face tracker is untouched. Source firmware is ready for separately authorized deployment and native qualification, not declared physically accepted. See RUNBOOK.md for safe replay, integration details, default-off rollback and the explicit native qualification boundary.

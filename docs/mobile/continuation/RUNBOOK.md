# Native unarmed continuation runbook

This extends PR #10. Do not run `run_elegoo_head2.py`, `test_mobile_track.py`, any pan/chassis command, firmware tool, `--hardware`, Robotron game or policy activation. Original Pi install `/home/five/Projects/charlie` and its evidence remain untouched. Native path names below are operator-reported, not reverified from this worker. First verify they exist and the isolated checkout is clean; if dirty, preserve it and use another isolated checkout instead of resetting.

## Update only the isolated mobile checkout

```bash
cd /home/five/charlie-mobile-pets
git status --short
git fetch origin feature/mobile-perception-pet-following
git merge --ff-only origin/feature/mobile-perception-pet-following
git rev-parse HEAD
```

Only proceed with the merge if the preceding status is clean and this is the intended mobile checkout. Do not change network interfaces/routes or restart unknown services. Read `ip -br addr`, `ip route` and process listings to verify Robotron has primary ownership before a camera/Hailo run. The existing lease is cooperative; another application that ignores it is not protected by a filename. Mobile inference yields/closes resources on detected primary/thermal/resource faults. It cannot force an unrelated Hailo user to cooperate.

Use the already available Python with Hailo support; operator previously verified `/home/five/Projects/charlie/.venv/bin/python`. Invoking that interpreter from the isolated mobile directory does not edit the primary checkout. Do not install new packages over its environment without review.

## Preserve and import the original Monty evidence

Keep original `events.jsonl` and nine PNGs in `/home/five/charlie-mobile-evidence/pet-watch-20261024-234649/`. The importer reads originals, verifies exact pixel hashes, and writes only to a new output directory. It never reruns detection, relabels predictions or connects to the car. Create an annotation JSON mapping each of `pet-001.png` … `pet-009.png` to `{ "species":"cat", "subject":"Monty", "source":"operator confirmation 2026-10-24" }`. These labels apply ONLY to those nine images. No dog was in that room; Nigel is a separate reference, not a second animal in this sequence.

```bash
PYTHONDONTWRITEBYTECODE=1 /home/five/Projects/charlie/.venv/bin/python -m learning.mobile_evidence \
  --events /home/five/charlie-mobile-evidence/pet-watch-20261024-234649/events.jsonl \
  --images /home/five/charlie-mobile-evidence/pet-watch-20261024-234649 \
  --labels /path/to/operator-monty-labels.json \
  --output /home/five/charlie-mobile-evidence/continuation-state/mobile-native/monty-original \
  --expected-events-sha 03490c149e57795b013190bfaa5b9261f43cf8b9883f652014b446c5191130f3 \
  --reference-photo /home/five/pet-test.jpg \
  --reference-sha 5ec8a0b655389130b86c7a3ebd6005002b22092d791541fa3c7bf4290dda66ba \
  --reference-subject Nigel --reference-species cat
```

The placeholder label path must be replaced with the actual file. `review.html` plus local overlay PNGs provides a read-only visual review. `summary.json` scopes metrics to reviewed captures; `tracking.jsonl` preserves all 614 event positions, including the 605 unlabeled events. `native-evidence.sqlite3` separates raw predictions, operator annotations, and the separately attributed terminal timeout (which was not in the original log). Source software SHA/inference timing remain unknown where absent. Timestamp intervals are event cadence, NOT camera FPS or measured inference latency. Raw pixels and PNG bytes have distinct hashes. Repeated import is idempotent.

## Normal Executive review, no hardware

```bash
PYTHONDONTWRITEBYTECODE=1 /home/five/Projects/charlie/.venv/bin/python main.py --offline \
  --learning-state /home/five/charlie-mobile-evidence/continuation-state \
  --episode-root /home/five/charlie-mobile-evidence/no-game-episodes \
  --learning-turns 1 --learning-budget 2
```

That state directory is dedicated to this mobile review. Its existing Executive acquires native journals under `mobile-native/*/native-evidence.sqlite3`, Reflection supplies evidence-backed opportunities, and the normal portfolio may select `mobile-evidence-review` alongside other available projects. The independent Evaluator compares preserved species predictions against pixel-bound operator labels. One correlated log is ONE evidence unit, never nine independent trials. The existing Executive stores the outcome/bookmark, pauses the completed historical retrieval, and waits for new evidence instead of repeating it. Existing active Robotron projects retain the chooser's normal precedence. No hardcoded Monty agenda, neural training, model correction or physical improvement is claimed.

## Bounded stationary watcher, depth optional

Prepare a `charlie.mobile.models.v1` JSON manifest with the existing verified YOLO HEF path/hash and its exact complete 80-class COCO export order. Do not provide just cat/dog/person as the class list. Operator verified HEF:

- `/home/five/charlie-mobile-models/yolov8n-hailo8l.hef`
- SHA256 `90e2cdad2875f23fb436ecdba88b4789de3bd8112cdf6b34beb1c8aa9fd7eed1`
- objects fields: `path`, `sha256`, `classes` (complete export order), `size:640`; optional `persistent:true`.
- `stream_url`: `http://192.168.4.1:81/stream` (verify route first).
- Omit `depth` until its artifact/runtime contract is independently verified. It then returns an explicit unavailable-depth observation and navigation stays stopped.

```bash
PYTHONDONTWRITEBYTECODE=1 /home/five/Projects/charlie/.venv/bin/python main.py \
  --mobile-observe --mobile-manifest /path/to/verified-mobile-models.json \
  --learning-state /home/five/charlie-mobile-evidence/continuation-state \
  --mobile-seconds 300 --mobile-frames 10000 --mobile-max-faults 10 \
  --mobile-retain events --mobile-captures 100
```

This uses only the camera URL, not the control socket. Ctrl+C closes the reader/session/journal. Default retention is event-triggered, at most one capture per second, max 100 captures and 64 MiB. `--mobile-retain none` disables image retention; `all` deliberately records all eligible frames up to the same caps. Status heartbeats, model/resource times, faults and final p50/p95/p99 are printed; no motor dispatcher is attached. Reader retries are bounded (three, exponential backoff, cancellation), old reader generations cannot publish after reconnect, and stale targets are invalidated on faults. Reconnection resumes observation, never motion. End-to-end timing is decode-receipt-to-decision; exposure age remains unknown.

A concurrent normal Executive process for the SAME state may import observations through its existing acquisition turn; its existing lock prevents a competing owner. Alternatively run the finite offline Executive command after a watcher session. The watcher itself does not introduce another Executive scheduler. Unqualified live detections may produce provisional sensing questions, not established species/identity facts or permission to move. Executing prospective fresh-view requests requires an available unarmed service; absent that service the project remains blocked, with its bookmark intact.

Detector-only observation retains a configured Hailo session under the shared cooperative lease. If depth is supplied, the detector releases its session before the depth network takes that lease; this conservative sequential mode is not a native-qualified multi-network scheduler. Sustained native throughput/thermals, cancellation and primary-task contention must be measured before changing that schedule.

## Sourced FastDepth candidate — still unqualified on Charlie

`depth-source.json` records the official Model Zoo v2.19.0 Hailo-8L download, MIT source/config links and verified downloaded-byte SHA256 `625c8d6a236d8f305454d28ae43bab129ca65025c4be0dbcd6cf6d3e41983c79` (4,635,184 bytes). Binary is not committed. On Pi, download to a NEW model filename; verify SHA256 and run `hailortcli parse-hef` without motor/control connections. Require HAILO8L, input 224×224×3, one output 224×224×1, and actual runtime 4.23.0 compatibility. Do not assume downloaded bytes mean native acceptance.

Depth manifest fields after verification: `path`, exact `sha256`, `input_shape:[224,224,3]`, `output_shape:[224,224,1]`, `larger_is_nearer:false`, `preprocessing:"fast-depth-v2.19"`. Official preprocessing resizes RGB to 250×332, central crop .91, then 224×224; /255 normalization is in the export. Host adapter uses OpenCV float32 bilinear; TensorFlow/native parity is still pending. Head postprocessing is identity. Nine spatial zones retain relative near quantiles, not calibrated meters or certified floor/stair clearance. Planner rejects mismatched frame-bound depth, missing range/FOV/lateral-clearance/pose/heartbeat evidence and all unqualified perception.

## Unimplemented physical interfaces and rollback

No read-only ultrasonic command was proven safe from the installed firmware, so none is invented or sent. Driver/firmware revision, independent local STOP/watchdog, sensor timestamps/FOV, floor/stair/blind-spot coverage, geometry, speed calibration and electrical/power safety remain physically unverified. The physical executor remains unattached. Test dictionaries and mock SDK/ACKs are explicitly simulated. Empty-room motion, pet-present motion and camera pan each need separate scope-specific authorization after the relevant independent safety qualification; this document grants none.

Stop sensing with Ctrl+C. Leave the primary checkout at its existing verified state. Roll software review back by selecting a25b2b7256dffe140c375916d882b759e85b9911 in a SEPARATE checkout; preserve new and old journals/captures. No firmware rollback is needed. Never reset/clean the user's existing worktrees or evidence.

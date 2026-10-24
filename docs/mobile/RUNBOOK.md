# Mobile perception and pet following — disarmed software

## Checkout and unarmed replay

Use the repository branch `feature/mobile-perception-pet-following`. Do not merge or deploy over the installed face-tracking checkout. Source supports Python 3.12+; Pi-specific dependencies are OS/runtime packages.

From the checked-out repository root (these relative paths were exercised on host):

```bash
python -m pip install -r requirements.txt pytest
python -m pytest tests/test_mobile_perception.py tests/test_mobile_tracking_navigation.py tests/test_mobile_integration.py tests/test_mobile_legacy_regression.py tests/test_memory_recall.py -q
python main.py --mobile-replay tests/fixtures/mobile/species-loss.json --learning-state /tmp/charlie-mobile-review --mobile-frames 4
python main.py --offline --learning-state /tmp/charlie-mobile-review --episode-root /tmp/charlie-mobile-no-episodes --learning-turns 1 --learning-budget 1
```

Replay uses explicitly marked handcrafted object/depth inputs and blank pixels. It is not a CPU neural fallback, authentic pet sequence, Hailo inference or navigation qualification. It confirms a complete no-motion path through frame -> inference contract -> stable species target -> guarded proposal -> rejected execution -> durable evidence -> existing Executive acquisition. It never instantiates Deck, MobileBase or the legacy moving face behavior. `--hardware` cannot be combined with mobile acquisition. No ARM installation or live model command has been executed here.

`learning-state/mobile-evidence.sqlite3` contains immutable observations, proposed actions, rejection reasons and acquisition faults. The normal lifecycle imports them into `learning-evidence.sqlite3` on its existing acquisition turn. Repeat imports preserve original IDs and do not duplicate observations. Native-qualified observations may supply hypotheses through existing Reflection and Executive project selection; fixtures and unqualified live outputs cannot create qualified mobile projects. Existing Executive requests/bookmarks persist, and the capability registry exposes `mobile-observe`, `mobile-navigation-proposal` and an explicitly unavailable `mobile-mobility` affordance. `mobile-observe` accepts an injected unarmed service; no second scheduler is added. The existing offline CNN/Robotron chooser does not automatically execute mobile investigations without that sensing opportunity/service. No new source of hypotheses, experiments, learning rewards or actuation authority bypasses the Executive.

## Live unarmed perception prerequisites

First obtain a real Pi session and verify installed checkout/firmware without running any legacy start scripts. In particular, `run_elegoo_head2.py` and `test_mobile_track.py` can move pan/chassis and are NOT unarmed tests. Preserve their existing controls and startup unchanged.

Verify camera URL/network route, single-client limits, exposure/receipt timing and exact deployed face mode. Verify `hailortcli` architecture/runtime, artifact licenses, HEF SHA256s and compiled preprocessing. No HEFs are bundled. PR 6's NMS backend is reused unchanged and only supports one Hailo NMS output; raw YOLO heads fail closed. Depth requires an actual Hailo-8L single-RGB-input, single-HWC-depth-output export matching the manifest, not merely a FastDepth/SCDepth model name. Relative depth is never calibrated meters. No silent fallback or simulated Hailo backend exists.

The live entry point is `main.py --mobile-observe --mobile-manifest PATH --learning-state STATE --mobile-frames N` (documented interface; NOT Pi-validated here). It opens only the camera and Hailo models, records bounded PNG pixels under STATE/mobile-pixels (64 MiB default), and emits observation JSON. The source-frame pixel digest and separate encoded PNG hash/path are retained. Disk quota exhaustion or any model/resource/transport failure interrupts acquisition with a durable inconclusive fault. Re-running reconnects without repeating an old buffered frame. Existing camera metadata uses local monotonic decode receipt; source capture time and synchronization uncertainty remain unknown.

Manifest shape (placeholder values MUST be replaced by verified local artifacts and export contracts):

```json
{
  "schema":"charlie.mobile.models.v1",
  "stream_url":"http://192.168.4.1:81/stream",
  "objects":{"path":"/verified/objects.hef","sha256":"ACTUAL_SHA256","classes":["EXACT_COMPLETE_ORDER_FROM_EXPORT_INCLUDING_person_cat_dog"],"size":640},
  "depth":{"path":"/verified/depth.hef","sha256":"ACTUAL_SHA256","input_shape":[192,640,3],"output_shape":[192,640,1],"larger_is_nearer":true}
}
```

Shapes, class order, normalization, interpretation, model/version and runtime must be established from the real artifact; example dimensions are NOT a recommendation or compatibility claim. Runtime packages and hardware versions must be recorded at native qualification. Capture p50/p95/p99 receipt-to-decision timing, inference latency, packet drops/reconnects, thermal/resource samples and authentic frame hashes. The cooperative nonblocking Hailo lease protects mobile clients that use it; unrelated existing applications must participate or be scheduled away. ResourceGuard yields during gameplay and thermal/resource faults. No simultaneous score-reader throughput guarantee is made.

## Separate acceptance gates

|Gate|Needed evidence|Current disposition|
|---|---|---|
|Native no-motion sensing|Authentic car stream, Pi/Hailo runtime/HEFs, independently labeled indoor frames, overlays, timing/thermal report|BLOCKED: hardware/artifacts unavailable|
|Legacy installed regression|Authorized pan/yaw face trial, loss/STOP/sentry and exact deployed firmware|PENDING separate moving-trial authorization|
|Sensor communication|Verified read-only firmware protocol for ranging, timestamps and watchdog; no guessed commands|BLOCKED: installed protocol unknown|
|Empty-room supervised motion|Car-local STOP/disconnect timeout, bounded speed/duration, independent floor/edge/blind-spot guards, fresh capture and sensors, operator STOP|NO AUTHORIZATION; no physical backend supplied|
|Pet-present following|Passed empty-room trials, stand-off/escape space, stop on distress, measured target distance, never chase under furniture or toward stairs|NO AUTHORIZATION; physically unqualified|
|Autonomous operation|Separate scoped authority, qualification record, expiring boot-bound lease and independent safety check|DISARMED|
|Executive/PPAL learning|Charlie-originated authentic investigation, persistent hypothesis/results, controlled experience-to-later-choice comparison and independent evaluation|NOT DEMONSTRATED|

The proposal interface lives in PPAL (`experiments/ppal/mobile_navigation.py`). Engineering default speed/duration/distance limits are only conservative offline constraints, not evidence-based operating thresholds. It requires real ranging plus separately qualified floor/hazard/blind-spot guards; ultrasonic alone cannot establish clearance. Off-axis or unknown pan vetoes forward space assumptions. Generic cat/dog classification is not individual pet identification. Track association abstains on crossings and short occlusion holds selection without allowing motion. There is no SLAM, stair detector, certified floor segmentation or verified car-local watchdog implementation hidden behind these booleans.

`MobileExecutionGate` requires an independent safety check, qualified car-local bounded executor, authority/lease with matching boot identity and fresh proposals. No physical implementation is supplied: current MobileBase has no verified bounded forward/range protocol. A mocked ACK is not physical execution; dispatched, acknowledged, executed and observed consequence remain distinct. Test-only injection exercises the interface. A future physical adapter must use verified existing MobileBase/protocol and undergo the separate gates above. Never assign `car_local_qualified` to the current driver to bypass missing firmware evidence. No firmware flash is authorized.

## Rollback

This branch neither replaces the installed checkout nor changes legacy face mode defaults. To stop unarmed sensing, use Ctrl+C; only its camera/Hailo/journal resources close. Leave the existing installation at its previously verified commit. For software review, check out the base commit `bcf8082f6319c63c4bd6bcceeab5faea37241654` in a separate checkout. Preserve all existing notebooks and experimental archives. Never delete a user's worktree or reset their state. No motion authority survives process restart; no firmware rollback is needed because no firmware was flashed.

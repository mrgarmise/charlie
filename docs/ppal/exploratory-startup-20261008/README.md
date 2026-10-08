# Autonomous recorded sensory preflight and exploratory startup

This continues controller checkpoint f6f23a78cb9a45ae7b4a2be5751e4790884f5a2e. No physical actions occurred. Original failed-start PNG/report/provenance are preserved in tests/fixtures/robotron-failed-start-031501; the full original archive remains unchanged in its original Library identity. The PNG still classifies unknown. It is not a taught title reference or a new independent experience.

## Existing owners and ordering

The established play_robotron entry point now starts a recording session before warmup or optical preparation. The existing PiCameraSource/CameraLease/ObservedCamera remain the camera owners. Its passive publisher continues serving the browser preview from the same observations. No second camera, controller, planner, Executive or application is created. Active Vision's existing local geometry/focus optimizer is reused; physical viewpoint capability remains unavailable without independent CAL-1 qualification/authorization and no motion is attempted.

Each session performs the existing measured exposure optimization, current full-field border discovery, local optical focus search and post-focus geometry verification. Saved historical geometry is not assumed current. Measured white balance gains can be locked using advertised camera controls; absolute color fidelity remains UNQUALIFIED without a reference chart. There is no fabricated digital color correction. A 60-second overall deadline and existing finite geometry/focus/exposure attempts bound optimization. Lack of useful detail or geometry preserves sensory-preflight.json and asks for assistance. No controller is constructed on preflight failure.

Successful preflight flushes original timestamped lossless pixels and verifies the journal before the controller's initial NEUTRAL/ACK handshake. Only then can exploration begin. Caption/status changes are not image quality proof. Recording session, exploratory action, fresh gameplay observations, agency identity and independent score qualification remain separate concepts. The previously positive classifier gate is now a diagnostic; unknown pages can be investigated inside explicit existing --arm session authority. No physical session was authorized or run by this mission.

## Exploration and feedback

Forebrain chooses from actual permitted hardware inputs and stick options using session-local context/coverage. No COIN -> START success rule is installed. Each choice poses a question, durably commits a prospective prediction via the existing EvidenceJournal, records the actual transport execution, then records the following observation and resolution. A changed scene is at most a visual association, not independently verified causation. Lack of change is inconclusive, not failure. A controlled fixture deliberately tries START before BACK and then revisits START after context changes; it demonstrates discovery of that fixture's startup relationship, not physical Robotron learning.

Three fresh gameplay classifications are required before the existing SELF/agency acquisition path proceeds. A command ACK is never game commencement. Exploration is bounded by configurable actions/time (defaults 32/30 seconds), preserving unsuccessful attempts, and requests further readable observations when exhausted. It does not spin forever or choose physical authority for itself.

## Evidence integrity and interruption

ObservedCamera delegates original-frame recording to one bounded four-frame writer in existing progress_evidence.py. The writer owns only I/O and the established append-only session-evidence.sqlite3, never priorities or decisions. Every frame is lossless PNG, timestamped and hash-addressed. Preparation may wait for this writer before any controller authority is exercised. During gameplay, saturation stops actions through the existing ObservationFailure/finalization path instead of silently dropping observations. One already captured overflow image is retained and written after controls close. Controller hold leases and supervision remain active. Camera/encoder blocking on unhealthy OS storage still requires native supervision validation; no hard real-time guarantee is asserted.

Existing steps.jsonl now fsyncs completed steps. Interrupted journals retain already committed predictions and unresolved outcomes. Restart of the recorder preserves original records, advances file numbering, and keeps orphaned durable pixels without manufacturing their missing journal rows. Reopening the recorder does not commission work or replay old observations as new experience. Normal player outputs still refuse overwrite. Source manifests and normal acquisition preserve the full session evidence for existing Reflection/MemoryGateway/Evaluator processing.

## One taught boundary anchor

Optional --title-reference loads a declaration alongside an operator-verified image of the RECTIFIED playfield:

```json
{"schema":"charlie-title-reference-v1","verified_by":"operator","image":"title.png","sha256":"<actual image SHA256>","roi":[0.1,0.1,0.9,0.4],"maximum_normalized_error":0.04}
```

The normalized ROI must isolate a discriminating, stable title marker. Loader checks path containment, image hash, operator provenance, ROI and contrast. Matching uses bounded local RGB comparison, no GAME OVER/initials OCR. Native variations must qualify this reference before relying on it. An authentic reference was not supplied by this mission; title tests are explicitly constructed visual fixtures.

Repeated fresh positive title matches can corroborate the end of already established gameplay even when instructions/high-score/unknown pages intervened. Title before a game, duplicate timestamps, unverified title flags and absent SELF never establish that boundary. The prior published terminal/attract evidence rules are preserved. A title boundary does NOT qualify a score. Existing marathon restart admission accepts the exact taught-reference evidence, not arbitrary state changes. Additional terminal indicators remain questions for existing developmental learning.

## Acceptance procedure and limitations

Run host/native SOFTWARE fixtures only:

```bash
python -m pytest tests/test_controller_sandbox.py tests/test_robotron_exploration.py tests/test_sensory_recording.py tests/test_robotron_agency_integration.py tests/test_robotron_startup_boundaries.py tests/test_robotron_preflight.py tests/test_robotron_recorded_screen_states.py -q
```

These replace camera and controller with software fixtures, including tests passing --arm to the simulated runner. They do not grant or exercise physical authority. Preserve the actual Pi notebook/captures and original failed-run archive. No live --arm command, firmware update, servo command or policy activation is part of this acceptance. Separately authorized native sensing/transport readiness and physical gameplay are required later; independently measured complete-game score improvement remains UNKNOWN.

The focused tests passed 40 cases in 13.65 seconds before final full regression. Initial fixture/isolation failures are retained; the old fast-path dependency check exposed a unnecessary journal-module import used only for image hashing. It was replaced with bounded local hashlib, keeping dense retrospective work outside gameplay.

Final full host regression: 642 passed, 20 skipped in 119.17 seconds. Unavailable Torch and the unavailable original collision capture remain explicit skips. No native Pi or physical acceptance is claimed.

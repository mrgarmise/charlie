# Operator-requested object demonstration

Status: software implementation; native Pi/pico:ed and browser-to-Pi acceptance pending.
This is an opt-in extension of `main.py`, its AttentionManager and object runtime.
It does not start a second camera, serial owner, Executive or robot-control process.

## Request pathway and scope

The existing owner-private project dashboard has an **Abilities** area. Its browser
sends authenticated JSON directly to an explicitly enabled, loopback-only adapter
inside Charlie. A static Site is not a command queue or a robot connection.
An SSH forward is required from an operator workstation; no public listener, cloud
relay, tunnel service, firmware deployment or credentials were installed by this work.

`POST /api/abilities` → existing capability registry → `operator_demonstration`
stimulus → existing AttentionManager admission → existing ObjectRecognition →
MobilePerception/HailoObjects → existing ObjectLabels/RP2040 serializer.

The fixed capability is `demonstrate-object-identification`, camera `pi-primary`,
duration integer `15`. Other cameras/abilities/motion arguments are rejected.
Each POST uses a UUID, current runtime boot ID and a single-use challenge from
`GET /api/abilities`; challenges expire after 30 monotonic seconds. Authentication
uses a separately provisioned high-entropy bearer token. Host/Origin are checked,
JSON bodies are limited to 4096 bytes, and secrets never enter URLs, site source,
server logs or browser persistent storage. Keep the token private. SSH encrypts the
network hop; HTTP is only between the local browser and the local SSH endpoint.

The HTTP adapter dispatches a request and reads status; the normal application loop
executes it. `requested` is not `running`, a recorded object is not a stable label,
and an RP2040 acknowledgment is not independently witnessed light output.
The dashboard keeps these counts/states separate and reports physical output as
unobserved. The authenticated API intentionally exposes no motor/firmware command.

## Existing attention and developmental state

Only no active behavior or the existing IdleBehavior can be temporarily suspended.
The same idle instance is retained without enter/exit/reinitialization, and its
updates are suppressed during the demonstration. Existing priority/pending intents,
face/mobile/pet activity, unknown behaviors and emergency latch reject admission
with a reason. They are not silently interrupted or claimed to have a durable
resume interface. New higher-priority intent cancels a running demonstration;
emergency STOP retains priority over queued starts. No new task chooser is added.

The normal Executive child continues with its existing notebook and chosen
investigations. A demonstration neither writes its agenda nor terminates/restarts
it; the existing supervisor remains in charge. If compute is busy, the existing
Hailo lease/resource guard may make recognition unavailable. This does not grant a
second inference owner or change the developmental priority.

The normal primary application lazily creates the existing recognition adapter
using the existing AttentionManager/display and feeder. The stationary Object
Recognition application borrows its existing model and pipeline, temporarily
selects Pi, changes only the evidence episode, and restores the previous camera
subscription/evidence episode afterward. Its continuous observations then resume.
Existing ELEGOO source switching remains supported; a dashboard ELEGOO demonstration
is deliberately not admitted. Pet/face command profiles refuse the dashboard option
at startup until their interruption semantics are qualified.

## Lifecycle and evidence

The 15-second budget uses monotonic time, including pipeline initialization.
No new display result is admitted after that budget. Cleanup runs on the next
application-loop opportunity; this is a cooperative bound, not a real-time deadline.
Native model initialization, Hailo calls, serial calls, disk writes and STOP/cancel
latency must be measured on Pi. An in-flight call cannot be forcibly killed safely.
The existing Hailo I/O timeout and stale-inference check remain unchanged.

A two-second lack of fresh processed frames ends a running session with a failure;
model/frame/serial faults do likewise. Label stabilization/confidence/TTL policy is
unchanged. Cleanup clears labels and releases a temporary subscription/model lease;
borrowed continuous-mode resources return to that existing mode. Failure to clear
or to receive display acknowledgment is retained as a failure. Hardware TTL remains
an independent fallback, not proof that the physical display cleared.

One request is admitted at a time. A second request cannot reset the deadline.
Cancellation is consumed in the normal loop. An advisory application lock protects
state from a second runtime; unfinished requested/running rows are cancelled on
restart and never replayed. The runtime boot/challenges also change on restart.

Private files under `--learning-state`:

- `operator-demonstrations.sqlite3`: request/session/execution IDs, UTC and monotonic
  timestamps, runtime environment, lifecycle/failure events, SHA-256 of canonical
  event bodies, stabilization decisions and acknowledged/unobserved display receipts.
- `mobile-evidence.sqlite3`: existing unaltered sensory-learning journal format,
  with `operator-demo:<execution_id>` episode, complete frame timing/source,
  model identity/revision, hypotheses and original qualification.
- `operator-demo-frames/`: existing FrameArtifactStore content-addressed PNGs,
  capped at 64 MiB; evidence references include paths and hashes. Exhaustion is
  reported, never silently evicted. Operator archival is required before filling it.

Firmware identity is explicitly unverified until native readback. Original
failure/inconclusive records are retained. Fixture tests do not become authentic
experience or physical success. The wider Executive may later import genuine
observations through its existing mechanisms; no human-selected conclusion is forced.

## Native acceptance and ordinary use

No Pi was reachable from the isolated x86_64 host (`charlie.local` did not resolve).
Installed code, current processes, native model/firmware identity, serial ownership
and notebook contents were not inspected or changed. Do not merge PR #13 or treat
this document as a qualified whole-robot release.

For Pi-connected Codex and an operator, after reviewing the candidate and preserving
all worktrees/evidence:

1. Read-only inspect the deployed branch/SHA/status, process owners, model manifest
   and hashes, installed Hailo runtime, firmware capabilities/readback and existing
   learning-state directory. Preserve original notebooks, local changes and logs.
2. Arrange a supervised stationary window with motion independently disarmed;
   keep the existing emergency stop/cutoff restrictions. No firmware flash is
   required or authorized. Use the reviewed object-label firmware already present.
3. Provision a random token locally (at least 32 characters), without putting it in
   source, a URL or a published log. For example, generate it privately with
   `python -c 'import secrets; print(secrets.token_urlsafe(32))'`, then securely set
   `CHARLIE_OPERATOR_TOKEN` in the application environment. Do not share it in a PR.
4. Launch the verified normal stationary application using the **existing** state
   and native Python environment, for example:

   ```sh
   "$PYTHON" main.py --hardware --object-recognition --camera-source pi \
     --object-label-display rp2040 --object-model-manifest "$VERIFIED_MANIFEST" \
     --learning-state "$EXISTING_STATE" --abilities-dashboard
   ```

   APP/PYTHON/state/manifest must be operator-verified paths, not guessed defaults.
   This example does not enable motion or replace an already running application;
   coordinate ownership before launch. Primary mode can also attach the ability,
   but any active tracking/calibration must yield through established rules first.
5. On the workstation, use existing SSH access:
   `ssh -N -L 8768:127.0.0.1:8768 five@charlie.local`.
   Open **Abilities** on the existing project dashboard, retain endpoint
   `http://127.0.0.1:8768`, enter the token, and connect. Where browser local-network
   policy prevents cross-origin access, use `http://127.0.0.1:8768/` through the same
   tunnel. Do not disable browser security or expose the listener publicly.
6. Request **Show me what you see** with recognizable stationary objects. Record
   request/execution IDs, UTC start/end and video showing physical pico:ed output,
   no movement and approximately 15-second demonstration. Compare observations,
   display ACKs and actual visible labels, preserving disagreement. Verify one
   feeder/serial owner, existing independent subscribers, and ongoing Executive
   notebook continuity before/during/after. Initial continuous object mode resumes
   afterward, so labels may legitimately return from that original activity.
7. Request a second demonstration without restarting. Then test cancellation,
   empty scene, unavailable model, source loss, serial loss, duplicate/stale
   requests and restart recovery under supervision without granting motor authority.
   Record measured deadline/cleanup/STOP timing and native limitations.
8. Preserve exact code/model/firmware identities, frame artifacts, original SQLite
   records, external video hashes and failures. Only witnessed observations can
   satisfy physical acceptance. Dashboard availability alone is not acceptance.

Rollback: stop this opt-in endpoint via the normal application shutdown, preserve
its evidence, remove `--abilities-dashboard` for the next authorized launch and
use the prior reviewed checkout. No firmware or actuator policy rollback is needed.

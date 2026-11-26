# Shared recognition development integration

This branch introduces an opt-in native qualification profile for the existing
foreground application. It grants no release, changes no canonical launcher,
and requires separate on-site authorization and physical power isolation before
any native test. Its state and credentials live in a new private session
directory. The original supervised-development launcher continues to select its
previous pinned profile.

The application remains the only physical owner in this profile. Its existing
ELEGOO CameraFeeder publishes immutable frames and the existing passive
snapshots. ObjectRecognition consumes one frame subscription, runs the configured
hash-bound Hailo model through the existing resource guard, and publishes
detections through DetectionPublication and the local request transport. Native
inference cadence, frame freshness, generation and close checks remain in place.
A single demand scheduler coalesces callers onto the next eligible observation
and reuses a fresh result for the same source/model contract. There is no
client-supplied HEF, source switch, raw serial or actuation API. Existing depth,
score and other-model entry points remain separate profiles, outside concurrent
ownership in this qualification.

Optional Pico display uses the existing RP2040Controller with one queued intent
per connected producer, existing acknowledgement handling, and firmware
precedence. The bounded FIFO serves at most one intent per owner-loop turn.
The observational STOP handler latches demand shutdown, drops queued display
work and clears the label during owner cleanup. An already selected serial
exchange remains subject to the existing protocol timeout. Recognition alone
does not create a Pico connection and does not print observation payloads.

The owner binds one AF_UNIX stream socket in a private directory. The guarded
Executive child may connect to that exact path only. Other authorized processes
use the same-UID and role-token interface. The tokens separate application roles
within the supervised account. They provide no isolation from a malicious
process running as that same UID or root. Connections, one active request per peer process, request size, frame quota,
deadline and pending deliveries are bounded. Closing a client connection removes
only its demand or queued display intent. The application closes the listener
and clients before releasing the recognition or display owner.

The Executive's live evidence acquisition can request a fresh observation when
explicitly enabled. This is observational work, without motion authority.
An authorized human or independent ability can use the same local client API.

## Qualification procedure, after separate authorization

Use the existing foreground safety controls. Create a fresh, empty, owner-only
directory with a short absolute path. Launch the development checkout on the
foreground terminal with `--hardware --object-recognition --camera-source elegoo
--object-seconds 90 --shared-recognition-directory /absolute/private/directory`.
Add `--object-label-display rp2040` to qualify the display path and
`--executive-recognition` to include Executive requests. The development profile
prompts for explicit owner authorization and power isolation. It shares the
existing runtime lock and writes only to the new session state.

From independent local processes in the development checkout:

```sh
python -m learning.recognition_transport /absolute/private/directory --frames 2
python -m learning.recognition_transport /absolute/private/directory --label CHAIR
```

For native qualification, run two recognition clients concurrently with an
existing passive frame reader and a display producer. Record device owners at
entry, under load and after STOP; frame/result identity and latency; serial ACKs
and visible precedence/clear; authorized and denied transport; thermal and
memory behavior; and cleanup after idle, cancellation and disconnect. Exercise
the Executive request in the guarded spawned process. Physical motion remains
prohibited throughout. The offline fixture results do not establish physical
ownership, inference timing, or serial behavior on the Pi.

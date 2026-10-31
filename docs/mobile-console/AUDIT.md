# Mobile Body audit — 2026-10-31

Repository `mrgarmise/charlie`. Isolated worktree `/home/five/charlie-mobile-console`,
branch `feature/mobile-body-console-20261031`. Original worktrees, dirty files,
PR heads, learning notebooks and physical records remain untouched.

## Pinned integration baseline

GitHub #13 head at audit: `77d7e3434229101a8612a81de69260b75925ed34`,
exact tree `5d4745ebb18650d916d9c4a624d4431bd3c9269c`.
Local #13 worktree was `8f3b988`, equivalent to published `ef41b4d`.
The two later published increments were restored into this isolated branch through
GitHub's authenticated file API; the resulting baseline tree matches exactly.
Local baseline commit `fa8c71e` is a source reconstruction, not a published ancestor.
New publication uses actual published #13 ancestry through Git-data API.
Shell fetch failed `Permission denied (publickey)`; no credential files modified.

#13's three head workflows were completed/success at audit: 40905354884
(unified), 40905354997 (sensory), 40905354962 (Best of Charlie).
Active PR inventory: #3, #5–#15, including #10 mobile abilities, #11 cameras/
object labels, #12 sensory contracts, #14 human questions, #15 model learning.
No merges, rebases, force pushes, or changes to these PRs are authorized by this
implementation's publication. New PR stacks on #13.

#10 inspected at `9c1319d2800749d19cd5086f34ba4643276d90a7`.
Its pet context, attention, Executive and safety layers are already reconciled
in #13. Existing face detector, pet tracker, qualified N2 pulses, STOP latches,
transport serializer, ActuatorSafetyAuthority, CapabilityDeployment, camera
feeder and StimulusBus remain the runtime owners. Dashboard requests do not
open a motor connection or acquire a camera.

## Dashboard and deployment

Existing hosted dashboard:
`https://charlie-project-dashboard.garmiseprojects.chatgpt.site`.
Sites project `appgprj_6ad39fb624888191ae560b8058e856a7`, version 2 at audit;
custom audience contains only its owner. Audience unchanged.
Its Git source is on `git.chatgpt-team.site`. The existing #13 in-process
`ui/dashboard.py` adapter serves abilities on loopback 8768 with exact hosted
Origin, strict Host and bearer authentication; SSH forwarding is documented.
Mobile Body extends this same server, rather than starting a competing control
service. Local navigation links Abilities and Mobile Body.

The Sites skill was read. Opening/packaging requires its Node source helper.
This session has no Node, external DNS resolution or socket creation; the helper
and source Git host cannot be used here. Site metadata/credential discovery was
read-only; no site version or access policy was changed. Hosted navigation
publication must remain explicitly pending until its actual source can be opened
and the prepared Mobile Body assets integrated, checked and published. Do not
replace the whole existing dashboard with the local fallback page.

## Native environment and physical boundary

Observed Raspberry Pi 5 Model B Rev 1.0, aarch64, Python 3.13, kernel
6.18.50+rpt-rpi-2712. No video/Hailo/ttyACM device nodes were exposed in this
session. `/proc/net/route` had no interfaces. Creating a loopback socket raised
`PermissionError: [Errno 1] Operation not permitted`; nodejs.org DNS resolution
failed. Chromium headless failed before rendering because crashpad's socket
operation was denied. These are environment failures, not native acceptance.
No hardware connection, motor command, firmware flash or active-service restart
was performed. Live camera FPS, exposure latency, ultrasonic accuracy and
physical driving are unmeasured.

#13's existing physical barriers still apply: exact installed firmware/bridge,
N2 completion timing, independently measured pan and exposure age, qualified
safety producers, device-local expiry, independent cutoff, physical STOP/loss/
preemption/braking measurements and boot-bound independent authority.
Browser ownership grants none of these. The original pivot-only envelope is
preserved; travel directions require additional measured per-direction trials.

## Sensor inventory

| Source | Existing support | Actual installed/live state |
| --- | --- | --- |
| ELEGOO MJPEG | Existing feeder, endpoint lease, shared frame subscriptions | Camera inaccessible here; no live measurement |
| Ultrasonic | Existing `read_ultrasonic`, N21/D1=2 via qualified shared transport | Requires installed-source protocol evidence/read-only authorization; no current reading |
| Chassis yaw | Existing N24 query and shared pose source | Installed semantics/accuracy need qualification; never substitute for servo position |
| Camera pan | Independent safety feed required | No verified measurement producer; last command is not a measurement |
| Line tracking | Candidate hardware in ELEGOO family; no shared verified installed driver | Physical presence and installed firmware protocol not established; deferred |
| Battery voltage | No qualified shared installed adapter found | Physical sensor/firmware availability not established; deferred |
| Raw inertial data | Yaw query exists; no verified raw accelerometer/gyro publication | Exact fitted IMU and installed read semantics unknown; deferred |

Manufacturer-family features are not proof of this car's installed sensors.
No speculative query packets, firmware updates or guessed registrations added.

## Tested increment updates

First published increment `35378337d50b0c4c923e2d553dfa7d26ccac7fcd`,
local `1ca0bd8`, tree `94b546a8265c949f47acaa5d008195dfa14f4072`.
Independent actual Chromium/HTTP/control validation: **26 passed**, 7.29 seconds,
job 124577256122 in run 41214888498; screenshots retained in mobile-browser
artifact 13047214911. This uses synthetic shared pixels and fake actuator wire.
The independent sensory workflow 41214888490 completed successfully on this head.
Full regression results are recorded separately when complete.

During publication, #13 advanced to `097f110fd0c6d321d24024c399d79f0a427bf23c`
with preserved validation documents only (nine files, no runtime changes).
PR #16 remains stacked and mergeable. No active PR was overwritten; the
implementation keeps its pinned runtime baseline and original ancestry.

Second increment prepares exact retained decision-frame overlays, independently
validated pan reads from the existing source/pixel-bound safety feed, and
bounded persistent manual replay protection using boot+opaque lease epoch+
strict monotonic sequence. It does not reset autonomous replay protections or
clear STOP uncertainty. Additional tests cover more than 256 manual requests,
actual watchdog worker operation, STOP during stalled encoding, missing forward/
reverse evidence, and stale/mismatched independent pan measurements. Focused
**82 passed** / canonical conformance **131 passed** on the second increment.

A native synthetic PNG baseline used 20 random 640×480 BGR frames, with median
51.0 ms and p95 56.2 ms encoding, mean 923,407 encoded bytes, about 18.9 encoding
operations/second on this Pi 5. This is NOT camera FPS or HTTP/exposure latency;
no transport/encoding optimization or achieved-live-target claim is made.
The complete machine-readable record is in validation/synthetic-png-baseline.json.

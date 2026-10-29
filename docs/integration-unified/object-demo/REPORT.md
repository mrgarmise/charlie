# Object demonstration implementation and validation

Mission: attached operator-requested 15-second Pi-camera identification demonstration.
Repository: `mrgarmise/charlie`; existing draft PR #13;
branch `integration/unified-sensory-motion-20261026`.
Inspected starting head: `ef41b4da77859be46378f3307e1da1112b0d64af`.
The PR description still referred to older heads; actual Git/API head was used.
Parent CI was in progress on inspection. No other PR was rewritten or merged.

## Implemented

Existing registry/AttentionManager intent admission; fixed stationary ability;
15-second monotonic lifecycle; authenticated, boot-bound single-use requests;
serialized repeated requests; cancellation and emergency preemption; restart
recovery and single-runtime lock; existing recognition/model/display reuse;
existing evidence journal and bounded content-addressed frame retention.
No Executive agenda mutation, new scheduler, physical acquisition owner or serial
owner. The stationary object application borrows its already-owned inference
pipeline; primary mode lazily attaches the same class to shared attention/display.

Extended `main.py`, `learning/object_runtime.py`, `learning/capabilities.py`,
`attention/manager.py`, `attention/object_labels.py`, `vision/object_recognition.py`,
and the previously empty `ui/dashboard.py`; bounded lifecycle is in
`learning/demonstration.py`. Shared local/hosted Abilities UI is in `ui/abilities.*`.

Existing Site identified by its source manifest and Sites response:
`appgprj_6ad39fb624888191ae560b8058e856a7`, owner-private custom access,
https://charlie-project-dashboard.garmiseprojects.chatgpt.site .
Its original source head was `022858658ad018317ed800dbb5025ec461f3390f`, static `dist/`.
It had no operational/authenticated robot channel. The added browser UI calls the
opt-in adapter in Charlie itself via an operator's SSH forward, with same-origin
local fallback if browser local-network rules block hosted-to-loopback requests.
No hosted robot backend or public listener was introduced. Inventory/history and
Site access are retained. Site source/deployment IDs will be recorded after publication.

## Software evidence

Host: isolated Linux x86_64; Python 3.12 virtual environment; no Pi hardware.
Fixture pixels/models/serial replies and loopback HTTP only. Test results do not
certify native firmware, Hailo throughput, physical label output or motion safety.

- Original affected regression selection: 54 passed (`validation/regression.txt`).
- Latest focused ability/object/display/normal-app selection: 86 passed, 3.36 s
  (`validation/focused-final.txt`, JUnit adjacent).
- Existing canonical integration conformance: 129 passed, 2.35 s
  (`validation/conformance.txt`). These overlap focused tests; do not add counts.
- Development full suite: 1,595 passed, 21 skipped, one existing JUnit format warning,
  364.01 s (`validation/full.txt`, JUnit adjacent). Development edits continued while
  it ran; it is not represented as a final-commit certificate. Clean-checkout and
  independent CI receipts will identify the exact final implementation revision.
- Node controller checks cover token memory, accepted-vs-executed state, cancel,
  network loss, route cleanup and endpoint validation (`validation/ui-controller.txt`).
- Existing dashboard: 11 Python inventory checks and 9 view/controller checks pass.
- Browser preview: existing overview and Abilities rendered; disconnected controls
  disabled, physical display unobserved, overview → Abilities repeated navigation
  worked. No browser-to-Pi execution was possible or simulated as native success.

Preserved initial failures: an incorrect test filename yielded no tests; the camera
fault fixture mistakenly republished a healthy frame before reading its fault;
the new repeat-app fixture omitted FixtureModel.close. The latter two fixtures were
corrected, without changing production safety expectations. Original transcripts
are retained in `validation/`. A `fatal library error, lookup self` diagnostic appeared
in the development full log, which nevertheless completed with zero failed tests;
no unsupported causal diagnosis or native success is inferred.

## Remaining acceptance

The exact setup, launch, tunnel, evidence and supervised acceptance procedure is in
[README.md](README.md). Installed runtime, notebook, Hailo/model identity, firmware
readback and physical pico:ed display remain **unverified**. `charlie.local` did not
resolve on this host. No motors, firmware, actuator grants or native services were
changed. No whole-robot deployment or merge was attempted.

The duration is cooperative: no new post-deadline label is admitted, but in-flight
native inference/serial/disk calls and cleanup must be measured. No native deadline
or STOP latency is claimed. Active face/pet/tracking/calibration work without a safe
resume contract is rejected, not falsely advertised as interruptible. The Executive
continues its existing durable notebook and developmental priorities.

## Published implementation and deadline correction

Initial implementation published as `23d2b07f494b48988181790ad5a0e52818cefd4d`
(local `58cda83`, identical tree `ec1d40b6409447f672619f68a8fc6de444249eba`).
Clean checkout: 86 focused passed / 129 conformance passed, before publication.
The existing branch was advanced with an exact expected-head check through GitHub's
Git-data API because shell Git has no push credential. Original ancestry is retained.

A subsequent review found two bounded-lifecycle edges: an active demonstration
could defer the existing whole-application `--object-seconds` shutdown, and attention
could tick a pending label immediately before the demonstration's deadline check.
The correction keeps application shutdown/quit ahead of demo work and checks demo
cancellation/expiry before label refresh. New tests cover both, alongside the repeat
normal-app test. Corrected focused selection: 88 passed, 2.96 s
(`validation/bounds-focused.txt`). Native timing remains unqualified.

# Native software recovery resumed — 24 October 2026

Software continuation of PR #9, not a new physical trial. The operator confirmed
there has been no later native recovery trial or timed controller-release test
since October 22 and explicitly directed reuse of the existing evidence.
No physical repetition is requested by this correction.

## Source recovery and preserved evidence

Published starting head: `0b40569ee3d282907ce7d077d30dcd058cc1fa1b`, tree
`412f9ec9a0548abba96a0c970dfce54d131a7b91`. The local recovery commit
`6fc794c` has that exact tree; ancestry/commit identity differs, source does not.
The older foreground worktree's lease changes are preserved; they are already
published in runtime `d6ef07b0b5a5959feedf50ef7f53a7fa026e29c6`.
Arcade PR #4 remains at `5ed9cc6fdf66cb22b93ba1587170e8280bc6a417`.
Nothing is merged or deployed by this continuation.

The authentic failure remains at:
`/home/five/charlie-native-trials/learning-20261022-025334`.
Its only recorded episode has zero action steps, unconfirmed terminal state,
baseline policy at d6ef07b, and `No complete game border found` before gameplay.
Neither the normal supervisor exit nor this recovery converts it into a game.
Original images, reports, journals and notebooks remain unchanged.

Camera/focus evidence is retained at:
`/home/five/charlie-final-admission-6gYsJjHl`.
The original metadata reports LensPosition 2.0, FocusFoM 8069 and AfState 0.
The empty owners-before file is an evidence-time observation, not a current
ownership certificate. `evidence.json` records the actual local source hashes.

Controller evidence location supplied by the operator:
`charlie-arcade:/home/five/controller-final-kFwHl9pA/controller.jsonl`.
On October 24 the operator confirmed that this existing test demonstrated
neutralization in approximately **0.92 seconds**. This supplies the timing missing
from earlier local review notes; it is not a newly performed test. The reported
latency is below the existing 1.4-second acceptance window. The source remains on
the arcade host and was not destructively changed or replaced.

A read-only SSH fetch was attempted. The normal client refused the visible system
SSH config ownership; the already documented explicit-config invocation then hit
`socket: Operation not permitted`. These receipts are retained. The remote JSONL
was not read or hashed by Codex, so no independently recomputed latency, additional
secondary-client result or all-gates physical acceptance is claimed. This is an
artifact-access limit, not a controller failure and not a reason to repeat the
physical test. If an independent audit needs the raw lines, transfer/review the
existing file through the ordinary host mechanism; do not rerun the experiment.

## Software correction and verification

The prior recovery fixes the authentic border failure with at most four fresh
final-frame reads within the existing sensory deadline. Every accepted frame must
independently pass border/edge/endpoint, stable-geometry agreement, focus and detail
gates. Supported geometry movement fails immediately; persistent misses and unsafe
frames fail closed. No border assertion, focus lock or geometry limit is relaxed.
Archived failure/good frames exercise this exact failure path in regression tests.
Their reordered replay does not claim a successful later native frame.

This continuation repairs a separate evidence gap in the existing native resource
callback. Thermal, memory, throttling and disk refusals previously raised before
recording the failing observation. They now append and fsync a `status=stopped`
record with available measurements and the original exception. Disk free bytes,
monotonic time and admitted status are also retained. A failed stop-trace write
adds a note to the original safety exception rather than masking it. An admission
trace/fsync failure still aborts the trial. The existing supervisor continues to
stop its owned worker; there is no automatic cooling/resume or retry.

Existing 75°C, throttling, 768 MiB process-tree memory and 2 GiB disk safeguards
are unchanged. No physical controller, camera, firmware, service or policy interface
was changed. This is instrumentation/safety engineering, not Charlie-originated
learning. It needs software verification, not a new physical release experiment.

Final focused selection: **84 passed in 61.96 seconds**, zero errors/failures/skips.
It includes archived-frame border recovery, resource refusal/trace failure cases,
marathon camera/session and between-game learning, native wrapper, preflight,
recording and integration contracts. Prior native 153-test and arcade ARMv6 receipts
remain valid for their recorded source identities; they are not relabeled as tests
of this changed source. All earlier failures remain preserved.

Reproduce without physical device access:

```bash
CHARLIE_AUDIT_CODE=/home/five/charlie-pr9-recovery \
  bash /home/five/charlie-native-integration-evidence-20261020/sandbox.sh \
  -m pytest -q tests/test_recovery_entrypoint.py tests/test_final_image_recovery.py \
  tests/test_marathon_camera_session.py tests/test_marathon_deferred.py \
  tests/test_native_robotron_trial.py tests/test_robotron_preflight.py \
  tests/test_sensory_recording.py tests/test_native_integration_contracts.py \
  -p no:cacheprovider
```

## Authority and claims

Standing gameplay authority remains in force under
[the operator grant](../../OPERATOR_GAMEPLAY_AUTHORIZATION.md). The historical
recovery README's reference to another express gameplay approval does not override
that grant. Technical readiness and bounded phase reviews remain mandatory.
Per the latest instruction, software recovery uses existing October 22 evidence;
no additional physical trial is required or launched for this correction.

|Item|Status|
|---|---|
|Published source/tree reconciliation|VERIFIED|
|Archived final-border failure reproduction/recovery controls|VERIFIED in software|
|Resource-stop evidence and fail-closed writer behavior|VERIFIED in software|
|October 22 camera/focus metadata|VERIFIED locally, historical|
|Approximately 0.92-second neutralization|RECORDED operator evidence; raw remote file not independently read|
|Original developmental attempt|FAILED before gameplay; zero completed games|
|New Game 1 → Game 2, complete-game performance|NOT YET DEMONSTRATED; not attempted|
|New authentic E1/P1/I1 acceptance|NOT YET DEMONSTRATED|

No new learned candidate is manufactured or activated. Existing qualified-policy
interfaces and retained-memory provenance remain intact. The recovery mode retains
Executive selection, durable projects and eligible between-game Reflection/Meditation;
flags and saved records alone do not prove E1/P1/I1. No physical retest is needed to
close this engineering correction, and no marathon success or ALA-2 closure is claimed.

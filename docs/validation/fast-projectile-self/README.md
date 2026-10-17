# Fast SELF acquisition — implementation and open native validation

Baseline: `d74d7a620c39104ce58fb2c9551381543a66b5f2`.
Implementation branch: `feature/fast-projectile-self`.
This work does not authorize physical gameplay, controller access, firmware,
servos, or activation of an unqualified policy. No native campaign was run.
ALA_LEARNING_CHARTER.md and ALA2_ACCEPTANCE_STANDARD.md govern acceptance.
**E1, P1, and I1 each remain NOT YET DEMONSTRATED.**

## Changes

Acquisition now starts with stationary E and N firing experiments, then falls
back to the original movement/reversal/neutral evidence thresholds. Provisional
identity no longer terminates discovery. Generic component extraction bypasses
taught template classification during acquisition; ordinary Forebrain/Hindbrain
recognition, decisions, and thresholds are unchanged. Recovery removes the
redundant four-frame template batch. Faster observation and fire-first evidence
use the existing three-second recovery action budget. That safety budget is not
extended to compensate for failed identification. Existing terminal safety, the
20-second uncertainty deadline,
watchdogs, recording limits, and neutralization remain in force.

Center ordering applies at initial acquisition and after an independently
confirmed respawn. It adds no causal hits or confidence. `confirmed_respawn`
requires both death and respawn confirmation and rejects GAME OVER; reframing
retires identities and projectile evidence without recycling track IDs.
**The native screen classifier currently has no qualified individual-life
signal. SELF disappearance is not one. The boundary API is implemented and
host-tested, but automatic life-boundary integration remains blocked on native
life evidence.** Unknown-identity recovery still runs fire-first acquisition.

Small components are only projectile *candidates*. Shot inference requires a
new component absent from the pre-command baseline, three strictly increasing
observations, unique temporal association, outward straight motion aligned
with the acknowledged firing command, and a unique back-projected sprite
origin within the command timing window. Two nonparallel experiments with a
common origin provide the alternative confirmation route. Preexisting objects,
crossings, curved effects, off-axis motion, multiple plausible origins, mass
transitions, missing/mismatched command timing, stale evidence, and competing
origins cannot qualify. These are conservative geometric gates, not calibrated
probabilities or a learned projectile classifier.

The alternative route is disabled by default. `--projectile-self` is an
explicit experimental option in the player and marathon runner. It must not be
selected for a native campaign until independent native qualification and
physical authorization exist. Shadow shot evidence and movement confirmation
work without that option. No movement threshold was reduced and no synthetic
movement hits are manufactured from shots. A qualified shot identity uses the
existing SELF handoff; disappearance, uncertain association, global motion, or
reframing invalidates that route. New contradictory measured BODY evidence
also invalidates shot confirmation. Historical movement-only replay explicitly
disables fire-first experiments; saved frames are never relabeled as new shots.

Manual focus **2.0** in current sensory preflight, the single uninterrupted
marathon camera owner, automatic restart permission checks, and the three-game
block/reflection order are retained. The campaign adapter and original
3,247-record notebook were not modified. No new learning outcome is claimed.

## Host validation

Final frozen-source `python3 -m pytest -q tests`: **1,301 passed, 21 skipped,
0 failures, 0 errors**, in 337.06 seconds. The single warning concerns JUnit
`record_property` formatting. A 90-test focused regression set also passed.
The 23 new deterministic cases are included in the full result. Tests use
synthetic scenes, saved observations, fake clocks/cameras, and loopback or
in-memory controllers; they establish no new physical performance or learning.
`host-tests/` contains final logs, JUnit, source hashes, environment metadata,
and earlier failed/interrupted development runs. Source hashes match the
published implementation; no runtime code changed after the final run began.

## Authentic October 17 failure

`originals/` contains the exact recovered `charlie-first-game-diagnostics.tar.gz`
and `charlie-first-three.log`, with SHA-256 hashes. Originals in the user's
source files remain unchanged. The archive contains session
`development-20261017-182719`, baseline d74d7a6, 35 agency rows, provisional
identity but no confirmed SELF, zero tactical ticks, and result
`OBSERVATION UNCERTAIN`. Discovery took about 5.97 seconds; subsequent recovery
lasted about 20.28 seconds. These are failure observations, not successful
replay or new gameplay. The included limited images are insufficient to replay
three-frame projectile trajectories; none are invented or relabeled.

`timing.json` separates archival native metadata from a host-only benchmark on
one authentic saved playfield image. Archival median delivered cadence is
1.491 observations/s, sensor frame-duration cadence 14.906/s, exposure 66,636
microseconds, capture call 116.1 ms, unique-command readiness 24.2 ms, and
per-wire-command acknowledgment 10.6 ms. Readiness includes no-op intervals;
acknowledgment is not physical controller response latency. Acquisition-specific
processing latency was not recorded in that campaign. No 20-ms sampling or
30-shots/s assertion is supported. New native rates are **unmeasured**.

The host benchmark has ten samples per path, approximately 20.4 ms for class-free
extraction versus 37.1 ms for full recognition. It ran on the host under shared
load; it does not predict Raspberry Pi performance, detection quality, FPS,
shot rate, or gameplay success. Pixels, component gates, and body association
require native validation with labeled trajectories.

## Reproduction and native validation

Host only (use an isolated TMPDIR; tests use fixtures and loopback controllers):

```sh
mkdir -p /tmp/charlie-fast-self-tests
TMPDIR=/tmp/charlie-fast-self-tests python3 -m pytest -q tests
python3 -m pytest -q tests/test_projectile_agency.py
```

Do not run repository-root pytest: legacy manual scripts attempt hardware
imports/access during collection. An initial mistaken root collection attempted
the absent `/dev/ttyACM0` and failed; no device opened. The resulting collection
failure is retained with the test evidence.

Read-only archival audit after extracting the preserved archive to a separate
directory (never modify the original):

```sh
python3 -m experiments.ppal.projectile_agency /path/to/game-01/agency.jsonl
```

When a Pi operator has permission for camera-only observation, the following
opens only the camera, locks focus 2.0, measures fresh requests and processing,
closes the camera, and then writes JSON. It imports no controller and sends no
controls. Use an output outside the original notebook/evidence directories:

```sh
python3 -m experiments.ppal.acquisition_profile --native-camera --seconds 10 --output /tmp/charlie-acquisition-timing.json
```

Report independent delivered cadence, sensor FrameDuration and SensorTimestamp,
ExposureTime, capture wait, processing distribution, focus metadata, missing
metadata, and skipped frames separately. Keep raw timing rows. The short
camera-only profile is not the later uninterrupted three-game camera session.
The profiler processes full camera frames, not the calibrated gameplay pipeline;
it does not measure complete screen-classification/journal overhead.
Controller acknowledgment and physical response latency require independently
authorized native observation; synthetic clocks cannot establish either.

Before enabling projectile confirmation: obtain consecutive native frames with
independently labeled player/enemy/effect origins, changes in fire direction,
occlusion, crossings, and life boundaries. Replay with the exact recorded
command/acknowledgment/exposure times; establish false-positive and missed-shot
rates for the documented geometric gates. Verify that ambiguity stays unknown,
a confirmed shot identity reaches the existing tactical policy promptly, and
movement fallback still works. Supply qualified individual-life evidence to
`confirmed_respawn`, then demonstrate fresh center-prior acquisition without
inheriting prior-life identity. Never use UNKNOWN as a confirmed death.

Only after a **separate** physical grant and native qualification: use the
existing campaign's one three-game block and automatic restart permission
checks. Keep focus 2.0 and the same camera session through all three complete
games; run offline reflection/meditation only after all three have completed
and the camera is closed. An uncertain boundary must stop restarts rather than
count as a complete game. This document is not that grant and intentionally
does not give an armed launch command.

## Outstanding blockers

- No Pi access in this environment: new native FPS, processing, controller
  response, reliable projectile discrimination, acquisition speed, and meaningful
  tactical gameplay have not been demonstrated.
- Projectile confirmation is experimental and off by default; native thresholds
  and false-positive qualification are required before activation.
- Independently verified native death/respawn sensing is unavailable. The API
  does not turn missing SELF or GAME OVER into life evidence.
- If fast acquisition still fails within the existing three-second action budget,
  controls still stop for terminal investigation. Eliminating that quiet period
  has not been demonstrated and is not achieved by relaxing a safety budget.
- No new three-complete-game campaign, uninterrupted-session result, or learning
  improvement is claimed. Original notebook and evidence remain preserved.
- E1, P1, and I1 remain independently open; host tests close none of them.

## Rollback

No deployment or firmware change occurred. For an offline rollback, first retain
any new evidence and notebook files outside the checkout, then create a separate
baseline checkout:

```sh
git worktree add ../charlie-d74-rollback d74d7a620c39104ce58fb2c9551381543a66b5f2
```

Do not reset, delete, or initialize the original notebook. A future operator
must obtain physical authority separately before running either revision.

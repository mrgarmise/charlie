# Retained-work dependency wakeup — 2026-10-05

Recovered and published stall-accounting implementation checkpoint:
`c62c155c32a618cfc8b310084cc262199ddb4fdd`. During continuation, independently
fetched and preserved the additional recovery evidence at
`718cf50eeb10365021e1dab98c58b019c8b3374d`; it changes no functional code.
This checkpoint continues the same Executive and acquisition interfaces.

## Independently demonstrated fixes

A new regression first demonstrated that a blocked experiment's changed
checkpoint was ignored after restart: the durable waiting signature did not
include retained experiment state. The initial failure is preserved here.
Waiting now includes substantive checkpoints of blocked, unfinished predictions,
the existing capability descriptions, execution-adapter hashes, and verified
identity-location changes. Experiment resumption uses the same dependency
contract. A changed checkpoint, reviewed capability, or adapter implementation
can therefore wake the ORIGINAL prediction. A heartbeat/PID/clock change does
not wake it. Completed predictions are excluded; no independent evidence or
qualification credit is awarded for a runtime change.

A second regression first demonstrated that a partially reflected context whose
source was subsequently quarantined falsely kept the portfolio busy. That
failure is also retained. Pending meditation eligibility now uses the same
acquisition eligibility check as actual reflection. Genuine modified artifacts
remain quarantined, original commissions/checkpoints remain intact, and an
otherwise exhausted portfolio waits without repeating commissions. Other valid
investigations remain eligible through the existing Executive.

## Executed evidence

- Recovery targeted suite: 39 passed in 46.54s before publication of the recovered
  checkpoint; inherited reports are preserved as prior-session evidence.
- Wakeup/stall focused suite: 11 passed in 11.57s.
- Integrated lifecycle/identity/yield suite after quarantine correction:
  44 passed, 1 authentic-artifact test skipped because its environment path was
  not supplied to that invocation.
- Final full offline `tests/` suite with original October 1 archives supplied:
  **542 passed, 19 Torch-dependent skips in 94.55s**. Raw logs/JUnit retained.
- Normal `main.py --offline`, twelve turns then twelve restart turns on a COPY
  of the preserved 475-record host continuation notebook: both exit 0; first
  and restart both contain **488 records**. All 475 original IDs, documents and
  commitment timestamps are preserved exactly. Both original temporal project
  experiment histories are unchanged. Thirteen relocation/consolidation,
  acquisition-bookmark and waiting records are not new findings or game episodes.
  No new scientific findings or independent games were created by replay.

Host notebook: `/workspace/scratch/1e5a01e5b074/stall-wakeup-continuation`.
Source notebook: `/workspace/scratch/c81a2d35e2bc/stall-authentic-continuation`
remains unchanged. Retained restarted journal content digest:
`c2368284b0249ba97e57ca04ac867cbdad7a6d06716ce0a86173cb6f3658a1d9`.
The controlled acquisition-delivery regressions commission and independently
evaluate Charlie-originated offline candidates without deployment grants. They
are software acceptance evidence, not authentic physical observations or score
improvements. Authentic investigations remain waiting for qualified evidence.

## Native gate and commands

The supplied native status/log shows paused unresolved work, acquisition gaps,
and repeated phases at d6eea1cc. Work cannot access the actual Pi journal or its
commission/checkpoint trajectory; its exact progress or stall cause is not
inferred solely from that status. Operator-reported native 82-test regression
does not establish native developmental acceptance. **Native acceptance remains
PENDING** until the following is executed against the same interrupted notebook:

```bash
cd /home/five/charlie-ala2-bae659f60b0e
RELEASE='<full containing published SHA>'
git fetch origin feature/agency-first-self
git show "$RELEASE:tools/update_existing_ala2_pi.sh" | bash -s -- "$RELEASE"
CHARLIE_LEARNING_STATE=/home/five/.local/share/charlie/development \
  bash tools/accept_episode_identity_pi.sh "$RELEASE"
```

Set CHARLIE_LEARNING_STATE to the actual interrupted notebook. The existing
guarded procedure preserves original artifacts, exports pre-run history under
acquisition-owned evidence exports, records pre/post commissions, checkpoints,
requests and outcomes, runs native regressions, then twelve normal turns and
twelve restart turns without activation grants. It requires durable waiting and
exact restart history, not mere phase activity. Advancing incomplete work remains
pending; retain its receipts rather than deleting it or removing resource bounds.

No physical gameplay, movement, firmware or learned physical policy activation
was performed or authorized. Future gameplay behavior has not been activated.
ALA-2 remains open: independently verified learning-derived complete-game
Robotron SCORE improvement has not been demonstrated.

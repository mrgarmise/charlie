# Bounded meditation yield and continuation

Parent independently verified on feature/agency-first-self: `eb6dce754e5085d3e99a4b8e9f5b6c67b93ea883`.
This is a bounded-resource recovery fix, not another episode-identity implementation.

Operator-reported native update: 524 tests passed; acceptance regression: 77 passed.
The subsequent twelve-turn normal lifecycle **did not finish**: its bounded
meditation deadline escaped through reconstruct_once, reflect_experience and
LearningExecutive.develop. Native lifecycle acceptance remains incomplete.
No native Pi/Pico access or physical action occurred in this fix session.

## Behavior

The resource deadline is unchanged (normal budget remains 1..60 seconds).
Expected deadline/primary-task interruptions save an atomic, source-hash-bound
checkpoint and a durable `normal_meditation_yield` event, not a completed finding.
The same context and content-addressed Executive commission resume next turn.
Reconstruction retains its left/neighbor cursor and previously scored candidate
pairs; JSON round trips preserve the original stable ranking and mutual-best
algorithm. A reconstructed iteration is retained when yielding before evaluation.
Completed iteration history is retained, and a saved stable iteration is not run
again. Legacy whole-iteration checkpoints remain readable. New checkpoint digests
and context/commission binding reject inconsistent state instead of publishing
invented findings. Immutable yield receipts record their checkpoint hash at that
time; checkpoint files advance as working state and are not immutable findings.

A deadline yield permits other eligible Executive investigations. Actual primary
task contention preempts the rest of the developmental turn. Existing camera,
controller, scheduler, activation, rollback and source identity interfaces remain
in place. Unexpected exceptions and evidence-integrity violations still fail;
there is no broad swallowing of TimeoutError or arbitrary meditation failures.
An abrupt process kill may redo only work since its last durable checkpoint;
completed committed iterations/results and commissions are reused.

## Executed host evidence

Five dedicated regressions exercise interruption inside reconstruct_once,
non-repetition of completed pair comparisons, deadline and primary-task yielding,
normal subprocess restart with one commission/result, retained original records,
Executive resolutions, subsequent restart deduplication, old stable checkpoint
reuse and corrupt-checkpoint refusal. Normal lifecycle plus new regressions:
16 passed. Final broad suite: **529 passed, 20 skipped in 66.65s**.
Nineteen skips require Torch; one requires the separately supplied authentic
October 1 artifacts. The authentic identity suite is also rerun separately with
those originals (see identity.txt for exact results). Raw reports and skip
reasons are retained here.
The initial broad failure was a test expectation that primary preemption must
raise; it was corrected to assert ordinary experiencing disposition instead.
Its raw report remains preserved. Hardware IO is simulated in controlled tests.

Separately, normal main.py continued a COPY of the authentic 455-record recovered
notebook with a one-second learning slice for twelve turns and restarted for
another twelve. Both normal processes exited successfully. The final notebook
contains 467 records and retains all original IDs/documents/commitment timestamps.
The original notebook was not modified. Logs and summary are retained here.
Copy location: `/workspace/scratch/c81a2d35e2bc/yield-authentic-continuation`;
source: `/workspace/scratch/1e5a01e5b074/identity-authentic-final`.
This is host preserved-evidence processing, not simulation or new independent
physical experience. Authentic work remains waiting for independently qualified
evidence; no eligible physical improvement was manufactured or activated.
The twelve additional records are evidence-continuation references/events, not
new game experience or new diagnostic findings. This already-completed notebook
had no pending meditation yield; the forced inner-yield regressions establish
resumption itself. The two original temporal investigations and historical
partitions are preserved.

## Guarded native rerun on the SAME notebook

Use the full containing release SHA reported after publication:

```bash
cd /home/five/charlie-ala2-bae659f60b0e
RELEASE='<published full SHA>'
git fetch origin feature/agency-first-self
git show "$RELEASE:tools/update_existing_ala2_pi.sh" | bash -s -- "$RELEASE"
CHARLIE_LEARNING_STATE=/home/five/.local/share/charlie/development \
  bash tools/accept_episode_identity_pi.sh "$RELEASE"
```

Set CHARLIE_LEARNING_STATE to the actual prior failed run's persistent notebook;
do not create a replacement or delete partial meditations. The existing script
requires that journal, exports history before execution, preserves original
capture roots, now includes the yield regressions, and runs twelve normal turns
then twelve restart turns with no offline/physical deployment grant. Untracked
files and historical notebooks remain intact. No firmware or hardware is started.

If unfinished meditation continues during the second run, the existing exact
restart comparison deliberately reports changed state; both logs and notebooks
survive. This is continuing work, not proof of duplicate experience. Inspect
commission/result IDs, yield checkpoint progression and retained original rows;
continue the same normal offline application until stable. Do not call the native
acceptance passed merely because regression tests passed or a finite run exited.
Guarded native lifecycle completion and independent score evidence remain pending.

ALA-2 remains open until a Charlie-originated operational change independently
improves complete-game Robotron SCORE. No physical gameplay, servo movement,
firmware deployment or learned-policy activation is authorized by this handoff.

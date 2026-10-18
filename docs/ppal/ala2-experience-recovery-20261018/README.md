# ALA-2 experience-to-decision recovery — implementation checkpoint

**Status: software integration in progress; E1/P1/I1 NOT YET DEMONSTRATED.**
This work implements only scoped mechanisms. No original notebook, recorded
game, physical policy or controller has been modified or activated.

## Governing rules

Read ALA_LEARNING_CHARTER.md and ALA2_ACCEPTANCE_STANDARD.md. Preserve
the original mission (including exact October 9 invalid meditation, native
original-notebook acceptance and complete-game score comparison). A copied
archive is not a new independent experience, and meditation is not automatically
learning.

## Preserved inventory and immediate recovery targets

The October 18 audit located 57 recording candidates, not 57 qualified
complete games. Its primary notebook has 3,247 records, 46 directly imported
recordings and 17 unambiguously bound completed-meditation groups. The separate
October 16 copied notebook has 3,832 records, including seven more completed
meditations; it is **not** a replacement production notebook.

Eleven recording candidates without primary ingested contexts are:

- development-20261011-183415/game-01
- marathon-20261008-032614/game-01
- marathon-20261009-004249/game-01
- marathon-20261009-021200/game-01 (reported GAME OVER; not independently certified)
- development-20261011-043454/game-01
- development-20261017-182719/game-01
- development-20261017-200109/game-01
- development-20261011-203343/game-01 (reported GAME OVER; not independently certified)
- development-20261011-212606/game-01
- charlie-shot-validation-01
- development-20261011-221727/game-01

**No indiscriminate import.** First compare source identities and partial
sessions, then ask the existing Executive to investigate only eligible new
contexts. Reject duplicate recordings and unfinished/uncertain boundary claims.
The preserved originals, canonical manifest, direct traces and overnight
continuation are distinct sources. The original Mint microSD-image comparison
remains required; the two SSD copies alone do not prove complete migration.

## Implemented on this branch

1. The ordinary offline investigation loop no longer treats an **unresolved**
   prediction as harmful feedback to a selected hypothesis. Contradicted
   hypotheses remain falsified, but that is not a judgment that the method
   itself was uninformative, or that score performance improved.
2. A bounded durable tactical diagnostic ledger keeps only confirmed
   same-track action-response windows, source IDs, results and local episode
   origins. It rejects ambiguous/ineligible observations and duplicate
   prediction identity. It can be reloaded after a process boundary.
3. Hindbrain can receive that ledger during **offline software evaluation**.
   Retained experience changes a traceable shadow preference, while the normal
   physical action remains unchanged. The game runner does not instantiate
   the ledger or activate a learned policy; separate native integration and
   authorization are required.

These are implementation claims, not authentic acceptance. Synthetic tests
must be reported as tests, never as new gameplay or E1/P1/I1 success.

## Native work to resume without rebuilding the Executive

Perform development on a separate code worktree; retain the existing Pi local
serialization fix and the newer PR #5 capture changes for explicit review.
Never replace the current Pi checkout with GitHub master by force.

1. Quiesce writers and make a consistent **isolated copy** of the 3,247-record
   notebook and its associated source stores (including main/WAL if present).
   Record source/copy SHA before work. Keep the 3,832-record overnight copy
   separately, and reconcile its additional records by IDs and provenance
   rather than overwriting the baseline.
2. Use existing `main.py --offline --episode-root PATH --learning-state COPY`
   and the existing lifecycle/acquisition/meditation/Executive machinery to
   process verified, previously unlinked recordings. The Executive, not Codex,
   owns questions, experiment choices and outcome conclusions. Preserve
   meditations and rejected/inconclusive results. It is allowed to wait.
3. Reconcile the recovered 8 score annotations/6 images through the already
   implemented PR #3/best-of review importer **on copies**, resolving label
   finality and use partitions before testing a held-out score reader. No
   synthetic score improvement claim.
4. Build an offline adapter to recover actual historical `tactical_prediction`,
   `tactical_execution` and `tactical_outcome` links into the diagnostic
   ledger. Require exact source identity, episode origin, confirmation and
   same-track window, **and never credit archived copies as fresh trials**.
   Do not put synchronous SQLite/JSON writes in the real-time gameplay loop.
5. In an isolated evaluation harness, freeze identical PPAL inputs and compare
   no learned state vs retained state vs ablated state, across fresh process
   reload. The shadow must show exactly which authentic evidence changed
   valuation. Do not actuate the learned choice until existing qualification,
   readiness, authorization, safety and rollback gates approve it.
6. For E1, freeze opportunity set before normal authentic Executive
   investigation, retain the resolution through restart, record actual later
   selection/valuation and its scoped causal control. Do not equate retrieving
   frozen references with resolving causal gameplay uncertainty. The optional
   information-yield shadow is not an authorized production chooser.
7. Keep source-image survival, exact October 9 native continuity, qualified
   E1/P1/I1 integration, independent score and autonomous operation as
   **separate** acceptance decisions. Update CHA-5/6/7/9/10/13 with dated
   evidence without creating parallel project records.

## Predeployment checks

Run targeted new tests, existing lifecycle/Evaluator/Hindbrain/PPAL tests,
then the complete host software suite. Run all native tests with hardware
disarmed. Do not claim native acceptance based on GitHub Actions alone.
Measure overhead before any future real-time integration. Obtain separate
permission before gameplay, policy activation or firmware/servo operations.

### Recovery status

- Historical copy parity: audit-reported, original SD image not compared.
- Native copied-state continuation: historical result only.
- E1: NOT YET DEMONSTRATED.
- P1: NOT YET DEMONSTRATED.
- I1: NOT YET DEMONSTRATED.
- Complete-game SCORE comparison: NOT YET DEMONSTRATED.

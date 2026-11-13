# Separate promotion / reconciliation manifest

**Review candidate only. No merge, cherry-pick, promotion or deployment performed.**
The separately running runtime-promotion review remains authoritative for any
future integration decision. This continuation does not approve its parent stack.

| Source | Verified published identity / consequence |
|---|---|
| PR #23, campaign/mobile-review-options-20261101 | `3b364f9b3eca8ae3348fb5f9eb4eaeb315f32b27`; inherited review options and normal Executive lifecycle. |
| PR #26, objective-a/normal-runtime-20261101 | `3d8591d8126bf9bc8c49bdddfb80fd7ea5487b98`; inherited normal attention/vision/monitoring integration. |
| PR #27 older metadata | `b60f4a5edb3605bac212ce7ed81a1f9b43ba92e5`; connector PR head remains stale. |
| Actual fetched PR #27 branch | `b0c04ad4c5c6e1f0b2b9fd2e6316af286c36c01f`; confirmed by git fetch and ls-remote, contains b60f4a5. Adds optional-metric benchmark fix, two tests and report. This is the continuation base. |
| New isolated branch | `feature/operational-consultation-20261104`; based on b0c04ad, targets PR #27 branch for a minimal review diff. |
| Approved stationary runtime | `f3304c588a893a953e34e5c4d00bd5f9bfb18f19`; operator-specified identity. Absent from this clone and GitHub commit lookup returned 422. Native tree, dirty state, approval and launcher comparison **pending**. |
| PR #25 / pico display | Not imported or changed by this continuation. Approved runtime may contain native integration not present in this parent stack. Preserve it. |

The machine-readable source manifest retains inherited file inventory, original
PR #27 patch digest and continuation changes. The full inherited diff is available
with `git diff 3d8591d8126bf9bc8c49bdddfb80fd7ea5487b98 b0c04ad4c5c6e1f0b2b9fd2e6316af286c36c01f`.
Original PR #27 CI reports 1782 pass / 27 skip; those are historical source results,
not results of this continuation.

## Minimal implementation delta from PR #27

| File | Change / dependency |
|---|---|
| learning/consultation_activation.py | New gated local-only transport, attestation/residency/service checks, finite safe-idle admission and uncertain-completion latch. Uses existing bounded HTTP/parser and service/journal interface. |
| learning/consultation.py | Result-retention acknowledgment, transport cleanup/status, original evidence-age recheck. Existing Executive selection, privacy, daily/queue budgets and append-only unverified outcomes retained. |
| learning/lifecycle.py | Pass the optional approval into the existing worker's consultation factory and close its provider on lifecycle shutdown. No additional Executive or notebook. |
| main.py | Additional default-off approval flag; forward only to normal development worker; reject synchronous mobile/pet paths. |
| tests/test_consultation_activation.py | Native fakes, failure/restart/expiry/concurrency/cleanup boundaries. No physical I/O. |
| .github/workflows/consultation.yml | New continuation branch plus relevant path triggers; existing focused/contracts/full suite and evidence artifact. |
| docs/consultation/OPERATIONAL_* and PROMOTION_RECONCILIATION.md | Scope, limitations, native acceptance, rollback and evidence ledger. |

No hardware, firmware, motion, acquisition, AttentionManager, vision, model-learning
policy, existing journal implementation, human correction or dashboard server file
is modified by this delta. No inherited source is silently promoted into the
approved runtime merely because it is an ancestor of the review branch.

## Required read-only native reconciliation before any promotion proposal

On the Pi, verify the approved SHA and clean/dirty state, preserve unpublished
patches, and compare trees in a separate candidate worktree. Obtain exact
`git diff --name-status f3304c5... <candidate>` and inspect changes to main/lifecycle
against the native integration, including pico font and manual/monitoring changes.
Do not assume a commit absent from GitHub is missing locally or reconstruct it.

If PR #27 is absent from the approved runtime, first reconcile its consultation,
Executive, UI/status and review-option dependencies as an explicit reviewed
change. Then apply this small continuation delta in an isolated promotion branch.
Do not wholesale replace main.py or import the full #23/#26 branch. Re-run normal
review-option combinations, architecture contracts, full suite and native
qualification on the resulting exact integrated tree. This manifest contains no
command to write, reset or cherry-pick into `~/charlie-runtime`.

Even after software review, safe-idle real transport needs its native prerequisites
and finite integration acceptance. Active sensing remains unsupported because
stock Ollama cannot atomically guarantee resident-only inference. Hardware movement
restrictions, rollback, original approvals and all unrelated draft PR holds remain.

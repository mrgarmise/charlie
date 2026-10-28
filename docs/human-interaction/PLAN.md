# Implementation boundary and acceptance plan

Baseline: master bcf8082. Inspected all PRs #3–#13 and branch inventory on
2026-10-28. PR #13 head 08ae83f is draft; all three latest CI workflows pass.
PR #12 ae09f52, #10 9c1319d, #8 b4f2588 and #7 83112b4 remain open.
No upstream branch is merged, rebased, overwritten or deployed by this work.

Owners: memory.learning_projects.LearningExecutive decides; EvidenceJournal
owns immutable evidence; MemoryGateway/MemoryEvaluator select durable memory;
learning.lifecycle and capabilities retain execution ownership. PR #13's
MobileEvidenceAdapter records mobile_perception with PetTracker session-scoped
IDs. ScoreObserver owns score_review_proposal and its stricter digit review.
Existing viewers provide no suitable general authenticated question lifecycle.

1. Extend the existing Executive with opt-in evidence-derived question review.
2. Project durable lifecycle from the existing EvidenceJournal, with atomic
   answer/evidence commits and requester-specific consumption receipts.
3. Provide a separate loopback-only HTTP renderer with authenticated writes,
   same-origin checks, bounded input, no camera or actuator dependencies.
4. Exercise deterministic pet and Robotron contracts, security and regressions;
   publish coherent tested increments and independent CI receipts.

Acceptance matrix: Executive-derived request, persistence, attributed evidence,
consumer routing and both fixture examples are software-test eligible. Browser
interaction must be exercised separately. Live pet integration is PENDING:
master lacks learning.mobile.MobileEvidenceAdapter and PetTracker. Its
opportunities(observation_id) on PR #13 is the future opt-in call site; do not
patch that active branch. Actual game/Pi/phone/physical acceptance remains
PENDING unless directly exercised. No authority, firmware or GPIO change.

# Exact proposed merge order and gates

No master or operational merge is authorized. The proposed master unit is the
single cumulative draft [PR #39](https://github.com/mrgarmise/charlie/pull/39).
Its final independently green exact SHA/tree must be pinned in the PR evidence
before a human may approve that source-only merge. Do not merge donor PRs again.
All source PRs remain open and their original heads/evidence remain preserved.

Internal dependency order already represented in the candidate is:
#13 (supersedes #10/#11/#12), #18, #19 (reconciles #14), #20 (#15), #21 (#16),
#22 (scoped #7 immutable acquisition), #23, #26 plus separately selected sibling
#25 font, #27, #33, #36, #38, then #39 adoption tools; #28 networking and
#29 firmware core, #30 inherited by latest #31 cab7babcae913cb33c15aa3115867ca31fe0ecf6,
then #32 audit-only; finally #9's compatible #5/#6/#7/#8 source slices with
current camera/Hailo ownership retained. #3 score feedback uses its newer
reconciled implementation. #24/#34/#35/#37 are documentary, not extra runtime.

Before each disposable integration increment: refresh source/target identity and
holds, inspect ancestry and changed owners, compare the real approved baseline,
retain source test baseline, identify expected paths and conflict resolutions.
After: focused and negative safety tests, contracts, baseline manual-LLM guards,
full CI, relevant browser/C++/firmware builds and artifact hashes, evidence/state
preservation, kill/restart and rollback compatibility. Failure blocks dependent
integration until repaired; retain the failed receipt. A source reconstruction
never starts a service or carries over an active authority grant.

Master gate: exact candidate CI, complete ledger and evidence, dormant defaults,
explicit human approval for PR #39. Release gate: separate approval, fresh scoped
backup, verified actual owner/launcher and immutable staged candidate, no pending
native contract for a capability proposed active. Hardware gate: independent
firmware readback/rollback and supervised qualification, plus explicit physical
authorization. Enablement gate: one ability, exact runtime/boot/zone/evidence,
independent signed review and measured admission. No blanket enablement.

The approved runtime d3dca905 and f3304c5 rollback remain unchanged throughout.
A master merge does not install, restart, flash or enable anything. A release
pointer switch does not establish an operating service or physical readiness.

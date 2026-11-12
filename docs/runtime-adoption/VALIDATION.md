# v2 source validation ledger

Baseline: actual local approved d3dca9059233b5f054c4f6f9979085b1422f9674,
clean; previous f3304c588a893a953e34e5c4d00bd5f9bfb18f19 remains rollback.
November10 QUALIFICATION entry supersedes only the approved revision and manual
LLM scope. Existing stationary-only/no-motion/no-autonomous restrictions survive.
See evidence/approved-baseline.json and baseline-preservation-matrix.json.

Published master was independently refreshed to c53c7e6; it is not the installed
runtime. #38 exact source and current CI were inspected, not inferred from ancestry.
All 38 original PRs and preserved worktrees are recorded. Empty checks mean unknown,
not pass. Prior failed jobs and skipped tag/native stages remain in exact-head
metadata and original PR bodies; later green jobs do not erase earlier failures.
A matching tree is source identity only, never firmware or physical qualification.

Initial adoption tool tests: 34 passed (one test-authoring defect in the missing
firmware digest path produced TypeError rather than the intended refusal; fixed
with type-safe digest validation, original failure retained in session receipts).
Expanded core baseline selection and exact candidate full CI follow. No test is
removed, xfailed or timeout-relaxed. Restricted host real-loopback cases are
reported separately and execute on independent CI.

Host system/user unit inventories refuse bus access. TCP listing reports denied
netlink access; its empty namespace result cannot establish native idle. Device
readback, actual host-owner inventory and running operational identity remain
UNKNOWN. No sensor, transport, root scheduler or model was opened to fill the gap.

Preservation hashes are in evidence/local-inventory-start.json and the approved
baseline record. Final reports must recheck the same original files. Native
qualification never rewrites an old receipt's code/model/firmware binding.

Increment A host: 206 passed, 2 skipped, 2 real-loopback cases deferred to CI; 131 contracts passed. Raw core-focused XML/text and core-contracts text are retained under evidence/.

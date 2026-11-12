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

First independent core CI 43238637623 failed one guard-fingerprint comparison
(208 passed / one skipped). The three guarded file hashes matched; only Python
3.12 vs 3.13 ast.dump formatting differed. Corrected by hashing exact function
source bytes, rather than interpreter-specific AST dumps. No protected source or
acceptance condition changed. Raw first failure is retained in evidence/ and
artifact [13952683417](https://github.com/mrgarmise/charlie/actions/runs/43238637623/artifacts/13952683417), ZIP SHA256 `696d975bf1313e434f83b98efed1c0e84960b71be659c99d530f1d34d1ba5081`, remains on the failed workflow.

Core correction independently passed exact-head source CI: run 43239537206
software reported 210 focused / one optional-source skip, 131 contracts and
2060 full / 28 skips. Its separate browser first attempt had one existing
viewport input timing failure (35 passed); push run 43239526388 browser passed.
The failed job/artifact 13954441203 is retained (ZIP SHA256
7c0b80f11fe976db6b635b009b3bcf8cff9cac45a0e0012ea16ebd4cdb51d60c),
and only that failed job was retried. Software artifact 13955140342 SHA256
919ec928a028514088db6a7739a53ab5515bb0974b634a091a6d40a22edd8e80.

Firmware/network before-transfer host check: eight UBSan C++ suites passed,
real TCP bridge deferred to independent CI. After transfer: 267 Python checks
passed / six optional-dependency or sandbox-loopback skips / two baseline
loopback cases deferred to CI. No source test failure was suppressed.
Historical stock STOP remains HANDLED—DONE/OK per latest #31; older #32 reports
are preserved as historical, not reopened acceptance. New candidate firmware
and transport timing remain a separate artifact-specific physical gate.

Increment B canonical contracts: 134 passed (new owner-UNO parameter cases extend the earlier 131 selection). Current build/TLS/browser and full CI remain mandatory.

Increment B first clean-checkout CI exposed omitted staging of five networking
modules: they existed locally but were absent from the committed tree. This was
a publication error, not missing hardware. The original runs and collection
errors remain on 43242132654 / 43242132434; the new tracked-source manifest
regression fails before staging and passes after it. No test was skipped to
repair the problem. S3 native-build job in run 43242132279 passed both OPI/QSPI
compile and image/partition checks; host failed only because the omitted peer
package could not import. Browser timing failure on the unchanged existing
viewport test remains separately recorded.

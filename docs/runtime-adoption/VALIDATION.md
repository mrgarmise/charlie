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

The tracked-file regression was strengthened again after finding the reviewed
dashboard hook was still unstaged: it now checks actual index blob bytes, not
merely file presence or working-tree bytes, including UI/tests/tools. The exact
reviewed dashboard source is included in the correction. This prevents local
uncommitted behavior from being counted as published integration.
Approval records now bind the complete manifest digest, and that manifest binds
the canonical CI bundle digest; changed evidence cannot reuse a signed review.
All review tools remain read-only, with Git hooks/fsmonitor disabled for inventory.

## Candidate proposal and interruption validation

Added a versioned candidate-manifest assembly command, with all abilities forced
disabled and native gate receipts empty. Input ledger acceptance cannot become
active authority. Review validation still requires exact independent CI and a
separate evidence-bound signature for master/release/enablement.
A fixture-only inventory process was killed at a protected read and restarted;
source, Git metadata, original state, approval and backup bytes remained intact.
Isolated restore matched the original state hash. See promotion-interruption.xml
and promotion-proposal.xml. Real runtime/state/firmware rollback remains an
operator qualification, not inferred from these software tests.

## Combined independent acceptance and final promotion hardening

Exact head b0733e15d466214e8fdbbce3e7f4aee1089048ad, tree
7a53b18c5c7dcda0a6866306fefe1b01df4ab667:
[adoption run43325659748](https://github.com/mrgarmise/charlie/actions/runs/43325659748)
passed2521 full/30skips,214focused/1skip,134contracts,36browser,84CPU engineering.
[S3 run43325670140](https://github.com/mrgarmise/charlie/actions/runs/43325670140)
passed183 Python host checks, nine C++ ASan/UBSan suites and prior firmware core,
and build-only OPI/QSPI. Artifact IDs and SHA256 digests are recorded verbatim in
combined-artifacts.json; semantic receipts bind the exact candidate/tree.
Source-review-b073.json is a positive dry-run SOURCE review only. The reference
candidate and release BOM retain disabled flags, unknown installed identities,
empty native receipts and pending fresh-backup qualification. Neither is installed
or release-approved. Local restricted socket failures remain preserved; these
exact-head unrestricted jobs execute the full suite successfully.

Final promotion changes add Robotron index/worktree source-manifest verification,
BOM per-ability source/firmware/model provenance and manual-LLM/protected hashes,
and a release-stage refusal for missing/stale/incomplete backup scope, incompatible
state or unverified isolated restore. A signed review must bind this entire
record and its evidence. Historical backup presence alone cannot pass release.
41 fixture-only promotion tests pass, including kill/restart, isolated restore,
missing/native/firmware/STOP/ACK/question/approval failures and positive dry review.
The final PR-head rerun, artifact hashes and counts are in PR39; no earlier head
is relabeled. SHA256SUMS covers the versioned evidence files verbatim.

The preserved approved runtime remains clean at d3dca905; original journals,
QUALIFICATION.md, approved.sha and both launchers match their starting hashes
(see preservation-after-combined.json). No native service ownership, firmware
installation, physical STOP, autonomous operation or gameplay/model benefit is
inferred from these software receipts. Historical stock STOP remains accepted.

# Batch A evidence for independent review

These files supply CI inputs for the existing unsigned Batch A packet on Charlie. The separate evidence branch leaves PR #44's measured controller at `5732d34f49db9b08ff8bb2f90c7eab10cfc0ae76`. The application remains `d7cabfc65b6c25d5d71af7ce5141ab5de828ba4f`. The original approved fallback is `d3dca9059233b5f054c4f6f9979085b1422f9674`. Each CI receipt expires seven days after its own completion time.

## What was checked

The reviewer can reproduce the software checks by opening the job and artifact links in the two JSON files. Candidate jobs were rerun on the original application commit. Each referenced ZIP was downloaded and its bytes checked against GitHub's SHA-256. Counts come from the enclosed JUnit XML, the contract job step, or the two compile-only reports. The firmware job compiled OPI and QSPI variants. Neither image was installed. The controller receipt independently identifies its own Git tree, workflow and artifacts. Keep these files in review staging until the eligible reviewer accepts them.

## Native review

The operator already prepared `~/charlie-ops/stationary-review/drafts/unsigned-ctecf6le` on the Pi. Reuse it. Operator-reported evidence includes the 229- and 354-observation sessions, a later 349-observation session, STOP/display-clear observations and a restore rehearsal. The preparation output reported three validated native session logs. A log with forced logger cleanup must retain its actual cleanup outcome. Source inspection of the current validator confirms it requires a complete validated log for acceptance of that case. No additional camera trial was used to prepare these CI receipts.

| Decision | Available evidence | Remaining review |
|---|---|---|
| N0, source and owners | Controller and application identities and external CI verified. The controller restricts its own process and worker transports. | Inspect installed firmware identity, device owners and alternate hardware privileges recorded on Charlie. An idle device check alone does not establish exclusive authority. |
| N1, stationary recognition | Operator-reported ELEGOO/Hailo/Pico observations and STOP/display clear. Software checks exercise the transport restriction and interrupted logger. | Compare the private measurement files and hashes with the signed scope, including owner release, thermal observations and any supported Pico ACK. Preserve uncertainty where an ACK was not recorded. |
| N2, compatibility | Consultation, resource and historical-question source hashes plus private-read and approval-check function hashes match the repository's original approved baseline record. The historic consultation launcher stays tied to the original checkout. | Inspect the host launcher binding, native consultation evidence, complete restore scope and notebook lineage. CI establishes software compatibility only. |
| N5, release decision | Existing unsigned gate templates, exact software receipts and tested independent rollback. | Eligible independent reviewer assesses the private evidence and signs the release and individual Batch A decision after accepting scope. |
| Normal operation | Last operator report preserved the original launcher. | After separate cutover authorization, use the documented normal launcher once under supervision and verify the resulting source, shutdown and resource release. |

No signed approvals or native pass receipts are included. The source PR contains the canonical switch and rollback commands. This evidence branch does not enable a capability, change a launcher, edit a notebook or grant motion, firmware or autonomous consultation authority.

[Controller runbook at the measured revision](https://github.com/mrgarmise/charlie/blob/5732d34f49db9b08ff8bb2f90c7eab10cfc0ae76/docs/runtime-adoption/STATIONARY_CUTOVER.md)

# Operator-controlled adoption runbook

This document is a future procedure, not authorization. This mission executes
source-only work. Do not run deploy, flash, restart, motion, model or scheduler
commands from it without the separate applicable operator approval.

Start in the final exact candidate checkout. Inspect the final PR #39 head/tree,
CI/artifacts and ledger, then compare against the actual approved runtime:

```sh
GIT_OPTIONAL_LOCKS=0 git -C /home/five/charlie-runtime status --short
GIT_OPTIONAL_LOCKS=0 git -C /home/five/charlie-runtime rev-parse HEAD HEAD^{tree}
cat /home/five/charlie-ops/approved.sha
sha256sum /home/five/charlie-ops/start-stationary.sh /home/five/charlie-ops/run-historical-consultation.py
python -m tools.runtime_adoption inventory --baseline /home/five/charlie-runtime --candidate "$PWD" --ops /home/five/charlie-ops --protected /home/five/charlie-ops/approved.sha
python -m tools.runtime_adoption plan --manifest docs/runtime-adoption/abilities.json
```

Inventory writes only stdout. Capture reports into a new review/evidence directory,
never into protected journals. Missing ownership or baseline binding is a refusal.
The known approved pin is d3dca9059233b5f054c4f6f9979085b1422f9674; a newer
verified local approval supersedes this record. Existing accepted stationary and
manual consultation evidence stays accepted within its original scope.

For a complete candidate manifest and exact-head CI receipt bundle, use:

```sh
python -m tools.runtime_adoption validate --stage source --source-root "$PWD" --manifest "$MANIFEST" --inventory "$INVENTORY" --receipts "$RECEIPTS"
python -m tools.runtime_adoption release-manifest --manifest "$MANIFEST"
```

The result is eligibility for review, never installation. For master/release/
enablement validation additionally supply a separately signed approval, pinned
trust-key file and its independently verified SHA256, and exact selected ability.
Do not use test fixture keys or generated self-approval. Review binds manifest,
CI bundle, candidate, stage, abilities, reviewer and expiry. An unapproved BOM is
not an approved runtime. There is no apply/enable command in these tools.

Actual operations currently use a Git worktree, approved.sha, existing runtime
lock and bounded foreground launchers. They do not establish an installed release
symlink or an active systemd service. Preserve this approval hierarchy. Discover
owners before choosing any maintenance command. Existing charlie_ops may support
future immutable staging: global --state and --release-root precede backup,
verify-backup, stage, deploy or rollback. Its --approved flag alone is not an
independent approval or native gate. Do not substitute it for charlie-ops records.

Before separately approved staging: take a fresh complete state backup, verify
hashes/permissions and isolated restore; preserve current approval, launchers,
model/calibration/firmware identities and failed receipts. Stage into a NEW
versioned path only. Run N0–N2, then applicable N3–N4 from NATIVE_HANDOFF.
Separately authorize source merge, release cutover and each capability. Confirm
exact post-cutover source/boot/owners, disabled authority and manual LLM guards.
No automatic restart follows a pointer switch. Observe N5 and retain benefit data.

On uncertainty: deny new capability admission, use the independently established
physical cutoff if physical authority exists, and perform bounded owner cleanup.
Do not clear durable faults or rewrite journals to recover. Operator rollback
uses the preserved current d3 approval/launcher and f330 historical fallback only
under its actual qualification. Restore compatible state only after isolated
verification; source rollback alone does not roll back firmware or journals.

A worked immutable source-only example is evidence/reference-candidate-b073.json,
with inventory, exact CI receipts, BOM and successful dry SOURCE review beside it.
It is not a release approval. Recreate the final-head proposal from a fresh
read-only inventory and its exact receipts with `candidate-manifest`; preserve
the reference files. Release validation additionally requires a signed
backup_qualification record binding complete scope, compatible state, isolated
restore, independent review, exact manifests/candidate and a fresh completion
time (<=7 days). Historical backup manifests alone are refused.

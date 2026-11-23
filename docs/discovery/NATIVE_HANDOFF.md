# Discovery Engine development handoff

Use the release packet's `RELEASE.json` for the exact candidate commit, tree, archive digest, reader versions and test receipts. Compare the packet's external SHA-256 with the delivery message before extracting into a new directory. The private seed belongs with the release packet. Git contains implementation, tests and the separately licensed reference tables.

## Candidate ancestry and runtime identity

The base of this draft is the stationary review controller at `5732d34f49db9b08ff8bb2f90c7eab10cfc0ae76` (tree `f58c8fc400ee3d78aff3178d264077b144ee8a29`). It contains the question-selection head `0567147d9bdf87b74aac143124fb60c9b4c39322`, native scheduler head `e83b7d469e403559c68025b92120da27dc342dc9`, and source integration `57e07eb850b139eda6a5f1a930cc0ef7b5bf5f18`. The draft adds no commits from the separate UEL, agent factory or robot-body branches. The local inventory covered the available worktrees, refs and reflogs, the published heads and relevant draft PRs. Unmounted workspaces on other machines were outside this inventory.

The stationary review records identify the historical approved commit as `d3dca9059233b5f054c4f6f9979085b1422f9674` and its tree as `72cd9e4eba5939c181ae88d6ed03d5bbc50527c4`. PR #44 records a separate runtime candidate. The release machine had no mounted Pi ops directory. Compare fresh on-Pi evidence before treating either historical record as current.

## Read-only G0 procedure

1. Verify the external packet digest and run `sha256sum -c SHA256SUMS` from the unpacked packet. Retain the original packet. Inspect `RELEASE.json`, the archive manifest and the JUnit/CI receipts. Cross-check the GitHub draft head against the release commit and tree.
2. In a separate directory use `git clone candidate.bundle candidate`. The bundle is self-contained. Run `git -C candidate rev-parse HEAD HEAD^{tree}`. Confirm both identities before using candidate code. Run commands with `PYTHONDONTWRITEBYTECODE=1` to avoid writing caches.
3. On the Pi, run the following command from the **candidate** directory. Use the actual SSD mount and released identifiers. Compare its control digests against an independent pre-existing Pi snapshot, the approved worktree revision and tree, and the launcher actually selected. Record any drift. A return code of zero covers only the listed comparisons.

```sh
python3 -B tools/discovery_release/preflight.py --repo . --ops "$HOME/charlie-ops" \
  --disk "$SSD_MOUNT" --expected-commit "$RELEASE_COMMIT" --expected-tree "$RELEASE_TREE"
```

4. Run the packet's offline audit on the isolated SSD copy. Confirm FTS5, source IDs and hashes, version-specific rows, footprint and sources with missing redistribution rights. Confirm sufficient headroom for two archive copies, journal quota, temporary build space and rollback. The unpacked release and the interpreter's native libraries contribute to the SSD budget if installed there. Stay below 8 GiB across the entire operational allocation.
5. Independently inspect current boot ID, kernel isolation and cgroup limits, active services, protection/ownership of the scheduler policy/socket, model identity/residency, device/lease inventory, available memory, thermals and recent cooldown/daily usage. The expected model blob digest is `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`. Neither a string match nor a desktop test qualifies a native slot.

## Later reversible native qualification

A later operator may stage a verified copy in a fresh versioned, operator-owned directory on the SSD and place the journal in its own data directory. Record paths and SHA-256 inventory, free space, control hashes, boot ID, policy version and service states before the session. Capture stdout and stderr outside the candidate checkout. Start with the offline reader and an empty journal. The normal launcher and policy remain owned by the existing runtime. Review `docs/consultation/MEDITATION_NATIVE_NOTICE_HANDOFF.md` for independent grant, visible notice, STOP, teardown and uncertain-completion requirements.

A live trial needs the existing independent supervisor to grant a safe slot, an authenticated owner, the exact reviewed configuration, and a person monitoring the foreground session. Compare model-off and admitted model-on runs using the same archive and question. Record the commission, budget, peak RSS, thermal state, token counts when available, citations, uncertainty, durable journal ID, cancellation behavior and evidence of provider cleanup. Slots are at most 90 seconds. Keep actual service state, resources, controller pin and qualification evidence in the native receipt. A failed precondition leaves the trial pending.

Rollback for the isolated manual trial is to end the candidate process through its existing cancellation path, verify cleanup and lease release with the independent supervisor, and close the candidate store. Preserve the entire trial directory, journal and evidence. With the process stopped, quarantine the versioned trial directory by renaming it on the same filesystem. Recompute the original operational control hashes and compare service state and approved worktree identity with the before snapshot. If a control or service changed, stop and reconcile against the operator's prior backup. Preserve both journals and do not overwrite the operational database. No native install, rollback or service transition was performed by the parent mission.

For a WAL-consistent notebook copy, use `python3 -B -m tools.discovery_release.notebook_copy SOURCE NEW_FILE`. The same operation restores into a fresh private destination. It validates foreign keys, SQLite integrity and the research schema and refuses an existing destination. Preserve its SHA-256 receipt alongside the original evidence. The release's clean-run test exercises a live writer, backup, later writes and restore into a distinct file.

## Text and archive commands

From a clean candidate checkout, with `PACKET` pointing at the extracted release and `PRIVATE` at a new owner-only directory outside the archive:

```sh
python3 -B -m learning.discovery.archive audit "$PACKET/archive" --expected-manifest-sha256 "$ARCHIVE_MANIFEST_SHA256"
python3 -B -m tools.discovery --journal "$PRIVATE/journal.sqlite" init --archive "$PACKET/archive"
python3 -B -m tools.discovery --journal "$PRIVATE/journal.sqlite" ask 'What have you been thinking about lately?'
python3 -B -m tools.discovery --journal "$PRIVATE/journal.sqlite" queue 'How do seeds store energy?'
```

Queueing records an owner preference. The existing scheduler grants any later live execution. The read-only text adapter can return the complete structured digest with `--json` before `ask`. Detailed evidence from any recorded session is available with `ask 'Show me the evidence for that conclusion' --session-id ID`. The packaged sample reports are desktop development demonstrations, separate from Charlie's operational notebook.

Discovery is off unless the existing protected broker policy supplies a `discovery` object with `enabled` set to true, an absolute `archive_dir` and separate absolute `journal_path`, and the release's `archive_version` and `archive_manifest_sha256`. A source-only review uses `model_enabled: false`. Optional model review additionally binds a root-owned `prompt_catalog` file and its `prompt_catalog_sha256`. The candidate exposes `learning.discovery.inquiry.prompt_catalog(archive)` to generate the review input from the verified archive. Review individual prompt contents before pinning them. The protected cooldown, per-day and per-slot limits also apply in source-only mode.

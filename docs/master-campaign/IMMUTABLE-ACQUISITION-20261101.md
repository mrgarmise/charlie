# Scoped PR 7 acquisition recovery

Source: PR #7 at `83112b4b9d20f97178a6494f09f48713d4210344`.
This stage transfers only the compound kind/category index, hash-bound session
import receipt reuse, SQLite-sidecar rejection and their four regression tests.
The existing normal Executive calls import_queue during acquisition; no new
writer, scheduler, capture owner, gameplay path or policy is introduced.

Writable copied notebooks gain the category index. Read-only legacy journals
are never migrated. An unchanged source receipt is reused only when its exact
hash matches and all delivered record IDs still exist. Changed sources take
the original verification path. WAL/SHM/journal sidecars require a quiesced
snapshot; they are preserved and recorded as an acquisition deficiency.

23 focused tests passed, including normal acquisition, immutable-source retry,
changed-source reimport, missing-delivery denial, sidecar preservation, query
plan selection, read-only byte preservation and question/restart compatibility.
The focused run uses its own temporary test directory to prevent concurrent
synthetic suites from sharing the gameplay resource lock. Earlier mixed-run
resource refusals and the mistyped test-path receipt are retained locally.
No production resource/ownership gate or timeout changes.

This is a selective source transfer, not inclusion of all #7 changes. Original
scoped E1 recurrence and retrospective P1 receipts remain historical evidence;
I1 and complete-game improvement remain unestablished. ALA charter/acceptance,
original notebook, source journals and review photographs remain authoritative.
No operational notebook was opened for writing, no hardware/firmware/service
was operated, and no learned or model pointer was activated. Keep draft with
all inherited campaign/source holds. Independent full regression remains required.

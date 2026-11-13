# Robotron source reconciliation

Donor: PR #9 at 9ba60e2e9c645c43f71072de413118dd5373e8c6,
including the inherited #5/#6/#7/#8 changes relative to common ancestor
bcf8082f6319c63c4bd6bcceeab5faea37241654. Existing score feedback from #3
is retained through its newer reconciled implementation. This is source-only
reconstruction in a disposable review checkout; original branches are preserved.

The candidate retains the existing physical camera publisher and HailoSession.
Robotron consumes subscriptions. Published request metadata retains original
source/frame/sequence/generation and authentic exposure timing; a bounded consumer
wait cannot cancel or flush the acquisition owner. A generation change or an
exposure gap inside a causal window refuses the window. Outside such windows,
missing exposures are counted rather than represented as complete acquisition.

The detector_bridge conflict was resolved by retaining the incumbent persistent
HailoSession API and adding donor admission. Nonpersistent detector and optional
neural score inference share the existing cross-process accelerator_lease.
Admission contention never becomes a CPU fallback. No second Hailo scheduler,
physical camera reader, controller owner or Learning Executive is started.

Fixed score recognition remains the default. Neural CPU training/export uses
synthetic test data in a separate engineering CI job. It is not a qualified
model, held-out evaluation, Hailo HEF, score-reader replacement or gameplay benefit.
The sealed final-test partition and authentic journals remain untouched.
The original October 17 failed archive and report are byte-preserved; their
failure remains a failure. E1/P1 diagnostics do not establish I1 or game benefit.

First focused run: 20 failed / 139 passed / 1 skipped due to omitted inherited
AgencyTracker dependencies and a required historical receipt. Dependencies were
restored from the same exact donor, not mocked or weakened. Repaired focused run:
159 passed / 1 skipped. Ownership regression run: 87 passed. Expanded run:
367 passed / 2 skipped / 1 failed because the original public failure archive was
absent. Its exact original bytes were restored and its integrity test then passed.
Full-suite and independent CI results must be read at the final exact published
head; local restricted TCP tests cannot qualify native operation.

Local full run: 2,372 passed / 43 skipped / 37 failed / 11 errors. Every
failure/error contains PermissionError for restricted loopback socket creation;
none has another cause (verified by parsing every JUnit failure/error). This is
not a green full result. Independent CI must execute these nodes unrestricted.
Final camera/Hailo/neural focus: 141 passed / 1 optional dependency skipped.
The first final-focus command referenced nonexistent test_camera_broker.py and
ran no tests; its diagnostic is retained and the corrected selection passed.

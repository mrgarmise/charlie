# Selective demonstration retention

The operator's [October 31 checkpoint](https://github.com/mrgarmise/charlie/pull/13#issuecomment-6546621388)
preserves a successful scoped Pi/Hailo/physical-label milestone and the failed
6.408-second dashboard run. The cumulative 64 MiB PNG cap was reached while
saving every incoming full-resolution frame, including cadence-skipped frames.

Demonstrations now select exact pixels after successful perception: the first
decision, changed class sets, and five-second context, with at most four saved
samples per session. The original cumulative byte bound remains 64 MiB. Existing
PNGs are never evicted or overwritten. Each observation journals its source,
generation, frame ID, original pixel hash and explicit retention outcome. A full
budget records `cumulative_pixel_budget_exhausted` and continues observations;
it never claims those missing pixels were saved. Other I/O/encoding failures
continue through the existing failure path. Display, deadlines, cancellation,
source ownership and hardware admission are unchanged.

Validation: 61 focused tests passed with permitted loopback, including real
attention/perception/serializer integration, full-store continuation, exact
frame receipts, bounded encoding and storage-error propagation. Canonical
contracts: 129 passed. Restricted first run: 57 passed, one HTTP socket denial;
the original receipt is retained separately. Full regression/independent CI
must be recorded before promotion. No native demonstration or hardware operation
was run by this change; full 15-second/two-session and USB recovery acceptance
remain pending, without reopening the accepted scoped label milestone.

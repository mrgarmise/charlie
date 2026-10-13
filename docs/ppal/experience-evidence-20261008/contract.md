# Experience witnesses and qualification contract

Scope: the identical 17,271-byte Library work instructions named Charlie_ALA2_Experience_Evidence_and_Score_Qualification_Work.md, read in full on October 8, 2026. Verified remote parent 751c05e35fda056439d12c009a2e16abb232c302; no newer published revision. Surviving dirty worktrees are preserved in place. New isolated feature/experience-evidence checkout.

## Current path and limitations

ObservedCamera owns no camera: it delegates to the existing camera lease/source, snapshots exposure metadata, and attaches CaptureEvidence. Currently every source read copies a full image into one bounded FIFO writer. The writer encodes lossless PNG, commits descriptors, predictions and outcomes, and fsyncs logs. PPAL perception/agency supplies provisional track/SELF estimates; Forebrain and Hindbrain alone choose actions. ScoreObserver is a separate best-effort instrument using the same original frames, with a queue of two, first/change/final retention and disclosed dropped samples. It does not independently qualify scores. Main application's Learning Executive and meditation operate separately from time-critical decisions. Episode acquisition preserves live journal IDs. Exact writer receipt currently requires every camera descriptor to bind an original PNG; changing that rule globally would corrupt the strict evidence contract. Marathon safe_to_restart currently checks terminal evidence but does not itself require a verified writer receipt.

Published host baseline: 670 passed / 20 skipped; foreground median 84.329 ms frozen synchronous recorder vs 1.361 ms buffered recorder at nominal 10 Hz, 20 replay frames. Typical source fixture is 1280x720 RGB (2,764,800 raw bytes). PNG sizes depend on source entropy. Neither measured throughput nor 20-frame latency establishes Pi performance. Existing control pulses 30..200 ms and extra response-window reads mean actual cadence is variable; this mission will record actual timestamps rather than assert 20–30 Hz gameplay. Full perception/transport cost remains independently measured work.

## Witness contract

Charlie authors internal detections, estimates, prospective choices and updates. Recorder authors only original retained pixels. Evaluator authors independent reconciliation. No witness can rewrite another. Missing image means not independently inspectable, never proof of no observation. Prediction enqueue acknowledgement is RAM, not pre-action durable commitment. All records keep actual monotonic/exposure timestamps and source identity. Interpolation is an estimate, never substituted causal evidence.

Strict mode remains default and unchanged. Opt-in sampled-visual-v1 records every camera descriptor and trace, and explicitly classifies every source's retention. Predictable time-based sampling is independent of beliefs. Missing optional payloads are disclosed, while critical trace failure uses the existing stop/yield boundary. Completing this writer does not imply a complete game or qualified score. Experiments requiring all pixels reject sampled contracts unless explicitly designed for them. Historical packages are never rewritten.

## Incremental acceptance matrix

| Milestone | Existing owners extended | Required independent checks |
|---|---|---|
| Full-rate trace / sampled originals | ObservedCamera, CaptureEvidence, PPAL, episode identity | 30 Hz source / 5–10 Hz retained fixtures, exact clocks/IDs, multi-frame sources, strict compatibility, optional pressure vs critical failure, failed writer/restart receipt |
| Incident recall | CaptureEvidence and PPAL feedback | duration/count/byte eviction, past/future interval, overlap dedup, admission/shortfall, baseline reserve, no encoding in controls |
| Reconciliation | Evaluator, episode acquisition, Reflection | exact source matching, plausible/unobserved/disputed/unresolved, uncertainty/occlusion, durable discrepancy handoff, original immutability |
| Score review / qualification | ScoreObserver, score tools, independent evaluation | confirm/correct/unreadable, immutable proposal, reviewer/source provenance, episode partitions, uncertainty/abstention, missing final/boundary pixels rejection |
| Handoff / performance | Marathon, existing native benchmark | terminated writer and verified receipt, consecutive runs, timeout/process death, sustained throughput/queue/rolling RSS, guarded Pi-only procedure |

Only host software fixtures and original-pixel replay are authorized here. Native camera measurements require reachable Pi and existing ownership; native performance pending if unavailable. No controller arming, physical gameplay, motion, firmware or physical policy activation. ALA-2 closure requires statistically supported mean complete-game SCORE improvement on separate independently qualified games with frozen baseline and rollback.

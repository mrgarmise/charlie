# Physical developmental learning audit — 2026-10-02

Charlie demonstrates a narrow diagnostic learning return path, not established strategic learning or improved Robotron performance. Three live prospective actuator experiments were supported. Thousands of replay-derived records came from those same episodes and are not independent physical experiments.

This audit compares b9624ce with the repair. The companion JSON contains archive/report hashes, exact recorded startup times, plans/resolutions, commitment timelines, classifications and measurements. Original archives remain unchanged. The first unpublished working copy was lost when the workspace reverted; repairs were recovered in a separate checkout, retested, and the processing fix published independently as 05ec6ab. All reported physical evidence was subsequently recovered from the supplied archives.

## Session reconstruction

| Session | Revision | Agency samples | Tracker score | Stop / final physical display |
|---|---|---:|---:|---|
| development-20261002-003511 | 0bd08c1 | 81 | 1000 | Diagnostic TIME LIMIT, 20 seconds; still gameplay |
| development-20261002-005944 | 0bd08c1 | 380 | 1200 | Diagnostic TIME LIMIT, 120 seconds; rankings then instruction display |
| development-20261002-012801 | 49632c4 | 347 | 3500 | Diagnostic TIME LIMIT, 120 seconds; rankings then instruction display |
| development-20261002-015817 | b9624ce | 365 | 3300 | OBSERVATION UNCERTAIN; productive offline derivation then interrupted |

Each invocation supplied one physical game, not three games. Agency samples include probes, response endpoints, FIRE exploration and neutral recovery; ordinary-action rows are a different population. Provisional SELF remains a hypothesis. Confirmed is AgencyTracker's reported belief status, not external certification. SELF loss does not prove death or respawn.

START-to-first-ordinary-controller-action delays were 6.408, 6.585, 6.372 and 6.691 seconds. These use local controller transport timestamps, not measured TV execution latency. In 015817 exposure took 9.924 seconds and calibration 24.044 seconds **before START**. First classified gameplay was at monotonic 6178.791022; confirmed gameplay 6180.037752; discovery began 6181.717432; first BODY probe 6182.700478; provisional observation 6184.021207; first ordinary action 6184.827953. The archives do not independently timestamp deaths. No additional sensor-timing repair was inferred from older missing timestamps.

003511 generated actuator-response hypotheses through existing Reflection. 005944 selected BODY E/FIRE NONE; 012801 E/N; 015817 E/NONE. Their archived alternatives and Evaluator priorities explain selection. No direction or expected result was manually assigned during this audit. Each selected prediction preceded its executed action and resolved against a later eligible same-ID response window. Support means agreement with the AgencyTracker response reason, not knowledge of FIRE causality, true identity, rescue semantics or score attribution.

Project d838af954e2e persisted across separate invocations. Its latest archived projection had two resolved episodes/two conditions plus an unresolved earlier 015607 attempt. That earlier attempt is distinct from 015817. The latest supported resolution and Evaluator feedback committed before replay interruption; its Executive handoff was scheduled after replay and was never reached. The repair moves that handoff immediately after resolution. Existing completion criteria measure diagnostic reproducibility, not high score.

## Processing interruption and repair

The latest supervisor recorded **processing_budget_exhausted after 300.213528 seconds**, then SIGINT. It recorded 290 coalesced progress updates; the final update was under a second before interruption. The traceback identifies where SIGINT arrived, not evidence that SQLite was hung.

The retained journal had 1 episode, 1,071 observations, 6,850 events, 7,569 resolution references and no derivation-complete marker. Its replay notebook had 318 observations, 7,618 predictions and 7,569 resolutions: 49 predictions were pending. Recovery on a copy retained all **15,491** existing canonical records unchanged, completed at **17,133**, and a second retry added nothing. Latest host recovery/verification: **3.04 seconds**. Originals were not modified.

New behavior:

- Atomic durable camera-observation units amortize fsync; SQLite durability settings and append-only triggers remain unchanged.
- Exact committed forecasts/resolutions are retrieved on recovery; no hindsight forecasts replace history. Conflicting reinterpretation requires a new version.
- Productive work cooperatively yields at verified/committed checkpoints (exit 75), then automatically resumes for at most three work chunks.
- The independent 60-second inactivity watchdog remains. Its hard work-budget limit includes ten seconds of cooperative-exit grace; genuinely stalled work is still interrupted/killed/reaped.
- Exhausted productive chunks record processing_deferred and retain evidence. No new START follows incomplete processing.
- Physical experiment results reach the Executive before optional diagnostic replay.
- Completed Meditation is reused only for matching input hash and reconstruction version.

Canonical and replay notebooks commit independently; retry repairs an interrupted reference handoff by stable content identity. A yield is not a prediction verdict or completed derivation. Offline --resume never opens the camera or sends START.

## Stage audit and resource costs

| Existing stage | Actual function | Complexity / useful distinction |
|---|---|---|
| Import | Hashes preserved artifacts and indexes immutable locations | O(bytes + records); no camera/tracker rerun |
| Live resolution | Compares committed prediction to eligible later response window; updates existing Evaluator | O(agency rows), verified phase-local artifact cache; retry idempotent |
| Executive result | Records cumulative physical experiment outcome | Now independent of successful diagnostic replay |
| Derive | Tracker allocation/SELF belief events, chronological constant-velocity predictions/resolutions | O(points plus bounded per-track windows); old per-record durable writes expensive |
| Reflection | Replay summary, actuator-response hypotheses, existing project proposals | 36/81/81 proposals in completed runs; overlapping windows are not independent discoveries |
| Meditation | Conservative mutual-best fragment links with temporal-onset indexing | Bounded six iterations or no new links; dense eligible windows still costly |
| Context Reflection | Objective/prediction/resolution, separate observations, uncertainties and questions | Existing Experience/Gateway/Evaluator/question queue; no executable tactics or new selector |

Old Pi first-to-last journal commitment spans were **65.07 seconds, 991.88 seconds, 992.50 seconds**. These are recorded spans, not exact CPU or full processing wall time. In 005944, tracker events began around 00:03:18, resolution references around 00:09:13, derivation completed 00:16:56, final Reflection/project commitments around 00:19:31. Substantial cost was in derivation and memory/project work. The archives do not justify blaming the entire delay on Meditation, and lack per-stage Pi CPU/RSS measurements.

Fresh isolated host measurements on 005944:

| Metric | Baseline | Repair |
|---|---:|---:|
| Full path wall seconds | 11.82 | 9.47 |
| CPU seconds | 11.81 | 9.53 |
| Peak RSS KiB | 333,652 | 334,096 |
| SQLite bytes across isolated stores | 45,506,560 | 45,535,232 |
| Replay resolution references | 10,812 | 10,812 |

A cached retry completed in **3.94 seconds** with unchanged record counts/database size. Fresh repaired journals passed SQLite integrity and evidence-reference verification. One earlier host benchmark using a reused workspace path produced a malformed scratch database after the workspace recovery; that measurement was rejected, retained separately and excluded. No original physical archive was affected. The fresh unique-directory validation succeeded.

Measurements include import, derivation, existing memory/Executive proposals, Meditation and new context Reflection; isolated host stores did not contain the original live-plan memory state. Live resolution/retry is tested separately and evidenced by the physical commitments. These are **not Pi speedup claims**. New workers persist per-stage wall/CPU snapshots, peak RSS and database sizes, retained per supervised chunk. Large notebooks and verified caches still use roughly 326 MiB peak; reducing record count or RAM further remains a limitation. Chunk reports must be combined for total work cost.

The existing classifier now checks ordinary observations as well as recovery, so a lingering false SELF hypothesis cannot hide a terminal display. Additional template matching costs and actual Pi perception/action cadence remain to be measured. E/E and learning remain offline. Score stays a bounded passive worker consuming the existing raw frame; no camera ownership, policy or termination dependency was added.

## Meditation, useful learning and diminishing returns

Meditation hypothesized **61, 372 and 414** fragment links. New links rapidly declined; 012801 produced 258,107,37,11,1,0. It already stops at no new links or its iteration bound. Mean moving-trajectory error did not consistently improve: approximately 1.257→1.267 in 005944 and 1.439→1.458 in 012801, with changed evaluation populations. Link count is not identity accuracy, causal understanding or score improvement.

Useful learning demonstrated: an evidence-derived actuator-response expectation was supported across distinct physical episodes/conditions, stored/evaluated and used to choose a subsequent explicit experiment. Unproductive inflation: thousands of correlated replay results and many variants from overlapping response windows can look like more knowledge than they are. Previously Meditation's file did not inform episode Reflection. It now contributes an explicitly unresolved identity-verification question with input/version provenance; its interpreted IDs never become canonical physical identity.

The new learning-report.md records objective, attempted experiment, expected response, resolution, supporting canonical/resolution IDs, Evaluator change, reported identity states, separate score observations and open questions. Reflection conditionally forms questions from identity gaps, unverified boundaries, reconstructed links and conflicting observations through its existing queue and memory path. These questions do not preselect a tactic or assign an Executive goal. The tactical chooser remains unchanged.

## Episode boundary diagnosis

Every appearance challenge after sustained SELF loss in the three longer sessions had zero eligible attempts. That cannot count as rejection. The original observer required eight positive non-gameplay observations **and** an actual rejected controllability challenge; it could not produce that corroboration without an eligible candidate. Generic discovery returning no SELF was correctly insufficient.

Saved rankings pages narrowly missed the old dual-heading threshold: heroes .7733/.7628/.7715 versus .78, corresponding all-time headings .7972/.7890/.8202. Session 005944 now extends the existing recorded-label bank without lowering thresholds. Held-out 012801 and 015817 rankings become terminal; the held-out 015817 final instruction page becomes startable. Blank/ungrounded striped pages and obscured transitions remain UNKNOWN. Healthy gameplay frames with temporary SELF absence remain gameplay.

An alternate conservative boundary rule requires prior positive gameplay, three fresh terminal rankings observations, then at least three fresh instruction/attract observations inside an eight-observation positive non-gameplay streak. Stale exposures do not count. UNKNOWN breaks current corroboration and never permits START; gameplay clears terminal context. Capture timestamps and phase history are retained. The existing causal-challenge rule remains compatible. The marathon still requires normal child exit, completed processing and explicit confirmed GAME OVER before a second START.

Saved review frames are sparse: they prove recognition of these pages, not all consecutive live captures required by the new rule. No historical stop reason was rewritten to GAME OVER. Player death versus respawn remains UNKNOWN unless separately observed; it is not inferred from disappearing SELF. A genuine unattended three-game physical marathon remains unproven.

## Score audit

Preserve both observations: 012801 tracker **3500**, physical screen report **2400**; 015817 tracker **3300**, physical screen report **1300**. External observations have unknown timestamps and no special authority. The earlier 012801 false-jump capture itself reads 1500; its later final screen reads 2400. These are not simultaneous readings.

The exact score-raw-0175.png for 1100→3300 visibly reads 1300. Single-threshold segmentation produced a false exact signature/confidence 1.0; nearby thresholds disagree or lose glyphs. The 3500 false-jump capture similarly gives 1500 nearby. Bright acceptance now requires two adjacent-threshold agreements, and both problematic frames abstain. Historical logs remain intact; no game-specific jump limit, negative reward or person-specific adjudication was added.

The original real-camera corpus was available with its own calibration: **4/14 pass on both baseline and repair**, ten remain unreadable. Unit tests do not establish reliable score perception. Digit 7 still has no real exemplar and remains inferred at reduced confidence. Hue is not an identity requirement; absent P2 remains None. Dim/blurred glyph recognition remains a real gap before score comparisons can support performance conclusions. Optional external-observations.json records explicit source/value/timestamp independently; later annotations do not alter captured-manifest or observation identities.

## Architecture and deferred work

Reused: one SpriteTracker, AgencyTracker/provisional embodiment, evidence and prediction lifecycle, Reflection, Experience/MemoryFormer, MemoryGateway/Evaluator/MARM outbox, existing chooser/Executive, supervisor, classifier, optics/calibration and passive ScoreTracker.

Extended: durable units and replay recovery, progress/work-budget separation, earlier Executive handoff, Meditation reuse/provenance, context/questions/learning summary, external observations, actual-page reference bank and visual transition corroboration.

Not built: another tracker, parallel memory/question/Executive system, manually assigned BODY/FIRE strategy, score-driven policy, semantic Robotron rules, privileged score overrides or speculative restarts.

The complete Pi Evaluator/outbox/project stores were not supplied, so their full cross-invocation contents cannot be reconstructed. Project generation remains actuator-response reproducibility; existing completion criteria assess diagnostic coverage/support, not ultimate score. Sticky portfolio selection and interruption/resumption have controlled tests but these sessions do not demonstrate autonomous perceptual-project interruption and resumption. Wider question-to-project/method synthesis, information-value/cost assessment and strategic learning remain gaps. No causal performance improvement is claimed.

## Offline Pi validation before another marathon

```bash
cd ~/Projects/charlie
source .venv/bin/activate
git pull --ff-only origin feature/agency-first-self
python -m pytest tests -q
PYTHONPATH="$PWD" python -m experiments.ppal.process_robotron_episode \
  robotron-runs/development-20261002-015817/game-01-evidence/processing-config.json --resume

tar -czf robotron-runs/development-20261002-015817-resumed.tar.gz \
  robotron-runs/development-20261002-015817
```

Return development-20261002-015817-resumed.tar.gz with chunk/resource reports, completed/retained journals, commitments, between-game.json, meditation.json, learning-report.md and original evidence. Keep the original archive. This command performs no capture or START. Preserve local run_camera.py work; never reset it.

After complete Pi measurements verify productive processing/resumption, the next physical validation should be the existing developmental marathon, learning projects, **three games**, progress supervision and no normal gameplay deadline. Required evidence: fresh positive boundaries, no uncertain START, bounded post-game processing, real project/experiment continuity and honest score uncertainty. That armed test is deferred until offline validation; no additional marathon is requested now.

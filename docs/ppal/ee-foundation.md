# E/E foundation: the evidence layer beneath existing memory

Governing milestone: Alex's `PPAL_EE_Foundation_Gap_First_Work_Spec.md`.
This implementation is offline. No E/E import, emission, persistence, model,
memory feedback or policy change was added to `play_robotron.py`.

## Reuse/gap audit

| Requirement | Existing implementation | Decision and reason |
|---|---|---|
| Selective durable memory | `memory/marm.py`, `store.py` | Reuse MARM client/outbox and store protocol. Dense evidence does not enter MARM automatically. |
| Producer boundary, recall | `memory/gateway.py` | Reuse `remember`, scoped recall, feedback, correction and decision assessment. |
| Experience and selection | `memory/former.py` | Reuse frozen Experience, tags, source, evidence, subject, confidence, significance. No new Experience type. |
| Evaluation and provisional candidates | `memory/evaluator.py` | Reuse candidate IDs, provisional/promoted/dormant states, explicit helpful/harmful feedback, comparison-based decision credit. These assess memory usefulness, not physical truth. |
| Contradiction/correction | Evaluator + Gateway | Reuse explicit feedback and supersession of selected claims. Do not apply memory usefulness scores to raw pixels or auto-credit score adjacency. |
| Reflection and questions | `reflect_robotron.py` | Extend with `reflect_evidence`; retain existing findings, recall and question queue. No duplicate question engine. |
| Meditation | `meditate_robotron.py` | Reuse iterative reconstruction/evaluation. It revises interpreted tracks, not canonical tracker observations. No second meditation cycle. |
| Trajectory predictions | `predict_robotron.py` | Reuse `predict_next` with past points only. Existing batch output includes actual outcomes and errors; it has no durable separate commitment/resolution. Add that missing lifecycle. |
| Live forecasts | `shadow_predictor.py`, live `steps[].shadow` | Preserve as **reported forecasts**. They are CV diagnostics, not action counterfactuals. The final report cannot prove a forecast was durably committed before an outcome. |
| Exact replay | `replay_tracking.py` | Retain exact inputs/settings/IDs and existing replay unchanged. E/E reads its telemetry; it never calls association. |
| Image replay/reconstruction | `replay_robotron.py`, `reconstruct_robotron_tracks.py` | Retain offline tools. Legacy image replay can infer different identities; those cannot replace live IDs/history. |
| PPAL dense transitions | `experiments/ppal/memory.py` | Existing before/action/after JSONL fits its producers; lacks common scoped IDs, artifact provenance and commitment lifecycle. Do not replace it. |
| Session boundary | `robotron_session.py`, live report | Reuse existing state/outcome/configuration artifacts; the new notebook is an index of a run, not a second session controller. Failed calibration and UNKNOWN SELF runs remain valid. |
| Event diary | `GameDiary`, `Transition` | Existing append-only runtime events are subsystem reports. Generic versioned derived events/source references are missing; add only this provenance envelope. |
| Generic physical tracks | `eyes/tracking.py`, `robotron_agency.py` | Preserve IDs and tracker events. Allocation is not physical birth; missing observations are not deaths. No competing object IDs. |
| Detection/class metadata | detectors, sprites, taught recognizer | Preserve original centers/boxes/class scores/UNKNOWN through artifact references. A subsystem's label is not a semantic fact. |
| Agency/SELF | `AgencyTracker`, `VisualAgency` | Preserve belief scores, runner-up, measured/unmeasured phases, provisional status and controlled ID. Do not duplicate inference or change gates. |
| Persistent SELF | `PersistentSelfTracker` | Live shares the generic tracker and uses `bind_track/observe_tracks`. E/E neither seeds nor updates it. |
| Actions and timing | `ArcadeController` in `hands.py`, `ObservedCamera`, source timing | Reference actual command/sent/ack/ready/return/exposure evidence, including discovery actions. Do not substitute ideal actuator timings. Missing time remains None. |
| Preflight/state/end | exposure/settle/preflight, screen-state and episode-end modules | Reference report fields and setup frames. Do not relabel an identity loss as death or take over episode termination. |
| Score | ScoreObserver/System/Tracker/HUD/events | Reference original raw HUD frames, independent P1/P2/SELF, acceptance/UNKNOWN/confidence and measured overhead. Keep score passive and acceptance untouched. |
| Human annotations/hypotheses | Experience tags/source/evidence + Evaluator | Existing sourced claims and corrections suffice at this milestone. A human report is a new observation with `source=user:Alex`; interpretations remain existing Experience. No new hypothesis engine or teaching UI. |
| Immutable low-level evidence | No common generic substrate found | New `memory/evidence.py`: dense append-only journal with canonical references, IDs, provenance and prospective lifecycle; no memory selection/recall. |

This audit confirms the narrower gap. Existing memory feedback is not a general
world-truth solver. Existing reconstruction is not an immutable observation
archive. Existing causal-in-history prediction code is useful but is not a
durable historical prediction commitment.

## Flow and integration point

The offline command consumes an **extracted existing run directory** containing
`report.json`, with optional agency/score/events JSONL and external frames:

```bash
python -m experiments.ppal.episode_evidence \
  robotron-runs/body-fire-bootstrap-20261001-020552 \
  --output robotron-evidence/body-fire-bootstrap-20261001-020552 --reflect
```

`--reflect` is opt-in. It calls the existing MemoryGateway, Evaluator and normal
MARM outbox. It does not send memory to a remote server; normal memory sync remains
separate. Without this flag the command only builds/replays evidence. No camera,
controller, live policy or semantic teaching is opened. Keep output outside the
original run directory. Process older extracted run directories with the same
command and their own output directories.

`import_episode(root, journal)` indexes the existing run rather than replacing
its session. `derive_episode(root, journal, episode, window=..., tolerance=...)`
appends versioned interpretations and constructs one ordered replay notebook.
`reflect_evidence(journal, episode, gateway)` selectively consolidates diagnostic
resolution summaries using **Experience → MemoryGateway → MemoryEvaluator →
existing store/outbox**. Existing reflection questions and meditation remain
available; neither is automatically invented from these diagnostic counts.

To revisit the same evidence with another explicit derivation configuration:

```bash
python -m experiments.ppal.episode_evidence \
  robotron-runs/body-fire-bootstrap-20261001-020552 \
  --output robotron-evidence/body-fire-bootstrap-20261001-020552 \
  --window 5 --tolerance 4 --reflect
```

This is a changed diagnostic model/criterion, **not proof that the second model
is better**. A wider tolerance naturally supports more outcomes. Original
observations and prior derivations remain present. Repeating a completed version
is idempotent; interrupted versions remain visible and require a new output or
version rather than silent repair/deletion.

## Persistence, epistemic boundaries and provenance

SQLite is already used by Evaluator and MARM outbox. This new database fills the
distinct dense evidence gap; it is not another durable cognitive memory store.
Each canonical record has schema, episode, producer/model version, monotonic
time when known, source IDs, provenance and canonical JSON. SHA-256 content IDs
survive reload. SQL triggers reject UPDATE/DELETE. The frozen record returns a
new decoded JSON value on each access, preventing nested mutation from changing
committed history. External artifacts carry hashes plus relative paths and
line/JSON locations; `read_artifact` verifies bytes and rejects path escape.
Images remain external and preserve full RGB evidence. Keep the original archive
and extracted files with the notebooks; references are not backups.

Episode identity is the hash of the existing report. Source dirty-worktree status
and source revision are preserved. No wall/monotonic correspondence is invented:
these source logs lack a wall-clock anchor; import commitment has its own UTC
time, and original sensor times retain their original scope. Tracker IDs are
local to the episode. Frame reference, command timestamps, exposure metadata,
class scores and confidence are recoverable through original observation refs.

A row saying `self_track_id=...`, `identity_status=provisional`, `kind=grunt` or
`score=888` means the subsystem reported it. It does not certify physical SELF,
hostility or true game score. A tracker-created event means ID allocation, not a
physical birth. Disappearance/contact/death/respawn/score causation are not
manufactured from proximity or missing pixels. Accepted score changes are
versioned events with **unknown attribution**.

Malformed source bytes are not silently edited: retain originals and append a
new sourced observation/interpretation. Existing Gateway/Evaluator correction
applies to selected memories. No parallel correction store was created.

## Prediction → resolution

The generic `predict` API commits a separate prediction containing model,
sources, creation time, future horizon, expected measurable outcome and explicit
mode. It rejects future source dependencies and predictions made after later
observations are already in that notebook. `resolve` requires a previously
committed prediction and later evidence in both sequence and observation time;
it rejects supported/contradicted outcomes beyond the horizon, duplicate
resolutions and invalid errors. Supported/contradicted/unresolved are distinct.
The generic append API rejects bypassing this lifecycle with reserved kinds.

The Robotron adapter uses existing `predict_next`, normalized physical track
positions and a next-agency-sample/one-second horizon. A missing same-ID outcome,
a skipped sample, late observation or episode end is **unresolved**. This is a
kinematic diagnostic, not learned BODY/FIRE physics or AgencyTracker inference.

The canonical source archive already contains the whole historical run. Thus
the adapter creates an explicitly **replay_prospective** ordered notebook: it
admits each source observation in order, commits forecasts using past points
only, then admits/resolves future evidence. Canonical resolution references
identify the replay notebook and resolution ID; its prediction/source chain
leads back to original evidence. Completion records hash the replay notebook.
Reload verifies content/schema/source ordering. Both notebooks must be retained.

This demonstrates durable prospective commitments **within replay**, not that
Charlie made these predictions before the original real-world events. Live
shadow forecasts are imported as reported observations, never retroactively
promoted to live commitments. The generic API reserves an explicit live mode
with a current-process timestamp check, but **live emission is not wired or
validated here**. Arbitrary custom models cannot be proven ignorant of future
data by a timestamp alone. The adapter supplies past-only model input, and its
known-archive provenance makes the limitation explicit.

SQLite commits are transactional. A crash may leave a partial import/replay,
including unresolved pending forecasts; completed earlier records remain.
Disk failure raises visibly from the offline command and does not affect the
already completed gameplay. This is a single-writer offline interface; no new
runtime queue/thread or distributed commitment protocol was introduced.

## Real demonstration

Full supplied `body-fire-bootstrap-20261001-020552` archive, source `dfdccde`,
dirty worktree recorded:

- 76 agency observations / 2,206 detections.
- 62 UNKNOWN and 14 provisional SELF samples; zero confirmed SELF samples.
- Eight ordinary BODY+FIRE decisions, then recovery/control-challenge rows.
- Discovery includes FIRE-only and simultaneous BODY/FIRE transport evidence.
- Time-limit completion is preserved; observed deaths/respawns are not upgraded
  to inferred facts merely because SELF was lost.
- Observer baseline 888 was accepted at sample 6. No accepted score change was
  logged. Alex independently reports 400. The final saved view is the high-score
  display, not proof of a final HUD score. Both claims remain preserved.

| Replay model/criterion | Supported | Contradicted | Unresolved |
|---|---:|---:|---:|
| Past window 3, tolerance 2 board percent | 1,370 | 186 | 245 |
| Past window 5, tolerance 4 board percent | 1,508 | 48 | 245 |

These counts are per-track kinematic tests, not SELF accuracy, policy quality,
calibrated probabilities, points earned or semantic learning. Both versions
resolve 1,801 forecasts and coexist beneath the same unchanged source evidence.
The compact [example](ee-body-fire-example.json) records selected provenance,
resolution IDs, reflection summaries and an actual existing-memory correction:
a tentative observer-score interpretation is superseded after Alex's sourced
400 annotation, while the original 888 observation remains intact.

The demonstration used the real MemoryGateway/Evaluator and existing JsonlStore
locally, avoiding remote delivery. Normal `--reflect` selects the normal outbox.
No new Experience, memory IDs, question queue or hypothesis abstraction was
created. A resolution is not automatically labeled helpful/harmful to memory.

Older evidence also exercises the chain: response-window-012341 has accepted
200→300/+100 score evidence; exposure-010300 has UNKNOWN SELF and fragmentation;
goodview-002659 failed before agency. Their observations do not require correct
score, useful semantics or a completed game to be represented.

## Performance and tests

Measured full new-archive import plus first derivation on the development host:
5.078 seconds offline; second version 5.041 seconds. Initial unoptimized replay
was about 40 seconds; SQL filtering reduced redundant decoding. These are host
measurements, not Pi benchmark claims. **Added live-loop cost is zero by design**:
the live runner has no dependency or call to E/E. Existing live logging/score
costs are preserved, not represented as zero.

New tests prove nested immutability, UNKNOWN/provenance/stable ID reload,
prediction ordering/hindsight rejection, three resolution states, duplicate
resolution rejection, failed episodes, source tamper detection, two derivations
without source mutation, existing MemoryGateway consolidation, real camera
fixture integration without any SpriteTracker update, visible offline failure
and absent live dependency. The real full archive supplies the integration
demonstration; synthetic sequence tests are explicitly synthetic.

Existing suites cover Former selection, Evaluator contradiction/dormancy and
supersession, MARM delivery/retry/corrected recall, Reflection questions,
Meditation/reconstruction/prediction, exact tracking replay, provisional bootstrap,
mock armed controller behavior, score isolation/UNKNOWN, camera timing and
calibration. They remain part of the full suite.

Validation: `python -m pytest tests -q` — **312 passed in 20.80 seconds**.

## Deliberately not built / remaining

No Learning Executive, curriculum stages, curiosity/experiment optimizer, policy
update, semantic teaching UI, automatic score attribution, new hypothesis engine,
projectile classifier, reverse-ray FIRE localization, contact truth, rescue/death
labels, cross-episode rule learning or second tracker. No gameplay fixes accompany
this foundation, including the newly exposed score discrepancy or recovery stall.

The forthcoming-run dependency is now met by the supplied BODY/FIRE archive.
Still awaiting evidence/implementation: reliable measured score changes during
BODY/FIRE play; validated projectile detections/origin convergence; independent
identity/contact ground truth; actual live pre-outcome commitments; Pi overhead
for any future live emission. These are not prerequisites for preserving evidence.

Extension boundaries: versioned derivations reference observations; future
behavioral clustering/world predictions/surprise use the generic prediction API;
cross-episode interpretations use existing Experience evidence/tags and
Gateway/Evaluator; human semantic teaching adds sourced Experience/observations;
question formation stays in Reflection; future experiment selection belongs to
the deferred Learning Executive. Live commitment scheduling, clock anchoring,
multi-source horizons, crash resume/migrations and provenance linkage across
notebooks may evolve before that executive is introduced.

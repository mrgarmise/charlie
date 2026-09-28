# Robotron learning readiness audit — 2026-09-28

## Verdict

Do not start an unattended 50–100-game learning batch yet. The current integration
branch has substantial perception, tracking, replay, memory, shadow prediction,
and marathon scaffolding. The earlier uncommitted camera-tracker draft is
superseded and must not be overlaid on it.

This audit starts from `feature/ppal-integration` at `2905b05` (not the older
`feature/ppal-vision-focus`). Reported local changes after the 147-test run may
not be pushed. Reconcile that exact local `play_robotron.py` before deploying.
No live Pi hardware validation was performed here.

The official first 20-second run remains **600 points**. The roughly 1,000-point
full-game estimate is not an official measurement. SCORE is the external goal.
Survival, rescues, prediction errors, and action disagreements are diagnostics.

## Findings and changes

| Area | Finding | Resolution in this branch |
|---|---|---|
| Episode boundaries | Marathon treated tracking/control failure as permission for a new START. | Fail closed unless a successful report explicitly supplies confirmed game-over evidence. Existing runner reports unknown; consequently automatic chaining is intentionally blocked. |
| Failed starts | Another START could be sent even though the first start's outcome was unknown. | Stop for review instead of inferring exhausted credits or game over. |
| Player reacquisition | Global appearance could reassign SELF to another sprite; reseeding could use stale pre-recovery detections. | Prefer repeated local continuity; use the latest recovery detections; reset motion/goal history after reacquisition. |
| Causal discovery | Two successful legs could be combined despite a failed leg; after-image resemblance was not required. | Require all E/S/W legs with unbroken association and player-like after evidence. This remains heuristic, not proof of causal identity. |
| Identity tracking | Greedy near-ties could swap identities. | Reject ambiguous assignments and ambiguous SELF seeds. Missing evidence remains missing. |
| Prediction | Velocity measured per tick despite variable camera/action latency. | Add capture-time prediction, explicit units and horizon; reject evaluation at incompatible times or after SELF-ID changes. Retain tick mode for older callers. |
| Score evidence | Ledger accepted negative/coerced scores and did not distinguish incomplete runs. | Validate scores/lives; identify human-reported score and whether the run ended with confirmed game over. |
| Review questions | Existing reflection consumed replay artifacts, but marathon live reports weren't connected to that queue. | Add live review with grouped score, episode-end, and SELF questions; include failed attempts. No claims promoted as learned strategy. |
| Evidence | Live loop did not retain representative failure images or identify code/knowledge version. | Save up to 40 review frames (including final view), timestamps, git revision/dirty flag, and knowledge hash. |

## Remaining work and required mode

1. **Reconcile the user's current local runner — Work + one local source upload.**
   Need the full current file or committed branch, not only a diff statistic.
   Preserve newer seconds-horizon edits and rerun regression tests after merging.
2. **Distinguish active play, demo, life loss, level completion, and game over —
   Work + labeled camera recordings.** Board geometry alone is insufficient.
   A failed movement challenge can mean death, collision, wrong detection, or
   communications trouble. It must not be interpreted as confirmed game over.
3. **Read SCORE reliably — Work + score/HUD calibration; Chat for user confirmation.**
   Need visible HUD, temporal agreement, rollover/reset handling, and manual
   cross-checks. Unknown must stay null. Manual ledger entry remains available.
4. **Validate player/tracker accuracy on unseen recordings — Work; Chat for sprite
   labels and ambiguous moments.** Measure identity switches, lost duration,
   incorrect reacquisition, and false human/mine classification. Current
   nearest-neighbor tracking still lacks robust occlusion and appearance-assisted
   association; rejecting ties trades continuity for fewer confident mistakes.
5. **Learning mechanism — Work implementation; Chat can settle experiment goals.**
   Live Forebrain/Hindbrain are fixed rules. Shadow forecasts never control the
   game. Meditation reconstructs trajectories; it does not demonstrate increased
   score or change live policy. Add versioned candidate policies and randomized
   baseline/candidate runs after outcome measurement works. Do not credit unchosen
   actions from shadow predictions or reconstructed paths as actual outcomes.
6. **Dataset and confidence — Work.** Keep raw observations distinct from inferred
   track links, use held-out games, report uncertainty, and check that prediction
   gains survive identity errors. Adjacent frames from the same tuned clip are
   not independent validation data.
7. **Hardware endurance — Pi execution, assisted in Chat.** Verify camera alignment,
   control release on connection/process failure, latency with recording enabled,
   disk limits/rotation, score capture, and actual episode restarts. Work is useful
   for code fixes and analyzing uploaded runs; it cannot physically validate this Pi.
8. **Question feedback loop — Work implementation; Chat answers.** The new queue
   groups repeated questions and points to evidence. Human answers still need a
   reviewed, versioned path into labels/policy; do not auto-train on uncertain answers.

## Rollout gate

First reconcile and deploy one tested build. Run three supervised complete games
with manually checked start, game-over, final score, and player identity. Then
10 supervised games to validate restart reliability and evidence retention.
Only expand to 50–100 after the boundary/score checks pass. Stop on unresolved
SELF or episode state; no blind credit spending. Compare full games with full
games and equal-duration segments with equal-duration segments.

To review existing live evidence without controls:

```bash
python3 -m experiments.ppal.learning_review robotron-runs/play-EXAMPLE \
  --output robotron-runs/learning-review
```

This emits `learning-review.json`. It is a diagnostic question list, not a learned
policy or a guarantee of improvement.

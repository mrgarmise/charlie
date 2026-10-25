# Operator procedure: three / meditation / three

These are future operator commands, not permission granted by the October 25 software mission. No command below was used to start physical play during implementation. Keep PR #9 draft; use a separately reviewed, clean native checkout of its final published commit. Do not install firmware, move servos or activate a learned policy as part of this procedure.

## Prepare offline

From the reviewed checkout, set paths outside the source and original notebook. Retain the existing original notebook; do not initialize a replacement, copy a live SQLite database without its sidecars, or reset prior investigations.

```bash
CHARLIE_MARATHON_REVISION='<reviewed final PR #9 commit>'
CHARLIE_CAMPAIGN='/home/five/charlie-native-trials/original-marathon-20261025'
CHARLIE_NOTEBOOK='/home/five/.local/share/charlie/development'
CHARLIE_CONDITIONS='/home/five/charlie-native-trials/original-marathon-conditions.json'
python -m learning.campaign prepare "$CHARLIE_CAMPAIGN" \
  --notebook "$CHARLIE_NOTEBOOK" --marathon --conditions "$CHARLIE_CONDITIONS"
```

The conditions JSON must contain nonempty `camera`, `game`, `system`, and `measurement` objects describing the actual frozen focus/framing/camera configuration, game/settings/controller configuration, reviewed runtime/host configuration, and independent complete-game/final-score measurement method. Include original artifact hashes and method versions. Set these before gameplay. Do not use the software-test fixture conditions as native evidence. Exact conditions must accompany each independent evaluation record.

Preparation freezes exactly six target games, original baseline for block one, fixed 3/3 order, independent certificates, source/runtime hashes, notebook location and conditions. It neither arms devices nor confers physical authority.

## Native review and block one

Use the existing same-boot review schema described in the preserved [native handoff](../experience-action-20261021/NATIVE-OPERATOR.md), bound to the reviewed revision above. Review must be at most one hour old. All seven existing proof classes are still mandatory: independent physical stop, independent neutral release, controller identity/lease, camera ownership, fixed focus/framing, host monitoring and passing software tests. The software XML must cover every one of the 34 formerly blocked socket tests without failure/error/skip. Historical 0.92-second operator-observed neutralization remains historical evidence; this implementation does not invent a new timing measurement.

The installed compatible controller lease/deadman and independent release path must already have their required acceptance. Retain actual native thermal, memory, throttling, disk and ownership checks. An agent namespace restriction is not a device failure and is not permission to bypass it.

Only after the operator has the separately applicable gameplay authority and actual prerequisites:

```bash
python -m learning.campaign arm "$CHARLIE_CAMPAIGN" --hours 1
python tools/native_robotron_trial.py \
  --expected-revision "$CHARLIE_MARATHON_REVISION" \
  --review /absolute/path/to/fresh-native-review.json \
  --campaign "$CHARLIE_CAMPAIGN" \
  --output /home/five/charlie-native-trials/original-marathon-monitor-block1
```

The second command is inspect-only. Add `--run` to that exact command only for an authorized physical launch. The evidence output must be fresh and outside the checkout. The wrapper launches `learning.campaign run`, requires the controller server lease, records every native resource sample and stops only its owned worker tree. It does not restart the campaign automatically.

The campaign runs three complete games through the existing marathon. No diagnostic time limit is used as a completion criterion. The first game also waits for a fresh recognized START permission and cannot attach to an already running partial game. Every restart still needs the independently validated prior boundary and a fresh eligible screen. GAME OVER itself is not START permission. Loss of SELF and zero reserve icons supply neither terminal nor START authority.

After three native-qualified complete games and physical resource release, the existing offline Reflection/Meditation/Executive lifecycle runs. The campaign reaches `awaiting_second_block`, or retains a yielded `reflecting` phase. This is an intentional successful handoff; it cannot spend the first-block grant on a fourth game.

## Resume offline work or reconcile interruption

```bash
python -m learning.campaign run "$CHARLIE_CAMPAIGN"
```

Without `--arm`, a retained `reflecting` phase resumes only offline work. The original captures, imports and notebook identities are retained. Do not edit campaign JSON or delete lock/evidence files to force a transition.

If interrupted while marked `playing`, a normal run fails closed without issuing START. After independently confirming the worker is stopped and resources released, the operator may request evidence reconciliation:

```bash
python -m learning.campaign reconcile "$CHARLIE_CAMPAIGN"
python -m learning.campaign run "$CHARLIE_CAMPAIGN"
```

Reconciliation reads the original worker progress/session, reopens original recordings and requires a complete native three-game block. It does not launch a game. A partial or uncertain block remains blocked; its games, raw captures and faults remain authentic evidence and do not qualify the campaign target or unlock meditation. This procedure does not automatically restart an interrupted game or reuse a possibly consumed START. Additional recovery from an incomplete block requires evidence-based operator reconciliation, not a new notebook or a falsified completion count.

During authorized native execution, create `STOP` in that launch's monitor output directory, or interrupt its foreground process, to stop owned workers. Use the independent physical stop if required. Also revoke future gameplay authority with:

```bash
python -m learning.campaign disarm "$CHARLIE_CAMPAIGN"
```

Disarming is not a substitute for independently verifying physical neutral release. Camera/controller ownership and the existing gameplay interlock exclude offline processing while resources are active. Preserve the runner result, resource trace, complete session, partial captures and fault details after any failure.

## Review meditation, then block two

Inspect `campaign.json`, first-session `reflection-progress.json`, the original notebook's `development-status.json`, preserved evaluator/project outcomes and before/after retained-state snapshots. Identify every candidate by original proposal, evaluation and checkpoint identities. A checkpoint is not acceptance of a candidate. Do not fabricate a candidate if none qualifies.

The second block requires the existing reviewed-native-three gate for this campaign's first session, at the same frozen revision, and a separate grant. Without a qualified retained policy, use:

```bash
python -m learning.campaign arm "$CHARLIE_CAMPAIGN" --hours 1 \
  --reliability-session /absolute/path/to/this-campaign-first-session \
  --observed-native-three
```

This explicitly records that no learned improvement was selected through activation safeguards and retains the original baseline. It does not prove that learning occurred. A separately authorized, already activated and physically qualified retained policy may instead be selected with `--second-policy /absolute/path/to/qualified-manifest.json` on that arm command. The campaign does not create or activate the manifest. Existing qualification, physical readiness, exact runtime identity, authorization and rollback checks run again at every episode load. A failed explicit load stops; it cannot silently swap to baseline. The October 25 mission authorizes no such activation or physical execution.

Run the native wrapper again using a fresh same-boot review and a new monitor output directory, the same campaign path and frozen revision. Inspect without `--run` first. Under separate gameplay authority, `--run` then executes the second three-game block. No additional scheduled meditation is interposed; the state reaches `awaiting_comparison`. No seventh target game can launch.

## Independent comparison and learning acceptance

Use the existing score review/annotation and independent measurement interfaces to place six `robotron_evaluation_episode` records in the retained independent measurement journal. Each must bind its actual original report SHA, exact `policy_identity`, source episode, independently qualified new-game start, persistent terminal captures, final score, proof hashes and the frozen conditions. The existing `experiments.comparison.robotron.validate_certificates` enforces these references. A held reader score or an operator observation without the required independent artifacts is not a certificate. Preserve disagreement and unreadable final scores.

```bash
python -m learning.campaign compare "$CHARLIE_CAMPAIGN" \
  --journal /absolute/path/to/independent-measurements.sqlite3 \
  --record '<game1-evaluation-record-id>' --record '<game2-evaluation-record-id>' \
  --record '<game3-evaluation-record-id>' --record '<game4-evaluation-record-id>' \
  --record '<game5-evaluation-record-id>' --record '<game6-evaluation-record-id>'
```

The comparator uses the existing certificate validator and refuses duplicate, missing, changed or conflicting evidence. It reports individual scores and descriptive block means/change; fixed phase order is a confound. It cannot convert score change into learning acceptance.

Independently review E1, P1 and I1 using the ALA charter/acceptance standard. Use preserved original decisions/contexts, authentic experience, exact retained updates/reload, comparable later choices and controlled replay/ablation. The existing Executive causal-audit interface and existing qualified-policy controlled replay interfaces remain available. The campaign records their source identities, but it does not automatically certify either layer. Record NOT YET DEMONSTRATED wherever evidence is missing, including when a retained valuation changes without qualified downstream activation. Report autonomous operation, independent performance, E1, P1 and I1 separately.

## Software verification scope

CLI help/argument interfaces, simulated full 3/checkpoint/3 phase order, independent certificate handling, old-frame terminal/score regressions, interruption handoff, existing lifecycle imports and safety/controller regressions are tested offline. This is not a claim that the operator commands or hardware campaign have already succeeded natively. Use the final archived test receipts and exact published source hashes when reviewing the checkout.

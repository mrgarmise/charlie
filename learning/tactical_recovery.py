"""Read-only qualification of historical PPAL motion feedback.

The existing capture journal is the authority.  This module does not generate
an experiment, start gameplay, or treat a copied journal as another episode.
Only an explicitly linked prediction -> execution -> same-track endpoint ->
resolution may enter the *diagnostic* (never activated) tactical ledger.
"""
from __future__ import annotations

import math


def qualified_motion_outcomes(journal):
    """Yield (episode_origin, evidence_record_id, outcome), with strict linkage.

    Any unconfirmed source is excluded; eligible here means the recorded
    response window was structurally linked, NOT that it is independent final
    gameplay evidence or a valid causal/score claim.
    """
    predictions = {
        r.id: r for r in journal.records("prediction")
        if r.data["payload"].get("category") == "tactical_prediction"
    }
    executions = {}
    for r in journal.records("observation"):
        p = r.data["payload"]
        if p.get("category") == "tactical_execution" and isinstance(p.get("prediction_id"), str):
            executions.setdefault(p["prediction_id"], []).append(r)

    for r in journal.records("observation"):
        p = r.data["payload"]
        if p.get("category") != "tactical_outcome":
            continue
        prediction_id = p.get("prediction_id")
        pred = predictions.get(prediction_id)
        if pred is None or pred.data["episode"] != r.data["episode"]:
            continue
        if (p.get("eligible") is not True or p.get("identity_status") != "confirmed"
                or p.get("result") not in ("supported", "contradicted")
                or not isinstance(p.get("track_id"), (str, int))
                or not isinstance(p.get("along"), (float, int))
                or isinstance(p["along"], bool)
                or not math.isfinite(p["along"])):
            continue
        origin_at, observed_at = p.get("origin_at"), p.get("observed_at")
        if (not all(isinstance(t, (int, float)) and not isinstance(t, bool)
                    and math.isfinite(t) for t in (origin_at, observed_at))
                or not 0 < observed_at - origin_at <= 2):
            continue

        predicted = pred.data["payload"].get("actual_action") or pred.data["payload"].get("selected")
        if not isinstance(predicted, dict):
            continue
        linked = [e for e in executions.get(prediction_id, [])
                  if e.data["episode"] == r.data["episode"]
                  and isinstance(e.data["payload"].get("action"), dict)
                  and all(e.data["payload"]["action"].get(k) == predicted.get(k)
                          for k in ("move", "fire"))]
        if len(linked) != 1:
            continue
        action = linked[0].data["payload"]["action"]
        if (p.get("actual_action") is not None
                and any(p["actual_action"].get(k) != action.get(k)
                        for k in ("move", "fire"))):
            continue
        resolution = journal.resolution_for(prediction_id)
        if (resolution is None or resolution.data["payload"].get("result") != p["result"]):
            continue

        # The source episode is an observed recording origin, not a guarantee
        # of independent trial or a verified complete-game boundary.
        yield r.data["episode"], r.id, dict(p, actual_action=dict(
            move=action["move"], fire=action["fire"]))


def qualified_motion_summary(journal, memory, *, commit=False):
    """Summarize, optionally append to a separate bounded diagnostic artifact.

    Never write a source journal.  Calling twice with the same capture IDs
    cannot turn one observation into two independent episodes.
    """
    accepted = list(qualified_motion_outcomes(journal))
    recorded = 0
    if commit:
        for episode, evidence_id, outcome in accepted:
            recorded += int(memory.record(outcome, episode=episode, evidence_id=evidence_id))
    return dict(qualified_windows=len(accepted),
                appended_diagnostic_rows=recorded,
                source_ids=[evidence_id for _, evidence_id, _ in accepted],
                committed=bool(commit), eligible_for_policy_activation=False,
                interpretation="exact linked archival observations; no new gameplay or independent-score credit")

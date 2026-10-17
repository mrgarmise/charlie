"""Conservative, read-only outcome-yield estimator for Executive research.

This module is an experimental *shadow* valuation, not an operational chooser.
It uses the Executive's retained authenticated outcome rows, but overlapping
archived references are treated as a single evidence partition. Distinct
partitions are not certified independent experiences. The estimate describes
whether an investigation produces a decisive diagnostic resolution, *not*
whether the finding is causally correct or improves Robotron performance.
"""
from __future__ import annotations

from collections import Counter

PRIOR_DECISIVE = 2
PRIOR_UNRESOLVED = 2
RESOLVED = frozenset(("supported", "contradicted"))
KNOWN = RESOLVED | {"unresolved"}


def evidence_partitions(project):
    """Merge overlapping offline source groups; ignore unqualified identities.

    The caller never supplies new observations. A missing/empty source group
    makes an outcome ineligible for the yield estimate; it remains in history.
    A physical episode needs a separate independent-identity review and is
    deliberately not inferred from an arbitrary episode string here.
    """
    partitions = []
    excluded = []
    for row in project.get("experiment_history", ()):
        verdict = row.get("result")
        groups = row.get("evidence_groups") or ()
        source_ids = frozenset(x for x in groups if isinstance(x, str) and x)
        resolution_id = row.get("resolution_id")
        if (row.get("experiment_kind") != "offline" or verdict not in KNOWN
                or not source_ids or not isinstance(resolution_id, str)
                or not resolution_id):
            excluded.append(resolution_id)
            continue
        item = {"sources": set(source_ids), "verdicts": {verdict},
                "resolution_ids": {resolution_id}}
        overlapping = [p for p in partitions if p["sources"] & item["sources"]]
        while overlapping:
            for p in overlapping:
                item["sources"].update(p["sources"])
                item["verdicts"].update(p["verdicts"])
                item["resolution_ids"].update(p["resolution_ids"])
                partitions.remove(p)
            overlapping = [p for p in partitions if p["sources"] & item["sources"]]
        partitions.append(item)
    return partitions, excluded


def information_yield(project):
    """Estimate bounded relative diagnostic yield with explicit provenance.

    Each non-overlapping archive partition contributes at most once. A mixed
    unresolved/decisive partition is inconclusive; conflicting supported and
    contradicted results are inconclusive too. Priors are method-independent
    pseudocounts (2, 2); they are not prior evidence observations.
    """
    partitions, excluded = evidence_partitions(project)
    verdicts = Counter()
    evidence = []
    for group in partitions:
        seen = group["verdicts"]
        decisive = bool(seen & RESOLVED) and "unresolved" not in seen
        decisive = decisive and not RESOLVED.issubset(seen)
        state = "decisive" if decisive else "inconclusive"
        verdicts[state] += 1
        evidence.append({
            "resolution_ids": sorted(group["resolution_ids"]),
            "source_reference_count": len(group["sources"]),
            "classification": state,
        })
    numerator = PRIOR_DECISIVE + verdicts["decisive"]
    denominator = PRIOR_DECISIVE + PRIOR_UNRESOLVED + len(partitions)
    mean = numerator / denominator
    return {
        "schema": "e1-shadow-information-yield-v1",
        "estimate": mean,
        "baseline_estimate": PRIOR_DECISIVE / (PRIOR_DECISIVE + PRIOR_UNRESOLVED),
        "relative_multiplier": mean * 2,
        "decisive_partitions": verdicts["decisive"],
        "inconclusive_partitions": verdicts["inconclusive"],
        "partitions": evidence,
        "excluded_resolution_ids": sorted(i for i in excluded if isinstance(i, str)),
        "independence_qualified": False,
        "interpretation": "Bounded retrospective diagnostic-yield hypothesis; overlapping references collapsed; no authenticity, independence, strategy improvement or E1 acceptance inferred.",
    }

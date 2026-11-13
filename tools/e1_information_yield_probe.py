"""Read-only counterfactual for a proposed outcome-informed Executive valuation.

The production Executive remains unchanged. This shadow estimate is NOT E1
acceptance; it measures whether a general learned information-yield statistic
could affect the same chooser over a frozen historical opportunity set.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from memory.investigation_learning import information_yield
from tools.e1_decision_probe import decision, load_projects


def shadow_comparison(before_path, after_path):
    old, before_ids = load_projects(before_path)
    new, after_ids = load_projects(after_path)
    if after_ids[:len(before_ids)] != before_ids:
        raise ValueError("AFTER is not an append-only continuation of BEFORE")
    shared = sorted(set(old) & set(new))
    # Freeze all opportunity, eligibility, capability and independent-unit fields
    # to the BEFORE snapshot. ONLY the proposed outcome-yield estimate varies.
    frozen = {pid: copy.deepcopy(old[pid]) for pid in shared}
    proposals = []
    evaluated = {}
    for name, source in (("before", old), ("learned", new)):
        projects = copy.deepcopy(frozen)
        diagnostics = {}
        for pid in shared:
            info = information_yield(source[pid])
            # The existing chooser expects uncertainty terms in [0, 1].
            starting = float(frozen[pid].get("uncertainty", .5))
            projected = min(1.0, starting * info["relative_multiplier"])
            projects[pid]["uncertainty"] = projected
            diagnostics[pid] = dict(
                initial_uncertainty=starting,
                projected_uncertainty=projected,
                decisive_partitions=info["decisive_partitions"],
                inconclusive_partitions=info["inconclusive_partitions"],
                partitions=info["partitions"],
                excluded_resolution_ids=info["excluded_resolution_ids"],
            )
        evaluated[name] = dict(choice=decision(projects),
                               diagnostics=diagnostics)
    for pid in shared:
        prior = evaluated["before"]["choice"]["alternatives"].get(pid)
        later = evaluated["learned"]["choice"]["alternatives"].get(pid)
        if not prior or not later:
            continue
        if prior["score"] != later["score"]:
            proposals.append(dict(
                project_id=pid,
                goal=frozen[pid].get("goal"),
                baseline_score=prior["score"],
                shadow_score=later["score"],
                baseline=evaluated["before"]["diagnostics"][pid],
                learned=evaluated["learned"]["diagnostics"][pid],
                eligible_in_frozen_context=not prior["blocked"],
            ))
    return {
        "schema": "e1-shadow-yield-comparison-v1",
        "inputs": dict(before=before_path, after=after_path,
                       original_records=len(before_ids),
                       new_records=len(after_ids) - len(before_ids),
                       common_project_ids=len(shared)),
        "controls": "Identical baseline chooser code, project identities, holds, methods, resources, progress, and eligibility; only a hypothetical diagnostic-yield uncertainty term derives from different authentic outcome histories.",
        "baseline_choice": evaluated["before"]["choice"]["chosen"],
        "shadow_learned_choice": evaluated["learned"]["choice"]["chosen"],
        "changed_valuations": proposals,
        "acceptance": "NOT YET DEMONSTRATED",
        "limitations": [
            "Hypothetical shadow policy; it has NOT influenced an actual later Executive selection.",
            "Archive partitions are merely nonoverlapping source references, not independently qualified experiences.",
            "Fixed generic smoothing priors; a changed score alone is not demonstrated improved strategy.",
            "No learned model, PPAL policy, resource access or physical authorization activated.",
            "A genuine prospective E1 test must freeze this policy first, acquire independently qualified authentic outcomes, persist/reload, and replay a subsequent comparable decision."
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    destination = Path(args.output).resolve()
    if any(destination.is_relative_to(Path(p).resolve())
           for p in (args.before, args.after)):
        parser.error("output must be outside both evidence states")
    report = shadow_comparison(args.before, args.after)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "original_records": report["inputs"]["original_records"],
        "overnight_records": report["inputs"]["new_records"],
        "baseline_choice": report["baseline_choice"],
        "shadow_learned_choice": report["shadow_learned_choice"],
        "changed_project_valuations": len(report["changed_valuations"]),
        "changed_eligible_valuations": sum(
            bool(x["eligible_in_frozen_context"]) for x in report["changed_valuations"]),
        "acceptance": report["acceptance"],
        "report": str(destination),
    }, indent=2))


if __name__ == "__main__":
    main()

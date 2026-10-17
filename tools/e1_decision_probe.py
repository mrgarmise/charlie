"""Read-only native E1 probe: comparable Executive choices and outcome-state ablation.

Does not instantiate DevelopmentLifecycle, write notebooks, or authorize activity.
The ablation changes only the *evaluation input* in memory and never rewrites evidence.
A difference is a candidate causal signal, not E1 acceptance.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from memory.evidence import EvidenceJournal
from memory.learning_projects import LearningExecutive

METHODS = {"model-diagnostics", "meditation-motion", "evidence-review"}
RESOURCES = {"offline-slot", "RGB-examples", "torch", "model-evaluation",
             "context-evidence", "meditation-evidence"}
OUTCOME_FIELDS = ("progress", "experiment_history", "current_understanding")


def decision(projects):
    """Evaluate supplied frozen project states using the actual inspect-only chooser."""
    executive = object.__new__(LearningExecutive)
    # projects() is overridden on this uninitialized, non-writing reader.
    executive.projects = lambda: copy.deepcopy(projects)
    result = executive.select(methods=METHODS, resources=RESOURCES,
                              authorized_methods=METHODS, inspect=True)
    chosen = result["project"]
    alternatives = {
        row["project_id"]: row for row in result["alternatives"]
    }
    return dict(chosen=chosen["id"] if chosen else None,
                alternatives=alternatives,
                eligible=sorted(k for k, v in alternatives.items() if not v["blocked"]))


def load_projects(path):
    file = Path(path) / "learning-evidence.sqlite3"
    journal = EvidenceJournal(file, read_only=True)
    try:
        return LearningExecutive.project_state(journal), [r.id for r in journal.records()]
    finally:
        journal.close()


def analyze(before, after):
    old, before_ids = load_projects(before)
    new, after_ids = load_projects(after)
    if after_ids[:len(before_ids)] != before_ids:
        raise ValueError("AFTER is not an append-only continuation of BEFORE")
    shared = sorted(set(old) & set(new))
    pre = decision({k: old[k] for k in shared})
    post = decision({k: new[k] for k in shared})

    # Freeze the post-session opportunity set and post-session eligibility.
    # Remove *only* overnight changes to outcome-derived evaluation fields.
    # This does not remove acquisition events or lifecycle transitions.
    ablated = copy.deepcopy({k: new[k] for k in shared})
    for pid in shared:
        for field in OUTCOME_FIELDS:
            if field in old[pid]:
                ablated[pid][field] = copy.deepcopy(old[pid][field])
            else:
                ablated[pid].pop(field, None)
    control = decision(ablated)

    changes = []
    for pid in shared:
        a = pre["alternatives"].get(pid)
        b = post["alternatives"].get(pid)
        c = control["alternatives"].get(pid)
        if not (a and b and c):
            continue
        if a != b or b != c:
            changes.append(dict(id=pid, goal=new[pid].get("goal"),
                                baseline=a, learned=b, outcome_ablated=c))
    outcome_influence = any(
        post["alternatives"].get(k) != control["alternatives"].get(k)
        for k in shared
    )
    return dict(
        schema="charlie-e1-decision-probe-v1",
        source=dict(before=str(Path(before).resolve()),
                    after=str(Path(after).resolve()),
                    original_records=len(before_ids),
                    retained_records=len(after_ids)-len(before_ids),
                    shared_projects=len(shared),
                    new_project_ids=sorted(set(new)-set(old))),
        method="Same code and available methods. Shared project identities. "
               "Post-session outcome-derived fields restored from pre-session state "
               "in memory, with post-session lifecycle and eligibility unchanged.",
        baseline=pre, learned=post, outcome_ablated=control,
        changed_shared_projects=changes,
        outcome_evaluation_influence_observed=outcome_influence,
        selection_changed_baseline_to_learned=pre["chosen"] != post["chosen"],
        selection_changed_learned_to_ablation=post["chosen"] != control["chosen"],
        acceptance="NOT YET DEMONSTRATED",
        limitations=[
            "This is a retrospective, read-only causal screening test, not a full E1 acceptance.",
            "The fixed inspect-only chooser is not a prospective autonomous decision.",
            "Ablation substitutes entire historical outcome-derived fields, not individual authenticated resolution records.",
            "Other overnight changes, project holds, and evidence availability are not counterfactually reconstructed.",
            "Score differences under fixed rules alone do not demonstrate a learned investigation strategy.",
            "Physical authorization remains absent; no PPAL/I1 or performance claim."
        ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = analyze(args.before, args.after)
    destination = Path(args.output)
    if any(destination.resolve().is_relative_to(Path(p).resolve())
           for p in (args.before, args.after)):
        parser.error("output must be outside both notebook directories")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(
        original_records=report["source"]["original_records"],
        new_records=report["source"]["retained_records"],
        shared_projects=report["source"]["shared_projects"],
        baseline_choice=report["baseline"]["chosen"],
        learned_choice=report["learned"]["chosen"],
        ablated_choice=report["outcome_ablated"]["chosen"],
        outcome_evaluation_influence_observed=report["outcome_evaluation_influence_observed"],
        changed_project_evaluations=len(report["changed_shared_projects"]),
        acceptance=report["acceptance"],
        report=str(destination)), indent=2))


if __name__ == "__main__":
    main()

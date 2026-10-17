"""Engineering controls for read-only E1 probe; not authentic learning evidence."""
import copy
import pytest

from tools import e1_decision_probe as probe


def project(identifier, *, uncertainty=.8, units=0):
    return dict(id=identifier, goal=identifier, status="candidate",
                method="model-diagnostics", requires=[], dependencies=[],
                scope={}, expected="test", hold=False, progress={
                    "independent_offline_evidence_units": units,
                    "independent_physical_episodes": 0},
                experiment_history=[], objective_contribution=.5,
                learning_value=.5, uncertainty=uncertainty,
                cost=.5, risk=.5)


def test_inspect_only_decision_uses_retained_independent_units():
    base = {"a": project("a", uncertainty=1.0),
            "b": project("b", uncertainty=.9)}
    original = copy.deepcopy(base)
    before = probe.decision(base)
    assert before["chosen"] == "a"
    base["a"]["progress"]["independent_offline_evidence_units"] = 2
    after = probe.decision(base)
    assert after["chosen"] == "b"
    assert base != original
    assert original["a"]["progress"]["independent_offline_evidence_units"] == 0


def test_read_only_ablation_is_not_automatic_acceptance(monkeypatch):
    old = {"a": project("a", uncertainty=1.0),
           "b": project("b", uncertainty=.9)}
    new = copy.deepcopy(old)
    new["a"]["progress"]["independent_offline_evidence_units"] = 2
    def reader(path):
        return (old, ["prior"]) if path == "before" else (new, ["prior", "new"])
    monkeypatch.setattr(probe, "load_projects", reader)
    result = probe.analyze("before", "after")
    assert result["baseline"]["chosen"] == "a"
    assert result["learned"]["chosen"] == "b"
    assert result["outcome_ablated"]["chosen"] == "a"
    assert result["acceptance"] == "NOT YET DEMONSTRATED"
    assert result["outcome_evaluation_influence_observed"]
    assert result["outcome_ablation_effect"]["numerical_scores_changed"] == ["a"]


def test_append_only_identity_control(monkeypatch):
    state = {"a": project("a")}
    monkeypatch.setattr(probe, "load_projects",
                        lambda p: (state, ["old"]) if p == "before"
                        else (state, ["different", "new"]))
    with pytest.raises(ValueError, match="append-only"):
        probe.analyze("before", "after")


def test_resolution_ids_alone_are_not_learning_decision_influence(monkeypatch):
    """Regression for authentic overnight: extra resolutions but unchanged scores."""
    old = {"a": project("a", uncertainty=1.0)}
    new = copy.deepcopy(old)
    new["a"]["experiment_history"] = [
        {"resolution_id": "prior", "result": "supported"},
        {"resolution_id": "overnight", "result": "unresolved"},
    ]
    monkeypatch.setattr(probe, "load_projects",
                        lambda p: (old, ["prior"]) if p == "before"
                        else (new, ["prior", "overnight"]))
    result = probe.analyze("before", "after")
    assert not result["outcome_evaluation_influence_observed"]
    assert result["retained_outcome_metadata_changed"]
    assert result["outcome_ablation_effect"]["decision_evaluations_changed"] == []
    assert result["outcome_ablation_effect"]["metadata_only_changed"] == ["a"]
    assert result["baseline"]["chosen"] == result["learned"]["chosen"]


def test_lifecycle_hold_not_misread_as_outcome_ablation(monkeypatch):
    old = {"a": project("a", uncertainty=1.0)}
    new = copy.deepcopy(old)
    new["a"].update(status="paused", hold=True)
    monkeypatch.setattr(probe, "load_projects",
                        lambda p: (old, ["prior"]) if p == "before"
                        else (new, ["prior", "hold"]))
    result = probe.analyze("before", "after")
    assert result["baseline"]["chosen"] == "a"
    assert result["learned"]["chosen"] is None
    assert result["outcome_ablated"]["chosen"] is None
    assert not result["outcome_evaluation_influence_observed"]
    assert result["baseline_to_learned"]["eligibility_changed"]
    assert not result["outcome_ablation_effect"]["eligibility_changed"]

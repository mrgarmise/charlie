"""Engineering tests for shadow E1 information yield; synthetic, never E1 evidence."""
from copy import deepcopy

from memory.investigation_learning import information_yield
from tools import e1_information_yield_probe as shadow


def project(name="a", uncertainty=.8):
    return {
        "id": name, "goal": name, "status": "candidate",
        "method": "model-diagnostics", "requires": [], "dependencies": [],
        "objective_contribution": .5, "learning_value": .5,
        "uncertainty": uncertainty, "cost": .5, "risk": .5,
        "progress": {}, "experiment_history": [],
    }


def offline(resolution, verdict, *groups):
    return {
        "experiment_kind": "offline", "resolution_id": resolution,
        "result": verdict, "evidence_groups": list(groups),
        "episode": "frozen-archive-replay",
    }


def test_prior_is_neutral_and_does_not_claim_independence():
    report = information_yield(project())
    assert report["relative_multiplier"] == 1
    assert not report["independence_qualified"]
    assert report["partitions"] == []


def test_correlated_replays_do_not_multiply_evidence_partitions():
    single = project()
    single["experiment_history"] = [offline("r1", "unresolved", "episode:x")]
    replayed = deepcopy(single)
    replayed["experiment_history"].extend([
        offline("r2", "unresolved", "episode:x"),
        offline("r3", "unresolved", "episode:x", "episode:y"),
        offline("r4", "unresolved", "episode:y"),
    ])
    first = information_yield(single)
    second = information_yield(replayed)
    assert first["inconclusive_partitions"] == second["inconclusive_partitions"] == 1
    assert first["relative_multiplier"] == second["relative_multiplier"]


def test_decisive_and_inconclusive_outcomes_adjust_generic_yield():
    successful = project()
    unsuccessful = project()
    successful["experiment_history"] = [offline("s1", "supported", "episode:a")]
    unsuccessful["experiment_history"] = [offline("u1", "unresolved", "episode:a")]
    good = information_yield(successful)
    bad = information_yield(unsuccessful)
    assert good["relative_multiplier"] > 1
    assert bad["relative_multiplier"] < 1
    assert good["decisive_partitions"] == 1
    assert bad["inconclusive_partitions"] == 1


def test_conflicting_or_mixed_same_source_is_conservatively_inconclusive():
    p = project()
    p["experiment_history"] = [
        offline("s1", "supported", "episode:a"),
        offline("c1", "contradicted", "episode:a"),
        offline("u1", "unresolved", "episode:a"),
    ]
    result = information_yield(p)
    assert result["inconclusive_partitions"] == 1
    assert result["decisive_partitions"] == 0
    assert len(result["partitions"][0]["resolution_ids"]) == 3


def test_unknown_physical_id_is_not_counted_as_independent_evidence():
    p = project()
    p["experiment_history"] = [{
        "experiment_kind": "physical", "resolution_id": "physical-one",
        "result": "supported", "episode": "unverified-alias",
    }]
    report = information_yield(p)
    assert report["relative_multiplier"] == 1
    assert report["excluded_resolution_ids"] == ["physical-one"]


def test_frozen_opportunities_can_show_counterfactual_choice(monkeypatch):
    before = {"a": project("a", .8), "b": project("b", .7)}
    after = deepcopy(before)
    after["a"]["experiment_history"].append(
        offline("authored-fixture", "unresolved", "episode:one"))
    monkeypatch.setattr(shadow, "load_projects",
                        lambda key: (before, ["original"])
                        if key == "before" else (after, ["original", "outcome"]))
    result = shadow.shadow_comparison("before", "after")
    assert result["baseline_choice"] == "a"
    assert result["shadow_learned_choice"] == "b"
    assert result["acceptance"] == "NOT YET DEMONSTRATED"
    assert len(result["changed_valuations"]) == 1


def test_append_only_control_rejects_unrelated_history(monkeypatch):
    initial = {"a": project()}
    monkeypatch.setattr(shadow, "load_projects",
                        lambda key: (initial, ["authentic-old"])
                        if key == "before" else (initial, ["different-record"]))
    import pytest
    with pytest.raises(ValueError, match="append-only"):
        shadow.shadow_comparison("before", "after")

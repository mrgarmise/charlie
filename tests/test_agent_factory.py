from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from learning.agent_factory import Assignment, Capability, Factory


def outcome(goal, inputs):
    return {"goal": goal, "sources": sorted(inputs)}


@pytest.fixture
def registry():
    return [Capability("worker", "v1", "worker", outcome),
            Capability("supervisor", "v1", "supervisor", outcome)]


def test_restart_and_dependencies(tmp_path, registry):
    path = tmp_path / "mission.sqlite"
    factory = Factory(path, registry)
    nodes = (Assignment("child", "worker", ("parent",), "parent"),
             Assignment("parent", "supervisor"))
    factory.commission("test", "test", nodes)
    assert factory.step("test")
    restarted = Factory(path, registry)
    restarted.commission("test", "test", nodes)
    assert restarted.step("test")
    projection = restarted.inspect("test")
    assert projection["state"] == "completed"
    parent = projection["tasks"]["parent"]["evidence"]
    child = projection["tasks"]["child"]["evidence"]
    assert child["payload"]["inputs"] == {"parent": parent["digest"]}
    with pytest.raises(ValueError):
        restarted.commission("test", "changed", nodes)


@pytest.mark.parametrize("nodes", [
    (Assignment("a", "worker", ("b",)), Assignment("b", "worker", ("a",))),
    (Assignment("a", "supervisor", supervisor="a"),),
    (Assignment("a", "physical-motion"),),
    (Assignment("../source", "worker"),),
    (Assignment("a", "worker", supervisor="b"), Assignment("b", "worker")),
])
def test_reject_untrusted_assignments(tmp_path, registry, nodes):
    factory = Factory(tmp_path / "mission.sqlite", registry)
    with pytest.raises(ValueError):
        factory.commission("test", "test", nodes)


def test_simultaneous_claim_only_charges_once(tmp_path, registry):
    factory = Factory(tmp_path / "mission.sqlite", registry)
    factory.commission("test", "test", (Assignment("a", "worker"),))
    with ThreadPoolExecutor(8) as pool:
        claims = list(pool.map(factory.claim, ["test"] * 16))
    assert sum(claim is not None for claim in claims) == 1
    assert factory.inspect("test")["tasks"]["a"]["attempts"] == 1


def test_expired_and_cancelled_attempts_cannot_commit(tmp_path, registry):
    now = [0]
    path = tmp_path / "mission.sqlite"
    factory = Factory(path, registry, clock=lambda: now[0])
    factory.commission("test", "test", (Assignment("a", "worker"),))
    assert factory.claim("test")[2] == 1
    now[0] = 31
    restarted = Factory(path, registry, clock=lambda: now[0])
    assert restarted.claim("test")[2] == 2
    restarted._finish("test", "a", 1, "{}")
    assert restarted.inspect("test")["tasks"]["a"]["evidence"] is None
    restarted.cancel("test")
    restarted._finish("test", "a", 2, "{}")
    assert restarted.inspect("test")["state"] == "cancelled"
    assert restarted.inspect("test")["tasks"]["a"]["evidence"] is None


def test_attempt_ceiling_survives_restart_and_kill_switch(tmp_path, registry):
    path = tmp_path / "mission.sqlite"
    now = [0]
    factory = Factory(path, registry, clock=lambda: now[0])
    factory.commission("test", "test", (Assignment("a", "worker"),), seconds=200)
    for attempt in range(1, 4):
        reopened = Factory(path, registry, clock=lambda: now[0])
        assert reopened.claim("test")[2] == attempt
        now[0] += 31
    assert factory.claim("test") is None
    assert factory.inspect("test")["state"] == "failed"
    factory.stop()
    with pytest.raises(RuntimeError):
        reopened.commission("new", "test", (Assignment("a", "worker"),))


def test_retention_changes_ranking_after_restart_with_frozen_control(tmp_path):
    from memory.evidence import EvidenceJournal
    from learning.sandbox_executive import SandboxLearningExecutive

    def baseline(goal, inputs):
        return {"prediction": 0}

    def calibrated(goal, inputs):
        return {"prediction": 2}

    def evaluate(goal, inputs):
        prediction = inputs["estimate"]["payload"]["result"]["prediction"]
        residual = abs(32 - 30 - prediction)
        return {"organization_score": float(residual == 0), "evaluation_case": "fixture-offset-2"}

    path = tmp_path / "mission.sqlite"
    registry = [Capability("baseline", "v1", "worker", baseline),
                Capability("calibrated", "v1", "worker", calibrated),
                Capability("validation", "v1", "evaluator", evaluate)]
    templates = {
        worker: (Assignment("estimate", worker), Assignment("evaluate", "validation", ("estimate",)))
        for worker in ("baseline", "calibrated")
    }
    with closing(EvidenceJournal(tmp_path / "evidence.sqlite")) as journal:
        factory = Factory(path, registry)
        executive = SandboxLearningExecutive(journal, None)
        for mission in ("initial", "duplicate"):
            decision = executive.select_sandbox_organization(factory, mission, "offset", "sensor",
                                                               templates, frozen=True)
            assert decision[0]["template"] == "baseline"
            assert factory.step(mission)
            assert factory.step(mission)
        restarted = Factory(path, registry)
        decision = executive.select_sandbox_organization(restarted, "next", "offset", "sensor", templates)
        assert decision[0]["template"] == "calibrated"
        assert decision[1]["samples"] == 1
        assert restarted.inspect("next")["decision"] == decision
        assert restarted.rank("sensor", templates, frozen=True)[0]["template"] == "baseline"


def test_hard_exit_preserves_precharged_attempt(tmp_path, registry):
    from subprocess import run
    from sys import executable

    path = tmp_path / "mission.sqlite"
    parent = Factory(path, registry, clock=lambda: 100)
    parent.commission("test", "test", (Assignment("a", "worker"),), seconds=200)
    program = """
import os
import sys
from learning.agent_factory import Capability, Factory
def crash(goal, inputs):
    os._exit(17)
Factory(sys.argv[1], [Capability('worker', 'v1', 'worker', crash)],
        clock=lambda: 100).step('test')
"""
    child = run([executable, "-c", program, str(path)], timeout=10, check=False)
    assert child.returncode == 17
    assert parent.inspect("test")["tasks"]["a"] == {"attempts": 1, "evidence": None}
    restarted = Factory(path, registry, clock=lambda: 131)
    assert restarted.step("test")
    assert restarted.inspect("test")["tasks"]["a"]["attempts"] == 2


def test_synthetic_transfer_validates_timebase_and_missingness():
    from tools.agent_factory_demo import compare_replay, synthetic_transfer

    result = synthetic_transfer("fixture", {})
    assert result["mode"] == "synthetic"
    assert result["lag_seconds"] == pytest.approx(.04)
    assert result["heldout_fitted_squared_error"] == 0
    assert result["heldout_no_lag_squared_error"] > 0
    annotated = dict(mode="synthetic", clock="first", unit="rad", frame="model_world",
                     period_seconds=.02, samples=[0] * 12)
    with pytest.raises(ValueError, match="calibration"):
        compare_replay(annotated, dict(annotated, clock="second"))
    with pytest.raises(ValueError, match="missing"):
        compare_replay(annotated, dict(annotated, samples=[None] * 12))
    with pytest.raises(ValueError, match="ambiguous"):
        compare_replay(annotated, annotated)


def test_untrusted_json_has_no_tool_or_path_grants(tmp_path, registry):
    from json import dumps
    from learning.agent_factory import parse_assignments

    graph = dict(schema=1, assignments=[dict(name="a", capability="worker")])
    assert parse_assignments(dumps(graph)) == (Assignment("a", "worker"),)
    graph["assignments"][0]["tool"] = "serial"
    with pytest.raises(ValueError, match="assignment"):
        parse_assignments(dumps(graph))
    with pytest.raises(ValueError, match="size"):
        parse_assignments(" " * 65_537)


def test_existing_mission_dashboard_reads_opt_in_snapshot(tmp_path, registry, monkeypatch):
    from json import dumps
    from ui.missions import mission_status

    factory = Factory(tmp_path / "mission.sqlite", registry)
    factory.commission("display", "Display synthetic evidence", (Assignment("a", "worker"),))
    factory.step("display")
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(dumps(factory.inspect("display")))
    monkeypatch.setenv("CHARLIE_DEV_FACTORY_VIEW", str(snapshot))
    view = mission_status()["development_organization"]
    assert view["goal"] == "Display synthetic evidence"
    assert view["assignments"][0]["attempts"] == 1
    assert view["assignments"][0]["evidence"]["digest"]
    from json import loads
    from tests.test_mobile_http import call
    from ui.dashboard import start_dashboard

    server = start_dashboard(None, "m" * 40, port=0)
    try:
        assert call(server, "/api/missions", token="bad")[0] == 401
        code, body = call(server, "/api/missions")
        assert code == 200
        assert loads(body)["development_organization"] == view
        assert call(server, "/api/missions", method="POST", body={})[0] == 404
    finally:
        server.close()
    snapshot.write_bytes(b"a" * (128 * 1024 + 1))
    assert mission_status()["development_organization"]["state"] == "snapshot unavailable"

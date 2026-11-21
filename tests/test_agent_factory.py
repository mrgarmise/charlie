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
    with pytest.raises(ValueError, match="duplicate"):
        parse_assignments('{"schema": 1, "schema": 1, "assignments": []}')


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


def test_terminal_outcome_reuses_immutable_journal_and_is_idempotent(tmp_path, registry):
    from learning.sandbox_executive import SandboxLearningExecutive
    from memory.evidence import EvidenceJournal

    path = tmp_path / "ledger.sqlite"
    factory = Factory(path, registry)
    with closing(EvidenceJournal(path)) as journal:
        executive = SandboxLearningExecutive(journal, None)
        nodes = (Assignment("parent", "worker"), Assignment("child", "worker", ("parent",)))
        executive.commission_sandbox_organization(factory, "test", "observe", nodes)
        assert executive.retain_sandbox_outcome(factory, "test") is None
        assert factory.step("test")
        assert factory.step("test")
        first = executive.retain_sandbox_outcome(factory, "test")
        parent, child, terminal = journal.records()
        assert child.data["sources"] == [parent.id]
        assert terminal.data["sources"] == [parent.id, child.id]
        assert first.id == terminal.id
    with closing(EvidenceJournal(path)) as journal:
        reopened = SandboxLearningExecutive(journal, None)
        assert reopened.retain_sandbox_outcome(factory, "test").id == first.id
        assert len(journal.records()) == 3


def test_dynamic_delegation_and_lifecycle_publication(tmp_path):
    from learning.sandbox_events import LifecyclePublication
    from stimulus.bus import StimulusBus

    def supervise(goal, inputs):
        return {"organization_proposal": '{"schema":1,"assignments":[{"name":"child","capability":"worker"}]}'}

    registry = [Capability("manager", "v1", "supervisor", supervise, ("worker",)),
                Capability("worker", "v1", "worker", outcome)]
    path = tmp_path / "factory.sqlite"
    factory = Factory(path, registry)
    plan = (Assignment("parent", "manager"),)
    factory.commission("activity", "observe", plan)
    assert factory.step("activity")
    reopened = Factory(path, registry)
    reopened.commission("activity", "observe", plan)
    assert reopened.step("activity")
    view = reopened.inspect("activity")
    assert view["state"] == "completed"
    assert view["nodes"][1]["supervisor"] == "parent"
    assert view["tasks"]["child"]["evidence"]["payload"]["inputs"] == {
        "parent": view["tasks"]["parent"]["evidence"]["digest"]}
    bus = StimulusBus()
    with LifecyclePublication(bus, reopened, "activity") as publication:
        subscription = bus.subscribe_observations(publication.source)
        publication.flush()
        item = subscription.read()
        assert item.values["state"] == "completed"
        assert [event.values["kind"] for event in bus.recent_observations(publication.source)] == [
            "mission", "assignment", "claim", "mission", "result", "assignment", "claim",
            "result", "mission"]
        publication.flush()
        assert subscription.read() is None
        subscription.close()


def test_worker_cannot_expand_or_commit_partial_delegation(tmp_path):
    def counterfeit(goal, inputs):
        return {"organization_proposal": '{"schema":1,"assignments":[{"name":"child","capability":"worker"}]}'}

    factory = Factory(tmp_path / "factory.sqlite", [Capability("worker", "v1", "worker", counterfeit)])
    factory.commission("activity", "observe", (Assignment("parent", "worker"),))
    with pytest.raises(ValueError, match="allowlist"):
        factory.step("activity")
    view = factory.inspect("activity")
    assert list(view["tasks"]) == ["parent"]
    assert view["tasks"]["parent"] == {"attempts": 1, "evidence": None}


def test_pause_and_resume_fence_the_prior_attempt(tmp_path, registry):
    factory = Factory(tmp_path / "factory.sqlite", registry)
    factory.commission("activity", "observe", (Assignment("first", "worker"),))
    assert factory.claim("activity")[2] == 1
    factory.pause("activity")
    assert factory.inspect("activity")["state"] == "paused"
    assert not factory.lease_is_active("activity", "first", 1)
    assert factory.claim("activity") is None
    factory.resume("activity")
    assert factory.claim("activity") is None
    factory._finish("activity", "first", 1, "{}")
    assert factory.claim("activity")[2] == 2
    factory._finish("activity", "first", 1, "{}")
    assert factory.inspect("activity")["tasks"]["first"]["evidence"] is None


def test_oversized_delegation_never_changes_the_graph(tmp_path):
    import json

    def proposed(goal, inputs):
        return {"organization_proposal": json.dumps({"schema": 1, "assignments": [
            {"name": f"child-{i}", "capability": "worker"} for i in range(12)]})}

    factory = Factory(tmp_path / "factory.sqlite", [
        Capability("manager", "v1", "supervisor", proposed, ("worker",)),
        Capability("worker", "v1", "worker", outcome)])
    factory.commission("activity", "observe", (Assignment("root", "manager"),))
    with pytest.raises(ValueError, match="1–12"):
        factory.step("activity")
    assert list(factory.inspect("activity")["tasks"]) == ["root"]


def test_delegation_cannot_reset_root_budget(tmp_path):
    def supervise(goal, inputs):
        return {"organization_proposal": '{"schema":1,"assignments":[{"name":"child","capability":"worker"}]}'}

    path = tmp_path / "factory.sqlite"
    registry = [Capability("manager", "v1", "supervisor", supervise, ("worker",)),
                Capability("worker", "v1", "worker", outcome, work_units=3)]
    factory = Factory(path, registry)
    factory.commission("activity", "observe", (Assignment("parent", "manager"),), work_budget=3)
    assert factory.step("activity")
    reopened = Factory(path, registry)
    assert not reopened.step("activity")
    assert reopened.inspect("activity")["state"] == "failed"
    assert reopened.inspect("activity")["consumed_work_units"] == 1
    assert reopened.events("activity")[-1]["kind"] == "budget-exhausted"


def test_normal_development_scheduler_drives_factory(tmp_path):
    from subprocess import run
    from sys import executable
    import json

    output = tmp_path / "development"
    path = output / "learning-evidence.sqlite3"
    result = run([executable, "-m", "tools.agent_factory_demo", str(path),
                  "offset-demo", "offset", "--scheduled"], capture_output=True, text=True,
                 check=True, timeout=20)
    mission = json.loads(result.stdout)
    assert mission["state"] == "completed"
    assert mission["tasks"]["assessment"]["evidence"]["payload"]["result"]["held_out_residual"] == 0
    operational = json.loads((output / "development-operational-status.json").read_text())
    assert operational["run_counters"]["productive_turns"] == 2
    assert operational["physical_authorization"] is False
    assert operational["controller_writes"] == 0


def test_cli_rejects_existing_unmarked_lifecycle_notebook(tmp_path):
    from subprocess import run
    from sys import executable

    path = tmp_path / "learning-evidence.sqlite3"
    original = b"untouched preexisting notebook"
    path.write_bytes(original)
    for action in (["status"], ["offset", "--scheduled"]):
        result = run([executable, "-m", "tools.agent_factory_demo", str(path),
                      "mission", *action], capture_output=True, timeout=10, check=False)
        assert result.returncode == 2
        assert path.read_bytes() == original

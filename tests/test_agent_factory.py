from concurrent.futures import ThreadPoolExecutor

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

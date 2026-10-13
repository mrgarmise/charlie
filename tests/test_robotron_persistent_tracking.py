"""Persistent Robotron gameplay-object tracking tests."""

from experiments.ppal.models import Object, Position, WorldState
from experiments.ppal.vision_tracker import ObjectTracker


def _world(tick, humans=(), threats=()):
    return WorldState(
        tick=tick,
        player=Position(50, 50),
        targets=tuple(Object(f"raw_h_{i}", Position(*p)) for i, p in enumerate(humans)),
        threats=tuple(Object(f"raw_t_{i}", Position(*p)) for i, p in enumerate(threats)),
        alive=True,
    )


def test_human_id_survives_motion():
    tracker = ObjectTracker(max_jump=18, missed_limit=2)
    first = tracker.update(_world(0, humans=((20, 20),)))
    second = tracker.update(_world(1, humans=((24, 22),)))
    assert first.targets[0].id == second.targets[0].id


def test_threat_id_survives_motion():
    tracker = ObjectTracker(max_jump=18, missed_limit=2)
    first = tracker.update(_world(0, threats=((70, 70),)))
    second = tracker.update(_world(1, threats=((67, 68),)))
    assert first.threats[0].id == second.threats[0].id


def test_id_survives_brief_missing_detection():
    tracker = ObjectTracker(max_jump=18, missed_limit=2)
    first = tracker.update(_world(0, humans=((20, 20),)))
    tracker.update(_world(1))
    second = tracker.update(_world(2, humans=((22, 21),)))
    assert first.targets[0].id == second.targets[0].id


def test_human_and_threat_namespaces_are_separate():
    tracker = ObjectTracker(max_jump=18, missed_limit=2)
    result = tracker.update(
        _world(0, humans=((20, 20),), threats=((20, 20),)))
    assert result.targets[0].id.startswith("human_")
    assert result.threats[0].id.startswith("threat_")
    assert result.targets[0].id != result.threats[0].id

from dataclasses import dataclass
import json

import pytest

from experiments.ppal.robotron_session import (
    GameDiary, PersistentSelfTracker, RobotronSessionManager, SessionState,
)


@dataclass
class Detection:
    center: tuple[float, float]
    box: tuple[int, int, int, int] = (0, 0, 1, 1)
    kind: str = "unknown"


def test_state_machine_happy_path():
    s = RobotronSessionManager(clock=lambda: 1.0)
    for state in (SessionState.CAMERA_READY, SessionState.STARTING,
                  SessionState.WAITING_FOR_GAMEPLAY, SessionState.ACQUIRING,
                  SessionState.PLAYING, SessionState.REACQUIRING,
                  SessionState.PLAYING, SessionState.STOPPED):
        s.transition(state, "test")
    assert s.state == SessionState.STOPPED
    assert len(s.transitions) == 8


def test_state_machine_rejects_impossible_jump():
    s = RobotronSessionManager()
    with pytest.raises(ValueError):
        s.transition(SessionState.PLAYING, "skip acquisition")


def test_persistent_self_tracks_without_reclassification():
    t = PersistentSelfTracker(max_distance=7, max_missed=2)
    first = [Detection((50, 50)), Detection((20, 20))]
    seeded = t.seed(0, first, (50.1, 50.0))
    assert seeded.status == "seeded"
    player_id = seeded.track_id
    obs = t.update(1, [Detection((52, 50)), Detection((21, 20))])
    assert obs.status == "tracked"
    assert obs.track_id == player_id
    assert obs.center == (52, 50)


def test_persistent_self_requests_reacquisition_after_misses():
    t = PersistentSelfTracker(max_distance=7, max_missed=1)
    t.seed(0, [Detection((50, 50))], (50, 50))
    assert t.update(1, []).status == "temporarily_missing"
    assert t.update(2, []).status == "reacquire"


def test_diary_writes_jsonl_tracks_and_summary(tmp_path):
    times = iter([10.0, 10.1, 10.2, 10.3])
    d = GameDiary(tmp_path, clock=lambda: next(times))
    d.event("observation", tick=1)
    d.finish(result="done", state=SessionState.STOPPED,
             tracks=[{"track_id": 1}], extra={"ticks": 1})
    event = json.loads((tmp_path / "events.jsonl").read_text().strip())
    summary = json.loads((tmp_path / "summary.json").read_text())
    tracks = json.loads((tmp_path / "tracks.json").read_text())
    assert event["kind"] == "observation"
    assert summary["result"] == "done"
    assert summary["ticks"] == 1
    assert tracks["tracks"][0]["track_id"] == 1

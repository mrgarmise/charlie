from dataclasses import replace
import time

import pytest

from .core import Journal, Observation, Session
from .synthetic import LinearTwin


def setup_session(tmp_path):
    twin = LinearTwin()
    journal = Journal(tmp_path / "trials.db", "test", twin.profile, "revision")
    return twin, journal, Session(twin, journal, trials=4, seconds=10)


@pytest.mark.parametrize("fields", [{"transport": "physical"}, {"version": 2}, {"sensors": ()}])
def test_invalid_profile(fields):
    with pytest.raises((PermissionError, ValueError)):
        replace(LinearTwin().profile, **fields)


@pytest.mark.parametrize("action,duration", [((2, 0), .1), ((0, 0), -1), ((True, 0), .1)])
def test_invalid_command(tmp_path, action, duration):
    twin, journal, session = setup_session(tmp_path)
    with pytest.raises(ValueError):
        session.run(action, duration, 0)
    assert twin.stopped
    assert list(journal.read()) == []


def test_interrupted_trial_cannot_resume(tmp_path):
    twin, journal, _ = setup_session(tmp_path)
    journal.append(0, "planned", {})
    resumed = Session(twin, journal, trials=4, seconds=10)
    with pytest.raises(PermissionError):
        resumed.run((0, 0), .1, 1)
    assert [phase for _, phase, _ in journal.read()] == ["planned", "interrupted", "stopped"]


@pytest.mark.parametrize("observation", [Observation((0, 0), -1), Observation((), time.monotonic())])
def test_bad_telemetry_stops(tmp_path, observation):
    twin, journal, session = setup_session(tmp_path)
    twin.step = lambda *_: observation
    with pytest.raises(ValueError):
        session.run((0, 0), .1, 1)
    assert twin.stopped
    assert [phase for _, phase, _ in journal.read()] == ["planned", "stopped"]


def test_corrupt_evidence(tmp_path):
    _, journal, session = setup_session(tmp_path)
    session.run((0, 0), .1, 1)
    with journal.db:
        journal.db.execute("UPDATE events SET payload='{}'")
    with pytest.raises(ValueError, match="corrupt"):
        list(journal.read())


def test_cancel_and_expiry(tmp_path):
    twin, journal, session = setup_session(tmp_path)
    session.deadline = time.monotonic() - 1
    with pytest.raises(PermissionError):
        session.run((0, 0), .1, 1)
    assert twin.stopped
    assert [phase for _, phase, _ in journal.read()] == ["stopped"]

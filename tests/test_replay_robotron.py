"""Smoke tests for the offline Robotron replay helpers."""

from experiments.ppal.replay_robotron import _action_dict, _appearance_player
from experiments.ppal.models import Action


def test_replay_normalizes_stay_fire():
    assert _action_dict(Action("N", "STAY", "test"))["fire"] == "NONE"


def test_replay_has_no_controller_dependency():
    import experiments.ppal.replay_robotron as module
    assert "ArcadeController" not in module.__dict__


def test_empty_pairs_have_no_player():
    assert _appearance_player([]) is None

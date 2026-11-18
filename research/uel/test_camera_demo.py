from .camera import replay
from .camera_demo import run


def test_candidate_links_replayable_heldout_trials(tmp_path):
    path = tmp_path / "camera.sqlite"
    candidate = run(path, "test")
    assert candidate["scope"] == "simulation_only"
    assert candidate["status"] == "CANDIDATE_SIM"
    assert candidate["question_status"] == "VERIFIED_SIM"
    assert len(list(replay(path, candidate["evidence"]["training"]))) == 9
    assert len(list(replay(path, candidate["evidence"]["challenge"]))) == 3
    assert max(candidate["heldout_errors_px"]) <= 2

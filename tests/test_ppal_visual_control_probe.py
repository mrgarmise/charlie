from experiments.ppal.visual_control_probe import stable_player_fix, direction_verified


def test_stable_player_fix_accepts_repeated_single_candidate():
    fix = stable_player_fix([
        [(50.0, 50.0)], [(50.5, 49.8)], [(49.7, 50.2)],
        [(50.2, 50.1)], [], [(50.1, 49.9)],
    ])
    assert fix is not None
    assert fix.supporting_frames == 5
    assert fix.spread < 1


def test_stable_player_fix_rejects_ambiguity_without_enough_support():
    assert stable_player_fix([
        [(50, 50)], [(50, 50), (80, 80)], [], [(50, 50)], [(50, 50)], []
    ]) is None


def test_stable_player_fix_rejects_scattered_false_matches():
    assert stable_player_fix([
        [(10, 10)], [(30, 30)], [(50, 50)], [(70, 70)], [(90, 90)], []
    ]) is None


def test_direction_verification_cardinals():
    assert direction_verified((50, 50), (51, 50), "E")[0]
    assert direction_verified((50, 50), (49, 50), "W")[0]
    assert direction_verified((50, 50), (50, 49), "N")[0]
    assert direction_verified((50, 50), (50, 51), "S")[0]
    assert not direction_verified((50, 50), (49, 50), "E")[0]

from experiments.ppal.visual_control_probe import (
    PlayerFix,
    stable_player_fix,
    direction_verified,
    center_bootstrap_fix,
    anchored_player_fix,
    stationary_anchor_fix,
    motion_probe_fix,
)


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



def _candidate(x, y, player_score=.90, kind="unknown"):
    return {"center": [x, y], "player_score": player_score, "kind": kind}


def test_center_bootstrap_accepts_stable_unique_new_game_spawn():
    frames = [[_candidate(50.1, 50.3), _candidate(20, 20)] for _ in range(6)]
    fix = center_bootstrap_fix(frames)
    assert fix is not None
    assert fix.supporting_frames == 6
    assert abs(fix.center[0] - 50.1) < .01


def test_center_bootstrap_rejects_ambiguous_center():
    frames = [[_candidate(50, 50), _candidate(51, 50)] for _ in range(6)]
    assert center_bootstrap_fix(frames) is None


def test_anchored_reacquisition_carries_identity_forward():
    frames = [[_candidate(51.2, 50.1, .91), _candidate(75, 75, .96)] for _ in range(6)]
    fix = anchored_player_fix(frames, (50, 50))
    assert fix is not None
    assert fix.center[0] > 51


def test_anchored_reacquisition_requires_player_evidence():
    frames = [[_candidate(51, 50, .70)] for _ in range(6)]
    assert anchored_player_fix(frames, (50, 50)) is None



def _scored_candidate(x, y, player=.88, mine=.70):
    return {"center": [x, y], "player_score": player,
            "class_scores": {"player": player, "mine": mine}, "kind": "unknown"}


def test_stationary_anchor_uses_neutral_stillness():
    frames = [[_scored_candidate(52.0 + i*.02, 50.0), _scored_candidate(58+i, 55)]
              for i in range(6)]
    fix = stationary_anchor_fix(frames, (50, 50))
    assert fix is not None
    assert 51.9 < fix.center[0] < 52.2


def test_stationary_anchor_rejects_mine_like_object():
    frames = [[_scored_candidate(51, 50, player=.80, mine=.93)] for _ in range(6)]
    assert stationary_anchor_fix(frames, (50, 50)) is None


def test_motion_probe_identifies_candidate_that_obeys_command():
    neutral = PlayerFix((50, 50), 5, 6, .2)
    frames = [[_candidate(50.8 + i*.02, 50), _candidate(48, 50)] for i in range(6)]
    fix = motion_probe_fix(neutral, frames, "E")
    assert fix is not None
    assert fix.center[0] > 50.7

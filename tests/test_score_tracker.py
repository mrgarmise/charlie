from experiments.ppal.score_tracker import DualScoreTracker, ScoreTracker


def test_high_confidence_first_read_establishes_baseline():
    row = ScoreTracker().observe(600, .99)
    assert (row.score, row.delta, row.status) == (600, 0, "baseline")


def test_score_change_reports_reward_delta():
    t = ScoreTracker(); t.observe(600, .99)
    row = t.observe(1100, .99)
    assert (row.score, row.delta, row.changed) == (1100, 500, True)


def test_medium_confidence_change_needs_temporal_confirmation():
    t = ScoreTracker(confirm_samples=2); t.observe(600, .99)
    first, second = t.observe(700, .85), t.observe(700, .86)
    assert first.score == 600 and first.status == "pending_change"
    assert second.score == 700 and second.delta == 100


def test_single_bad_digit_does_not_corrupt_score():
    t = ScoreTracker(confirm_samples=2); t.observe(600, .99)
    assert t.observe(8600, .80).score == 600
    assert t.observe(600, .90).score == 600


def test_score_never_decreases_within_episode():
    t = ScoreTracker(); t.observe(1200, .99)
    row = t.observe(200, .99)
    assert row.score == 1200 and row.status == "rejected_decrease"


def test_absent_or_unreadable_frame_preserves_belief():
    t = ScoreTracker(); t.observe(600, .99)
    row = t.observe(None, 0)
    assert row.score == 600 and row.status == "absent_or_unreadable"


def test_low_confidence_read_does_not_start_transition():
    t = ScoreTracker(confirm_samples=2); t.observe(600, .99)
    assert t.observe(700, .40).status == "low_confidence"
    assert t.observe(700, .80).status == "pending_change"
    assert t.score == 600


def test_conflicting_pending_values_restart_confirmation():
    t = ScoreTracker(confirm_samples=2); t.observe(600, .99)
    t.observe(700, .80)
    assert t.observe(800, .80).score == 600
    row = t.observe(800, .80)
    assert (row.score, row.delta) == (800, 200)


def test_reset_allows_new_game_score_to_start_lower():
    t = ScoreTracker(); t.observe(5000, .99); t.reset()
    row = t.observe(0, .99)
    assert row.score == 0 and row.status == "baseline"


def test_optional_max_jump_rejects_implausible_read():
    t = ScoreTracker(max_jump=5000); t.observe(600, .99)
    row = t.observe(90600, .99)
    assert row.score == 600 and row.status == "rejected_jump"


def test_equal_read_is_stable_not_reward():
    t = ScoreTracker(); t.observe(600, .99)
    row = t.observe(600, .99)
    assert row.score == 600 and row.delta == 0 and not row.changed


def test_single_player_has_absent_p2_not_zero():
    t = DualScoreTracker()
    row = t.observe(8400, None, player1_confidence=.99, player2_confidence=0)
    assert row.player1.score == 8400
    assert row.player2.score is None
    assert row.self_score == 8400


def test_two_players_are_independent():
    t = DualScoreTracker()
    t.observe(8400, 1200, player1_confidence=.99, player2_confidence=.99)
    row = t.observe(8500, 1700, player1_confidence=.99, player2_confidence=.99)
    assert row.player1.delta == 100
    assert row.player2.delta == 500
    assert row.self_delta == 100


def test_self_can_be_player_two():
    t = DualScoreTracker(self_channel=2)
    t.observe(1000, 2000, player1_confidence=.99, player2_confidence=.99)
    row = t.observe(1500, 2100, player1_confidence=.99, player2_confidence=.99)
    assert row.self_score == 2100
    assert row.self_delta == 100


def test_self_channel_can_be_unknown_until_agency_resolves_it():
    t = DualScoreTracker(self_channel=None)
    row = t.observe(100, 200, player1_confidence=.99, player2_confidence=.99)
    assert row.self_score is None and row.self_delta == 0
    t.set_self_channel(2)
    assert t.observe(100, 300, player1_confidence=.99, player2_confidence=.99).self_delta == 100


def test_visual_wrapper_keeps_legacy_synthetic_hud_as_p1():
    from experiments.ppal.eyes.hud import HUDObservation
    from experiments.ppal.score_tracker import VisualScoreTracker
    class Reader:
        def read(self, image):
            return HUDObservation(score=900, lives=3, confidence=.99)
    row = VisualScoreTracker(Reader()).observe(object())
    assert row.player1.score == 900
    assert row.player2.score is None
    assert row.self_score == 900


def test_visual_wrapper_accepts_native_two_channel_reader():
    from dataclasses import dataclass
    from experiments.ppal.score_tracker import VisualScoreTracker
    @dataclass
    class HUD:
        player1_score: int | None
        player2_score: int | None
        player1_confidence: float
        player2_confidence: float
    class Reader:
        def read(self, image):
            return HUD(8400, 2500, .99, .98)
    row = VisualScoreTracker(Reader()).observe(object())
    assert row.player1.score == 8400
    assert row.player2.score == 2500


def test_visual_wrapper_tolerates_unreadable_frame():
    from experiments.ppal.score_tracker import VisualScoreTracker
    class Reader:
        def read(self, image):
            return None
    row = VisualScoreTracker(Reader()).observe(object())
    assert row.player1.score is None and row.player2.score is None


def test_score_event_log_records_both_channels_and_self_delta(tmp_path):
    import json
    from experiments.ppal.score_events import ScoreEventLog
    t = DualScoreTracker(self_channel=2)
    t.observe(1000, 2000, player1_confidence=.99, player2_confidence=.99)
    channels = t.observe(1100, 2500, player1_confidence=.99, player2_confidence=.99)
    row = ScoreEventLog(tmp_path/"score.jsonl").append(t=1.25, channels=channels)
    assert row["p1"]["delta"] == 100
    assert row["p2"]["delta"] == 500
    assert row["self_delta"] == 500
    saved = json.loads((tmp_path/"score.jsonl").read_text())
    assert saved["self_channel"] == 2

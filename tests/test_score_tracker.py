from experiments.ppal.score_tracker import ScoreTracker


def test_high_confidence_first_read_establishes_baseline():
    t = ScoreTracker()
    row = t.observe(600, .99)
    assert row.score == 600
    assert row.delta == 0
    assert row.status == "baseline"


def test_score_change_reports_reward_delta():
    t = ScoreTracker()
    t.observe(600, .99)
    row = t.observe(1100, .99)
    assert row.score == 1100
    assert row.delta == 500
    assert row.changed


def test_medium_confidence_change_needs_temporal_confirmation():
    t = ScoreTracker(confirm_samples=2)
    t.observe(600, .99)
    first = t.observe(700, .85)
    second = t.observe(700, .86)
    assert first.score == 600
    assert first.status == "pending_change"
    assert second.score == 700
    assert second.delta == 100


def test_single_bad_digit_does_not_corrupt_score():
    t = ScoreTracker(confirm_samples=2)
    t.observe(600, .99)
    assert t.observe(8600, .80).score == 600
    assert t.observe(600, .90).score == 600


def test_score_never_decreases_within_episode():
    t = ScoreTracker()
    t.observe(1200, .99)
    row = t.observe(200, .99)
    assert row.score == 1200
    assert row.status == "rejected_decrease"


def test_unreadable_frame_preserves_belief():
    t = ScoreTracker()
    t.observe(600, .99)
    row = t.observe(None, 0)
    assert row.score == 600
    assert row.status == "unreadable"


def test_low_confidence_read_does_not_start_transition():
    t = ScoreTracker(confirm_samples=2)
    t.observe(600, .99)
    assert t.observe(700, .40).status == "low_confidence"
    assert t.observe(700, .80).status == "pending_change"
    assert t.score == 600


def test_conflicting_pending_values_restart_confirmation():
    t = ScoreTracker(confirm_samples=2)
    t.observe(600, .99)
    t.observe(700, .80)
    row = t.observe(800, .80)
    assert row.score == 600
    assert row.status == "pending_change"
    row = t.observe(800, .80)
    assert row.score == 800
    assert row.delta == 200


def test_reset_allows_new_game_score_to_start_lower():
    t = ScoreTracker()
    t.observe(5000, .99)
    t.reset()
    row = t.observe(0, .99)
    assert row.score == 0
    assert row.status == "baseline"


def test_optional_max_jump_rejects_implausible_read():
    t = ScoreTracker(max_jump=5000)
    t.observe(600, .99)
    row = t.observe(90600, .99)
    assert row.score == 600
    assert row.status == "rejected_jump"


def test_equal_read_is_stable_not_reward():
    t = ScoreTracker()
    t.observe(600, .99)
    row = t.observe(600, .99)
    assert row.score == 600
    assert row.delta == 0
    assert not row.changed
    assert row.status == "stable"


def test_visual_wrapper_uses_reader_score_and_confidence():
    from experiments.ppal.eyes.hud import HUDObservation
    from experiments.ppal.score_tracker import VisualScoreTracker

    class Reader:
        def read(self, image):
            return HUDObservation(score=900, lives=3, confidence=.99)

    row = VisualScoreTracker(Reader()).observe(object())
    assert row.score == 900
    assert row.status == "baseline"


def test_visual_wrapper_tolerates_unreadable_frame():
    from experiments.ppal.score_tracker import VisualScoreTracker

    class Reader:
        def read(self, image):
            return None

    row = VisualScoreTracker(Reader()).observe(object())
    assert row.score is None
    assert row.status == "unreadable"

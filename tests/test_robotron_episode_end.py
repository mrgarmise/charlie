from experiments.ppal.episode_end import EpisodeEndObserver


def test_self_loss_alone_can_never_confirm_game_over():
    end = EpisodeEndObserver()

    # SELF can be absent for arbitrarily long periods.  Absence itself is not
    # terminal evidence.
    for _ in range(500):
        end.observe_screen("unknown")

    assert not end.confirmed
    assert end.not_gameplay_streak == 0
    assert end.agency_failures == 0


def test_failed_agency_alone_can_never_confirm_game_over():
    end = EpisodeEndObserver()

    for _ in range(20):
        end.observe_agency(False)

    assert end.agency_failures == 20
    assert not end.confirmed


def test_not_gameplay_alone_is_not_enough():
    end = EpisodeEndObserver(required_not_gameplay=8)

    for _ in range(20):
        end.observe_screen("not_gameplay")

    assert end.not_gameplay_streak == 20
    assert not end.confirmed


def test_single_not_gameplay_frame_is_not_enough():
    end = EpisodeEndObserver(required_not_gameplay=8)

    end.observe_agency(False)
    end.observe_screen("not_gameplay")

    assert not end.confirmed


def test_unknown_breaks_not_gameplay_streak():
    end = EpisodeEndObserver(required_not_gameplay=8)

    for _ in range(7):
        end.observe_screen("not_gameplay")

    end.observe_screen("unknown")
    end.observe_agency(False)

    assert end.not_gameplay_streak == 0
    assert not end.confirmed


def test_gameplay_breaks_not_gameplay_streak():
    end = EpisodeEndObserver(required_not_gameplay=8)

    for _ in range(7):
        end.observe_screen("not_gameplay")

    end.observe_screen("gameplay")
    end.observe_agency(False)

    assert end.not_gameplay_streak == 0
    assert not end.confirmed


def test_persistent_not_gameplay_plus_failed_agency_confirms():
    end = EpisodeEndObserver(required_not_gameplay=8)

    end.observe_agency(False)

    for _ in range(7):
        end.observe_screen("not_gameplay")
        assert not end.confirmed

    end.observe_screen("not_gameplay")

    assert end.confirmed


def test_confirmed_agency_clears_failed_agency_evidence():
    end = EpisodeEndObserver(required_not_gameplay=8)

    end.observe_agency(False)
    for _ in range(8):
        end.observe_screen("not_gameplay")

    assert end.confirmed

    end.observe_agency(True)

    assert end.agency_failures == 0
    assert not end.confirmed


def test_self_reacquisition_clears_all_terminal_suspicion():
    end = EpisodeEndObserver(required_not_gameplay=8)

    end.observe_agency(False)
    for _ in range(8):
        end.observe_screen("not_gameplay")

    assert end.confirmed

    end.self_reacquired()

    assert end.not_gameplay_streak == 0
    assert end.agency_failures == 0
    assert not end.confirmed

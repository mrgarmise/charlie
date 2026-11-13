from dataclasses import replace

import pytest

from experiments.ppal.reserve_life_evidence import ReserveObservation, reserve_support


def pair(a=1, b=0):
    first = ReserveObservation('game-1', 'P1', 'one', 'a' * 64, 10., a, True, True)
    return first, replace(first, observation_id='two', source_sha256='b' * 64,
                          timestamp=11., count=b)


def test_final_active_life_is_never_terminal_or_self_or_restart_authority():
    result = reserve_support(*pair(), max_gap=2)
    assert result['reserve_delta'] == -1
    assert result['final_active_life_possible']
    assert not any(result[k] for k in ('game_over', 'self_confirmed', 'restart_authorized'))


@pytest.mark.parametrize('changes', [dict(hud_visible=False), dict(reviewed=False),
    dict(count=None), dict(episode='game-2'), dict(channel='P2'), dict(timestamp=10.),
    dict(timestamp=15.), dict(source_sha256='a'*64), dict(observation_id='one')])
def test_missing_mixed_stale_and_duplicate_evidence_abstains(changes):
    before, after = pair()
    assert reserve_support(before, replace(after, **changes), max_gap=2)['status'] == 'unknown'


@pytest.mark.parametrize('a,b,label', [(0,0,'unchanged_reserves'),
    (0,1,'reserve_increase_possible_bonus_or_new_game'),
    (3,0,'multiple_losses_or_discontinuity')])
def test_other_changes_remain_ambiguous(a,b,label):
    result = reserve_support(*pair(a,b), max_gap=2)
    assert result['support'] == label
    assert not result['game_over']


@pytest.mark.parametrize('changes', [dict(count=True), dict(count=-1),
    dict(timestamp=float('nan')), dict(timestamp=True), dict(source_sha256=''),
    dict(reviewed=1)])
def test_malformed_review_is_rejected(changes):
    before, _ = pair()
    with pytest.raises(ValueError):
        replace(before, **changes)

"""Controlled trajectory experiments, including confounds and identity loss."""
import pytest
from experiments.ppal.agency import AgencyTracker
from experiments.ppal.robotron_agency import VisualAgency
from experiments.ppal.eyes.detectors import Detection

SEQ = [(1, 0), (0, 0), (-1, 0), (0, 0), (0, 1), (0, 0)]


def experiment(agency=None, follower=None, ids=(1, 2), sequence=SEQ):
    a = agency or AgencyTracker()
    positions = {ids[0]: (20., 20.), ids[1]: (70., 70.)}
    a.observe(positions)
    previous = (0, 0)
    snapshots = []
    for u in sequence:
        p = positions[ids[0]]
        positions[ids[0]] = (p[0]+u[0], p[1]+u[1])
        v = follower(u, previous) if follower else (0, 0)
        p = positions[ids[1]]
        positions[ids[1]] = (p[0]+v[0], p[1]+v[1])
        snapshots.append(a.observe(positions, u))
        previous = u
    return a, positions, snapshots


def test_repeated_motion_stops_and_reversal_identify_self():
    a, _, rows = experiment()
    assert all(row['self_track_id'] is None for row in rows[:4])
    assert a.self_id == 1
    assert a.beliefs[1].reversed
    assert a.beliefs[1].stops == 3


@pytest.mark.parametrize('wrong_kind', ['player', 'unknown'])
def test_appearance_and_center_do_not_admit_or_rank_candidates(wrong_kind):
    visual = VisualAgency()
    points = {1: (20.,20.), 2: (50.,50.)}
    def pairs():
        return [(Detection('unknown' if i == 1 else wrong_kind, p, (1,1,10,20), 100),
                 {'class_scores': {'player': .01 if i == 1 else .99}}) for i,p in points.items()]
    visual.observe(pairs())
    for u in SEQ:
        x,y = points[1]; points[1] = (x+u[0],y+u[1])
        visual.observe(pairs(), {(1,0):'E',(-1,0):'W',(0,1):'S',(0,0):'STAY'}[u])
    assert visual.player == points[1]


def test_one_coincidental_response_does_not_commit():
    a, _, _ = experiment(sequence=[(1,0)], follower=lambda u,p:u)
    assert a.self_id is None


def test_multiple_identical_responses_remain_ambiguous():
    a, _, _ = experiment(follower=lambda u,p:u)
    assert a.self_id is None
    assert a.last_snapshot['runner_up_confidence'] == a.last_snapshot['confidence']


def test_delayed_pursuer_loses_to_direct_self():
    a, _, rows = experiment(follower=lambda u,p:p)
    assert a.self_id == 1
    assert a.beliefs[2].contradictions >= 3
    assert a.beliefs[2].indirect_score > 0
    assert any(e['reason'] == 'continued_during_neutral' for row in rows for e in row['evidence'])


def test_matching_motion_but_continuing_during_neutral_is_not_self():
    a, _, _ = experiment(follower=lambda u,p:u if any(u) else p)
    assert a.self_id == 1
    assert a.beliefs[2].stops == 0


def test_mine_never_accumulates_identity_from_stillness():
    a, _, _ = experiment()
    assert a.beliefs[2].hits == 0
    assert a.beliefs[2].confidence == 0


def test_brief_occlusion_keeps_belief_but_not_stale_location():
    a, positions, _ = experiment()
    confidence = a.beliefs[1].confidence
    a.observe({2:positions[2]})
    assert a.self_id == 1
    assert a.beliefs[1].confidence == confidence
    # No displacement may be inferred through the unobserved gap.
    row = a.observe({1:(90,90),2:positions[2]}, (1,0))
    assert not any(e['track_id'] == 1 for e in row['evidence'])


def test_sustained_disappearance_collapses_identity():
    a, positions, _ = experiment()
    for _ in range(4): a.observe({2:positions[2]})
    assert a.self_id is None


def test_explicit_death_reset_clears_all_evidence():
    a, _, _ = experiment()
    a.reset()
    assert a.self_id is None and not a.beliefs and not a.previous


def test_respawn_elsewhere_can_earn_new_identity():
    a, _, _ = experiment()
    a.reset()
    a, _, _ = experiment(a, ids=(31,8))
    assert a.self_id == 31


def test_fresh_track_lineage_requires_fresh_causal_evidence():
    a, positions, _ = experiment()
    for _ in range(4): a.observe({2:positions[2],31:(21,21)})
    assert a.self_id is None
    a, _, _ = experiment(a, ids=(31,2))
    assert a.self_id == 31


def test_reversal_is_required_before_identity():
    a, _, _ = experiment(sequence=[(1,0),(0,0),(0,1),(0,0),(1,0),(0,0)]*3)
    assert a.self_id is None
    assert not a.beliefs[1].reversed


def test_no_reliable_response_returns_unknown():
    a=AgencyTracker(); p={1:(10,10),2:(80,80)}; a.observe(p)
    for u in SEQ*3: a.observe(p,u)
    assert a.self_id is None


@pytest.mark.parametrize('offset', [(1,0),(.7,.7),(-1,0)])
def test_global_motion_does_not_create_arbitrary_self(offset):
    a=AgencyTracker(); p={i:(i*20.,i*20.) for i in range(1,5)}; a.observe(p)
    for u in SEQ*3:
        p={i:(v[0]+offset[0],v[1]+offset[1]) for i,v in p.items()}
        row=a.observe(p,u)
        assert row['global_motion'] and a.self_id is None


def test_normal_gameplay_reinforces_existing_identity():
    a,p,_=experiment(); old=a.beliefs[1].confidence
    p[1]=(p[1][0]+1,p[1][1]); row=a.observe(p,(1,0))
    assert a.self_id == 1 and a.beliefs[1].confidence > old
    assert row['evidence'][0]['reason'] == 'signed_command_response'


def test_contradictory_gameplay_triggers_reacquisition():
    a,p,_=experiment()
    for _ in range(3):
        p[1]=(p[1][0]-1,p[1][1]); a.observe(p,(1,0))
    assert a.self_id is None
    assert a.beliefs[1].contradictions >= 3


def test_single_blocked_command_does_not_erase_prior_identity():
    a,p,_=experiment(sequence=SEQ+[(0,-1),(0,0)])
    a.observe(p,(1,0))
    assert a.self_id == 1


def test_unknown_control_interval_is_not_neutral():
    a,p,_=experiment(); old=a.beliefs[1].confidence
    a.observe(p,None)
    assert a.beliefs[1].confidence == old


def test_motion_toward_known_self_logs_indirect_evidence():
    a,p,_=experiment()
    p[1]=(p[1][0]+1,p[1][1]); p[2]=(p[2][0]-1,p[2][1]-1)
    a.observe(p,(1,0))
    assert a.beliefs[2].indirect_score > 0


def test_crossing_creates_new_track_and_abstains():
    v=VisualAgency()
    def pairs(points): return [(Detection('unknown',p,(1,1,10,20),100),{}) for p in points]
    v.observe(pairs([(40,50),(42,50)]))
    old=set(v.positions)
    v.observe(pairs([(41,50)]),'E')
    assert not old.intersection(v.positions)
    assert v.player is None


def test_global_motion_after_acquisition_revokes_control_permission():
    a,p,_=experiment()
    p[3]=(40,80); a.observe(p)
    p={i:(v[0]+1,v[1]) for i,v in p.items()}
    row=a.observe(p,(1,0))
    assert row['global_motion'] and a.self_id is None


def test_adapter_discovers_unknown_sprite_with_bounded_neutral_probes():
    from experiments.ppal.robotron_agency import VECTORS
    from experiments.ppal.models import Action
    points={1:(20.,20.),2:(70.,70.)}; commands=[]; snapshots=[]
    def read():
        return [(Detection('unknown',p,(1,1,10,20),100),{}) for p in points.values()]
    class Controller:
        def execute(self,action,ms):
            assert action.fire == 'NONE' and ms == 60
            commands.append(action.move)
            u=VECTORS[action.move]; p=points[1]; points[1]=(p[0]+u[0],p[1]+u[1])
    v=VisualAgency()
    assert v.discover(read,Controller(),record=snapshots.append) == points[1]
    assert commands == ['E','STAY','W','STAY','S','STAY']
    assert snapshots[-1]['self_track_id'] is not None
    assert snapshots[-1]['latency_seconds'] is None


def test_adapter_no_candidates_does_not_send_blind_commands():
    from unittest.mock import Mock
    controller=Mock(); v=VisualAgency()
    assert v.discover(lambda:[],controller) is None
    controller.execute.assert_not_called()


def test_adapter_ambiguous_candidates_exhausts_bounded_probes():
    from experiments.ppal.robotron_agency import VECTORS
    points=[(20.,20.),(70.,70.)]; commands=[]
    def read(): return [(Detection('unknown',p,(1,1,10,20),100),{}) for p in points]
    class Controller:
        def execute(self,action,ms):
            commands.append(action.move); u=VECTORS[action.move]
            points[:]=[(p[0]+u[0],p[1]+u[1]) for p in points]
    v=VisualAgency()
    assert v.discover(read,Controller()) is None
    assert len(commands) == 12


def test_adapter_deadline_prevents_new_probe():
    from unittest.mock import Mock
    controller=Mock(); v=VisualAgency()
    pairs=[(Detection('unknown',(20,20),(1,1,10,20),100),{})]
    assert v.discover(lambda:pairs,controller,deadline=0) is None
    controller.execute.assert_not_called()


def test_neutral_alone_cannot_resurrect_discredited_identity():
    a,p,_=experiment()
    for _ in range(3):
        p[1]=(p[1][0]-1,p[1][1]); a.observe(p,(1,0))
    for _ in range(30): a.observe(p,(0,0))
    assert a.self_id is None


def test_new_lineage_is_reported_as_reacquisition():
    a,p,_=experiment()
    for _ in range(4): a.observe({2:p[2]})
    a,_,rows=experiment(a,ids=(31,2))
    assert any(row['event']=='reacquired' for row in rows)

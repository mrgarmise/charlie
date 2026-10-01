import json
import pytest
from experiments.ppal.marathon_robotron import safe_to_restart
from experiments.ppal.learning_review import review_session
from experiments.ppal.performance_ledger import append_record
from experiments.ppal.eyes.tracking import SpriteTracker
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.shadow_predictor import ShadowPredictor
from experiments.ppal.models import WorldState, Position
from experiments.ppal.evaluate_robotron_shadow import evaluate


def test_no_restart_on_tracking_loss_or_error():
    for result in ('TIME LIMIT','NOT_GAMEPLAY: control challenge failed','UNCERTAIN','INTERRUPTED'):
        assert not safe_to_restart({'result':result,'armed':True,'acquisition':'x','steps':[{'action':{}}]})
    report={'result':'GAME OVER','episode_end':{'state':'game_over','confirmed':True,
        'evidence':{'rule':'persistent_not_gameplay_plus_no_controlled_self',
                    'not_gameplay_streak':8,'agency_failures':1,'screen':{'state':'not_gameplay','phase':'terminal'}}}}
    assert safe_to_restart(report)
    assert not safe_to_restart(report,1)
    report['episode_end']['evidence']=None
    assert not safe_to_restart(report)


def test_ambiguous_crossing_does_not_reuse_old_identity():
    t=SpriteTracker()
    def det(x):return Detection('unknown',(x,50),(1,1,10,20),100)
    first=t.update(0,[det(40),det(42)])
    second=t.update(1,[det(41)])
    assert second[0] not in first.values()


def test_seconds_predictor_uses_elapsed_time():
    p=ShadowPredictor(horizon_seconds=.2,max_speed=100)
    p.observe(WorldState(0,Position(10,10),(),()),1.)
    w=WorldState(1,Position(12,10),(),())
    p.observe(w,1.1)
    assert p.project(w).player.x == pytest.approx(16.)
    with pytest.raises(ValueError):p.observe(w,1.1)


def test_prediction_rejects_wrong_horizon_and_self_switch():
    def step(t,id=1):return {'tick':t,'self_track_id':id,'shadow':{'prediction':{'horizon_ticks':2,'player_predicted':[1,1],'player_now':[0,0]}}}
    assert evaluate({'steps':[step(0),step(1)]})['all']['n']==0
    a,b=step(0),step(1,2)
    a['shadow']['prediction']['horizon_ticks']=1
    assert evaluate({'steps':[a,b]})['all']['n']==0


def test_review_groups_questions_without_awarding_learning(tmp_path):
    games=[]
    for n in range(2):
        p=tmp_path/str(n);p.mkdir();(p/'report.json').write_text(json.dumps({'armed':True,'steps':[{'status':'reacquiring'}]}));games.append({'path':str(p)})
    r=review_session(tmp_path/'review',games)
    assert len(r['questions'])==3
    assert all(len(q['examples'])==2 for q in r['questions'])
    assert not any(e['eligible_for_score_comparison'] for e in r['episodes'])


def test_score_rejects_invalid_and_marks_partial_run(tmp_path):
    p=tmp_path/'report.json';p.write_text('{}')
    for score in (-1,True,3.5):
        with pytest.raises(ValueError):append_record(tmp_path/'ledger',p,score)
    record=append_record(tmp_path/'ledger',p,600)
    assert record['score']==600
    assert not record['episode_complete']
    assert record['score_source']=='human_reported'


def test_control_challenge_requires_three_hits_to_confirm(monkeypatch):
    from experiments.ppal import play_robotron as play
    from unittest.mock import Mock
    monkeypatch.setattr(play, '_quick_frames', lambda *a, **k: [[]])
    monkeypatch.setattr(play, '_appearance_bootstrap', lambda frames: (50, 50))
    answers = iter([(51, 50), (51, 51), (50, 51)])
    monkeypatch.setattr(play, '_causal_bootstrap',
                        lambda *a, **k: next(answers))
    controller = Mock()

    r = play._control_challenge(
        None, None, None, controller, initial_frames=[[]])

    assert r['eligible']
    assert r['confirmed']
    assert not r['rejected']
    assert r['hits'] == 3
    assert r['failures'] == 0
    assert r['attempts'] == 3
    assert controller.execute.call_count == 3


def test_control_challenge_two_failures_reject_self(monkeypatch):
    from experiments.ppal import play_robotron as play
    from unittest.mock import Mock
    monkeypatch.setattr(play, '_quick_frames', lambda *a, **k: [[]])
    monkeypatch.setattr(play, '_appearance_bootstrap', lambda frames: (50, 50))
    answers = iter([None, None, (50, 51)])
    monkeypatch.setattr(play, '_causal_bootstrap',
                        lambda *a, **k: next(answers))
    controller = Mock()

    r = play._control_challenge(
        None, None, None, controller, initial_frames=[[]])

    assert r['eligible']
    assert not r['confirmed']
    assert r['rejected']
    assert r['hits'] == 1
    assert r['failures'] == 2
    assert r['attempts'] == 3
    assert controller.execute.call_count == 3


def test_control_challenge_one_failure_is_inconclusive(monkeypatch):
    from experiments.ppal import play_robotron as play
    from unittest.mock import Mock
    monkeypatch.setattr(play, '_quick_frames', lambda *a, **k: [[]])
    monkeypatch.setattr(play, '_appearance_bootstrap', lambda frames: (50, 50))
    answers = iter([(51, 50), None, (50, 51)])
    monkeypatch.setattr(play, '_causal_bootstrap',
                        lambda *a, **k: next(answers))
    controller = Mock()

    r = play._control_challenge(
        None, None, None, controller, initial_frames=[[]])

    assert r['eligible']
    assert not r['confirmed']
    assert not r['rejected']
    assert r['hits'] == 2
    assert r['failures'] == 1
    assert r['attempts'] == 3
    assert controller.execute.call_count == 3

def test_control_challenge_sends_nothing_without_plausible_self(monkeypatch):
    from experiments.ppal import play_robotron as play
    from unittest.mock import Mock
    monkeypatch.setattr(play,'_appearance_bootstrap',lambda frames:None)
    controller=Mock()

    r=play._control_challenge(None,None,None,controller,initial_frames=[[]])

    assert not r['eligible']
    assert not r['confirmed']
    assert r['attempts']==0
    assert r['hits']==0
    assert r['player'] is None
    assert r['evidence']==[]
    controller.execute.assert_not_called()


def test_causal_match_requires_after_player_evidence():
    from experiments.ppal.play_robotron import _causal_bootstrap
    before=Detection('unknown',(50,50),(1,1,10,20),100)
    after=Detection('unknown',(51,50),(1,1,10,20),100)
    b=[[(before,{'class_scores':{'player':.9,'mine':.1}})]]
    a=[[(after,{'class_scores':{'player':.1,'mine':.1}})]]
    assert _causal_bootstrap(b,a) is None

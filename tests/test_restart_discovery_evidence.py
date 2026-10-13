"""Synthetic boundary/probe evidence: never authentic Robotron acceptance."""
import copy
import pytest
from experiments.ppal.episode_end import EpisodeEndObserver
from experiments.ppal.robotron_agency import VisualAgency
from experiments.ppal.marathon_robotron import safe_to_restart


def negative():
    return dict(schema='causal-discovery-result-v1',complete=True,confirmed_self=False,
                commands=['E','STAY','W','STAY','S','STAY','N','STAY'],
                capture_timestamps=list(map(float,range(1,10))))


def frame(end,at,phase='unknown',reason='unrecognized_striped_page'):
    end.observe_phase(dict(capture_timestamp=float(at),state='not_gameplay',phase=phase,reason=reason))


def test_unrecognized_stripes_accumulate_but_never_authorize_restart():
    end=EpisodeEndObserver();end.observe_phase(dict(capture_timestamp=0.,state='gameplay',phase='gameplay'))
    assert end.observe_discovery(negative())
    for at in range(10,20):frame(end,at)
    assert end.not_gameplay_streak==10 and not end.confirmed
    frame(end,20,'startable');frame(end,21,'startable')
    assert not end.confirmed  # a heading glimpsed twice is insufficient
    frame(end,22,'startable')
    assert end.confirmed
    report=dict(result='GAME OVER',episode_end=dict(state='game_over',confirmed=True,
                evidence=end.evidence(screen=dict(state='not_gameplay',phase='startable'),self_lost_frames=99)))
    assert safe_to_restart(report)
    report['episode_end']['evidence']['screen']['phase']='unknown'
    assert not safe_to_restart(report)


@pytest.mark.parametrize('change',[{'complete':False},{'confirmed_self':True},{'commands':['E','STAY']},
    {'capture_timestamps':[1.]*9},{'capture_timestamps':[float('nan')]*9},{'schema':'made-up'}])
def test_incomplete_invalid_or_positive_probes_never_become_negative_evidence(change):
    end=EpisodeEndObserver();result=negative();result.update(change)
    assert not end.observe_discovery(result) and end.agency_failures==0


def test_duplicate_probe_receipt_is_not_independent_failure():
    end=EpisodeEndObserver();assert end.observe_discovery(negative())
    assert not end.observe_discovery(copy.deepcopy(negative()))
    assert end.agency_failures==1


def test_death_respawn_and_attract_demo_cannot_be_ended_by_no_self_budget():
    end=EpisodeEndObserver();assert end.observe_discovery(negative())
    for at in range(10,500):end.observe_phase(dict(capture_timestamp=float(at),state='gameplay',phase='gameplay'))
    assert not end.confirmed
    end.self_reacquired();assert end.agency_failures==0 and end.discovery_evidence is None


def test_empty_regions_still_produce_a_qualified_bounded_probe_receipt():
    agency=VisualAgency();clock=[0.];commands=[]
    def read():clock[0]+=1.;return []
    class Controller:
        def execute(self,action,ms):commands.append(action.move)
    assert agency.discover(read,Controller(),observation_time=lambda:clock[0]) is None
    assert len(commands)==12 and EpisodeEndObserver().observe_discovery(agency.last_discovery)


def test_autonomous_attract_sprite_never_becomes_causal_self():
    from experiments.ppal.eyes.detectors import Detection
    agency=VisualAgency();clock=[0.]
    def read():
        clock[0]+=1.
        return [(Detection('player',(clock[0],20.),(1,1,4,4),16),{})]
    class Controller:
        def execute(self,*args):pass  # demonstration ignores the controller
    assert agency.discover(read,Controller(),observation_time=lambda:clock[0]) is None
    assert agency.agency.self_id is None
    assert EpisodeEndObserver().observe_discovery(agency.last_discovery)


def test_qualified_boundary_progresses_to_game_two_and_three_before_offline_handoff(tmp_path,monkeypatch):
    import json
    from pathlib import Path
    from experiments.ppal import marathon_robotron as marathon
    from test_marathon_deferred import args,prepare
    from test_experiment_return import gateway
    from test_learning_projects import synthetic_game
    from test_recording_handoff import seal_software_recording
    a=args(tmp_path);g=gateway(tmp_path);prepare(tmp_path,a,g);played=[]
    def reflect(session,*v,**kw):
        assert len(played)==3
        return {'phase':'checkpointed','simulation':True}
    monkeypatch.setattr(marathon,'reflect_marathon',reflect)
    def driver(cmd,*v):
        assert '--arm' in cmd
        game=Path(cmd[cmd.index('--output')+1])
        plan=json.loads(Path(cmd[cmd.index('--experiment-plan')+1]).read_text())
        synthetic_game(game,plan)
        end=EpisodeEndObserver();end.observe_phase(dict(capture_timestamp=0.,state='gameplay',phase='gameplay'))
        assert end.observe_discovery(negative())
        for at in range(10,18):frame(end,at)
        for at in range(18,21):frame(end,at,'startable')
        report=json.loads((game/'report.json').read_text())
        report['result']='GAME OVER'
        report['episode_end']=dict(state='game_over',confirmed=end.confirmed,
            evidence=end.evidence(screen=dict(state='not_gameplay',phase='startable'),self_lost_frames=100))
        (game/'report.json').write_text(json.dumps(report))
        seal_software_recording(game)
        assert safe_to_restart(report,capture_root=game)
        played.append(game)
        return 0
    doc=marathon.developmental_marathon(a,driver=driver,gateway=g)
    assert len(played)==3 and len(set(played))==3
    assert doc['status']=='bounded_attempts_complete'

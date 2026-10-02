"""Startup must finish before START; incomplete recovery is not terminal evidence."""
import json
import sys
import pytest
from PIL import Image


def test_failed_prestart_calibration_never_constructs_controller(monkeypatch,tmp_path):
    from experiments.ppal import play_robotron as play
    closed=[]
    class Source:
        def read(self):return Image.new('RGB',(100,100))
        def close(self):closed.append('camera')
    monkeypatch.setattr(play,'PiCameraSource',Source)
    monkeypatch.setattr(play.TaughtRecognizer,'load',lambda *a:object())
    monkeypatch.setattr(play.time,'sleep',lambda *a:None)
    monkeypatch.setattr(play,'optimize_screen_exposure',lambda *a:{'status':'mock'})
    def prepare(*a,**kw):
        assert kw['require_uniform_border'] is False
        raise ValueError('no stable geometry')
    monkeypatch.setattr(play,'prepare',prepare)
    def controller(*a,**kw):pytest.fail('No controller or START before successful geometry')
    monkeypatch.setattr(play,'ArcadeController',controller)
    monkeypatch.setattr(sys,'argv',['play','--arm','--supervised-child','--recalibrate','--output',str(tmp_path/'run')])
    with pytest.raises(ValueError,match='no stable geometry'):play.main()
    report=json.loads((tmp_path/'run/report.json').read_text())
    assert 'start_requested' not in report['session_timing']
    assert not report['episode_end']['confirmed'] and not report['steps']
    assert report['session_transitions'][-1]['new']=='stopped'
    assert closed==['camera']


def test_recovery_frame_collection_stops_scheduling_at_deadline(monkeypatch):
    from experiments.ppal import play_robotron as play
    clock=[0.];calls=[]
    class Source:
        def read(self):
            calls.append(clock[0]);clock[0]+=.6
            return Image.new('RGB',(1,1))
    class Calibration:
        def apply(self,f):return f
    class Recognizer:
        def detect(self,f):return []
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(play.time,'sleep',lambda d:None)
    frames=play._quick_frames(Source(),Calibration(),Recognizer(),count=10,interval=0,deadline=1.)
    assert len(frames)==2 and all(t<1. for t in calls)


def test_partial_control_challenge_does_not_count_failure(monkeypatch):
    from experiments.ppal import play_robotron as play
    clock=[0.];actions=[]
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(play,'_appearance_bootstrap',lambda frames:(50.,50.))
    def frames(*a,**kw):clock[0]=2.;return [[]]
    monkeypatch.setattr(play,'_quick_frames',frames)
    class Controller:
        def execute(self,*a):actions.append(a)
    r=play._control_challenge(None,None,None,Controller(),initial_frames=[[]],deadline=1.)
    assert len(actions)==1 and r['attempts']==0 and not r['rejected'] and not r['eligible']


@pytest.mark.parametrize('mutation',[
    {'result':'TIME LIMIT'}, {'result':'INTERRUPTED'},
    {'rule':'established_gameplay_plus_eligible_failed_agency'},
    {'not_gameplay_streak':7}, {'agency_failures':0}, {'screen':{'state':'unknown'}},
    {'screen':{'state':'gameplay'}}])
def test_restart_requires_independent_current_terminal_evidence(mutation):
    from experiments.ppal.marathon_robotron import safe_to_restart
    evidence={'rule':'persistent_not_gameplay_plus_no_controlled_self',
              'not_gameplay_streak':8,'agency_failures':1,'screen':{'state':'not_gameplay','phase':'terminal'}}
    report={'result':'GAME OVER','episode_end':{'state':'game_over','confirmed':True,'evidence':evidence}}
    assert safe_to_restart(report)
    if 'result' in mutation:report.update(mutation)
    else:evidence.update(mutation)
    assert not safe_to_restart(report)

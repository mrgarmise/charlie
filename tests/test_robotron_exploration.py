import json, hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image, ImageDraw
from experiments.ppal import play_robotron as play
from experiments.ppal.forebrain import Forebrain
from experiments.ppal.episode_end import EpisodeEndObserver
from experiments.ppal.controller_sandbox import ControllerSandbox

ROOT=Path(__file__).parent/'fixtures/robotron-failed-start-031501'

class Recorder:
    def __init__(self):self.rows=[]
    def event(self,kind,payload,*,at):
        self.rows.append((kind,payload));return 'record:'+str(len(self.rows))


def test_original_unknown_capture_can_be_explored_without_relabeling(monkeypatch):
    raw=Image.open(ROOT/'start-decision-000.png').convert('RGB')
    report=json.loads((ROOT/'original-report.json').read_text())
    from experiments.ppal.eyes.calibration import Calibration
    c=Calibration(tuple(tuple(p) for p in report['calibration']['corners']))
    clock=[0.];commands=[]
    class Source:
        def read(self):clock[0]+=.1;self.timestamp=clock[0];return raw
    class Controller:
        def _command(self,x):commands.append(x)
        def execute(self,a,n):commands.append(a)
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    r=Recorder();result=play._explore_startup(Source(),c,Controller(),Forebrain(),r,timeout=3,max_actions=3)
    assert commands and not result['gameplay_verified']
    assert all(p['screen']['phase']=='unknown' for k,p in r.rows if k=='exploratory_prediction')
    assert result['request']
    assert hashlib.sha256((ROOT/'start-decision-000.png').read_bytes()).hexdigest()==json.loads((ROOT/'provenance.json').read_text())['sha256']


def test_startup_sequence_discovered_by_options_and_observations(monkeypatch):
    clock=[0.];pressed=[];credit=[False];playing=[False]
    class Source:
        def read(self):clock[0]+=.1;self.timestamp=clock[0];return Image.new('RGB',(64,48),'white' if playing[0] else 'gray' if credit[0] else 'black')
    class Controller:
        def _command(self,x):
            pressed.append(x)
            if x=='BACK':credit[0]=True
            if x=='START' and credit[0]:playing[0]=True
        def execute(self,*a):pytest.fail('restricted fixture vocabulary uses buttons')
    class Brain(Forebrain):
        def exploratory_action(self,screen,controls=None):
            # START is deliberately first: the first hypothesis fails. The
            # changed credit context then permits revisiting START.
            return super().exploratory_action(screen,('START','BACK'))
    classify=lambda frame:{'phase':'gameplay' if playing[0] else 'unknown','state':'gameplay' if playing[0] else 'unknown'}
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    recorder=Recorder();brain=Brain()
    r=play._explore_startup(Source(),SimpleNamespace(apply=lambda f:f),Controller(),brain,recorder,
                            timeout=5,max_actions=8,classifier=classify)
    assert pressed==['START','BACK','START'] and r['gameplay_verified']
    assert brain.exploration_history[0]['result']=='inconclusive'
    assert brain.exploration_history[-1]['screen']['phase']=='gameplay'
    assert brain.exploration_history[-1]['proposed_sequence']==[['START'],['BACK'],['START']]
    assert len([r for r in recorder.rows if r[0]=='exploratory_prediction'])==3


def test_title_requires_operator_declaration_and_real_match(tmp_path):
    from experiments.ppal.robotron_screen_state import TaughtTitleReference
    image=Image.new('RGB',(64,48));ImageDraw.Draw(image).rectangle((8,8,56,30),outline='white',width=3)
    path=tmp_path/'title.png';image.save(path)
    d=dict(schema='charlie-title-reference-v1',verified_by='operator',image='title.png',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),roi=[0,0,1,1])
    declaration=tmp_path/'title.json';declaration.write_text(json.dumps(d));ref=TaughtTitleReference(declaration)
    assert ref.classify(image)['phase']=='title'
    assert ref.classify(Image.new('RGB',(64,48)))['phase']!='title'
    d['verified_by']='Charlie inferred';declaration.write_text(json.dumps(d))
    with pytest.raises(ValueError):TaughtTitleReference(declaration)


def test_title_after_established_gameplay_confirms_boundary_not_score():
    o=EpisodeEndObserver(required_not_gameplay=3)
    title=dict(phase='title',state='not_gameplay',title_reference=dict(matched=True,sha256='source-hash'))
    for n in range(3):o.observe_phase(dict(title,capture_timestamp=n+1))
    assert not o.confirmed # pregame without prior gameplay cannot end a game
    o.observe_phase(dict(phase='gameplay',state='gameplay',capture_timestamp=4))
    o.observe_phase(dict(phase='unknown',state='unknown',capture_timestamp=5))
    for n in range(3):o.observe_phase(dict(title,capture_timestamp=n+6))
    assert o.visual_boundary
    e=o.evidence(screen=title,self_lost_frames=0)
    assert e['rule']=='established_gameplay_then_verified_title' and 'score' not in e


def test_repeated_or_unverified_title_frames_never_make_boundary():
    o=EpisodeEndObserver(required_not_gameplay=3)
    o.observe_phase(dict(phase='gameplay',state='gameplay',capture_timestamp=1))
    for n in range(5):o.observe_phase(dict(phase='title',state='not_gameplay',capture_timestamp=2))
    assert not o.confirmed

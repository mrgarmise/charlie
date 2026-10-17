"""Controllerless fixtures verify lifecycle; none qualify native gameplay."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image,ImageDraw
from experiments.ppal.camera_session import CameraSession
from experiments.ppal.cal_recovery import request_recovery
from experiments.ppal.live_view import LiveViewMonitor
from experiments.ppal.game_evidence import preserve_game
from memory.evidence import EvidenceJournal


@pytest.mark.parametrize('stop',[None,RuntimeError,KeyboardInterrupt])
def test_one_live_camera_one_preflight_cleanup_and_fresh_next_marathon(tmp_path,stop):
    events=[]
    class Camera:
        def close(self):events.append('close')
    def factory():events.append('open');return Camera()
    calibration=object()
    def preflight(source,output,**kw):
        assert kw['seed_position'] is None
        events.append('preflight');return calibration,{'status':'usable'}
    first=CameraSession(factory)
    try:
        for index in range(3):
            borrower=first.borrow()
            c,r=first.establish(borrower,tmp_path,preflight)
            assert c is calibration and r['camera_session']['reused']==(index>0)
            borrower.close()
            assert events.count('close')==0
            if stop and index==1:raise stop()
    except (RuntimeError,KeyboardInterrupt):pass
    finally:first.close();first.close()
    assert events==['open','preflight','close']
    second=CameraSession(factory)
    second.establish(second.borrow(),tmp_path,preflight)
    second.close()
    assert first.id!=second.id and events==['open','preflight','close']*2
    with pytest.raises(RuntimeError):first.borrow()


def test_invalid_camera_cannot_be_reused_and_cal_has_no_authority(tmp_path):
    owner=CameraSession(lambda:SimpleNamespace(close=lambda:None))
    owner.borrow();owner.invalid=True
    with pytest.raises(RuntimeError):owner.borrow()
    result=request_recovery(episode=tmp_path,symptoms={'capture_failure':'disconnected'},camera_session=owner.id)
    assert result['status']=='unavailable' and result['request']['physical_authorization'] is False
    assert 'symptoms' in result['request'] and 'hypotheses' in result['request']
    owner.close()


def test_transition_occlusion_and_duplicate_frame_do_not_trigger_cal():
    reference=Image.new('RGB',(100,100),'black')
    ImageDraw.Draw(reference).rectangle((0,0,99,99),outline='white',width=3)
    monitor=LiveViewMonitor(reference)
    black=Image.new('RGB',(100,100),'black')
    for stamp in range(30):
        assert monitor.observe(black,{'state':'not_gameplay','phase':'unknown'},stamp) is None
    assert monitor.observe(black,{'state':'gameplay'},31) is None
    for _ in range(10):assert monitor.observe(black,{'state':'gameplay'},31) is None
    assert monitor.observe(reference,{'state':'gameplay'},32) is None
    assert monitor.observe(black,{'state':'gameplay'},33) is None
    assert monitor.observe(black,{'state':'gameplay'},34) is None
    failure=monitor.observe(black,{'state':'gameplay'},35)
    assert failure and 'unqualified' in failure['inference']


def completed(root):
    from test_recording_handoff import seal_software_recording
    root.mkdir()
    report=dict(armed=True,acquisition='simulated_causal_identity',steps=[{'action':{'move':'E'}}],
        result='GAME OVER',score_summary={'status':'unmeasured','self_score':None},
        provenance={'simulation':True},episode_end=dict(state='game_over',confirmed=True,evidence=dict(
            rule='persistent_not_gameplay_plus_no_controlled_self',agency_failures=1,
            not_gameplay_streak=8,screen={'state':'not_gameplay','phase':'startable'})))
    (root/'report.json').write_text(json.dumps(report));seal_software_recording(root)
    return json.loads((root/'report.json').read_text())


def test_durable_earlier_complete_game_survives_invalid_and_incomplete(tmp_path):
    journal=EvidenceJournal(tmp_path/'development/game-evidence.sqlite3')
    first=tmp_path/'game-01';report=completed(first)
    one=preserve_game(journal,first,marathon=tmp_path,returncode=0,report=report)
    assert one['classification']=='completed'
    assert preserve_game(journal,first,marathon=tmp_path,returncode=0,report=report)['record_id']==one['record_id']
    second=tmp_path/'game-02';second.mkdir()
    two=preserve_game(journal,second,marathon=tmp_path,returncode=1,report={'cal_recovery':request_recovery(episode=second,symptoms={'capture':'failed'})})
    assert two['classification']=='invalid'
    third=tmp_path/'game-03';third.mkdir()
    three=preserve_game(journal,third,marathon=tmp_path,returncode=130,report=None)
    assert three['classification']=='incomplete_unverified'
    journal.close()
    journal=EvidenceJournal(tmp_path/'development/game-evidence.sqlite3')
    records=journal.records('game_completion');assert len(records)==3
    assert records[0].data['payload']['score']['self_score'] is None
    assert records[0].data['payload']['artifacts'] and records[0].data['payload']['checks']['recording']['status']=='ready'
    journal.verify();journal.close()


def test_default_marathon_runner_borrows_camera_for_game_two_and_three(tmp_path,monkeypatch):
    from experiments.ppal import marathon_robotron as m,play_robotron as play
    from test_experiment_return import gateway
    from test_marathon_deferred import args
    a=args(tmp_path);a.focus=None
    events=[];session_ids=[]
    class Camera:
        def close(self):events.append('close')
    monkeypatch.setattr(play,'PiCameraSource',lambda:(events.append('open') or Camera()))
    def sensory(*values,**kwargs):
        events.append('preflight');return object(),{'status':'usable','physical_motion':False}
    def player(argv,*,camera_session,progress_path):
        game=Path(argv[argv.index('--output')+1])
        camera_session.establish(camera_session.borrow(),game,sensory,seed_position=None)
        session_ids.append(camera_session.id)
        completed(game)
    monkeypatch.setattr(play,'main',player)
    def reflect(*v,**kw):
        assert events==['open','preflight','close']
        return {'phase':'checkpointed'}
    monkeypatch.setattr(m,'reflect_marathon',reflect)
    doc=m.developmental_marathon(a,gateway=gateway(tmp_path))
    assert doc['completion_counts']=={'completed':3} and doc['target_met']
    assert len(set(session_ids))==1 and len(session_ids)==3
    assert events==['open','preflight','close']


@pytest.mark.parametrize('failure',[RuntimeError,KeyboardInterrupt])
def test_default_runner_failure_preserves_game_one_and_releases_camera(tmp_path,monkeypatch,failure):
    from experiments.ppal import marathon_robotron as m,play_robotron as play
    from test_experiment_return import gateway
    from test_marathon_deferred import args
    a=args(tmp_path);a.focus=None;events=[]
    monkeypatch.setattr(play,'PiCameraSource',lambda:SimpleNamespace(close=lambda:events.append('close')))
    def player(argv,*,camera_session,progress_path):
        game=Path(argv[argv.index('--output')+1]);camera_session.borrow()
        if game.name=='game-01':completed(game)
        else:game.mkdir();raise failure('fixture interruption')
    monkeypatch.setattr(play,'main',player)
    monkeypatch.setattr(m,'reflect_marathon',lambda *v,**kw:{'phase':'checkpointed'})
    doc=m.developmental_marathon(a,gateway=gateway(tmp_path))
    assert events==['close'] and doc['completion_counts']['completed']==1
    assert doc['completion_counts']['incomplete_unverified']==1
    journal=EvidenceJournal(a.learning_root/'game-evidence.sqlite3',read_only=True)
    assert len(journal.records('game_completion'))==2;journal.close()


@pytest.mark.parametrize('camera_failure',[False,True])
def test_real_player_starts_two_simulated_playable_games_on_one_camera(tmp_path,monkeypatch,camera_failure,terminal_pages=False,terminal_delay=False):
    """Real player + marathon; simulated pixels/controls, not Pi acceptance."""
    import time
    from experiments.ppal import marathon_robotron as m,play_robotron as play
    from experiments.ppal.eyes.detectors import Detection
    from experiments.ppal.robotron_agency import VECTORS
    from test_experiment_return import gateway
    from test_marathon_deferred import args
    real_sleep=time.sleep
    # This accelerated, synthetic clock tests episode transitions, not writer
    # throughput. Finish prior durable work before advancing an exposure so
    # host scheduling cannot randomly turn it into a backpressure test. Real
    # recorder limits/fail-closed overflow have separate dedicated regressions.
    from experiments.ppal import progress_evidence
    real_recorder=progress_evidence.CaptureEvidence
    recorders=[]
    def recorder(*values,**options):
        value=real_recorder(*values,**options);recorders.append(value);return value
    monkeypatch.setattr(progress_evidence,'CaptureEvidence',recorder)
    clock=[0.];starts=[];preflights=[];closed=[];points=[(25.,25.),(50.,50.)]
    world={'game':0,'reads':0}
    class Camera:
        def __init__(self):closed.append('opened')
        def read(self):
            if recorders and not recorders[-1]._closed:recorders[-1].flush()
            real_sleep(.01);clock[0]+=.05
            if world['game']:world['reads']+=1
            if terminal_delay and world['reads']==102:clock[0]+=25.
            if camera_failure and world['game']==2 and world['reads']>65:
                raise RuntimeError('simulated capture disconnected')
            return Image.new('RGB',(100,100))
        def close(self):closed.append('camera_closed')
    class Controller:
        def __init__(self,*a,**kw):self.last_execution=None
        def _command(self,command):
            self.last_command=dict(command=command,write_started_at=clock[0],write_completed_at=clock[0],ack_at=clock[0])
            if command=='START':
                world['game']+=1;world['reads']=0;points[0]=(25.,25.);starts.append(world['game'])
        def execute(self,action,ms):
            if terminal_pages:assert world['reads']<100 # no postgame/demo agency probes
            self.last_execution=dict(started_at=clock[0],move=action.move,fire=action.fire,duration_ms=ms)
            clock[0]+=ms/1000
            if world['reads']<100:
                u=VECTORS[action.move];points[0]=(points[0][0]+u[0],points[0][1]+u[1])
        def close(self):closed.append('controller_closed')
    class Recognizer:
        def detect(self,frame):
            if world['reads']>=100:return []
            return [(Detection('unknown',p,(1,1,10,20),100),{'class_scores':{}}) for p in points]
    def screen(frame):
        if terminal_pages and world['game']:
            if 100<=world['reads']<104:return dict(state='not_gameplay',phase='terminal',reason='recorded_heroes_headings',label_scores={'heroes':.9,'all-time':.9})
            if 104<=world['reads']<107 or 131<=world['reads']<134 or world['reads']>=146:return dict(state='not_gameplay',phase='title',title_reference={'matched':True,'sha256':'a'*64})
            if world['reads']>=107:return dict(state='gameplay',phase='gameplay') # autonomous demonstration
        if not world['game'] or world['reads']>=106:return dict(state='not_gameplay',phase='startable')
        if world['reads']>=100:return dict(state='not_gameplay',phase='terminal')
        return dict(state='gameplay',phase='gameplay')
    def sensory(source,output,**kw):
        preflights.append(world['game'])
        assert world['game']==0
        return SimpleNamespace(apply=lambda f:f),dict(status='usable',physical_motion=False,fixture=True)
    monkeypatch.setattr(play,'PiCameraSource',Camera)
    monkeypatch.setattr(play,'ArcadeController',Controller)
    monkeypatch.setattr(play.TaughtRecognizer,'load',lambda *a:Recognizer())
    monkeypatch.setattr(play,'classify_screen_state',screen)
    monkeypatch.setattr(play,'sensory_preflight',sensory)
    monkeypatch.setattr(time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(time,'sleep',lambda t:None)
    monkeypatch.setattr(m,'reflect_marathon',lambda *v,**kw:{'phase':'checkpointed'})
    a=args(tmp_path);a.focus=None;a.max_games=2
    doc=m.developmental_marathon(a,gateway=gateway(tmp_path))
    assert starts==[1,2] and preflights==[0]
    assert closed.count('opened')==closed.count('camera_closed')==1
    assert doc['completion_counts']==({'completed':1,'invalid':1} if camera_failure else {'completed':2})
    reports=[json.loads((Path(g['path'])/'report.json').read_text()) for g in doc['games']]
    assert reports[0]['result']=='GAME OVER'
    if camera_failure:
        assert reports[1]['cal_recovery']['status']=='unavailable'
        assert reports[1]['failure_kind']=='observation_failure'
    else:
        assert all(r['result']=='GAME OVER' and r['acquisition']!='agency_unresolved' and r['ticks']>0 for r in reports)
    if terminal_pages:
        assert all(r['episode_end']['evidence']['rule']=='verified_gameplay_to_postgame_pages' for r in reports)
        assert reports[1]['start_decision']['start_commands']==1
        assert any(v['phase']=='gameplay' for v in reports[1]['start_decision']['observations'][:-3])
    assert reports[1]['calibration_mode']=='live_session_reuse'
    assert len({r['sensory_preflight']['camera_session']['id'] for r in reports})==1
    assert len({g['durable_game_evidence']['record_id'] for g in doc['games']})==2


def test_alias_is_not_a_second_independent_completed_game(tmp_path):
    import shutil
    first=tmp_path/'original';report=completed(first)
    journal=EvidenceJournal(tmp_path/'game-evidence.sqlite3')
    preserve_game(journal,first,marathon=tmp_path,returncode=0,report=report)
    alias=tmp_path/'alias';shutil.copytree(first,alias)
    with pytest.raises(ValueError,match='conflicting finalized'):
        preserve_game(journal,alias,marathon=tmp_path,returncode=0,report=report)
    assert len(journal.records('game_completion'))==1;journal.close()


def test_qualified_target_stops_after_two_confirmed_games(tmp_path,monkeypatch):
    from experiments.ppal import marathon_robotron as m
    from test_experiment_return import gateway
    from test_marathon_deferred import args
    a=args(tmp_path);a.qualified_games=2
    monkeypatch.setattr(m,'reflect_marathon',lambda *v,**kw:{'phase':'checkpointed'})
    def driver(cmd,*values):
        completed(Path(cmd[cmd.index('--output')+1]));return 0
    doc=m.developmental_marathon(a,driver=driver,gateway=gateway(tmp_path))
    assert doc['status']=='qualified_target_complete' and doc['target_met']
    assert len(doc['games'])==2 and doc['completion_counts']=={'completed':2}


def test_invalid_episode_is_retained_but_excluded_from_learning_handoff(tmp_path):
    from experiments.ppal import marathon_robotron as m
    from test_experiment_return import gateway
    from test_marathon_deferred import args
    a=args(tmp_path);session=a.root/'diagnostic';session.mkdir(parents=True)
    game=session/'game-01';game.mkdir()
    m.write_session(session/'session.json',dict(games=[dict(path=str(game),
        durable_game_evidence={'classification':'invalid','record_id':'fixture-reference'})]))
    result=m.reflect_marathon(session,a,gateway=gateway(tmp_path),
        processor=lambda *v,**kw:pytest.fail('invalid game entered gameplay learning'),
        development=lambda *v,**kw:None)
    assert result['episodes'][str(game.resolve())]['status']=='diagnostic_only'
    handoff=json.loads(Path(result['handoff']).read_text())
    assert handoff['episodes']==[] and game.exists()


@pytest.mark.parametrize('failure',['initialization','first_capture'])
def test_camera_failure_before_first_frame_preserves_request_without_start(tmp_path,monkeypatch,failure):
    from experiments.ppal import play_robotron as play
    events=[]
    class Camera:
        def __init__(self):
            if failure=='initialization':raise OSError('fixture camera unavailable')
        def read(self):raise OSError('fixture camera disconnected before first frame')
        def close(self):events.append('camera_closed')
    monkeypatch.setattr(play,'PiCameraSource',Camera)
    monkeypatch.setattr(play.TaughtRecognizer,'load',lambda *v:object())
    monkeypatch.setattr(play,'ArcadeController',lambda *v,**kw:pytest.fail('controller opened before usable view'))
    with pytest.raises((OSError,RuntimeError)):
        play.main(['--arm','--supervised-child','--output',str(tmp_path/'episode')])
    report=json.loads((tmp_path/'episode/report.json').read_text())
    assert report['cal_recovery']['status']=='unavailable'
    assert report['cal_recovery']['request']['physical_authorization'] is False
    assert report['episode_end']['confirmed'] is False
    if failure=='first_capture':assert events==['camera_closed']


def test_supplied_report_cannot_replace_sealed_original_measurement(tmp_path):
    root=tmp_path/'game';original=completed(root)
    altered=dict(original,score_summary={'status':'fabricated','self_score':999999})
    journal=EvidenceJournal(tmp_path/'game-evidence.sqlite3')
    result=preserve_game(journal,root,marathon=tmp_path,returncode=0,report=altered)
    assert result['classification']=='incomplete_unverified'
    assert journal.get(result['record_id']).data['payload']['checks']['report_matches_original'] is False
    assert json.loads((root/'report.json').read_text())==original
    journal.close()


def test_interrupted_capture_retains_original_identity_without_qualification(tmp_path):
    from memory.episode_identity import begin_capture
    root=tmp_path/'partial';origin=begin_capture(root)
    (root/'diagnostic.txt').write_text('original partial observation')
    journal=EvidenceJournal(tmp_path/'game-evidence.sqlite3')
    result=preserve_game(journal,root,marathon=tmp_path,returncode=130,report=None)
    row=journal.get(result['record_id'])
    assert row.data['episode']==origin['capture_id']
    assert row.data['payload']['artifacts']['diagnostic.txt']
    assert result['classification']=='incomplete_unverified'
    assert preserve_game(journal,root,marathon=tmp_path,returncode=130,report=None)['record_id']==row.id
    journal.close()

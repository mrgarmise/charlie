"""Exercise the real armed runner with a deterministic camera/controller world."""
import json
import sys
from PIL import Image
import pytest
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.robotron_agency import VECTORS


@pytest.mark.parametrize('fail_during_play,respawn,delayed_render,bootstrap,experiment,recalibrate,rejected_challenge,already_gameplay',
                         [(False,False,False,False,False,False,False,False),(True,False,False,False,False,False,False,False),
                          (False,True,False,False,False,False,False,False),(False,False,True,False,False,False,False,False),
                          (False,False,True,True,False,False,False,False),(False,False,True,True,True,False,False,False),
                          (False,False,False,True,False,True,False,False),(False,False,False,False,False,False,True,False),
                          (False,False,False,False,False,False,False,True)])

def test_armed_runner_uses_generic_agency_and_always_releases(monkeypatch,tmp_path,fail_during_play,respawn,delayed_render,bootstrap,experiment,recalibrate,rejected_challenge,already_gameplay,extended=False,terminal=False,finalization_disk_error=False):
    from experiments.ppal import play_robotron as play
    import time as real_time
    real_sleep=real_time.sleep
    start_read=[0]
    clock=[0.]; points=[(20.,20.),(50.,50.)]; commands=[]; closed=[]; reads=[0]
    image=Image.new('RGB',(100,100))
    pending = [None]; response_reads = [0]
    class Source:
        def read(self):
            real_sleep(.004)  # simulated camera cadence permits bounded evidence writer
            clock[0]+=.01; reads[0]+=1
            if pending[0] is not None:
                response_reads[0] += 1
                if response_reads[0] == 2:
                    u = pending[0]; p = points[0]
                    points[0] = (p[0]+u[0],p[1]+u[1])
                    pending[0] = None
            if respawn and reads[0] == start_read[0]+26: points[0]=(80.,80.)
            if fail_during_play and reads[0]>start_read[0]+28: raise RuntimeError('camera disconnected')
            if extended and reads[0]>600: raise KeyboardInterrupt
            return image
        def close(self): closed.append('camera')
    class Recognizer:
        def detect(self,frame):
            # Only the wrong stationary center object looks like PLAYER.
            return [(Detection('unknown' if i==0 else 'player',p,(1,1,10,20),100),
                     {'class_scores':{'player':.01 if i==0 else .99}}) for i,p in enumerate(points)]
    class Controller:
        def __init__(self,*a,**k): self.last_execution=None
        def _command(self,command):
            commands.append(command)
            if command=='START':start_read[0]=reads[0]
            self.last_command={'command':command,'write_started_at':clock[0],'write_completed_at':clock[0],'ack_at':clock[0]}
        def execute(self,action,ms):
            commands.append(action)
            self.last_execution={'started_at':clock[0],'move':action.move,'fire':action.fire,'duration_ms':ms}
            u=VECTORS[action.move]
            if delayed_render and action.move != "STAY":
                pending[0] = u; response_reads[0] = 0
            else:
                p=points[0]; points[0]=(p[0]+u[0],p[1]+u[1])
            clock[0]+=ms/1000
        def close(self): closed.append('controller')
    monkeypatch.setattr(play,'PiCameraSource',Source)
    monkeypatch.setattr(play.TaughtRecognizer,'load',lambda *a:Recognizer())
    monkeypatch.setattr(play.Calibration,'load',lambda *a:type('Calibration',(),{'apply':lambda self,f:f})())
    monkeypatch.setattr(play,'ArcadeController',Controller)
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(play.time,'sleep',lambda duration:None)
    monkeypatch.setattr(play,'classify_screen_state',lambda f:{'state':'gameplay' if ('START' in commands or already_gameplay) else 'not_gameplay',
        'phase':'gameplay' if ('START' in commands or already_gameplay) else 'startable'})
    challenges=[]
    if rejected_challenge:
        original_player=play.VisualAgency.player.fget
        monkeypatch.setattr(play.VisualAgency,'player',property(
            lambda self:None if reads[0]>start_read[0]+28 else original_player(self)))
        def reject(*a,**kw):
            challenges.append(True)
            return dict(confirmed=False,rejected=True,eligible=True,hits=0,failures=2,
                        attempts=2,evidence=[{'obeyed':False}]*2,frames=kw['initial_frames'])
        monkeypatch.setattr(play,'_control_challenge',reject)
        monkeypatch.setattr(play,'classify_screen_state',lambda f:{'state':'gameplay' if ('START' in commands or already_gameplay) else 'not_gameplay','phase':'gameplay' if ('START' in commands or already_gameplay) else 'startable'})
    if terminal:
        monkeypatch.setattr(play,'classify_screen_state',lambda f:{'state':'not_gameplay' if reads[0]>start_read[0]+28 else 'gameplay' if 'START' in commands else 'not_gameplay',
            'phase':'terminal' if reads[0]>start_read[0]+28 else 'gameplay' if 'START' in commands else 'startable'})
    if recalibrate:
        def prepare(source,output,**kwargs):
            assert 'START' not in commands
            assert kwargs['require_uniform_border'] is False
            clock[0]+=20.  # Slow geometry must spend no armed game time.
            return type('Calibration',(),{'apply':lambda self,f:f})()
        monkeypatch.setattr(play,'prepare',prepare)
        monkeypatch.setattr(play,'optimize_screen_exposure',lambda *a:{'status':'mock'})
    def sensory(source,output,**kwargs):
        assert 'START' not in commands
        calibration=play.prepare(source,output,require_uniform_border=False) if recalibrate else play.Calibration.load(None)
        return calibration,{'status':'usable','exposure':{'status':'simulated'},'physical_motion':False}
    monkeypatch.setattr(play,'sensory_preflight',sensory)
    if experiment:
        from pathlib import Path
        from memory.evidence import EvidenceJournal
        from memory.evaluator import MemoryEvaluator
        from memory.gateway import MemoryGateway
        from memory.store import JsonlStore
        from experiments.ppal.episode_evidence import import_episode
        from experiments.ppal.reflect_robotron import reflect_actuator_evidence
        from experiments.ppal.experiment_return import select_experiment,resolve_experiment
        fixture=Path(__file__).parent/'fixtures/robotron-body-fire-020552'
        root=tmp_path/'real-seed';root.mkdir()
        (root/'report.json').write_bytes((fixture/'report.json').read_bytes())
        (root/'agency.jsonl').write_bytes((fixture/'agency-response-extract.jsonl').read_bytes())
        gateway=MemoryGateway(evaluator=MemoryEvaluator(tmp_path/'eval.sqlite3',exploration_rate=0),store=JsonlStore(tmp_path/'memories.jsonl'))
        journal=EvidenceJournal(tmp_path/'seed.sqlite3');ep=import_episode(root,journal)
        reflect_actuator_evidence(root,journal,ep,gateway)
        commitments=EvidenceJournal(tmp_path/'commitments.sqlite3')
        plan=select_experiment(gateway,commitments,tmp_path/'run',horizon_seconds=30)
        (tmp_path/'plan.json').write_text(json.dumps(plan))
    if finalization_disk_error:
        transition=play.GameDiary.transition
        def faulty_diary(self,change):
            if change and change.new=='stopped':
                assert closed==['controller','camera']
                raise OSError('simulated finalization disk full')
            return transition(self,change)
        monkeypatch.setattr(play.GameDiary,'transition',faulty_diary)
    monkeypatch.setattr(sys,'argv',['play','--arm','--supervised-child','--output',str(tmp_path/'run')]
                        + ([] if extended or terminal else ['--seconds','3' if rejected_challenge else '1'])
                        + (['--bootstrap-body-fire'] if bootstrap else [])
                        + (['--experiment-plan',str(tmp_path/'plan.json')] if experiment else [])
                        + (['--recalibrate'] if recalibrate else []))
    if finalization_disk_error:
        from experiments.ppal.progress_supervision import ObservationFailure
        with pytest.raises(ObservationFailure,match='disk full'):play.main()
    elif fail_during_play:
        with pytest.raises(RuntimeError,match='camera disconnected'): play.main()
    else:
        play.main()
    report=json.loads((tmp_path/'run/report.json').read_text())
    t=report['session_timing']
    assert t['evidence_recording_started']<=t['calibration_started']<=t['evidence_ready']<=t['camera_ready']
    from memory.evidence import EvidenceJournal
    recording=EvidenceJournal(tmp_path/'run/session-evidence.sqlite3',read_only=True)
    captures=[r for r in recording.records('observation') if r.data['payload'].get('category')=='camera_capture']
    assert captures and all((tmp_path/'run'/r.data['payload']['artifact']['path']).exists() for r in captures)
    recording.verify()
    predictions=[r for r in recording.records('prediction') if r.data['payload'].get('expected',{}).get('category')=='tactical_prediction']
    executions=[r for r in recording.records('observation') if r.data['payload'].get('category')=='tactical_execution']
    assert predictions and executions
    assert {r.data['payload']['prediction_id'] for r in executions} <= {r.id for r in predictions}
    assert all(r.data['payload']['expected']['selected']=={k:r.data['payload']['expected']['actual_action'][k] for k in ('move','fire')} for r in predictions)
    assert all(r.data['sources'] for r in predictions)
    recording.close()
    if already_gameplay:
        assert 'START' not in commands and 'start_requested' not in t
        assert report['start_decision']['action']=='attach'
    else:
        assert commands.count('START')==1
        assert t['calibration_finished'] <= t['start_requested'] <= t['start_acknowledged']
        assert t['start_to_first_ordinary_action_seconds']==pytest.approx(
            t['first_ordinary_execution']['started_at']-t['start_transport']['write_completed_at'])
    assert t['self_discovery_started'] < t['self_discovery_finished'] <= t['gameplay_timer_started_at']
    assert t['first_ordinary_action_requested'] >= t['gameplay_timer_started_at']
    if extended or terminal:
        assert t['gameplay_deadline'] is None
    else:
        assert t['gameplay_deadline']-t['gameplay_timer_started_at']==pytest.approx(3. if rejected_challenge else 1.)
    telemetry_events=list(map(json.loads,(tmp_path/'run/events.jsonl').read_text().splitlines()))
    assert any(e['kind']=='state_transition' and e['new']=='playing' for e in telemetry_events)
    assert t['first_life_lost_at'] is None
    if recalibrate:
        assert t['start_requested']>=20. and report['calibration_mode']=='fresh_session'
    assert report['acquisition']==('provisional_body_agency' if bootstrap else 'generic_visual_agency')
    actions=[r for r in report['steps'] if 'action' in r]
    assert actions
    if respawn:
        assert any(r.get('status')=='player_reacquired' for r in report['steps'])
        assert any(r['player'][0]>60 for r in actions)
    else:
        if not extended:assert all(r['player'][0]<40 for r in actions)
    assert all(r['agency']['controlled_track_id'] is not None for r in actions)
    assert closed==['controller','camera']
    assert (tmp_path/'run/agency.jsonl').exists()
    telemetry=list(map(json.loads,(tmp_path/'run/agency.jsonl').read_text().splitlines()))
    assert telemetry[0]['command'] is None  # pre-command anchor is now recorded
    assert all(row['tracking']['clock']=='seconds' for row in telemetry)
    assert all(row['tracking']['detections'] for row in telemetry)
    assert (tmp_path/'run/tracks.json').exists()
    original=Image.open(tmp_path/'run'/report['raw_frames'][0]['path'])
    assert original.getextrema()==((0,0),(0,0),(0,0))
    assert all(r['self_track_id']==r['agency']['controlled_track_id'] for r in actions)
    if bootstrap:
        assert report['bootstrap_body_fire']
        assert any(getattr(c,'fire','NONE') != 'NONE' for c in commands)
        assert any(r['agency']['identity_status']=='provisional' for r in actions)
    if experiment:
        attempted=[r for r in actions if r.get('experiment')]
        assert len(attempted)==1
        action=attempted[0]['action'];baseline=attempted[0]['experiment']['baseline_action']
        assert (action['move'],action['fire'])==(plan['body'],plan['fire'])
        assert (baseline['move'],baseline['fire'])!=(plan['body'],plan['fire'])
        evidence=EvidenceJournal(tmp_path/'next.sqlite3');next_episode=import_episode(tmp_path/'run',evidence)
        resolution=resolve_experiment(tmp_path/'run',evidence,next_episode,commitments,plan,gateway)
        assert resolution['result']=='supported'
        evidence.close();commitments.close();journal.close()
    if rejected_challenge and not terminal:
        assert challenges and report['episode_end']['confirmed'] is False
        assert any(r.get('status')=='control_challenge' for r in report['steps'])
        assert report['result']=='DIAGNOSTIC LIMIT'
    if extended:
        assert report['result']=='INTERRUPTED'
        assert t['stopped_at']-t['gameplay_timer_started_at'] > 20.
        assert len(actions)>100
    elif terminal:
        from experiments.ppal.marathon_robotron import safe_to_restart
        assert safe_to_restart(report)
    elif finalization_disk_error:
        assert 'disk full' in report['recording_error']
        assert not (tmp_path/'run/capture-manifest.json').exists()
    else:
        assert report['result'].startswith('ERROR:') if fail_during_play else report['result']=='DIAGNOSTIC LIMIT'


def test_real_player_loop_has_no_default_duration_limit(monkeypatch,tmp_path):
    test_armed_runner_uses_generic_agency_and_always_releases(monkeypatch,tmp_path,
        False,False,False,False,False,False,False,False,extended=True)


def test_real_player_confirmed_terminal_completion(monkeypatch,tmp_path):
    test_armed_runner_uses_generic_agency_and_always_releases(monkeypatch,tmp_path,
        False,False,False,False,False,False,True,False,terminal=True)


def test_finalization_storage_error_releases_before_any_disk_logging(monkeypatch,tmp_path):
    test_armed_runner_uses_generic_agency_and_always_releases(monkeypatch,tmp_path,
        False,False,False,False,False,False,False,False,finalization_disk_error=True)

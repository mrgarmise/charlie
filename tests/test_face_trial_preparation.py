"""No-device trial admission, diagnostic integrity and normal routing checks."""
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
import main as app
from hardware.elegoo_mobile import ElegooMobileBase
from learning.face_trial import authorization_status, FaceTrialEvidence
from stimulus.bus import StimulusBus, Observation
from vision.mobile_perception import MobileFrame
from memory.evidence import EvidenceJournal


def test_complete_face_entry_uses_normal_owners_without_hailo_or_deck(monkeypatch,tmp_path):
    order=[];frame_bus=object();executor=object();telemetry=object()
    @contextmanager
    def cameras(args,**kw):
        assert kw['selected']==('elegoo',);order.append('camera');yield frame_bus
    @contextmanager
    def actuators(bus,**kw):
        assert bus is frame_bus and kw['wire_output']==tmp_path/'trial'/'driver-wire-final.json'
        order.append('executor');yield executor,telemetry
    run=Mock();process=Mock();process.is_alive.return_value=False
    monkeypatch.setattr(app,'application_camera_feeders',cameras)
    monkeypatch.setattr(app,'application_mobile_actuators',actuators)
    monkeypatch.setattr(app.multiprocessing,'get_context',lambda *a:SimpleNamespace(Process=lambda **kw:process))
    monkeypatch.setattr('learning.face_trial.run_face',run)
    app.main(['--hardware','--elegoo-face-track','--learning-state',str(tmp_path/'state'),
              '--face-evidence-dir',str(tmp_path/'trial')])
    assert order==['camera','executor'];process.start.assert_called_once()
    assert run.call_args.args[2:]==(frame_bus,executor,telemetry)
    process.join.assert_called_once()


@pytest.mark.parametrize('extra',[[],['--face-trial-seconds','nan'],['--face-trial-seconds','121'],['--face-authorization-wait','0']])
def test_invalid_trial_cannot_initialize_hardware(monkeypatch,tmp_path,extra):
    owners=Mock();monkeypatch.setattr(app,'application_camera_feeders',owners)
    argv=['--elegoo-face-track','--face-evidence-dir',str(tmp_path/'trial')]+extra
    if extra:argv.insert(0,'--hardware')
    with pytest.raises(ValueError):app.main(argv)
    owners.assert_not_called()


def test_admission_wait_never_forges_grants_and_requires_all_three_groups():
    e=SimpleNamespace(boot_id='boot',stop_uncertain=False,authority=None)
    assert not authorization_status(e)['ready']
    e.authority=Mock();e.authority.active.side_effect=lambda group,boot:(_ for _ in ()).throw(PermissionError('missing pan')) if group=='camera-pan' else ('external','report')
    s=authorization_status(e);assert not s['ready'] and s['groups']['chassis']['installed']
    e.authority.active.side_effect=None;assert authorization_status(e)['ready']
    e.stop_uncertain=True;assert not authorization_status(e)['ready']


def test_recording_reuses_original_writer_and_keeps_predictions_not_truth(tmp_path):
    car=ElegooMobileBase();bus=StimulusBus();owner=object()
    bus.claim_observations('elegoo-pose',owner,metadata={})
    e=SimpleNamespace(boot_id='software-only',base=SimpleNamespace(car=car),bus=bus)
    recorder=FaceTrialEvidence(tmp_path/'trial',e)
    import time
    now=time.monotonic()
    frame=MobileFrame('frame-1',np.zeros((48,64,3),dtype='uint8'),now,source='elegoo-v4',sequence=1,authentic=False)
    recorder.observation(frame,dict(normalized_x=.4,score=.9))
    car._handle_frame('{late_ok}')
    bus.publish_observation('elegoo-pose',owner,Observation('elegoo-pose',1,now,dict(yaw_degrees=3.,yaw_valid=True),{},'g'))
    recorder.poll();recorder.close()
    journal=EvidenceJournal(tmp_path/'trial/session-evidence.sqlite3',read_only=True)
    rows=journal.records();payloads=[r.data['payload'] for r in rows]
    assert any(r.get('category')=='camera_capture' for r in payloads)
    choice=next(r for r in payloads if r.get('category')=='face_selection')
    assert choice['authentic'] is False and choice['frame_id']=='frame-1'
    assert 'identity unverified' in choice['identity']
    assert any(r.get('category')=='face_wire' and r['events'][0]['frame']=='{late_ok}' for r in payloads)
    assert any(r.get('category')=='face_shared_observation' and r['values']['yaw_degrees']==3 for r in payloads)
    journal.close()
    with pytest.raises(FileExistsError):FaceTrialEvidence(tmp_path/'trial',e)


def test_wire_diagnostics_are_bounded_and_retain_unknown_or_late_replies():
    car=ElegooMobileBase()
    for _ in range(520):car._handle_frame('{old_ok}')
    h=car.wire_history()
    assert len(h['events'])==512 and h['evicted']
    h['events'][0]['frame']='changed'
    assert car.wire_history()['events'][0]['frame']=='{old_ok}'
    assert not car._pending


@pytest.mark.parametrize('reply',['{ok}','error','wrong-id'])
def test_qualified_pan_cannot_accept_untagged_negative_or_foreign_ack(reply):
    car=ElegooMobileBase();car._running=True
    def send(raw):
        command=json.loads(raw)
        frame={'{ok}':'{ok}','error':'{'+command['H']+'_error}','wrong-id':'{other_ok}'}[reply]
        car._handle_frame(frame)
    car.sock=SimpleNamespace(sendall=send)
    with pytest.raises(TimeoutError):car.pan_qualified(95,safety_check=lambda:True)
    assert not car._pending


def test_pan_cancellation_wins_ack_race():
    car=ElegooMobileBase();car._running=True;safe=[True]
    def send(raw):
        p=json.loads(raw);car._handle_frame('{'+p['H']+'_ok}');safe[0]=False
    car.sock=SimpleNamespace(sendall=send)
    with pytest.raises(InterruptedError):car.pan_qualified(95,safety_check=lambda:safe[0])


def test_stop_timeout_retains_command_and_does_not_retry():
    car=ElegooMobileBase();car._running=True;sent=[]
    car.sock=SimpleNamespace(sendall=sent.append)
    result=car.stop_verified()
    assert len(sent)==1 and json.loads(sent[0])==result['command']
    assert result['error']=='TimeoutError' and result['ack_timeout_seconds']==.150
    assert result['acknowledged'] is False and result['physically_stopped'] is None
    assert [r['kind'] for r in car.wire_history()['events']]==['tx_attempt','tx_complete','ack_timeout']
    car._handle_frame('{'+result['command']['H']+'_ok}')
    assert result['acknowledged'] is False


def test_face_keyboard_eof_attempts_emergency_stop(monkeypatch):
    import io,sys
    from stimulus.keyboard import KeyboardStimulus
    from threading import Thread
    bus=StimulusBus();stop=Mock()
    monkeypatch.setattr(sys,'stdin',io.StringIO(''))
    monkeypatch.setattr(Thread,'start',lambda self:None)
    keyboard=KeyboardStimulus(bus,emergency_only=True,on_emergency=stop,stop_on_eof=True)
    keyboard.loop()
    stop.assert_called_once();assert bus.get_all()==[('emergency_stop',None)]


def test_readiness_rejects_emergency_stop_even_with_installed_grants():
    e=SimpleNamespace(boot_id='b',stop_uncertain=False,_safety_stopped=True,authority=Mock())
    assert not authorization_status(e)['ready']
    e.authority.active.assert_not_called()


def test_missing_grants_wait_without_face_or_telemetry_dispatch(monkeypatch,tmp_path):
    from learning.face_trial import run_face
    from hardware.elegoo_mobile import AttentionAlignState
    import learning.face_trial as trial
    clock=[0.];monkeypatch.setattr(trial.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(trial.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    evidence=Mock();evidence.directory=tmp_path
    face=Mock();face.mobile.align=AttentionAlignState()
    guard=Mock();guard.sample={}
    keyboard=Mock();executor=SimpleNamespace(boot_id='b',stop_uncertain=False,authority=None,emergency_stop=Mock())
    monkeypatch.setattr(trial,'FaceTrialEvidence',lambda *a:evidence)
    monkeypatch.setattr('learning.resources.ResourceGuard',lambda *a:guard)
    monkeypatch.setattr('behaviors.mobile_face_runtime.MobileFaceRuntime',lambda *a,**kw:face)
    monkeypatch.setattr('stimulus.keyboard.KeyboardStimulus',lambda *a,**kw:keyboard)
    monkeypatch.setattr('memory.gateway.MemoryGateway',lambda:object())
    args=SimpleNamespace(face_evidence_dir=tmp_path/'trial',face_authorization_wait=1.,face_trial_seconds=1.)
    telemetry=Mock()
    with pytest.raises(TimeoutError):run_face(args,Mock(),StimulusBus(),executor,telemetry)
    face.observe.assert_not_called();telemetry.poll.assert_not_called()
    face.close.assert_not_called();evidence.close.assert_called_once()
    assert evidence.writer.append_line.call_args.args[1]['physical_acceptance'] is False


def test_evidence_failure_prevents_attention_motion(monkeypatch):
    import time
    from behaviors.mobile_face_runtime import MobileFaceRuntime
    bus=StimulusBus();owner=object();bus.claim_frames('elegoo-v4',owner)
    now=time.monotonic();pixels=np.zeros((12,16,3),dtype='uint8');pixels.setflags(write=False)
    f=MobileFrame('f',pixels,now,source='elegoo-v4',sequence=1)
    bus.publish_frame('elegoo-v4',owner,f)
    events=StimulusBus();executor=Mock();executor.bus=bus
    def failed(*a):raise OSError('storage unavailable')
    face=MobileFaceRuntime(bus,events,executor,detector=SimpleNamespace(detect=lambda pixels:dict(normalized_x=.8)),observation_callback=failed)
    face.observe()
    assert face.last_status['state']=='SOURCE_FAULT'
    assert events.get_all()==[];executor.request.assert_not_called();executor.stop.assert_called()
    face.subscription.close()


def test_receive_disconnect_has_evidence_instead_of_silent_ack_absence():
    car=ElegooMobileBase();car._running=True;car.sock=SimpleNamespace(recv=lambda size:b'')
    car._receive_loop()
    assert not car._running
    assert car.wire_history()['events'][-1]['kind']=='rx_eof'

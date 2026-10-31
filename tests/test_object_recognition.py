"""No-device end-to-end recognition through real perception, attention and serializer."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import json
import sys
import numpy as np
import pytest
from stimulus.bus import StimulusBus, install_application_frames, remove_application_frames
from vision.camera_source import CameraFrame
from vision.mobile_models import FixtureModel, UnavailableDepth
from vision.mobile_perception import MobilePerception
from vision.object_recognition import ObjectRecognition
from attention.object_display_runtime import DryRunDisplay
from attention.object_labels import ObjectLabels
from memory.evidence import EvidenceJournal
from learning.mobile import MobileEvidenceAdapter


def packet(at,source='pi-primary',sequence=1,generation='first'):
    pixels=np.frombuffer(bytes([0])*1200,dtype=np.uint8).reshape(20,20,3)
    return CameraFrame(source+str(sequence),pixels,at,source=source,sequence=sequence,
        camera_identity={'device':source},stream_generation=generation,capture_requested_at=at-.01)


def setup_session(tmp_path):
    now=[1.]
    frames=StimulusBus();events=StimulusBus();pi=object();elegoo=object()
    frames.claim_frames('pi-primary',pi);frames.claim_frames('elegoo-v4',elegoo)
    detector=FixtureModel([dict(label='chair',confidence=.95,box=[1,1,15,15]),
                           dict(label='cat',confidence=.85,box=[1,1,10,10])])
    detector.metadata['classes']=['chair','cat'];detector.close=Mock()
    perception=MobilePerception(detector,UnavailableDepth(),resources=SimpleNamespace(check=lambda **k:None),
        revision='fixture-only',cadence=.05,clock=lambda:now[0])
    journal=EvidenceJournal(tmp_path/'evidence.sqlite3')
    evidence=MobileEvidenceAdapter(journal,episode='fixture',revision='fixture-only')
    transport=DryRunDisplay();labels=ObjectLabels(transport,clock=lambda:now[0])
    session=ObjectRecognition(frames,perception,evidence,events,labels)
    session.select_camera('pi')
    return SimpleNamespace(now=now,frames=frames,events=events,pi=pi,elegoo=elegoo,session=session,
        journal=journal,transport=transport,detector=detector,labels=labels)


def feed(s,at,source='pi-primary',sequence=1,generation='first'):
    s.now[0]=at
    s.frames.publish_frame(source,s.pi if source=='pi-primary' else s.elegoo,
        packet(at,source,sequence,generation))
    return s.session.step()


def test_all_classes_through_attention_serializer_and_learning_with_no_motion(tmp_path):
    s=setup_session(tmp_path)
    try:
        for i,at in enumerate((1.,1.11,1.22)):result=feed(s,at,sequence=i)
        assert any('OBJECT_LABEL 4500 100 CHAIR' in command for command in s.transport.commands)
        assert result['observation']['source']=='pi-primary'
        assert result['observation']['camera_identity']['device']=='pi-primary'
        assert s.session.attention.mobile is None and s.session.attention.active is None
        rows=s.journal.category_records('observation','mobile_perception')
        assert len(rows)==3
        assert all(not row.data['payload']['execution']['dispatched'] for row in rows)
        assert all(not row.data['provenance']['authentic'] for row in rows)
        assert not s.journal.category_records('event','learning_project_proposal')
        assert s.detector.metadata['backend']=='offline-fixture'
    finally:s.session.close();s.transport.close();s.journal.close()


def test_switch_subscription_preserves_other_consumers_and_forces_reconfirmation(tmp_path):
    s=setup_session(tmp_path)
    face=s.frames.subscribe_frames('pi-primary',clock=lambda:s.now[0])
    learning=s.frames.subscribe_frames('pi-primary',clock=lambda:s.now[0])
    try:
        for i,at in enumerate((1.,1.11,1.22)):feed(s,at,sequence=i)
        assert s.labels.current==('pi-primary','CHAIR')
        s.events.emit('camera_source','elegoo');s.session.step()
        assert s.labels.current is None and s.transport.commands[-1]=='OBJECT_CLEAR'
        s.now[0]=1.3
        s.frames.publish_frame('pi-primary',s.pi,packet(1.3,sequence=4))
        assert face.read().sequence==learning.read().sequence==4
        assert s.session.step() is None
        assert feed(s,1.8,'elegoo-v4',5)['observation']['source']=='elegoo-v4'
        assert s.labels.current is None
        feed(s,1.91,'elegoo-v4',6);feed(s,2.02,'elegoo-v4',7)
        assert s.labels.current==('elegoo-v4','CHAIR')
        s.session.close()
        assert s.frames.frame_owners=={'pi-primary':s.pi,'elegoo-v4':s.elegoo}
    finally:s.session.close();face.close();learning.close();s.transport.close();s.journal.close()


def test_feeder_fault_and_generation_change_drop_display_and_stale_association(tmp_path):
    s=setup_session(tmp_path)
    try:
        for i,at in enumerate((1.,1.11,1.22)):feed(s,at,sequence=i)
        s.frames.frame_fault('pi-primary',s.pi,'source lost')
        with pytest.raises(OSError):s.session.step()
        assert s.labels.current is None
        assert len(s.journal.category_records('event','mobile_acquisition_fault'))==1
        feed(s,1.8,sequence=4,generation='replacement')
        assert s.labels.current is None
        feed(s,1.91,sequence=5,generation='replacement');feed(s,2.02,sequence=6,generation='replacement')
        assert s.labels.current==('pi-primary','CHAIR')
    finally:s.session.close();s.transport.close();s.journal.close()


def test_motion_events_are_never_forwarded_by_object_mode(tmp_path,monkeypatch):
    s=setup_session(tmp_path)
    try:
        for event in ('scan','track','idle','calibrate_neck','confirm_neck_start','vision_target'):
            s.events.emit(event,(1,2))
        s.session.step()
        assert s.session.attention.active is None and s.session.attention.pending is None
        assert s.session.attention.mobile is None
    finally:s.session.close();s.transport.close();s.journal.close()


def test_main_refuses_device_mode_without_explicit_hardware_and_excludes_replays():
    from main import main
    for args in (['--object-recognition'],
                 ['--object-recognition','--hardware','--object-label-replay','unused'],
                 ['--object-recognition','--hardware','--object-seconds','nan']):
        with pytest.raises(ValueError):main(args)


def test_legacy_pi_elegoo_and_tracker_use_same_publication_without_native_imports():
    from vision.camera import Camera
    from hardware.elegoo_camera import ElegooCamera
    from vision.tracker import Tracker
    frames=StimulusBus();pi=object();elegoo=object()
    frames.claim_frames('pi-primary',pi);frames.claim_frames('elegoo-v4',elegoo)
    install_application_frames(frames)
    try:
        camera=Camera();car=ElegooCamera();car.open();tracker=Tracker()
        import time
        at=time.monotonic()
        frames.publish_frame('pi-primary',pi,packet(at))
        frames.publish_frame('elegoo-v4',elegoo,packet(at,'elegoo-v4'))
        assert camera.read().shape==car.read().shape==(20,20,3)
        assert tracker.get_frame_and_error()[0].shape==(20,20,3)
        camera.close();car.close();tracker.close()
        assert frames.frame_owners=={'pi-primary':pi,'elegoo-v4':elegoo}
        assert 'picamera2' not in sys.modules
    finally:remove_application_frames(frames)


def test_tracking_emits_loss_on_subscription_stall(monkeypatch):
    from vision.stimulus import VisionStimulus
    bus=StimulusBus();now=[1.]
    monkeypatch.setattr('vision.stimulus.time.monotonic',lambda:now[0])
    camera=SimpleNamespace(read=Mock(side_effect=[np.zeros((2,2,3),np.uint8),None]))
    detector=SimpleNamespace(detect=lambda image:dict(x=1,y=1))
    vision=VisionStimulus(camera,detector,bus)
    vision.update();assert bus.get_all()==[('vision_target',(1,1))]
    now[0]=1.6;vision.update()
    assert bus.get_all()==[('vision_lost',None)]


def test_normal_main_owns_application_feeders_and_supervises_existing_learning(tmp_path,monkeypatch):
    from contextlib import contextmanager
    import main
    import learning.object_runtime
    calls=[];workers=[]
    class Worker:
        def __init__(self,**kwargs):workers.append(self);self.alive=False
        def start(self):calls.append('learning started')
        def is_alive(self):return self.alive
        def join(self,**kwargs):pass
    monkeypatch.setattr(main.multiprocessing,'get_context',lambda *a:SimpleNamespace(Process=Worker))
    @contextmanager
    def application_feeders(*a,**kw):
        calls.append('feeders started')
        try:yield 'existing application frame bus'
        finally:calls.append('feeders closed')
    monkeypatch.setattr(main,'application_camera_feeders',application_feeders)
    def recognition(args,resources,frame_bus,*,supervise):
        assert frame_bus=='existing application frame bus'
        assert args.object_label_display=='rp2040'
        assert args.camera_source=='pi'
        supervise()
        calls.append('recognition subscription')
    monkeypatch.setattr(learning.object_runtime,'run_objects',recognition)
    # Hardware construction is not mocked into a simulated motion success: it is forbidden.
    import motion.controller
    monkeypatch.setattr(motion.controller,'Deck',Mock(side_effect=AssertionError('object mode constructed Deck')))
    main.main(['--hardware','--object-recognition','--learning-state',str(tmp_path)])
    assert len(workers)==2 and calls.count('learning started')==2
    assert calls[-1]=='feeders closed' and 'recognition subscription' in calls
    motion.controller.Deck.assert_not_called()


def test_normal_recognition_runtime_uses_existing_manifest_and_immutable_frames_only(tmp_path,monkeypatch):
    from main import parser
    from learning.object_runtime import run_objects
    import learning.resources
    import vision.mobile_models
    import stimulus.keyboard
    import attention.object_display_runtime as display
    import time
    frames=StimulusBus();owner=object();frames.claim_frames('pi-primary',owner)
    model=FixtureModel([dict(label='chair',confidence=.95,box=[1,1,15,15])]);model.close=Mock()
    model.metadata['classes']=['chair']
    def detector(**config):
        assert config['include_all'] is True and config['sha256']=='fixture-only'
        return model
    monkeypatch.setattr(vision.mobile_models,'HailoObjects',detector)
    monkeypatch.setattr(learning.resources,'ResourceGuard',lambda *a:SimpleNamespace(check=lambda **k:None))
    monkeypatch.setattr(stimulus.keyboard,'KeyboardStimulus',lambda *a,**k:SimpleNamespace(close=lambda:None))
    links=[];attach=display.attach
    def tracked_attach(*a,**kw):
        result=attach(*a,**kw);links.append(result[1]);return result
    monkeypatch.setattr(display,'attach',tracked_attach)
    manifest=tmp_path/'models.json'
    manifest.write_text(json.dumps(dict(schema='charlie.mobile.models.v1',objects={'sha256':'fixture-only'})))
    args=parser().parse_args(['--hardware','--object-recognition','--object-model-manifest',str(manifest),
        '--object-label-display','dry-run','--object-frames','3','--object-seconds','5','--learning-state',str(tmp_path/'state')])
    sequence=[0]
    def supply():
        sequence[0]+=1
        frames.publish_frame('pi-primary',owner,packet(time.monotonic(),sequence=sequence[0]))
    run_objects(args,None,frames,supervise=supply)
    assert any(command=='OBJECT_LABEL 4500 100 CHAIR' for command in links[0].commands)
    assert frames.frame_owners['pi-primary'] is owner
    journal=EvidenceJournal(tmp_path/'state/mobile-evidence.sqlite3',read_only=True)
    try:
        rows=journal.category_records('observation','mobile_perception')
        assert len(rows)==3 and all(not r.data['payload']['execution']['dispatched'] for r in rows)
        journal.verify()
    finally:journal.close()


def test_mobile_capability_entrypoint_never_starts_camera_feeders(tmp_path,monkeypatch):
    import main
    import learning.mobile_runtime
    monkeypatch.setattr(main,'application_camera_feeders',Mock(side_effect=AssertionError('capability acquired capture')))
    observed=[]
    monkeypatch.setattr(learning.mobile_runtime,'run_mobile',lambda args,resources:observed.append(args.mobile_observe))
    main.main(['--mobile-observe','--learning-state',str(tmp_path)])
    assert observed==[True]
    main.application_camera_feeders.assert_not_called()


def test_empty_subscription_polls_are_never_recorded_as_captured_frames():
    from learning.mobile_runtime import watch
    behavior=SimpleNamespace(step=lambda:None,close=Mock())
    result=watch(behavior,frames=3,seconds=1,max_faults=1,fixture=True,clock=lambda:0.,publish=lambda row:None)
    assert result['polls']==3 and result['frames']==0 and result['records']==0
    behavior.close.assert_called_once()

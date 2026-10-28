"""No-device entry-point and emergency-preemption regressions."""
from contextlib import contextmanager
from unittest.mock import Mock
import pytest
import main as app
from stimulus.bus import StimulusBus
from stimulus.keyboard import KeyboardStimulus


def test_live_pet_and_objects_share_application_owners(monkeypatch,tmp_path):
    camera=object();executor=object();telemetry=object();calls=[]
    @contextmanager
    def feeders(args,**kwargs):
        calls.append(('feeder',kwargs));yield camera
    @contextmanager
    def actuators(bus,**kwargs):
        assert bus is camera;calls.append(('executor',kwargs));yield executor,telemetry
    def run(args,resources,frame_bus=None,actuator_executor=None,telemetry=None):
        calls.append(('runtime',args.object_recognition,args.pet_abilities,args.elegoo_face_track,
                      frame_bus,actuator_executor,telemetry))
    monkeypatch.setattr(app,'application_camera_feeders',feeders)
    monkeypatch.setattr(app,'application_mobile_actuators',actuators)
    monkeypatch.setattr('learning.mobile_runtime.run_mobile',run)
    app.main(['--hardware','--pet-abilities','--object-recognition','--elegoo-face-track',
              '--object-label-display','off','--learning-state',str(tmp_path)])
    assert [x[0] for x in calls] == ['feeder','executor','runtime']
    assert calls[-1][1:] == (True,True,True,camera,executor,telemetry)


def test_live_observation_can_use_application_camera_without_motion_authorization(monkeypatch,tmp_path):
    @contextmanager
    def feeders(args,**kwargs):yield 'frames'
    @contextmanager
    def actuators(bus,**kwargs):yield ('disarmed-executor','telemetry')
    run=Mock();monkeypatch.setattr(app,'application_camera_feeders',feeders)
    monkeypatch.setattr(app,'application_mobile_actuators',actuators)
    monkeypatch.setattr('learning.mobile_runtime.run_mobile',run)
    app.main(['--hardware','--mobile-observe','--learning-state',str(tmp_path)])
    assert run.call_args.args[2]=='frames'
    assert run.call_args.kwargs['actuator_executor']=='disarmed-executor'


def test_replay_is_not_run_with_hardware(tmp_path):
    with pytest.raises(ValueError,match='fixture replay'):
        app.main(['--hardware','--mobile-replay',str(tmp_path/'fixture')])


def test_emergency_keyboard_attempts_stop_before_event_even_on_error():
    bus=StimulusBus();order=[]
    def stop():
        order.append(('stop',bus.get_all()))
        raise OSError('fixture failure')
    keyboard=KeyboardStimulus.__new__(KeyboardStimulus)
    keyboard.bus=bus;keyboard.on_emergency=stop
    keyboard.emergency_stop()
    assert order==[('stop',[])]
    assert bus.get_all()==[('emergency_stop',None)]


def test_face_and_object_events_share_attention_and_camera_without_second_owner():
    import time
    import numpy as np
    from attention.manager import AttentionManager
    from behaviors.mobile_face_runtime import MobileFaceRuntime
    from vision.camera_source import CameraFrame
    frame_bus=StimulusBus();owner=object();frame_bus.claim_frames('elegoo-v4',owner)
    another=frame_bus.subscribe_frames('elegoo-v4',max_age=.5)
    events=StimulusBus();labels=Mock();attention=AttentionManager(events,mobile_enabled=False,object_labels=labels)
    attention.pet_service=Mock(intent='observe')
    executor=Mock();executor.request.return_value={'acknowledged':True,'commanded_degrees':120}
    detector=Mock();detector.detect.return_value={'normalized_x':.1}
    face=MobileFaceRuntime(frame_bus,events,executor,detector=detector)
    pixels=np.zeros((12,12,3),dtype=np.uint8);pixels.flags.writeable=False
    frame_bus.publish_frame('elegoo-v4',owner,CameraFrame('fixture-frame',pixels,time.monotonic(),source='elegoo-v4',sequence=1))
    packet={'schema':'charlie.object-observation.v1','source':'elegoo-v4','objects':[]}
    face.observe();events.emit('object_observation',packet);attention.update(None)
    assert another.read().id=='fixture-frame' and frame_bus.frame_owners['elegoo-v4'] is owner
    labels.observe.assert_called_once_with(packet,None)
    request=executor.request.call_args.args[0]
    assert request.source=='elegoo-v4' and request.observation_id=='fixture-frame'
    assert (request.group,request.action)==('camera-pan','pan')
    face.close();another.close()


def test_one_live_fixture_runtime_handles_primary_pet_objects_and_face(tmp_path,monkeypatch):
    import json
    import time
    import numpy as np
    from types import SimpleNamespace
    from vision.camera_source import CameraFrame
    from vision.mobile_models import FixtureModel
    from learning.mobile_runtime import run_mobile
    from learning.resources import DevelopmentResources
    import attention.manager
    import motion.controller
    import hardware.calibration_service
    import motion.rp2040_requests
    import vision.detector
    import vision.mobile_face
    import vision.mobile_models
    import learning.resources
    import stimulus.keyboard

    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:False)
    monkeypatch.setattr('learning.mobile_runtime.ResourceGuard',lambda *a:SimpleNamespace(check=lambda **kw:None))
    cat=FixtureModel([dict(label='cat',box=[1,1,10,10],confidence=.9)])
    monkeypatch.setattr('learning.mobile_runtime.HailoObjects',lambda **kw:cat)
    deck=Mock();deck.body=Mock();deck.observe_frame.return_value=None
    monkeypatch.setattr(motion.controller,'Deck',lambda:deck)
    neck=Mock();monkeypatch.setattr(hardware.calibration_service.CalibrationService,'open',lambda *a,**kw:neck)
    monkeypatch.setattr(motion.rp2040_requests,'RP2040Requests',lambda *a,**kw:Mock())
    primary_detector=Mock();primary_detector.detect.return_value=None
    monkeypatch.setattr(vision.detector,'ColorDetector',lambda **kw:primary_detector)
    face_detector=Mock();face_detector.detect.return_value=None
    monkeypatch.setattr(vision.mobile_face,'MobileFaceDetector',lambda:face_detector)
    monkeypatch.setattr(stimulus.keyboard,'KeyboardStimulus',lambda *a,**kw:SimpleNamespace(close=lambda:None))
    managers=[];original=attention.manager.AttentionManager
    def create_manager(*a,**kw):
        result=original(*a,**kw);managers.append(result);return result
    monkeypatch.setattr(attention.manager,'AttentionManager',create_manager)
    manifest=tmp_path/'models.json'
    manifest.write_text(json.dumps({'schema':'charlie.mobile.models.v1','objects':{}}))
    args=app.parser().parse_args(['--hardware','--pet-abilities','--object-recognition','--primary-vision',
        '--elegoo-face-track','--object-label-display','dry-run','--mobile-frames','1',
        '--mobile-seconds','3','--mobile-manifest',str(manifest),'--learning-state',str(tmp_path/'state')])
    frame_bus=StimulusBus();owners={s:object() for s in ('pi-primary','elegoo-v4')}
    pixels=np.zeros((30,40,3),dtype=np.uint8);pixels.flags.writeable=False
    for source,owner in owners.items():
        frame_bus.claim_frames(source,owner)
        frame_bus.publish_frame(source,owner,CameraFrame(source+':1',pixels,time.monotonic(),source=source,sequence=1))
    executor=Mock();executor.stop.return_value={'acknowledged':True}
    result=run_mobile(args,DevelopmentResources(),frame_bus,actuator_executor=executor)
    assert result['records']==1 and result['motion_authorized'] is False
    assert len(managers)==1 and managers[0].pet_service is not None and managers[0].object_labels is not None
    assert primary_detector.detect.call_count==1 and face_detector.detect.call_count==1
    deck.observe_frame.assert_called_once()
    assert frame_bus.frame_owners==owners


def test_idle_face_yields_to_pet_without_stopping_shared_executor():
    from behaviors.mobile_face_runtime import MobileFaceRuntime
    from attention.manager import AttentionManager
    frame_bus=StimulusBus();events=StimulusBus();executor=Mock()
    service=MobileFaceRuntime(frame_bus,events,executor,detector=Mock())
    manager=AttentionManager(events,mobile_enabled=False)
    manager.pet_service=Mock(intent='follow')
    manager.handle_event('elegoo_face_observation',{'service':service,'frame':None,'face':None})
    executor.stop.assert_not_called()
    service.behavior._sentry_turn_state=(0,0,'LEFT')
    manager.handle_event('elegoo_face_observation',{'service':service,'frame':None,'face':None})
    executor.stop.assert_called_once()
    service.close()

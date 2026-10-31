"""Independent callers exercise real console, bus, gateway; fake wire only."""
from dataclasses import replace
from types import SimpleNamespace
import threading
from unittest.mock import Mock
import numpy as np
import pytest
from motion.elegoo_executor import QualifiedElegooExecutor, ActuatorRequest
from experiments.ppal.mobile_navigation import MotionLease
from stimulus.bus import StimulusBus, Observation
from ui.mobile import MobileConsole
from vision.camera_source import CameraFrame
from vision.detection_publication import DetectionPublication


def fixture():
    now=[10.]
    bus=StimulusBus();producer=object();bus.claim_frames('elegoo-v4',producer)
    pixels=np.frombuffer(bytes(30*30*3),dtype=np.uint8).reshape(30,30,3)
    frame=CameraFrame('f1',pixels,10.,source='elegoo-v4',sequence=1,stream_generation='g')
    bus.publish_frame('elegoo-v4',producer,frame)
    pose=object();bus.claim_observations('elegoo-pose',pose,metadata={})
    bus.publish_observation('elegoo-pose',pose,Observation('elegoo-pose',1,10.,{'pan_degrees':90},{},'pose'))
    base=SimpleNamespace(connect=Mock(),close=Mock(),stop_verified=Mock(return_value={'acknowledged':True}),
        pulse=Mock(return_value={'acknowledged':True,'stop':{'acknowledged':True}}))
    authority=Mock()
    authority.safe.return_value=True
    authority.active.return_value=({}, {'envelope':dict(max_pwm=35,directions=['LEFT','RIGHT','FORWARD','REVERSE'])})
    def admit(request,evidence,boot_id):
        return dict(group='chassis',request_id=request.id,
            lease=MotionLease('supervised_trial',now[0]+.4,'test',boot_id),
            envelope=dict(directions=['LEFT','RIGHT','FORWARD','REVERSE'],max_pwm=35,max_duration=.1))
    authority.admit.side_effect=admit
    e=QualifiedElegooExecutor(base,bus=bus,authority=authority,clock=lambda:now[0])
    c=MobileConsole(bus,e,clock=lambda:now[0])
    return SimpleNamespace(now=now,bus=bus,producer=producer,frame=frame,base=base,e=e,c=c)


def command(s,action='drive',**changes):
    body=dict(boot=s.c.boot,lease=s.c.lease,sequence=s.c.sequence+1,action=action,direction='FORWARD',pwm=20)
    body.update(changes)
    return body


def autonomous(s):
    return ActuatorRequest('autonomous','face','chassis','pulse',s.now[0],'elegoo-v4','f1',
        dict(direction='LEFT',pwm=20,seconds=.1))


def test_manual_precedes_face_and_pet_but_each_manual_pulse_still_needs_qualification():
    s=fixture();lease=s.c.acquire();s.now[0]+=.001
    with pytest.raises(PermissionError):s.e.request(autonomous(s))
    with pytest.raises(PermissionError):s.e.execute_bounded({'at':s.now[0]},lease=MotionLease())
    s.c.control(command(s));s.base.pulse.assert_called_once()
    assert s.e.authority.admit.call_args.args[0].requester=='mobile-operator'
    assert s.base.pulse.call_args.kwargs['seconds']==.1
    s.e.authority.safe.return_value=False
    with pytest.raises(PermissionError):s.c.control(command(s))
    assert s.base.pulse.call_count==1
    s.c.close()


def test_manual_acquisition_preempts_inflight_autonomy_and_rejects_competing_operators():
    s=fixture();entered=threading.Event();cancelled=threading.Event()
    def pulse(*a,**kw):
        entered.set();assert kw['cancel'].wait(1);cancelled.set()
        return dict(acknowledged=True,stop={'acknowledged':True})
    s.base.pulse.side_effect=pulse
    worker=threading.Thread(target=lambda:s.e.request(autonomous(s)))
    worker.start();assert entered.wait(1)
    s.c.acquire();assert cancelled.wait(1);worker.join(1)
    with pytest.raises(PermissionError):s.c.acquire()
    s.c.close()


@pytest.mark.parametrize('action',['stop','release','emergency'])
def test_stop_release_and_emergency_preempt_active_manual_wire_without_waiting_for_operation_lock(action):
    s=fixture();s.c.acquire();s.now[0]+=.001
    entered=threading.Event();done=[]
    def pulse(*a,**kw):
        entered.set();assert kw['cancel'].wait(1)
        return dict(acknowledged=True,stop={'acknowledged':True})
    s.base.pulse.side_effect=pulse
    worker=threading.Thread(target=lambda:done.append(s.c.control(command(s))))
    worker.start();assert entered.wait(1)
    result=s.c.control(command(s,action));worker.join(1)
    assert not worker.is_alive() and result['acknowledged']
    if action=='emergency':
        assert s.e._safety_stopped
        with pytest.raises(PermissionError):s.c.acquire()
    s.c.close()


def test_disconnect_watchdog_revokes_and_stops_and_never_revives_expired_lease():
    s=fixture();s.c.acquire();old=command(s);s.now[0]+=.401
    assert s.c.expire();assert s.e._manual_owner is None
    assert s.c.status()['control']['command']['state']=='watchdog STOP'
    with pytest.raises(PermissionError):s.c.control(old)
    s.c.close()


@pytest.mark.parametrize('change',[{'boot':'other'},{'lease':'foreign'},{'sequence':-1},{'pwm':36},{'pwm':True},{'direction':'MIXED'}])
def test_rejects_foreign_replayed_or_unbounded_commands_without_wire(change):
    s=fixture();s.c.acquire();s.now[0]+=.001
    with pytest.raises((PermissionError,ValueError)):s.c.control(command(s,**change))
    s.base.pulse.assert_not_called();s.c.close()


def test_release_ends_manual_authority_and_old_requests_cannot_use_new_lease():
    s=fixture();s.c.acquire();old=command(s);s.c.control(command(s,'release'));s.now[0]+=.001
    s.c.acquire()
    with pytest.raises(PermissionError):s.c.control(old)
    s.c.close()


def test_replay_is_rejected_and_hardware_admission_failure_never_becomes_success():
    s=fixture();s.c.acquire();s.now[0]+=.001;b=command(s);s.c.control(b)
    with pytest.raises(ValueError):s.c.control(b)
    s.e.authority.admit.side_effect=PermissionError('unqualified')
    with pytest.raises(PermissionError):s.c.control(command(s))
    assert s.c.status()['control']['command']['state']=='rejected or failed';s.c.close()


def test_pan_and_source_requirements_are_independent_not_filled_from_commanded_state():
    s=fixture();s.c.acquire();s.now[0]+=.001
    s.bus.observation_fault('elegoo-pose',s.bus.observation_owners['elegoo-pose'],'no measured pan')
    s.e.authority.measured_pan.side_effect=PermissionError('no qualified independent feed')
    with pytest.raises(PermissionError):s.c.control(command(s))
    s.base.pulse.assert_not_called();s.c.close()


def test_stale_camera_removes_live_image_and_detections_without_acquisition_or_owner_changes():
    s=fixture();other=s.bus.subscribe_frames('elegoo-v4',clock=lambda:s.now[0]);pub=DetectionPublication(s.bus)
    packet=dict(source='elegoo-v4',frame_id='f1',stream_generation='g',geometry=[30,30],at=10.,objects=[{'label':'cat'}])
    pub.publish(packet)
    assert s.c.status()['detections']['frame_id']=='f1'
    assert s.c.image()[0].startswith(b'\x89PNG')
    assert other.read().id=='f1'
    s.now[0]=10.6
    assert s.c.status()['detections'] is None
    with pytest.raises(TimeoutError):s.c.image()
    s.c.close();pub.close()
    assert s.bus.frame_owners['elegoo-v4'] is s.producer


def test_source_generation_and_geometry_must_match_overlays_and_fault_invalidates_them():
    s=fixture();pub=DetectionPublication(s.bus)
    packet=dict(source='elegoo-v4',frame_id='f1',stream_generation='old',geometry=[30,30],at=10.,objects=[])
    pub.publish(packet);assert s.c.status()['detections'] is None
    packet.update(stream_generation='g',at=10.01);pub.publish(packet);s.now[0]=10.01
    assert s.c.status()['detections'] is not None
    pub.invalidate('switched');assert s.c.status()['detections'] is None
    s.bus.frame_fault('elegoo-v4',s.producer,'lost');assert not s.c.status()['camera']['available']
    s.now[0]=10.02;s.bus.publish_frame('elegoo-v4',s.producer,replace(s.frame,id='f2',sequence=2,received_at=10.02,stream_generation='new'))
    assert s.c.status()['camera']['available'];assert s.c.status()['detections'] is None
    pub.close();s.c.close()


def test_sensor_centimeters_frequency_age_failures_and_independent_delivery():
    s=fixture();o=object();s.bus.claim_observations('elegoo-ultrasonic',o,metadata={'modality':'range'})
    a=s.bus.subscribe_observations('elegoo-ultrasonic',clock=lambda:s.now[0]);b=s.bus.subscribe_observations('elegoo-ultrasonic',clock=lambda:s.now[0])
    for seq,at in enumerate((9.9,10.)):
        s.bus.publish_observation('elegoo-ultrasonic',o,Observation('elegoo-ultrasonic',seq,at,{'meters':1.25,'valid':True},{},'r'))
    v=s.c.status()['sensors']['elegoo-ultrasonic']
    assert v['available'] and v['centimeters']==125 and v['hz']==pytest.approx(10)
    assert a.read().values==b.read().values
    s.now[0]+=.6;v=s.c.status()['sensors']['elegoo-ultrasonic'];assert not v['available'] and v['values'] is None and v['age_seconds']>.5
    s.bus.observation_fault('elegoo-ultrasonic',o,'communication failed')
    v=s.c.status()['sensors']['elegoo-ultrasonic'];assert v['failures']==1 and not v['available']
    s.c.close()


def test_camera_rate_is_observed_not_a_target_and_latency_does_not_invent_exposure_age():
    s=fixture();s.c.status();s.now[0]=10.1
    s.bus.publish_frame('elegoo-v4',s.producer,replace(s.frame,id='f2',sequence=2,received_at=10.1))
    camera=s.c.status()['camera'];assert camera['subscriber_fps']==pytest.approx(10)
    assert camera['exposure_latency_seconds'] is None
    s.c.close()


def test_unqualified_or_monitoring_only_keeps_senses_available_but_never_acquires():
    s=fixture();s.e.authority.active.side_effect=PermissionError('no witnessed qualification')
    assert not s.c.status()['control']['available'];assert s.c.status()['camera']['available']
    with pytest.raises(PermissionError):s.c.acquire()
    s.base.connect.assert_not_called();s.c.close()
    c=MobileConsole(StimulusBus());assert not c.status()['control']['available']
    with pytest.raises(PermissionError):c.acquire()
    c.close()


def test_software_configuration_fails_before_hardware(monkeypatch):
    import main
    monkeypatch.delenv('CHARLIE_MONITOR_TOKEN',raising=False)
    with pytest.raises(ValueError):main.main(['--hardware','--mobile-dashboard'])


def test_overlay_transport_uses_exact_retained_decision_pixels_when_camera_has_advanced():
    s=fixture();s.c.status();pub=DetectionPublication(s.bus)
    packet=dict(source='elegoo-v4',frame_id='f1',stream_generation='g',geometry=[30,30],at=10.,objects=[])
    pub.publish(packet);s.now[0]=10.1
    s.bus.publish_frame('elegoo-v4',s.producer,replace(s.frame,id='f2',sequence=2,received_at=10.1))
    _,meta=s.c.image(overlays=True)
    assert meta['frame_id']=='f1' and meta['detections']['frame_id']=='f1'
    assert meta['age_seconds']==pytest.approx(.1)
    _,meta=s.c.image();assert meta['frame_id']=='f2' and meta['detections'] is None
    s.now[0]=10.6
    _,meta=s.c.image(overlays=True);assert meta['frame_id']=='f2' and meta['detections'] is None
    pub.close();s.c.close()


def test_watchdog_worker_stops_expired_owner_without_http_or_an_application_loop():
    import time
    s=fixture();s.c.acquire();s.c.start();s.now[0]+=.401
    deadline=time.monotonic()+1
    while s.c.lease is not None and time.monotonic()<deadline:time.sleep(.005)
    assert s.c.lease is None and s.e._manual_owner is None
    assert s.c.command['state']=='watchdog STOP'
    s.c.close()


def test_slow_encoding_and_monitoring_cannot_hold_control_stop_lock(monkeypatch):
    from PIL import Image
    s=fixture();s.c.acquire();entered=threading.Event();finish=threading.Event()
    original=Image.Image.save
    def slow(image,*args,**kwargs):
        entered.set();assert finish.wait(1);return original(image,*args,**kwargs)
    monkeypatch.setattr(Image.Image,'save',slow)
    worker=threading.Thread(target=s.c.image);worker.start();assert entered.wait(1)
    try:
        result=s.c.control({'action':'emergency'})
        assert s.e._safety_stopped and result['sent'] is False
    finally:finish.set();worker.join(1);s.c.close()


def test_persistent_manual_sequence_does_not_fill_autonomous_replay_budget_and_cannot_replay():
    s=fixture();s.c.acquire()
    for index in range(300):
        s.now[0]+=.0001
        s.c.control(command(s))
    assert s.base.pulse.call_count==300 and not s.e.used
    old=s.e.authority.admit.call_args.args[0]
    with pytest.raises(ValueError):s.e.request_manual(s.c.owner,old,sequence=s.c.sequence)
    with pytest.raises(PermissionError):s.e.request(old)
    s.c.control(command(s,'release'));s.now[0]+=.0001;s.c.acquire()
    with pytest.raises(PermissionError):s.e.request_manual(object(),old,sequence=1000)
    s.c.close()


def test_status_distinguishes_transport_from_qualification_and_reports_actual_direction_limits():
    s=fixture();s.e.authority.active.return_value=({}, {'envelope':{'max_pwm':22,'directions':['LEFT','RIGHT']}})
    v=s.c.status()['control']
    assert v['available'] and v['max_pwm']==22 and v['directions']==['LEFT','RIGHT']
    assert not v['transport_connected'] and v['executor_boot_id']==s.e.boot_id
    s.c.close()

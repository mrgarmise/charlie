from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from stimulus.bus import StimulusBus, Observation
from motion.elegoo_executor import QualifiedElegooExecutor, ActuatorRequest
from experiments.ppal.mobile_navigation import MotionLease
from hardware.elegoo_telemetry import ElegooTelemetry
from motion.mobile_requests import MobileRequests


def setup():
    bus=StimulusBus();owner=object();now=[10.]
    bus.claim_observations('vision',owner,metadata={'modality':'test'})
    bus.publish_observation('vision',owner,Observation('vision',1,10.,{'target':'fixture'},{},'g'))
    base=SimpleNamespace(connect=Mock(),close=Mock(),stop_verified=Mock(return_value={'acknowledged':True}),
        pulse=Mock(return_value={'acknowledged':True,'stop':{'acknowledged':True}}),
        car=SimpleNamespace(pan_qualified=Mock(return_value=100)))
    authority=Mock()
    def admit(r,e,boot_id):
        return dict(group=r.group,request_id=r.id,lease=MotionLease('supervised_trial',11.,'fixture-only',boot_id),
            envelope=dict(max_duration=.2,max_pwm=30,directions=['LEFT','RIGHT'],min_degrees=20,
                          max_degrees=160,position_command_verified=True))
    authority.admit.side_effect=admit;authority.safe.return_value=True
    executor=QualifiedElegooExecutor(base,bus=bus,authority=authority,clock=lambda:now[0])
    return executor,base,bus,owner,now


def request(id='r',group='chassis',**kw):
    return ActuatorRequest(id,'face',group,'pan' if group=='camera-pan' else 'pulse',10.,'vision','g:1',
                           kw or {'direction':'LEFT','pwm':20,'seconds':.1})


def test_both_groups_use_one_transport_and_receipts_are_not_pose():
    e,b,bus,_,_=setup()
    assert e.request(request())['acknowledged']
    assert e.request(request('pan','camera-pan',degrees=100))['commanded_degrees']==100
    b.connect.assert_called_once();b.pulse.assert_called_once();assert b.car.pan_qualified.call_args.args == (100,)
    state=bus.latest_observation('elegoo-actuator-state',clock=lambda:10.)
    assert state.values['physically_observed'] is None
    assert bus.latest_observation('elegoo-pose',clock=lambda:10.) is None


@pytest.mark.parametrize('change', ['stale','replay','unbound','veto','unqualified','bounds'])
def test_admission_cannot_be_bypassed(change):
    e,b,_,_,now=setup();r=request()
    if change=='stale':now[0]=10.2
    if change=='replay':e.used.add('r')
    if change=='unbound':r=ActuatorRequest('r','face','chassis','pulse',10.,'vision','other',r.parameters)
    if change=='veto':e.authority.safe.return_value=False
    if change=='unqualified':e.authority=None
    if change=='bounds':r=request(pwm=100,direction='LEFT',seconds=.1)
    with pytest.raises((ValueError,PermissionError)):e.request(r)
    b.connect.assert_not_called();b.pulse.assert_not_called()


def test_busy_and_stop_invalidate_prior_request():
    e,b,_,_,now=setup()
    e._request_lock.acquire()
    try:
        with pytest.raises(ValueError):e.request(request())
        e.stop()
    finally:e._request_lock.release()
    with pytest.raises(ValueError):e.request(request())
    b.pulse.assert_not_called()


def test_uncertainty_is_not_cleared_by_later_ack_or_replacement():
    e,b,_,_,now=setup();b.pulse.side_effect=TimeoutError()
    with pytest.raises(TimeoutError):e.request(request())
    assert e.stop_uncertain
    assert e.stop()['acknowledged']
    now[0]+=.01
    with pytest.raises(ValueError):e.request(request('new'))
    with pytest.raises(ValueError):QualifiedElegooExecutor(b,bus=StimulusBus())


def test_scalar_subscribers_are_independent_bounded_and_private():
    bus=StimulusBus();owner=object();bus.claim_observations('s',owner,metadata={})
    a=bus.subscribe_observations('s',clock=lambda:10.);b=bus.subscribe_observations('s',clock=lambda:10.)
    for seq in range(40):bus.publish_observation('s',owner,Observation('s',seq,10.,{'x':[]},{},'g'))
    x=a.read();x.values['x'].append(1)
    assert b.read().values['x']==[]
    assert len(bus.recent_observations('s',clock=lambda:10.))==32
    assert not bus.recent_observations('s',clock=lambda:11.)
    with pytest.raises(RuntimeError):bus.claim_observations('s',object(),metadata={})
    with pytest.raises(PermissionError):bus.publish_observation('s',object(),x)
    with pytest.raises(ValueError):bus.publish_observation('s',owner,x)
    bus.observation_fault('s',owner,'lost')
    with pytest.raises(OSError):a.read()


def test_telemetry_unknown_protocol_never_opens_transport():
    e,b,bus,_,_=setup();e.authority=None;t=ElegooTelemetry(e,clock=lambda:10.)
    assert not t.poll();b.connect.assert_not_called()
    with pytest.raises(OSError):bus.latest_observation('elegoo-ultrasonic')


def test_verified_reads_share_transport_and_do_not_manufacture_clearance():
    e,b,bus,_,_=setup()
    e.authority.telemetry_protocol.return_value=dict(read_only_connection_authorized=True,
        ultrasonic_read_only=True,ultrasonic={'N':21,'D1':2},yaw_read_only=True,yaw={'N':24},firmware_identity='fixture')
    b.read_ultrasonic=Mock(return_value=dict(meters=1.2,valid=True));b.yaw=Mock(return_value=12.)
    t=ElegooTelemetry(e,clock=lambda:10.);assert t.poll()
    e.request(request());b.connect.assert_called_once()
    assert bus.latest_observation('elegoo-ultrasonic',clock=lambda:10.).values['clearance'] is None
    assert bus.latest_observation('elegoo-pose',clock=lambda:10.).values['pan_degrees'] is None


def test_alignment_keeps_yaw_counter_rotation_and_uses_bounded_renewals():
    e,b,bus,_,_=setup();client=MobileRequests(executor=e,clock=lambda:10.)
    client.source='vision';client.observation_id='g:1'
    client.yaw=Mock(side_effect=[0.,-10.,-15.])
    b.car.pan_qualified.side_effect=lambda degrees, **kw:degrees
    assert client.begin_attention_align(120,max_rotation=15)
    assert client.update_attention_align()['pan']==110
    status=client.update_attention_align()
    assert status['done'] and status['pan']==105 and status['reason']=='aligned'
    assert b.pulse.call_count==2
    assert all(c.kwargs['seconds']==.1 for c in b.pulse.call_args_list)


def test_application_blocks_other_motor_transports_without_opening_socket():
    from motion.elegoo_executor import install_application_executor, remove_application_executor
    from hardware.elegoo_mobile import ElegooMobileBase
    e,b,_,_,_=setup();install_application_executor(e)
    try:
        with pytest.raises(PermissionError):ElegooMobileBase().connect()
    finally:remove_application_executor(e)


def test_preflight_cancellation_inside_wire_lock_prevents_send():
    from hardware.elegoo_mobile import ElegooMobileBase
    car=ElegooMobileBase();car.sock=Mock();car._running=True
    with pytest.raises(InterruptedError):car._send_raw(b'not-sent',preflight=lambda:False)
    car.sock.sendall.assert_not_called()


def test_no_pan_centering_after_behavior_stop():
    from behaviors.mobile_face_track import MobileFaceTrackBehavior
    mobile=Mock();behavior=MobileFaceTrackBehavior(mobile=mobile)
    behavior.stop()
    mobile.stop.assert_called_once();mobile.pan.assert_not_called()


def test_nonblocking_sentry_renews_only_after_new_yaw_and_reacquires():
    from behaviors.mobile_face_track import MobileFaceTrackBehavior
    mobile=Mock();mobile.yaw.side_effect=[0.,0.,-10.]
    behavior=MobileFaceTrackBehavior(mobile=mobile)
    assert behavior._sentry_turn(10.)
    assert behavior._sentry_turn(10.1)
    assert mobile.pivot.call_count==2 and behavior.sentry_sector==0
    behavior.update_face({'normalized_x':.5})
    assert behavior._sentry_turn_state is None and behavior.sentry_sector==0
    mobile.stop.assert_called_once()


def test_rp2040_gateway_rejects_unqualified_and_stale_without_serial_motion():
    import numpy as np
    from motion.rp2040_requests import RP2040Requests
    from vision.camera_source import CameraFrame
    bus=StimulusBus();owner=object();bus.claim_frames('pi-primary',owner)
    pixels=np.zeros((4,4,3),dtype=np.uint8);pixels.flags.writeable=False
    bus.publish_frame('pi-primary',owner,CameraFrame('f',pixels,10.,source='pi-primary'))
    controller=Mock();calibration=SimpleNamespace(brain=SimpleNamespace(authorized=False,blocked=False),health=SimpleNamespace(quarantined=False))
    service=RP2040Requests(controller,calibration,bus,clock=lambda:10.)
    req=ActuatorRequest('id','attention','rp2040-head','track-target',10.,'pi-primary','f',{'target':{'x':1,'y':1}})
    with pytest.raises(PermissionError):service.request(req)
    controller.assert_not_called()
    controller.stop.return_value=False;service.stop()
    calibration.brain.authorized=True
    with pytest.raises(ValueError):service.request(req)
    assert service.uncertain


def test_durable_uncertainty_survives_new_facade(tmp_path):
    from pathlib import Path
    e,b,bus,owner,now=setup()
    marker=tmp_path/'uncertain';e.fault_path=marker
    b.pulse.side_effect=TimeoutError('unknown start')
    with pytest.raises(TimeoutError):e.request(request())
    assert marker.read_text().strip()=='r'
    fresh=SimpleNamespace(connect=Mock(),close=Mock(),stop_verified=Mock(return_value={'acknowledged':True}),
        pulse=Mock(),car=SimpleNamespace(pan_qualified=Mock()))
    new=QualifiedElegooExecutor(fresh,bus=StimulusBus(),authority=e.authority,clock=lambda:10.,fault_path=marker)
    assert new.stop_uncertain
    with pytest.raises(ValueError):new.request(request('fresh'))
    assert marker.exists()


def test_durable_marker_removed_only_after_acknowledged_completion(tmp_path):
    e,b,_,_,_=setup();e.fault_path=tmp_path/'uncertain'
    result=e.request(request())
    assert result['acknowledged'] and not e.fault_path.exists()
    assert e.bus.latest_observation('elegoo-actuator-state',clock=lambda:10.).values['physically_observed'] is None


def test_app_owner_constructs_disarmed_without_opening_hardware(tmp_path,monkeypatch):
    from main import application_mobile_actuators
    from hardware.elegoo_mobile import ElegooMobileBase
    connect=Mock(side_effect=AssertionError('must not connect'))
    monkeypatch.setattr(ElegooMobileBase,'connect',connect)
    with application_mobile_actuators(StimulusBus(),state=tmp_path) as (executor,telemetry):
        assert executor.authority is not None
        assert not telemetry.poll()
        assert not executor._connected
        connect.assert_not_called()


def test_stop_is_published_but_is_not_measured_stopping():
    e,b,bus,_,_=setup();e._connected=True
    result=e.stop();assert result['acknowledged']
    state=bus.latest_observation('elegoo-actuator-state',clock=lambda:10.)
    assert state.values['action']=='stop' and state.values['physically_observed'] is None


def test_legacy_motor_calls_cannot_bypass_application_executor():
    from motion.elegoo_executor import install_application_executor,remove_application_executor
    from motion.mobile_base import MobileBase
    e,b,_,_,_=setup();install_application_executor(e)
    try:
        legacy=MobileBase()
        with pytest.raises(PermissionError):legacy.pulse('LEFT')
        with pytest.raises(PermissionError):legacy.car.pan(90)
        with pytest.raises(PermissionError):legacy.car.start_pivot('LEFT')
        with pytest.raises(PermissionError):legacy.car.pan_qualified(90,safety_check=lambda:True)
    finally:remove_application_executor(e)

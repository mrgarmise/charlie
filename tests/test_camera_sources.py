"""Synthetic transport tests. Capabilities never open, configure or close cameras."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import time
import numpy as np
import pytest
from hardware.camera_ownership import ElegooCameraLease
from vision.camera_source import CameraFrame, CameraSubscription, _PiCapture, _ElegooCapture, TrackingCamera
from experiments.ppal.camera_session import CameraFeeder
from stimulus.bus import StimulusBus


def frame(at=1., source='pi-primary', sequence=1):
    pixels=np.frombuffer(bytes([30,20,10])*24,dtype=np.uint8).reshape(4,6,3)
    return CameraFrame(str(sequence),pixels,at,source=source,sequence=sequence,
        camera_identity={'device':'fixture'},stream_generation='fixture-generation')


def test_pi_capture_preserves_native_bgr_and_observed_identity():
    bgr=np.full((4,6,3),[30,20,10],np.uint8)
    camera=SimpleNamespace(read=lambda:bgr,close=Mock(),
        picam2=SimpleNamespace(camera_properties={'Model':'imx708','Id':'fixture-pi'}))
    capture=_PiCapture(camera=camera,clock=lambda:1.)
    first,second=capture.read(),capture.read()
    assert first.image[0,0].tolist()==[30,20,10]
    assert first.camera_identity['model']=='imx708' and first.id!=second.id
    assert first.metadata()['source_age_known'] is False
    capture.close();capture.close();camera.close.assert_called_once()
    with pytest.raises(InterruptedError):capture.read()


def test_elegoo_capture_preserves_bgr_receipt_and_generation():
    camera=SimpleNamespace(read=Mock(return_value=(np.zeros((4,6,3),np.uint8),dict(sequence=1,received_at=1.))),
        close=Mock(),stream_url='http://fixture:81/stream',_generation=7,_thread=None)
    capture=_ElegooCapture(camera=camera,clock=lambda:1.)
    result=capture.read()
    assert result.source=='elegoo-v4' and result.stream_generation.endswith(':7')
    assert result.camera_identity['endpoint']==camera.stream_url
    with pytest.raises(ValueError,match='stale or reordered'):capture.read()
    capture.close()


def test_subscription_switch_does_not_control_feeders_or_other_subscribers():
    bus=StimulusBus();pi=object();elegoo=object()
    bus.claim_frames('pi-primary',pi);bus.claim_frames('elegoo-v4',elegoo)
    face=bus.subscribe_frames('pi-primary',clock=lambda:1.)
    learner=bus.subscribe_frames('pi-primary',clock=lambda:1.)
    recognition=CameraSubscription(bus,clock=lambda:1.);recognition.switch('pi')
    bus.publish_frame('pi-primary',pi,frame())
    a,b=face.read(),learner.read()
    assert a.image is b.image and a.id==b.id==recognition.read().id
    a.camera_identity['device']='private mutation'
    assert b.camera_identity['device']=='fixture'
    with pytest.raises(ValueError):a.image.flags.writeable=True
    recognition.switch('elegoo')
    bus.publish_frame('pi-primary',pi,frame(sequence=2))
    assert face.read().sequence==learner.read().sequence==2 and recognition.read() is None
    bus.publish_frame('elegoo-v4',elegoo,frame(source='elegoo-v4'))
    assert recognition.read().source=='elegoo-v4'
    recognition.close()
    assert bus.frame_owners=={'pi-primary':pi,'elegoo-v4':elegoo}


def test_bounded_nonblocking_freshness_fault_and_publisher_authority():
    bus=StimulusBus();owner=object();bus.claim_frames('pi-primary',owner)
    fast=bus.subscribe_frames('pi-primary',clock=lambda:1.)
    slow=bus.subscribe_frames('pi-primary',clock=lambda:2.)
    for i in range(100):bus.publish_frame('pi-primary',owner,frame(sequence=i))
    assert fast.pending.qsize()==slow.pending.qsize()==1 and slow.dropped==99
    assert fast.read().sequence==99 and fast.read() is None
    with pytest.raises(TimeoutError):slow.read()
    with pytest.raises(PermissionError):bus.publish_frame('pi-primary',object(),frame())
    with pytest.raises(RuntimeError):bus.claim_frames('pi-primary',object())
    bus.frame_fault('pi-primary',owner,'disconnected')
    with pytest.raises(OSError,match='disconnected'):fast.read()
    fast.close();slow.close()


def wait_until(predicate):
    deadline=time.monotonic()+2
    while not predicate():
        if time.monotonic()>deadline:raise AssertionError('feeder deadline')
        time.sleep(.005)


def test_one_authoritative_capture_serves_many_consumers_until_application_closes():
    bus=StimulusBus();events=[]
    class Capture:
        sequence=0
        def read(self):
            self.sequence+=1
            return replace(frame(at=time.monotonic(),sequence=self.sequence),authentic=False)
        def close(self):events.append('close')
    def factory():events.append('open');return Capture()
    feeder=CameraFeeder(factory,bus,'pi-primary').start()
    first=bus.subscribe_frames('pi-primary');second=bus.subscribe_frames('pi-primary')
    try:
        wait_until(lambda:first.pending.qsize() and second.pending.qsize())
        assert first.read().image is second.read().image
        first.close()
        wait_until(lambda:second.pending.qsize())
        assert second.read().source=='pi-primary' and events==['open']
    finally:feeder.close();second.close()
    assert events==['open','close'] and not feeder.thread.is_alive()


def test_feeder_failure_invalidates_and_recovers_without_consumer_capture():
    bus=StimulusBus();attempts=[]
    def factory():attempts.append(1);raise OSError('fixture unavailable')
    feeder=CameraFeeder(factory,bus,'pi-primary',recovery_attempts=1).start()
    subscriber=bus.subscribe_frames('pi-primary')
    wait_until(lambda:not feeder.thread.is_alive())
    with pytest.raises(OSError):subscriber.read()
    feeder.close();subscriber.close()
    assert len(attempts)==2 and feeder.faults==2


def test_tracking_adapter_keeps_geometry_without_owning_capture():
    bus=StimulusBus();owner=object();bus.claim_frames('pi-primary',owner)
    subscription=CameraSubscription(bus,clock=lambda:1.);subscription.switch('pi')
    camera=TrackingCamera(subscription)
    assert camera.read() is None
    bus.publish_frame('pi-primary',owner,frame())
    result=camera.read()
    assert result.shape==(720,1280,3) and result[0,0].tolist()==[30,20,10]
    camera.close();assert bus.frame_owners['pi-primary'] is owner


def test_elegoo_lease_excludes_duplicate_capture_until_authoritative_release():
    first=ElegooCameraLease('http://fixture-owner:81/stream')
    try:
        with pytest.raises(BlockingIOError):ElegooCameraLease('http://fixture-owner:82/other')
    finally:first.close()
    again=ElegooCameraLease('http://fixture-owner:81/stream');again.close()


def test_failed_stream_open_releases_transport_lease(monkeypatch):
    from hardware.elegoo_camera import _ElegooCameraDevice as ElegooCamera
    monkeypatch.setattr('urllib.request.urlopen',Mock(side_effect=OSError('fixture offline')))
    camera=ElegooCamera(stream_url='http://fixture-open-error:81/stream')
    with pytest.raises(OSError):camera.open()
    assert camera._ownership is None
    lease=ElegooCameraLease(camera.stream_url);lease.close();camera.close()


def test_concurrent_capabilities_switch_without_capture_restart_or_slow_consumer_backpressure():
    bus=StimulusBus();opens=[];closes=[];capture_threads={};samples=[];stop=threading.Event()
    class Capture:
        def __init__(self,source):self.source=source;self.sequence=0
        def read(self):
            self.sequence+=1
            capture_threads.setdefault(self.source,set()).add(threading.get_ident())
            return replace(frame(time.monotonic(),self.source,self.sequence),stream_generation=self.source+'-one-owner')
        def close(self):closes.append(self.source)
    def factory(source):
        opens.append(source)
        return Capture(source)
    feeders=[CameraFeeder(lambda source=source:factory(source),bus,source,period=.01).start()
             for source in ('pi-primary','elegoo-v4')]
    face=bus.subscribe_frames('pi-primary');learning=bus.subscribe_frames('pi-primary')
    stalled=bus.subscribe_frames('pi-primary')
    recognition=CameraSubscription(bus);recognition.switch('pi')
    def consume(subscription):
        while not stop.wait(.003):
            value=subscription.read()
            if value is not None:samples.append((id(subscription),value.sequence,value.stream_generation))
    workers=[threading.Thread(target=consume,args=(s,)) for s in (face,learning)]
    for worker in workers:worker.start()
    try:
        for i in range(20):
            recognition.switch('elegoo' if i%2 else 'pi')
            time.sleep(.01)
            recognition.read()
        assert len(opens)==2 and not closes
        assert all(len(tids)==1 for tids in capture_threads.values())
        assert len(capture_threads)==2
        assert all(any(row[0]==id(s) for row in samples) for s in (face,learning))
        assert stalled.pending.qsize()==1 and stalled.dropped>=5
        assert all(f.frames>=10 for f in feeders)
        recognition.close()
        before=feeders[0].frames
        wait_until(lambda:feeders[0].frames>=before+3)
        assert not closes and len(opens)==2
    finally:
        stop.set()
        for worker in workers:worker.join(timeout=1)
        for s in (face,learning,stalled):s.close()
        recognition.close()
        for f in feeders:f.close()
    assert sorted(closes)==['elegoo-v4','pi-primary']


def test_only_authoritative_driver_implementations_can_open_physical_cameras():
    import ast
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    opens=[]
    for directory in ('vision','hardware','behaviors','learning','experiments','stimulus'):
        for path in (root/directory).rglob('*.py'):
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.Call):
                    name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr','')
                    if name in ('Picamera2','VideoCapture','_PiCameraDevice','_ElegooCameraDevice'):
                        opens.append((str(path.relative_to(root)),name))
    assert sorted(opens)==sorted([('vision/camera.py','Picamera2'),
        ('vision/camera_source.py','_PiCameraDevice'),('vision/camera_source.py','_ElegooCameraDevice')])


def test_configuration_executes_only_on_existing_feeder_thread_and_role():
    calls=[];bus=StimulusBus()
    class Capture:
        camera=SimpleNamespace(lease=SimpleNamespace(role='primary',should_yield=lambda:False),
            picam2=SimpleNamespace(camera_controls={},camera_properties={},
                set_controls=lambda controls:calls.append((threading.get_ident(),controls))))
        def read(self):return frame(time.monotonic())
        def close(self):pass
    feeder=CameraFeeder(Capture,bus,'pi-primary',period=.01).start()
    try:
        wait_until(lambda:feeder.frames>0)
        with pytest.raises(PermissionError):feeder.configure({'LensPosition':2.},role='preview')
        assert calls==[]
        feeder.configure({'LensPosition':2.},role='primary')
        assert calls==[(feeder.thread.ident,{'LensPosition':2.})]
        with pytest.raises(PermissionError):feeder.configure({'unreviewed_setting':1},role='primary')
    finally:feeder.close()

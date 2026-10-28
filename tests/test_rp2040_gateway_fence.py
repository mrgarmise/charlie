"""Deterministic host-only races, no serial hardware or physical claims."""
import threading
from types import SimpleNamespace
from hardware.rp2040_controller import RP2040Controller
from motion.controller import Deck
from motion.rp2040_requests import RP2040Requests
from stimulus.bus import StimulusBus


class Wire:
    def __init__(self):self.writes=[];self.timeout=.1
    def write(self,data):self.writes.append(data)
    def readline(self):return b''


def host():
    controller=RP2040Controller.__new__(RP2040Controller)
    controller.connected=True;controller.serial=Wire();controller.lock=threading.Lock()
    controller.motion_epoch=controller.motion_owner=None
    return controller


def test_stop_revokes_inflight_request_before_next_wire_write():
    controller=host();started=threading.Event();proceed=threading.Event();results=[]
    def request():
        with controller.motion_scope():
            started.set();assert proceed.wait(2)
            results.append(controller.send('LOOK 100 90'))
            results.append(controller._exchange('AUTHORIZE ACTIVE_VISION s 1 INITIAL','OK AUTHORIZE',timeout=.01))
    thread=threading.Thread(target=request);thread.start()
    try:
        assert started.wait(2)
        assert controller.stop()
        proceed.set();thread.join(2)
        assert not thread.is_alive()
        assert results == [False,None]
        assert controller.serial.writes == [b'STOP\n']
    finally:proceed.set();thread.join(2)


def test_new_scope_after_stop_is_distinct_and_does_not_authorize_motion():
    controller=host();assert controller.stop()
    with controller.motion_scope():
        assert controller.send('PING')
    assert controller.serial.writes == [b'STOP\n',b'PING\n']


def test_normal_deck_uses_existing_calibration_gateway_for_frames_and_stop():
    controller=host();calls=[]
    brain=SimpleNamespace(search_remaining=3,request_search=lambda:calls.append('search'))
    calibration=SimpleNamespace(brain=brain,observe_frame=lambda frame,target:calls.append((frame,target)),
                                health=SimpleNamespace(quarantined=False))
    gateway=RP2040Requests(controller,calibration,StimulusBus())
    deck=Deck(body=controller,calibration=calibration);deck.actuator_gateway=gateway
    deck.observe_frame('frame',{'x':1});deck.scan();deck.stop()
    assert calls == [('frame',{'x':1}),'search']
    assert brain.search_remaining==0 and controller.serial.writes==[b'STOP\n']


def test_stop_prevents_old_scope_from_scheduling_search():
    controller=host();started=threading.Event();proceed=threading.Event();results=[]
    brain=SimpleNamespace(search_remaining=0)
    brain.request_search=lambda:setattr(brain,'search_remaining',12)
    calibration=SimpleNamespace(brain=brain,health=SimpleNamespace(quarantined=False))
    gateway=RP2040Requests(controller,calibration,StimulusBus())
    def request():
        with controller.motion_scope():
            started.set();assert proceed.wait(2)
            results.append(gateway.request_search())
    thread=threading.Thread(target=request);thread.start()
    try:
        assert started.wait(2);gateway.stop();proceed.set();thread.join(2)
        assert results == [False] and brain.search_remaining==0
    finally:proceed.set();thread.join(2)


def test_unexpected_gateway_failure_latches_across_restart(tmp_path):
    import pytest
    controller=host();marker=tmp_path/'uncertain'
    def failure(frame,target):raise TimeoutError('unknown serial outcome')
    brain=SimpleNamespace(search_remaining=0,blocked=False)
    calibration=SimpleNamespace(brain=brain,observe_frame=failure,health=SimpleNamespace(quarantined=False))
    gateway=RP2040Requests(controller,calibration,StimulusBus(),fault_path=marker)
    with pytest.raises(TimeoutError):gateway.observe_frame('frame')
    assert gateway.uncertain and marker.exists()
    restarted=RP2040Requests(host(),calibration,StimulusBus(),fault_path=marker)
    assert restarted.uncertain and restarted.observe_frame('frame') is None
    restarted.stop();assert marker.exists()


def test_two_gateways_cannot_own_one_controller():
    import pytest
    controller=host();calibration=SimpleNamespace(brain=None,health=SimpleNamespace(quarantined=False))
    RP2040Requests(controller,calibration,StimulusBus())
    with pytest.raises(ValueError,match='already has'):
        RP2040Requests(controller,calibration,StimulusBus())


def test_serial_lease_blocks_another_cooperating_controller(monkeypatch,tmp_path):
    import hashlib
    import os
    from hardware.hailo_session import accelerator_lease
    import hardware.rp2040_controller as module
    controller=host();controller.port=str(tmp_path/'serial-fixture');controller.baud=115200
    controller.serial=None;controller._accepted=lambda *a:True
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    serial_open=MockSerial=[]
    def create(*a,**kw):
        MockSerial.append((a,kw));return Wire()
    monkeypatch.setattr(module.serial,'Serial',create)
    key=hashlib.sha256(os.path.realpath(controller.port).encode()).hexdigest()[:20]
    lock='/tmp/charlie-rp2040-'+key+'.lock'
    with accelerator_lease(lock):
        assert controller.connect() is False
        assert not serial_open
    assert controller.connect() is True
    assert len(serial_open)==1
    controller.close()


def test_status_publication_is_fresh_source_bound_and_not_measured_pose():
    controller=host();controller.link_session='fixture-session'
    controller.motion_status=lambda:dict(schema='charlie-motion-authority-v1',session='fixture-session',
        armed=False,moving=False,pan=90,tilt=90,pose_source='commanded_estimate',measured_position=None)
    calibration=SimpleNamespace(brain=None,health=SimpleNamespace(quarantined=False))
    bus=StimulusBus();gateway=RP2040Requests(controller,calibration,bus,clock=lambda:5.)
    first=bus.subscribe_observations('rp2040-motion-state',clock=lambda:5.)
    second=bus.subscribe_observations('rp2040-motion-state',clock=lambda:5.)
    assert gateway.poll()
    assert first.read().values['measured_position'] is None
    assert second.read().provenance['physical_pose']=='unknown'
    controller.motion_status=lambda:None
    assert not gateway.poll()
    import pytest
    with pytest.raises(OSError):first.read()
    gateway.close()


def test_normal_deck_legacy_shortcuts_cannot_bypass_gateway():
    controller=host();calls=[]
    brain=SimpleNamespace(search_remaining=0,request_search=lambda:calls.append('search'))
    calibration=SimpleNamespace(brain=brain,observe_frame=lambda frame,target:None,
                                health=SimpleNamespace(quarantined=False))
    gateway=RP2040Requests(controller,calibration,StimulusBus())
    deck=Deck(body=controller,calibration=calibration);deck.actuator_gateway=gateway
    assert deck.home() is False and deck.center() is False
    assert deck.track(100,90) is False
    deck.move_to(100,90);deck.set_all(100,90)
    assert controller.serial.writes==[]


def test_explicitly_disarmed_monitoring_does_not_write_motion_marker(tmp_path):
    controller=host();marker=tmp_path/'uncertain';calls=[]
    brain=SimpleNamespace(authorized=False,session=None,blocked=False)
    calibration=SimpleNamespace(brain=brain,observe_frame=lambda frame,target:calls.append(frame),
                                health=SimpleNamespace(quarantined=False))
    gateway=RP2040Requests(controller,calibration,StimulusBus(),fault_path=marker)
    gateway.observe_frame('frame')
    assert calls==['frame'] and not marker.exists() and not gateway.uncertain

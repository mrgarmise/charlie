"""No actual serial, pixels, PWM, camera, or model device are used."""
import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from test_active_vision_firmware import board
from rp2040.object_label import normalize_label,label_request
from attention.object_labels import ObjectLabels
from hardware.rp2040_controller import RP2040Controller
from attention.manager import AttentionManager
from stimulus.bus import StimulusBus

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def screen(monkeypatch):
    now=[0];pixels=[];calls=[]
    tree=ast.parse((ROOT/'rp2040/lib/Pico_ed.py').read_text())
    assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=='wordStock' for t in n.targets))
    font=ast.literal_eval(assignment.value)
    def pixel(x,y,b):
        assert 0<=x<17 and 0<=y<7;pixels.append((x,y,b))
    def show(text):
        assert len(text)<=3;calls.append(text)
    monkeypatch.setitem(sys.modules,'Pico_ed',SimpleNamespace(display=SimpleNamespace(wordStock=font,fill=lambda v:None,pixel=pixel,show=show)))
    monkeypatch.setattr('time.ticks_ms',lambda:now[0],raising=False)
    monkeypatch.setattr('time.ticks_add',lambda a,b:a+b,raising=False)
    monkeypatch.setattr('time.ticks_diff',lambda a,b:a-b,raising=False)
    spec=importlib.util.spec_from_file_location('object_firmware_display',ROOT/'rp2040/display.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return SimpleNamespace(d=module.Display(),now=now,pixels=pixels,calls=calls)


def transport(handler,board):
    class UART:
        timeout=.1
        writes=[]
        lines=[]
        def write(self,data):
            self.writes.append(data)
            out=io.StringIO()
            with contextlib.redirect_stdout(out):board.command(handler,data.decode())
            self.lines.extend((s+'\n').encode() for s in out.getvalue().splitlines())
        def readline(self):return self.lines.pop(0) if self.lines else b''
        def close(self):pass
    host=RP2040Controller.__new__(RP2040Controller)
    host.connected=True;host.serial=UART();host.lock=threading.Lock();host.link_session='fixture-session'
    host.motion_epoch=123;host.motion_owner='PRESERVED_TEST_OWNER';host.last_tx=0;host.running=False
    return host


def packet(at,label='cat',score=.9,source='elegoo',identifier='one',others=()):
    return dict(schema='charlie.object-observation.v1',source=source,frame_id=str(at),at=at,clock_domain='pi-monotonic',
        objects=[dict(id=identifier,label=label,confidence=score,prominence=.2),*others])


def fake_policy(**kw):
    now=[0.];host=SimpleNamespace(link_session='fixture',show_object_label=Mock(return_value=True),clear_object_label=Mock(return_value=True))
    return now,host,ObjectLabels(host,clock=lambda:now[0],**kw)


def feed(now,policy,label='cat',start=1,**kwargs):
    for at in (start,start+.11,start+.22):
        now[0]=at;policy.observe(packet(at,label,**kwargs));policy.tick()


@pytest.mark.parametrize('label,expected',[('cat','CAT'),('dog','DOG'),('person','PERSON'),('dining table','DINING TABLE'),('stop sign','STOP SIGN')])
def test_stabilized_labels_and_dedup(label,expected):
    now,h,p=fake_policy();feed(now,p,label)
    h.show_object_label.assert_called_once_with(expected,4500,100)
    for i in range(1,11):
        now[0]=1.22+i*.05;p.observe(packet(now[0],label));p.tick()
    assert h.show_object_label.call_count==1


def test_threshold_flicker_alternation_and_stale_clear():
    now,h,p=fake_policy()
    feed(now,p,score=.3);h.show_object_label.assert_not_called()
    for i in range(20):
        now[0]=3+i*.1;p.observe(packet(now[0],'cat' if i%2 else 'dog'));p.tick()
    h.show_object_label.assert_not_called()
    feed(now,p,start=6);assert h.show_object_label.call_count==1
    now[0]=8;p.tick();h.clear_object_label.assert_called_once()
    assert p.current is None


def test_attention_precedence_and_source_binding():
    now,h,p=fake_policy();bus=StimulusBus();attention=AttentionManager(bus,mobile_enabled=False,object_labels=p)
    bus.emit('object_attention',dict(source='elegoo',id='dog-track'))
    for at in (1,1.11,1.22):
        now[0]=at
        bus.emit('object_observation',packet(at,others=[dict(id='dog-track',label='dog',confidence=.8,prominence=.1)]))
        attention.update(None)
    h.show_object_label.assert_called_once_with('DOG',4500,100)
    now[0]=1.3;bus.emit('object_observation',packet(1.3,'bird',source='birdfeeder'));attention.update(None)
    assert h.show_object_label.call_count==1 and attention.mobile is None and attention.active is None


def test_fault_disconnect_reconnect_and_unsupported_no_flood():
    now,h,p=fake_policy();feed(now,p)
    p.invalidate('elegoo');p.tick();assert p.current is None
    h.show_object_label.return_value=False
    for i in range(30):
        now[0]=3+i*.01;p.observe(packet(now[0]));p.tick()
    assert h.show_object_label.call_count<=2
    h.link_session='new';p.tick();assert p.pending is None
    h.show_object_label.return_value=True;feed(now,p,start=5)
    assert p.current==('elegoo','CAT')


@pytest.mark.parametrize('value',['\nSTOP\nARM','é💥','a'*1000,'Cat\x00DOG',None,''])
def test_external_label_is_bounded_ascii_data(value):
    label=normalize_label(value);command=label_request(label,4500,100)
    assert len(label)<=24 and command.startswith('OBJECT_LABEL ') and '\n' not in command and '\x00' not in command
    with pytest.raises(ValueError):label_request('CAT\nSTOP',4500,100)


def test_real_uart_caps_object_scroll_and_stop_without_pwm(board,screen):
    a,behavior,handler,heartbeat=board.create(calibrated=False,electrical=False,interlock=False)
    handler.display=screen.d
    host=transport(handler,board)
    assert host.show_object_label('CAT')
    assert screen.d.object_label=='CAT'
    assert host.serial.writes[:2]==[b'DISPLAY_CAPS\n',b'OBJECT_LABEL 4500 100 CAT\n']
    assert host.motion_owner=='PRESERVED_TEST_OWNER' and host.motion_epoch==123
    for ms in range(100,2300,100):screen.now[0]=ms;screen.d.update()
    assert screen.pixels and screen.calls==[]  # Never vendor blocking long-string show().
    assert host.show_object_label('DOG') and screen.d.object_label=='DOG'
    assert b'DISPLAY_CAPS\n' not in host.serial.writes[2:]
    board.command(handler,'PING');board.command(handler,'STOP')
    assert heartbeat.beats>=4 and screen.d.object_label is None and not board.pwms


def test_render_priority_replacement_expiry_and_no_queue(screen):
    d=screen.d;d.show_object_label('DINING TABLE',4500,100)
    screen.now[0]=100;d.update();offset=d.object_offset
    d.show_text('ERR',1000);screen.now[0]=200;d.update()
    assert screen.calls==['ERR'] and d.object_offset==offset
    d.message=None;d.capability_status('CAL READY');screen.now[0]=300;d.update()
    assert d.object_offset==offset
    d.capability_status(None);d.feedback(d.ERROR,1000);screen.now[0]=400;d.update()
    assert d.object_offset==offset
    for name in ('CAT','DOG','PERSON'):d.show_object_label(name)
    assert d.object_label=='PERSON' and not hasattr(d,'object_queue')
    screen.now[0]=5000;d.update();assert d.object_label is None
    d.show_object_label('CAT');d.status(d.NO_BRAIN);assert d.object_label is None


def test_legacy_firmware_is_not_sent_new_commands():
    host=RP2040Controller.__new__(RP2040Controller);host.connected=True;host.link_session='old'
    host._exchange=Mock(return_value='ERR UNKNOWN_COMMAND');host.motion_owner='KEEP';host.motion_epoch=3
    for _ in range(20):assert host.show_object_label('CAT') is False
    host._exchange.assert_called_once_with('DISPLAY_CAPS','DISPLAY_CAPS ',timeout=.15)
    assert host.motion_owner=='KEEP'
    host.link_session='new';host.show_object_label('DOG');assert host._exchange.call_count==2

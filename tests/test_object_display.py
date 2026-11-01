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
    return SimpleNamespace(d=module.Display(),now=now,pixels=pixels,calls=calls,module=module)


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


def test_canonical_observation_normalization_preserves_source_and_attention():
    from vision.object_observation import object_observation
    obs=dict(frame=dict(source='remote-eye',id='frame',geometry=[100,100],received_at=1,clock_domain='pi-monotonic'),
        objects=[dict(label='dining table',box=[10,10,90,90],confidence=.9)],qualification='unqualified')
    packet=object_observation(obs,dict(target=dict(id='attended',box=[10,10,90,90])))
    assert packet['source']=='remote-eye' and packet['attention_target']['id']=='attended'
    assert packet['objects'][0]['id']=='attended' and packet['objects'][0]['label']=='dining table'
    assert 'class hypothesis' in packet['identity']


def test_real_policy_events_to_real_uart_cat_and_dog(board,screen):
    _,_,handler,_=board.create(calibrated=False,electrical=False,interlock=False);handler.display=screen.d
    host=transport(handler,board);now=[0.];labels=ObjectLabels(host,clock=lambda:now[0])
    bus=StimulusBus();manager=AttentionManager(bus,mobile_enabled=False,object_labels=labels)
    for at,label in ((1,'cat'),(1.11,'cat'),(1.22,'cat'),(3.5,'dog'),(3.61,'dog'),(3.72,'dog')):
        now[0]=at;bus.emit('object_observation',packet(at,label));manager.update(None)
    wires=host.serial.writes
    assert b'OBJECT_LABEL 4500 100 CAT\n' in wires and b'OBJECT_LABEL 4500 100 DOG\n' in wires
    assert screen.d.object_label=='DOG' and manager.mobile is None and not board.pwms
    assert all(b'LOOK' not in w and b'ARM' not in w and b'MOVE' not in w for w in wires)


def test_dry_run_normal_main_never_opens_serial_or_camera(monkeypatch,capsys):
    import serial
    import socket
    from main import main
    monkeypatch.setattr(serial,'Serial',Mock(side_effect=AssertionError('physical serial not permitted')))
    monkeypatch.setattr(socket,'create_connection',Mock(side_effect=AssertionError('camera/control not permitted')))
    main(['--object-label-replay',str(ROOT/'tests/fixtures/object-display/cat-dog.jsonl')])
    rows=[json.loads(s) for s in capsys.readouterr().out.splitlines()]
    commands=[c for row in rows for c in row['outgoing']]
    assert commands==['DISPLAY_CAPS','OBJECT_LABEL 4500 100 CAT','OBJECT_CLEAR','OBJECT_LABEL 4500 100 DOG','OBJECT_CLEAR']
    serial.Serial.assert_not_called();socket.create_connection.assert_not_called()
    with pytest.raises(ValueError):main(['--object-label-replay','unused','--object-label-display','rp2040'])


def test_refresh_does_not_restart_firmware_scroll(screen):
    d=screen.d;d.show_object_label('PERSON')
    screen.now[0]=100;d.update();offset=d.object_offset
    assert offset==16
    screen.now[0]=200;d.show_object_label('PERSON')
    assert d.object_offset==offset and d.last_object_step==100 and d.object_until==4700
    d.show_object_label('DINING TABLE');assert d.object_offset==17 and d.last_object_step==200


@pytest.mark.parametrize('command',['OBJECT_LABEL 999999 100 CAT','OBJECT_LABEL 4500 0 CAT','OBJECT_LABEL 4500 100 CAT;STOP','OBJECT_LABEL 4500 100 '+'A'*25])
def test_bad_firmware_labels_cannot_change_motion(board,screen,command,capsys):
    a,_,handler,_=board.create(calibrated=False,electrical=False,interlock=False);handler.display=screen.d
    board.command(handler,command)
    assert 'ERR' in capsys.readouterr().out and screen.d.object_label is None and not board.pwms
    assert a.status()['state']=='DISARMED'


def test_stale_future_reordered_and_faults_do_not_hold_current_label():
    now,h,p=fake_policy();feed(now,p)
    p.observe(packet(99));p.tick();assert p.current is None
    h.show_object_label.reset_mock()
    now[0]=5;p.observe(packet(1));p.tick();h.show_object_label.assert_not_called()


def test_safety_suppression_and_failed_acks_are_bounded():
    now,h,p=fake_policy();feed(now,p)
    p.suppressed=True;p.tick();assert p.current is None
    assert h.clear_object_label.call_count==1
    p.suppressed=False;h.show_object_label.return_value=False
    for i in range(100):
        now[0]=3+i*.01;p.observe(packet(now[0],'dog'));p.tick()
    assert h.show_object_label.call_count<=3


def test_existing_primary_visual_target_selects_matching_object_not_strongest():
    now,h,p=fake_policy();bus=StimulusBus();manager=AttentionManager(bus,mobile_enabled=False,object_labels=p)
    manager.handle_event('vision_target',(900,360))
    for at in (1,1.11,1.22):
        now[0]=at
        observation=packet(at,'cat',score=.99,source='pi-primary')
        observation.update(geometry=[1280,720])
        observation['objects'][0]['box']=[0,0,200,200]
        observation['objects'].append(dict(id='attended-chair',label='chair',confidence=.8,prominence=.1,box=[800,300,1000,500]))
        manager.handle_event('object_observation',observation);p.tick()
    h.show_object_label.assert_called_once_with('CHAIR',4500,100)
    assert manager.mobile is None


def test_all_existing_model_classes_can_flow_without_new_inference():
    import numpy as np
    from vision.mobile_models import FixtureModel
    from vision.mobile_perception import MobileFrame,MobilePerception
    detector=FixtureModel([dict(label='chair',box=[1,1,10,10],confidence=.9)])
    detector.metadata['classes']=['chair']
    depth=FixtureModel(dict(kind='relative',valid=False))
    resources=SimpleNamespace(check=lambda **k:None)
    perception=MobilePerception(detector,depth,resources=resources,revision='explicit-fixture',clock=lambda:1.)
    result=perception.observe(MobileFrame('test',np.zeros((20,20,3),np.uint8),1))
    assert result['objects'][0]['label']=='chair'


def test_rp2040_scheduler_services_stop_and_ping_while_long_label_scrolls(board,screen,monkeypatch,capsys):
    import runpy
    from test_active_vision_firmware import load
    instances=[];base=board.module.ServoController
    class Controller(base):
        def __init__(self,**kw):
            super().__init__(clock=lambda:board.now[0],**kw);instances.append(self)
    board.module.ServoController=Controller
    for name in ('scanner','behaviors','commands'):
        monkeypatch.setitem(sys.modules,name,load('object_scheduler_'+name,'rp2040/'+name+'.py'))
    monkeypatch.setitem(sys.modules,'display',SimpleNamespace(Display=lambda:screen.d))
    monkeypatch.setitem(sys.modules,'heartbeat',SimpleNamespace(Heartbeat=lambda:SimpleNamespace(alive=lambda:True,beat=lambda:None)))
    lines=iter(['DISPLAY_CAPS\n','OBJECT_LABEL 4500 100 TRAFFIC LIGHT\n','PING\n','PING\n','STOP\n','PING\n'])
    monkeypatch.setattr(sys,'stdin',SimpleNamespace(readline=lambda:next(lines)))
    monkeypatch.setitem(sys.modules,'select',SimpleNamespace(POLLIN=1,poll=lambda:SimpleNamespace(register=lambda *a:None,poll=lambda _:True)))
    sleeps=[]
    class Finished(Exception):pass
    def sleep(ms):
        sleeps.append(ms);screen.now[0]+=100;board.now[0]+=20
        if len(sleeps)==6:raise Finished()
    monkeypatch.setattr('time.sleep_ms',sleep,raising=False)
    with pytest.raises(Finished):runpy.run_path(str(ROOT/'rp2040/main.py'))
    text=capsys.readouterr().out
    assert 'DISPLAY_CAPS' in text and 'OK OBJECT_LABEL' in text and 'OK STOP' in text and text.count('ALIVE')==3
    assert sleeps==[20]*6 and not board.pwms and len(instances)==1


def test_display_failure_cannot_prevent_existing_behavior_update_or_shutdown():
    labels=Mock();labels.observe.side_effect=ValueError('malformed observation');labels.tick.side_effect=OSError('serial offline');labels.close.side_effect=OSError('closed')
    bus=StimulusBus();manager=AttentionManager(bus,mobile_enabled=False,object_labels=labels)
    behavior=Mock();behavior.is_finished.return_value=False;manager.active=behavior
    mobile=Mock();manager.mobile=mobile
    bus.emit('object_observation',dict(objects=None))
    manager.update('fake-deck')
    behavior.update.assert_called_once_with('fake-deck');mobile.update.assert_called_once()
    manager.close();mobile.exit.assert_called_once()
    assert manager.object_display_error


@pytest.mark.parametrize('char', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ')
def test_mini_glyphs_are_complete_bounded_and_use_existing_pixel_rules(screen,char):
    font=screen.module._OBJECT_FONT
    assert set(font)==set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ')
    columns=font[char]
    assert 1<=len(columns)<=3 and all(type(c) is int and 0<=c<32 for c in columns)
    if char!=' ':
        assert columns[0] and columns[-1]
    else:assert columns==(0,)
    # Space is part of the font; normalized protocol labels cannot be blank.
    screen.d.object_label=char
    screen.d._draw_object_label(0)
    assert all(1<=y<=5 and b==20 for x,y,b in screen.pixels)
    assert screen.calls==[]


@pytest.mark.parametrize('label,width', [('',0),('I',1),(' ',1),('II',3),('I I',5),
    ('CAT',11),('CHAIR',17),('AAAAI',17),('AAA1I',16),('AAAA1',18),('PERSON',23),('CAT CAT',25)])
def test_actual_variable_width_has_one_gap_and_no_trailing_column(screen,label,width):
    assert screen.module._object_label_width(label)==width
    assert screen.module._object_label_width(label)==width
    assert len(screen.module._OBJECT_FONT['I'])==len(screen.module._OBJECT_FONT[' '])==1


@pytest.mark.parametrize('label,rows', [
    ('CAT',[('.##','#..','#..','#..','.##'),('.#.','#.#','###','#.#','#.#'),('###','.#.','.#.','.#.','.#.')]),
    ('CHAIR',[('.##','#..','#..','#..','.##'),('#.#','#.#','###','#.#','#.#'),
              ('.#.','#.#','###','#.#','#.#'),('#',)*5,('##.','#.#','##.','#.#','#.#')]),
])
def test_short_words_are_complete_centered_and_stationary_on_first_update(screen,label,rows):
    expected_rows=['.'.join(glyph[y] for glyph in rows) for y in range(5)]
    left=(17-len(expected_rows[0]))//2
    expected={(left+x,y+1,20) for y,row in enumerate(expected_rows) for x,value in enumerate(row) if value=='#'}
    d=screen.d;d.show_object_label(label)
    # Object rendering must not consult the vendor stock or blocking show().
    screen.module.matrix.wordStock=None
    for now in (100,200,300,1000):
        screen.pixels.clear();screen.now[0]=now;d.update()
        assert set(screen.pixels)==expected and len(screen.pixels)==len(expected)
        assert d.object_offset==17 and d.last_object_step==0
    assert screen.calls==[]


def test_exact_fit_static_and_one_column_over_scrolls_at_original_cadence(screen):
    d=screen.d;d.show_object_label('AAAAI',step_ms=200)
    screen.now[0]=100;d.update()
    assert min(x for x,y,b in screen.pixels)==0 and max(x for x,y,b in screen.pixels)==16
    assert d.object_offset==17
    d.show_object_label('AAAA1',step_ms=200)
    screen.pixels.clear();screen.now[0]=200;d.update()
    assert d.object_offset==17 and screen.pixels==[]
    screen.now[0]=300;d.update();assert d.object_offset==16
    assert screen.pixels and all(x==16 for x,y,b in screen.pixels)
    screen.now[0]=400;d.update();assert d.object_offset==16
    screen.now[0]=500;d.update();assert d.object_offset==15
    # A delayed update still takes one step; no catch-up loop or timing change.
    screen.now[0]=1500;d.update();assert d.object_offset==14


def test_long_label_scroll_reaches_true_final_column_before_reset(screen):
    d=screen.d;d.show_object_label('AAAA1')
    width=screen.module._object_label_width(d.object_label)
    assert width==18
    # Exercise the whole cycle at the existing 100 ms step, within original TTL.
    for step in range(1,17+width+2):
        screen.pixels.clear();screen.now[0]=step*100;d.update()
        offset=17-step
        if offset < -width:offset=17
        assert d.object_offset==offset
        assert all(0<=x<17 and 1<=y<=5 and b==20 for x,y,b in screen.pixels)
        if offset==1-width:
            assert screen.pixels==[(0,y,20) for y in range(1,6)]
        if offset in (-width,17):assert screen.pixels==[]
    screen.now[0]=3700;d.update();assert d.object_offset==16
    assert screen.calls==[] and d.object_label=='AAAA1'


def test_static_refresh_extends_original_ttl_without_repositioning_and_clear(screen):
    d=screen.d;d.show_object_label('CAT',ttl_ms=500)
    screen.now[0]=100;d.update();first=list(screen.pixels)
    screen.now[0]=400;d.show_object_label('CAT',ttl_ms=500)
    assert d.object_until==900 and d.last_object_step==0
    screen.pixels.clear();screen.now[0]=800;d.update();assert screen.pixels==first
    screen.now[0]=900;d.update();assert d.object_label is None
    d.show_object_label('CHAIR');d.clear_object_label()
    assert d.object_label is None and d.object_until==0 and d.object_offset==17


@pytest.mark.parametrize('priority', ['ERROR','NO_BRAIN','SLEEP','message','feedback','capability','progress'])
def test_existing_higher_priorities_never_enter_object_renderer(screen,monkeypatch,priority):
    d=screen.d
    if priority in ('ERROR','NO_BRAIN','SLEEP'):d.status(priority)
    elif priority=='message':d.show_text('TEXT')
    elif priority=='feedback':d.feedback(d.HAPPY)
    elif priority=='capability':d.capability_status('CAL READY')
    else:d.set_progress(50)
    d.show_object_label('CAT')
    render=Mock(side_effect=AssertionError('priority bypass'))
    monkeypatch.setattr(d,'_draw_object_label',render)
    screen.now[0]=100;d.update();render.assert_not_called()
    assert d.object_offset==17


def test_ordinary_text_retains_vendor_pages_and_700ms_page_timing(screen):
    d=screen.d;d.show_object_label('CAT');d.show_text('ABCDE',1800)
    for now in (100,700,1400):screen.now[0]=now;d.update()
    assert screen.calls==['ABC','DE','ABC'] and d.object_offset==17
    screen.now[0]=1900;d.update()
    assert d.message is None and screen.calls==['ABC','DE','ABC']
    assert screen.pixels and all(1<=y<=5 for x,y,b in screen.pixels)


def test_existing_pixel_clipping_and_half_brightness_cap_are_unchanged(screen):
    d=screen.d
    for x,y in [(-1,0),(17,0),(0,-1),(0,7)]:d._pixel(x,y,1000)
    assert screen.pixels==[]
    for value in (-10,15,40,80,255,1000):d._pixel(8,3,value)
    assert screen.pixels==[(8,3,b) for b in (0,7,20,40,127,127)]


@pytest.mark.parametrize('state,expected', [
    ('IDLE',[(8,3,6)]),
    ('SCAN',[(x,y,b) for y in range(7) for x,b in [(0,12),(0,55)]]),
    ('TRACK',[(8,3,75),(6,3,20),(10,3,20),(8,1,20),(8,5,20)]),
    ('HOME',[(0,3,50),(16,3,50),(8,3,12)]),
    ('SLEEP',[(8,3,7)]),
    ('ERROR',[(5+i,y,70) for i in range(7) for y in (i,6-i)]),
    ('THINK',[(5,3,65),(8,3,7),(11,3,7)]),
    ('HAPPY',[(6,1,65),(10,1,65),(5,4,35),(6,5,50),(7,5,60),(8,5,70),(9,5,60),(10,5,50),(11,4,35)]),
])
def test_existing_status_animation_pixels_at_frame_zero(screen,state,expected):
    screen.d._draw_named_state(state)
    assert screen.pixels==expected

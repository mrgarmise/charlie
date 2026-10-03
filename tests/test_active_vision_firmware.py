"""Execute unchanged firmware APIs with simulated PWM, no physical pins."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def firmware(monkeypatch):
    class PWM:
        def __init__(self,pin):self.values=[]
        def freq(self,value):pass
        def duty_u16(self,value):self.values.append(value)
    monkeypatch.setitem(sys.modules,'machine',SimpleNamespace(Pin=lambda pin:pin,PWM=PWM))
    config=load('config','rp2040/config.py')
    monkeypatch.setitem(sys.modules,'config',config)
    servos=load('servo_test','rp2040/servos.py').ServoController()
    monkeypatch.setitem(sys.modules,'protocol',SimpleNamespace(Command=object))
    commands=load('commands_test','rp2040/commands.py')
    behavior=SimpleNamespace(servos=servos,mode='TRACK',IDLE='IDLE')
    def mode(value):behavior.mode=value
    behavior.set_mode=mode
    handler=commands.CommandHandler(behavior,None,SimpleNamespace(beat=lambda:None))
    return servos,handler


def test_stop_freezes_all_servos_during_travel(firmware):
    servos,handler=firmware
    servos.look(160,140)
    for _ in range(5):servos.update()
    positions=[s.position for s in (servos.a_pan,servos.a_tilt,servos.b_pan,servos.b_tilt)]
    handler.handle(SimpleNamespace(name='STOP'))
    for _ in range(100):servos.update()
    for s,p in zip((servos.a_pan,servos.a_tilt,servos.b_pan,servos.b_tilt),positions):
        assert s.position==p and s.target==p and s.velocity==0


def test_no_overshoot_and_travel_limits(firmware):
    servos,_=firmware
    servos.look(999,-100)
    for _ in range(500):
        servos.update()
        assert 0<=servos.a_pan.position<=180
        assert 20<=servos.a_tilt.position<=160
    assert servos.a_pan.position==180 and servos.a_tilt.position==20


def test_stationary_status_reports_stop_capability(firmware,capsys):
    servos,handler=firmware
    handler.handle(SimpleNamespace(name='STOP'))
    handler.handle(SimpleNamespace(name='VIEWPOINT'))
    assert 'VIEWPOINT 90.0 90.0 90.0 90.0 0 IDLE DISARMED' in capsys.readouterr().out


def test_slew_limit_executed_in_firmware(firmware):
    servos,_=firmware
    servos.look(140,100,rate=10)
    for _ in range(50):
        previous=servos.a_pan.position
        servos.update()
        assert abs(servos.a_pan.position-previous)<=10/50+1e-8


def test_protocol_accepts_position_query(firmware,monkeypatch):
    protocol=load('active_protocol','rp2040/protocol.py')
    assert protocol.parse('VIEWPOINT').name=='VIEWPOINT'
    assert protocol.parse('LOOK 100.5 90.2 15').arg_float(0)==100.5


def test_shared_host_transport_reads_measured_pose(monkeypatch):
    from hardware.rp2040_controller import RP2040Controller
    import threading
    class Serial:
        timeout=1
        def __init__(self):self.lines=iter([b'ALIVE\n',b'OK STOP\n',b'VIEWPOINT 91.5 89.5 91.5 89.5 0 IDLE STOP_HOLD\n'])
        def write(self,data):assert data==b'VIEWPOINT\n'
        def readline(self):return next(self.lines)
    controller=RP2040Controller.__new__(RP2040Controller)
    controller.serial=Serial();controller.lock=threading.Lock();controller.connected=True
    state=controller.viewpoint_status()
    assert state['pan']==91.5 and state['b_tilt']==89.5 and state['stop_hold']
    assert not state['moving'] and controller.serial.timeout==1


def test_legacy_integer_look_wire_format_is_preserved():
    from hardware.rp2040_controller import RP2040Controller
    controller=RP2040Controller.__new__(RP2040Controller)
    sent=[];controller.send=lambda command:sent.append(command) or True
    assert controller.look(102,87)
    assert sent==['LOOK 102 87']
    assert controller.look(102.5,87.5,rate=15)
    assert sent[-1]=='LOOK 102.5 87.5 15.0'


def test_optional_look_rate_routes_through_existing_handler(firmware):
    servos,handler=firmware
    protocol=load('look_protocol','rp2040/protocol.py')
    handler.behaviors.gaze=lambda pan,tilt,rate=None:servos.look(pan,tilt,rate)
    handler.handle(protocol.parse('LOOK 102.5 88.5 15'))
    assert servos.a_pan.target==102.5 and servos.a_tilt.target==88.5
    assert servos.a_pan.speed_limit==15/50


def test_actual_watchdog_loop_stops_once_and_does_not_resume_scan():
    import ast
    tree=ast.parse((ROOT/'rp2040/main.py').read_text())
    loop=next(n for n in tree.body if isinstance(n,ast.While))
    calls=[];states=iter([False,False,True]);ticks=[]
    behavior=SimpleNamespace(mode='SCAN',IDLE='IDLE',update=lambda:None)
    behavior.set_mode=lambda mode:setattr(behavior,'mode',mode)
    def sleep(milliseconds):
        ticks.append(milliseconds)
        if len(ticks)==3:raise StopIteration
    environment=dict(link_lost=False,poll=SimpleNamespace(poll=lambda _:False),
        behaviors=behavior,servos=SimpleNamespace(update=lambda:None,stop=lambda:calls.append('stop')),
        display=SimpleNamespace(update=lambda:None,NO_BRAIN='NO_BRAIN',status=lambda value:calls.append(value)),
        heartbeat=SimpleNamespace(alive=lambda:next(states)),gc=SimpleNamespace(collect=lambda:None),
        time=SimpleNamespace(sleep_ms=sleep))
    with pytest.raises(StopIteration):
        exec(compile(ast.Module(body=[loop],type_ignores=[]),'<actual firmware loop>','exec'),environment)
    assert calls==['stop','NO_BRAIN','IDLE'] and behavior.mode=='IDLE'


def test_disarmed_viewpoint_is_not_motion_authorization():
    """Recovery firmware must be recognized but never treated as motion-ready."""
    from hardware.rp2040_controller import RP2040Controller
    import threading

    class Serial:
        timeout = 1

        def __init__(self):
            self.lines = iter([
                b'VIEWPOINT 138.0 90.0 138.0 90.0 0 IDLE DISARMED\n'
            ])

        def write(self, data):
            assert data == b'VIEWPOINT\n'

        def readline(self):
            return next(self.lines)

    controller = RP2040Controller.__new__(RP2040Controller)
    controller.serial = Serial()
    controller.lock = threading.Lock()
    controller.connected = True

    status = controller.viewpoint_status()

    assert status is not None
    assert status['disarmed'] is True
    assert status['stop_hold'] is False
    assert status['pose_verified'] is False
    assert status['pan'] == 138.0
    assert status['moving'] is False

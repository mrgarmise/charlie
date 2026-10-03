"""RP2040 authority exercised with simulated time, local input and PWM only."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]
PROFILE=dict(assembled_head_verified=True,calibration_id='SIMULATED_001',pins=[4,5],
    pan=dict(min=85,max=95,min_us=1000,max_us=2000),
    tilt=dict(min=85,max=95,min_us=1000,max_us=2000),
    confirmed_arm_pose=[90,90],home_pose=[90,90],max_rate=5,max_step=2)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.fixture
def board(monkeypatch):
    now=[0];pressed=[False];pwms=[];pins=[]
    class PWM:
        def __init__(self,pin):self.pin=pin;self.values=[];self.disabled=False;pwms.append(self)
        def freq(self,value):self.frequency=value
        def duty_u16(self,value):self.values.append(value)
        def deinit(self):self.disabled=True
    def pin(number):pins.append(number);return number
    monkeypatch.setattr('time.ticks_ms',lambda:now[0],raising=False)
    monkeypatch.setattr('time.ticks_diff',lambda a,b:a-b,raising=False)
    config=load('motion_config','rp2040/config.py')
    profile=load('motion_profile','rp2040/motion_profile.py')
    monkeypatch.setitem(sys.modules,'config',config)
    monkeypatch.setitem(sys.modules,'motion_profile',profile)
    module=load('authority_test','rp2040/servos.py')
    monkeypatch.setitem(sys.modules,'servos',module)
    monkeypatch.setitem(sys.modules,'protocol',load('actual_protocol','rp2040/protocol.py'))
    scanner=load('scanner_test','rp2040/scanner.py')
    behaviors=load('behavior_test','rp2040/behaviors.py')
    commands=load('command_test','rp2040/commands.py')
    def create(calibrated=True,electrical=True,interlock=True):
        authority=module.ServoController(PROFILE if calibrated else None,
            electrical_gate=electrical,arm_input=(lambda:pressed[0]) if interlock else None,
            clock=lambda:now[0],pwm_factory=PWM,pin_factory=pin)
        behavior=behaviors.BehaviorManager(servos=authority,scanner=scanner.Scanner(authority))
        heartbeat=SimpleNamespace(beats=0)
        heartbeat.beat=lambda:setattr(heartbeat,'beats',heartbeat.beats+1)
        handler=commands.CommandHandler(behavior,None,heartbeat)
        return authority,behavior,handler,heartbeat
    def press(authority):
        pressed[0]=False
        for _ in range(3):now[0]+=20;authority.update()
        pressed[0]=True
        for _ in range(3):now[0]+=20;authority.update()
    def arm(authority):
        authority.establish_session('session_1234')
        press(authority)
        assert authority.status()['armed']
    def auth(authority,owner='ACTIVE_VISION',transition='INITIAL'):
        authority.authorize(owner,'session_1234',authority.status()['epoch'],transition)
        return dict(session='session_1234',epoch=authority.status()['epoch'])
    def command(handler,line):handler.handle(sys.modules['protocol'].parse(line))
    return SimpleNamespace(create=create,press=press,arm=arm,auth=auth,command=command,
        now=now,pressed=pressed,pwms=pwms,pins=pins,module=module,profile=profile)


def test_startup_creates_no_pwm_or_actuator_pin(board):
    a,_,_,_=board.create(calibrated=False,electrical=False,interlock=False)
    for _ in range(100):a.update()
    assert board.pwms==board.pins==[]
    assert a.status()['state']=='DISARMED' and a.status()['envelope'] is None
    assert all(s.pwm is None for s in (a.a_pan,a.a_tilt,a.b_pan,a.b_tilt))


@pytest.mark.parametrize('missing',['calibration','electrical','interlock','session'])
def test_local_button_cannot_bypass_any_prerequisite(board,missing):
    a,_,_,_=board.create(calibrated=missing!='calibration',electrical=missing!='electrical',interlock=missing!='interlock')
    if missing!='session':a.establish_session('session_1234')
    board.press(a)
    assert not a.status()['armed'] and not board.pwms


def test_held_button_on_boot_cannot_arm(board):
    a,_,_,_=board.create();a.establish_session('session_1234')
    board.pressed[0]=True
    for _ in range(20):a.update()
    assert not board.pwms
    board.press(a)
    assert [p.pin for p in board.pwms]==[4,5]


@pytest.mark.parametrize('method', ['look','home','head_a','head_b','write','move_to','servo_update'])
def test_direct_paths_cannot_bypass_default_lockout(board,method):
    a,_,_,_=board.create(calibrated=False,electrical=False,interlock=False)
    action={'look':lambda:a.look(91,90),'home':a.home,'head_a':lambda:a.head_a(91,90),
        'head_b':lambda:a.head_b(91,90),'write':lambda:a.a_pan.write(91),
        'move_to':lambda:a.a_pan.move_to(91),'servo_update':a.a_pan.update}[method]
    with pytest.raises(RuntimeError):action()
    assert not board.pwms and a.a_pan.target==90


def test_local_physical_arm_is_not_active_vision_authorization(board):
    a,_,_,_=board.create();board.arm(a)
    assert a.status()['owner'] is None
    with pytest.raises(RuntimeError,match='AUTHORIZATION'):a.look(91,90)
    assert a.a_pan.target==90 and a.a_pan.pwm=='AUTHORITY_OWNED'
    assert not hasattr(a.a_pan.pwm,'duty_u16')


@pytest.mark.parametrize('pan,tilt,rate', [(96,90,5),(90,84,5),(float('nan'),90,5),
    (90,float('inf'),5),(True,90,5),('garbage',90,5),(91,90,float('nan')),
    (91,90,6),(91,90,0),(94,90,5)])
def test_requests_reject_instead_of_clamping(board,pan,tilt,rate):
    a,_,_,_=board.create();board.arm(a);context=board.auth(a)
    before=[list(p.values) for p in board.pwms]
    with pytest.raises(RuntimeError):a.look(pan,tilt,rate,**context)
    assert a.a_pan.target==90 and [p.values for p in board.pwms]==before


def test_rate_bound_no_overshoot_and_head_b_never_activated(board):
    a,_,_,_=board.create();board.arm(a);context=board.auth(a)
    a.look(91,91,5,**context)
    for _ in range(100):
        previous=[a.a_pan.position,a.a_tilt.position]
        board.now[0]+=20;a.update()
        assert sum(abs(x-y) for x,y in zip(previous,[a.a_pan.position,a.a_tilt.position]))<=.1+1e-8
        assert a.a_pan.position<=91 and a.a_tilt.position<=91
    assert a.a_pan.position==pytest.approx(91) and a.a_tilt.position==pytest.approx(91)
    assert board.pins==[4,5] and a.b_pan.pwm is None and a.b_tilt.pwm is None
    with pytest.raises(RuntimeError,match='HEAD_B'):a.b_pan.write(90,**context)


def test_stop_disables_both_pwm_cancels_target_and_revokes_epoch(board):
    a,_,_,_=board.create();board.arm(a);context=board.auth(a)
    a.look(92,90,**context);board.now[0]+=20;a.update();position=a.a_pan.position
    a.stop();board.now[0]+=100;a.update()
    assert a.a_pan.position==a.a_pan.target==position and a.a_pan.velocity==0
    assert all(p.disabled and p.values[-1]==0 for p in board.pwms)
    assert a.status()['owner'] is None and not a.status()['armed']
    # A button held through STOP cannot re-arm.
    for _ in range(10):a.update()
    assert len(board.pwms)==2
    board.press(a)
    with pytest.raises(RuntimeError):a.look(91,90,**context)


def test_watchdog_is_checked_before_late_ping_and_reconnect_never_resumes(board):
    a,_,h,_=board.create();board.arm(a);context=board.auth(a);a.look(92,90,**context)
    board.now[0]+=10001;board.command(h,'PING')
    assert not a.status()['armed'] and all(p.disabled for p in board.pwms)
    board.command(h,'SESSION new_session_123')
    assert not a.status()['armed'] and not a.status()['owner']
    board.press(a)
    with pytest.raises(RuntimeError):a.look(91,90,**context)


@pytest.mark.parametrize('line',['ARM','LOOK nan 90','LOOK 90','LOOK 91 90','TRACK 91 90',
    'HOME','SCAN','MOVE session_1234 3 91 90 nan','AUTHORIZE ACTIVE_VISION session_1234 nan INITIAL',
    'PING extra','STOP extra','BANANA','LOOK '+('1'*150)+' 90'])
def test_malformed_or_unauthorized_protocol_does_not_move(board,line,capsys):
    a,_,h,heartbeat=board.create();board.arm(a)
    before=a.status();beats=heartbeat.beats
    board.command(h,line)
    assert 'ERR' in capsys.readouterr().out
    assert a.a_pan.target==90 and heartbeat.beats==beats
    assert a.status()['epoch']==before['epoch']


def test_scoped_protocol_and_behavior_scan_share_authority(board,capsys):
    a,b,h,_=board.create();board.arm(a);rev=a.status()['epoch']
    board.command(h,f'AUTHORIZE ACTIVE_VISION session_1234 {rev} INITIAL')
    board.command(h,f'LOOK 91 90 5 session_1234 {rev}')
    assert a.a_pan.target==91
    a.stop();board.press(a);rev=a.status()['epoch'];board.auth(a,'LEGACY')
    board.command(h,f'SCAN session_1234 {rev}')
    for _ in range(100):board.now[0]+=20;b.update();a.update()
    assert 85<=a.a_pan.target<=95 and b.mode=='SCAN'
    a.stop();b.update()
    assert b.mode=='IDLE' and all(p.disabled for p in board.pwms)
    with pytest.raises(RuntimeError):b.set_mode('SCAN')


def test_primary_transition_and_degradation_reacquisition(board):
    a,_,_,_=board.create();board.arm(a);context=board.auth(a);a.look(91,90,**context)
    a.primary_acquire(**context)
    assert a.status()['task']=='PRIMARY' and not a.status()['pwm_active']
    board.press(a)
    with pytest.raises(RuntimeError,match='DEGRADATION'):board.auth(a)
    context=board.auth(a,transition='DEGRADATION')
    a.look(91,90,**context)
    assert a.status()['owner']=='ACTIVE_VISION'


def test_invalid_profile_cannot_create_pwm(board):
    invalid=copy.deepcopy(PROFILE);invalid['pan']['min']=float('nan')
    with pytest.raises(RuntimeError):board.module.ServoController(invalid)
    invalid=copy.deepcopy(PROFILE);invalid['pins']=[14,15]
    with pytest.raises(RuntimeError):board.module.ServoController(invalid)
    assert not board.pwms


def test_pose_telemetry_states_estimates_not_measurements(board,capsys):
    a,b,h,_=board.create(calibrated=False,electrical=False,interlock=False)
    board.command(h,'VIEWPOINT');board.command(h,'MOTION_STATUS')
    lines=capsys.readouterr().out.splitlines()
    assert 'VIEWPOINT 90.0 90.0 90.0 90.0 0 IDLE DISARMED'==lines[0]
    status=json.loads(lines[1].split(' ',1)[1])
    assert status['pose_source']=='commanded_estimate' and status['measured_position'] is None
    assert status['pose_verified'] is False and status['inactive_pins']==[14,15]


def test_direct_servo_construction_is_not_an_alternate_controller(board):
    with pytest.raises(RuntimeError):board.module.Servo(4)
    assert not board.pwms


def test_buzzer_library_also_creates_no_startup_pwm():
    tree=ast.parse((ROOT/'rp2040/lib/Pico_ed.py').read_text())
    music=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Music')
    namespace={'PWM':lambda *_:pytest.fail('startup PWM'),'Pin':lambda *_:pytest.fail('startup pin')}
    exec(compile(ast.Module(body=[music],type_ignores=[]),'<real music class>','exec'),namespace)
    assert namespace['Music']().buzzer is None


def test_stop_attempts_both_output_disables_even_on_error(board):
    a,_,_,_=board.create();board.arm(a)
    board.pwms[0].duty_u16=lambda _:(_ for _ in ()).throw(OSError('driver'))
    with pytest.raises(RuntimeError,match='PWM_DISABLE'):a.stop()
    assert all(p.disabled for p in board.pwms) and not a.status()['armed']


def transport(board):
    """Use the real Pi transport against the real handler via simulated UART."""
    import contextlib,io,threading
    from hardware.rp2040_controller import RP2040Controller
    authority,behavior,handler,_=board.create()
    class Serial:
        timeout=1
        def __init__(self):self.lines=[];self.closed=False;self.writes=[]
        def write(self,data):
            self.writes.append(data)
            board.now[0]+=20;authority.update()
            captured=io.StringIO()
            with contextlib.redirect_stdout(captured):board.command(handler,data.decode().strip())
            self.lines.extend((line+'\n').encode() for line in captured.getvalue().splitlines())
        def readline(self):return self.lines.pop(0) if self.lines else b''
        def close(self):self.closed=True
    host=RP2040Controller.__new__(RP2040Controller)
    host.connected=True;host.serial=Serial();host.lock=threading.Lock();host.last_tx=0
    host.link_session='session_1234';host.motion_epoch=host.motion_owner=None
    authority.establish_session(host.link_session)
    return host,authority,behavior


def test_host_requests_never_physically_arm(board):
    host,a,_=transport(board)
    assert not host.request_active_vision()
    assert host.send('ARM')
    assert host.motion_status()['state']=='DISARMED' and not board.pwms
    board.press(a)
    assert host.request_active_vision()
    assert host.look(91,90,rate=5)
    assert a.a_pan.target==91
    assert host.stop()
    status=host.motion_status()
    assert not status['pwm_active'] and not status['armed']
    assert status['owner'] is None and host.motion_epoch is None


def test_host_reconnection_sends_stop_new_session_and_clears_authority(board,monkeypatch):
    host,a,_=transport(board);board.press(a);assert host.request_active_vision()
    host.look(91,90,rate=5)
    old=host.serial
    new=type(old)()
    monkeypatch.setattr('hardware.rp2040_controller.serial.Serial',lambda *_args,**_kw:new)
    monkeypatch.setattr('hardware.rp2040_controller.time.sleep',lambda _:None)
    host.port='SIMULATED';host.baud=115200
    assert host.connect()
    assert new.writes[0]==b'STOP\n' and new.writes[1].startswith(b'SESSION ')
    assert old.closed and host.motion_owner is None and host.motion_epoch is None
    assert not a.status()['armed'] and a.status()['owner'] is None
    assert a.a_pan.target==a.a_pan.position


def test_legacy_pose_reply_is_estimate_and_not_authorization(board):
    host,a,_=transport(board)
    status=host.viewpoint_status()
    assert status['disarmed'] and status['pose_verified'] is False
    assert status['pose_source']=='commanded_estimate' and status['measured_position'] is None
    assert not status['stop_hold']


def test_primary_cancels_host_scope_and_requires_degradation(board):
    host,a,_=transport(board);board.press(a);assert host.request_active_vision()
    old=host.motion_epoch
    assert host.primary_ownership()
    assert a.status()['task']=='PRIMARY' and not a.status()['pwm_active']
    board.press(a)
    assert not host.request_active_vision('INITIAL')
    assert host.request_active_vision('DEGRADATION')
    assert host.motion_epoch!=old


def test_complete_safe_authority_optimizer_primary_and_reacquisition(board,tmp_path):
    from experiments.ppal.eyes.active_vision import ActiveVision,DegradationGate,apply_validated_view
    from experiments.ppal.eyes.simulate_active_vision import SimulatedCamera
    from experiments.ppal.eyes.camera_lease import CameraLease
    host,a,_=transport(board);board.press(a)
    sources=[]
    def source_factory():
        head=SimpleNamespace()
        class Pose:
            @property
            def pose(self):return (a.a_pan.position,a.a_tilt.position)
        source=SimulatedCamera(Pose(),optimum=(94,90))
        lease=CameraLease(directory=tmp_path,role='active_vision')
        source.camera=SimpleNamespace(lease=lease)
        original=source.close
        source.close=lambda:(original(),lease.close())
        sources.append(source)
        return source
    def wait(seconds):
        board.now[0]+=int(seconds*1000);a.update()
    optimizer=ActiveVision(source_factory,host,tmp_path/'first',initial_pose=(90,90),
        authorized=True,wait=wait)
    result=optimizer.run()
    assert result['state']=='LOCKED' and result['resources_released']
    assert result['pose'][0]>90 and sources[-1].closed
    assert not a.status()['armed'] and not a.status()['pwm_active']
    assert host.primary_ownership()
    primary=CameraLease(directory=tmp_path)
    before=optimizer.samples
    primary.close()
    gate=DegradationGate(persistence=3,severe=5)
    ref=[[.1,.1],[.9,.1],[.9,.9],[.1,.9]]
    moved=[[x+.1,y] for x,y in ref]
    for tick in range(3):outcome=gate.observe(ref,moved,now=tick+1,authorized=True)
    assert outcome=='reacquire'
    board.press(a)
    second=ActiveVision(source_factory,host,tmp_path/'second',initial_pose=(90,90),
        authorized=True,reacquisition=gate.reacquisition_permit(),wait=wait)
    assert second.run()['state']=='LOCKED'
    assert optimizer.samples==before and not a.status()['pwm_active']


def test_physical_config_cannot_expand_firmware_calibration(board,tmp_path):
    from experiments.ppal.eyes.active_vision import ActiveVision,Config
    host,a,_=transport(board);board.press(a)
    opened=[]
    av=ActiveVision(lambda:opened.append(True),host,tmp_path/'wide',initial_pose=(90,90),
        authorized=True,config=Config())
    with pytest.raises(ValueError,match='exceeds RP2040'):av.run()
    assert not opened and not a.status()['armed']


def test_rollback_boots_recovery_without_pwm(board,tmp_path):
    """Execute preserved recovery servos from git with simulated machine API."""
    import subprocess
    recovery=subprocess.check_output(['git','show','8777955:rp2040/servos.py'],cwd=ROOT).decode()
    machine=SimpleNamespace(Pin=lambda *_:pytest.fail('recovery GPIO'),
        PWM=lambda *_:pytest.fail('recovery PWM'))
    import unittest.mock
    with unittest.mock.patch.dict(sys.modules,{'machine':machine}):
        namespace={};exec(compile(recovery,'<preserved recovery>','exec'),namespace)
        old=namespace['ServoController']()
        old.update();old.stop()
        assert all(s.pwm is None for s in (old.a_pan,old.a_tilt,old.b_pan,old.b_tilt))
        with pytest.raises(RuntimeError):old.look(90,90)


@pytest.mark.parametrize('initially_armed', [False, True])
def test_real_main_scheduler_expires_before_arriving_ping(board, monkeypatch, initially_armed):
    """Execute the shipped scheduler; only display, UART and time are fake."""
    a, _, _, _ = board.create(calibrated=initially_armed,
                              electrical=initially_armed, interlock=initially_armed)
    if initially_armed:
        board.arm(a)
        a.look(92, 90, **board.auth(a))
    monkeypatch.setattr(board.module, 'ServoController', lambda **_: a)
    for name in ('scanner', 'behaviors', 'commands', 'heartbeat'):
        monkeypatch.setitem(sys.modules, name, load('scheduler_' + name, 'rp2040/' + name + '.py'))
    display = SimpleNamespace(NO_BRAIN='NO_BRAIN', status=lambda _: None, update=lambda: None)
    monkeypatch.setitem(sys.modules, 'display', SimpleNamespace(Display=lambda: display))
    cycles = [0]
    class Poll:
        def register(self, *_): pass
        def poll(self, _):
            if cycles[0] == 1:
                # This arriving heartbeat cannot rescue the expired motion.
                assert not a.status()['armed']
                return [1]
            return []
    monkeypatch.setattr('select.poll', Poll)
    monkeypatch.setattr(sys, 'stdin', SimpleNamespace(readline=lambda: 'PING\n'))
    class EndScheduler(BaseException): pass
    def sleep(_):
        cycles[0] += 1
        board.now[0] += 10001 if cycles[0] == 1 else 20
        if cycles[0] == 3: raise EndScheduler()
    monkeypatch.setattr('time.sleep_ms', sleep, raising=False)
    namespace = {}
    with pytest.raises(EndScheduler):
        exec(compile((ROOT/'rp2040/main.py').read_text(), '<real scheduler>', 'exec'), namespace)
    assert namespace['behaviors'].mode == 'IDLE'
    assert not a.status()['armed'] and a.status()['owner'] is None
    assert a.a_pan.target == a.a_pan.position
    assert all(p.disabled for p in board.pwms)
    if not initially_armed: assert board.pins == board.pwms == []

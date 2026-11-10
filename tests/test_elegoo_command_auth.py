import hashlib
import hmac
import pytest
from hardware.elegoo_command_auth import CommandAuthenticator
from hardware.elegoo_mobile import ElegooMobileBase

TOKEN='A'*43
NONCE='0102030405060708090a0b0c0d0e0f10'
FRAME=b'{"N":2,"H":"pulse1","D1":3,"D2":20,"T":100}'

def test_exact_frame_binding_sequence_reset_and_denial():
    auth=CommandAuthenticator(TOKEN,clock=lambda:0)
    assert auth.wrap(b'{Heartbeat}',qualified=False)==b'{Heartbeat}'
    with pytest.raises(PermissionError):auth.wrap(FRAME,qualified=False)
    assert auth.challenge('{Challenge:'+NONCE+':0}')
    for sequence in (1,2):
        tag=hmac.new(TOKEN.encode(),f'charlie-elegoo-command-v1\n{NONCE}\n{sequence}\n100\n'.encode()+FRAME,hashlib.sha256).hexdigest()
        assert auth.wrap(FRAME,qualified=True)==f'{{Auth:{sequence}:100:{tag}}}'.encode()+FRAME
    auth.challenge('{Challenge:'+NONCE+':0}')
    with pytest.raises(PermissionError):auth.wrap(FRAME,qualified=True)
    auth.reset()
    with pytest.raises(PermissionError):auth.wrap(FRAME,qualified=True)

class Socket:
    def __init__(self):self.writes=[]
    def sendall(self,raw):self.writes.append(raw)

def test_existing_wire_guard_after_challenge_and_no_auth_logging():
    car=ElegooMobileBase(command_key=TOKEN)
    car.sock=Socket();car._running=True
    car._qualified_owner=object() # fixture for constructor-bound executor
    car._handle_frame('{Challenge:'+NONCE+':0}')
    with pytest.raises(InterruptedError):car._send_raw(FRAME,preflight=lambda:False)
    assert car.sock.writes==[]
    car._send_raw(FRAME,preflight=lambda:True)
    assert car.sock.writes[0].startswith(b'{Auth:2:')
    assert all('Auth:' not in str(row) and TOKEN not in str(row) for row in car.wire_history()['events'])
    with pytest.raises(PermissionError):car._send_raw(FRAME)

def test_stop_no_qualification_and_no_legacy_fallback():
    car=ElegooMobileBase(command_key=TOKEN);car.sock=Socket();car._running=True
    stop=b'{"N":1,"H":"stop1","D1":0,"D2":0,"D3":0}'
    car._send_raw(stop)
    assert car.sock.writes==[stop]
    with pytest.raises(PermissionError):car._send_raw(b'{"N":3,"D1":3,"D2":20}')
    with pytest.raises(PermissionError):car.bind_qualified_executor(object())

@pytest.mark.parametrize('token',['', 'x'*42, 'x'*65, 'bad secret'*6])
def test_token_bounds(token):
    with pytest.raises(ValueError):CommandAuthenticator(token)

def test_real_executor_binding_admission_before_existing_transport():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from stimulus.bus import StimulusBus, Observation
    from motion.elegoo_executor import QualifiedElegooExecutor, ActuatorRequest
    from experiments.ppal.mobile_navigation import MotionLease
    bus=StimulusBus();owner=object()
    bus.claim_observations('fixture',owner,metadata={'modality':'test'})
    bus.publish_observation('fixture',owner,Observation('fixture',1,10.,{}, {},'g'))
    car=ElegooMobileBase(command_key=TOKEN)
    base=SimpleNamespace(car=car,connect=Mock(),stop_verified=Mock(return_value={'acknowledged':True}))
    executor=QualifiedElegooExecutor(base,bus=bus,clock=lambda:10.)
    request=ActuatorRequest('r','fixture','chassis','pulse',10.,'fixture','g:1',
                            {'direction':'FORWARD','pwm':20,'seconds':.1})
    with pytest.raises(PermissionError):executor.request(request)
    base.connect.assert_not_called()
    assert car._qualified_owner is executor
    authority=Mock();authority.safe.return_value=True
    authority.admit.return_value=dict(group='chassis',request_id='r',
        lease=MotionLease('supervised_trial',11.,'fixture-only',executor.boot_id),
        envelope=dict(max_duration=.2,max_pwm=35,directions=['FORWARD']))
    executor.authority=authority
    def connect():
        car.sock=Socket();car._running=True;car._handle_frame('{Challenge:'+NONCE+':0}')
    base.connect.side_effect=connect
    def pulse(*args,**kwargs):
        assert kwargs['_executor'] is executor and kwargs['safety_check']()
        car._send_raw(FRAME,preflight=kwargs['safety_check'])
        return {'acknowledged':True,'stop':{'acknowledged':True}}
    base.pulse=pulse
    assert executor.request(request)['acknowledged']
    assert car.sock.writes[0].startswith(b'{Auth:1:')
    authority.admit.assert_called_once()

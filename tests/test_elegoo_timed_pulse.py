"""Device-free stock N2 protocol simulation, not physical stopping evidence."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from hardware.elegoo_mobile import ElegooMobileBase
from experiments.ppal.mobile_navigation import MotionLease
from motion.mobile_base import MobileBase
from motion.elegoo_executor import ActuatorRequest, QualifiedElegooExecutor
from stimulus.bus import StimulusBus, Observation


class Peer:
    def __init__(self,monkeypatch,*,ack='valid',stop_ack='valid'):
        self.now=10.;self.commands=[];self.due=[];self.ack=ack;self.stop_ack=stop_ack;self.on_tick=lambda:None
        peer=self
        class Event:
            def __init__(self):self.flag=False
            def set(self):self.flag=True
            def is_set(self):return self.flag
            def wait(self,timeout):
                if not self.flag:
                    peer.now+=timeout;peer.on_tick();peer.deliver()
                return self.flag
        monkeypatch.setattr('hardware.elegoo_mobile.threading.Event',Event)
        self.car=ElegooMobileBase();self.car.sock=SimpleNamespace(sendall=self.sendall);self.car._running=True
        self.car.connect=Mock(side_effect=AssertionError('no physical connection/reconnect'))

    def clock(self):return self.now

    def sendall(self,raw):
        payload=json.loads(raw);self.commands.append(payload)
        if payload['N']==2:
            ident=payload['H'];kind=self.ack
            reply={'valid':'{'+ident+'_ok}','early':'{'+ident+'_ok}',
                   'bare':'{ok}','wrong_value':'{'+ident+'_error}','wrong_id':'{another_ok}'}
            if kind=='early':self.car._handle_frame(reply[kind])
            elif kind!='missing':self.due.append((self.now+payload['T']/1000.+.005,reply[kind]))
        elif payload['N']==1:
            if self.stop_ack=='valid':self.car._handle_frame('{'+payload['H']+'_ok}')
            elif self.stop_ack=='bare':self.car._handle_frame('{ok}')
        elif payload['N']==21:
            self.car._handle_frame('{'+payload['H']+'_123}')
        else:raise AssertionError('unexpected command, especially unlimited N3')

    def deliver(self):
        for at,reply in list(self.due):
            if self.now>=at:
                self.due.remove((at,reply));self.car._handle_frame(reply)

    def pulse(self,**changes):
        options=dict(pwm=30,seconds=.1,lease=MotionLease('supervised_trial',11.,'fixture','boot'),
            boot_id='boot',envelope={'max_pwm':35,'max_duration':.2},safety_check=lambda:True,clock=self.clock)
        options.update(changes)
        return self.car.pulse('LEFT',**options)


@pytest.mark.parametrize('seconds,milliseconds',[(.001,1),(.0019,1),(.029,29),(.1,100),(.2,200)])
def test_millisecond_bound_and_completion_then_independent_stop(monkeypatch,seconds,milliseconds):
    peer=Peer(monkeypatch);result=peer.pulse(seconds=seconds)
    assert [p['N'] for p in peer.commands]==[2,1]
    assert peer.commands[0]['T']==milliseconds
    assert 0<peer.commands[0]['T']<=seconds*1000
    assert result['acknowledged'] and result['timed_completion']
    assert result['stop']['acknowledged'] and result['stop']['physically_stopped'] is None
    assert result['executed'] is None and result['physically_observed'] is None
    assert peer.now>=10.+milliseconds/1000.
    peer.car.connect.assert_not_called()


@pytest.mark.parametrize('seconds',[0,-.1,.00001,.000999,.200001,True,float('nan'),float('inf')])
def test_invalid_zero_or_unbounded_timer_never_reaches_wire(monkeypatch,seconds):
    peer=Peer(monkeypatch)
    with pytest.raises(ValueError):peer.pulse(seconds=seconds)
    assert not peer.commands


@pytest.mark.parametrize('ack',['early','bare','wrong_value','wrong_id','missing'])
def test_bad_or_missing_completion_is_ambiguous_and_stops(monkeypatch,ack):
    peer=Peer(monkeypatch,ack=ack)
    with pytest.raises(TimeoutError):peer.pulse()
    assert [p['N'] for p in peer.commands]==[2,1]
    assert peer.car.last_pulse['acknowledged'] is False
    assert peer.car.last_pulse['timed_completion'] is False
    assert peer.car.last_pulse['error']=='TimeoutError'
    assert peer.car.last_pulse['stop']['physically_stopped'] is None
    assert not peer.car._pending


@pytest.mark.parametrize('change',['cancel','lease','safety','disconnect'])
def test_waiting_completion_keeps_safety_and_cancellation_live(monkeypatch,change):
    peer=Peer(monkeypatch);cancel=SimpleNamespace(is_set=lambda:False);safe=[True]
    def tick():
        if peer.now>=10.03:
            if change=='cancel':cancel.is_set=lambda:True
            elif change=='safety':safe[0]=False
            elif change=='disconnect':peer.car._running=False
    peer.on_tick=tick
    lease=MotionLease('supervised_trial',10.12 if change=='lease' else 11.,'fixture','boot')
    # A missing reply keeps the waiter active through expiry.
    peer.ack='missing'
    with pytest.raises(InterruptedError):peer.pulse(cancel=cancel,lease=lease,safety_check=lambda:safe[0])
    assert peer.commands[0]['N']==2
    if change!='disconnect':assert peer.commands[-1]['N']==1
    assert peer.car.last_pulse['acknowledged'] is False
    assert peer.car.last_pulse['stop']['physically_stopped'] is None


def test_cancellation_wins_completion_ack_race(monkeypatch):
    peer=Peer(monkeypatch);cancel=[False]
    peer.on_tick=lambda:cancel.__setitem__(0,peer.now>=10.105)
    with pytest.raises(InterruptedError):peer.pulse(cancel=SimpleNamespace(is_set=lambda:cancel[0]))
    assert peer.commands[-1]['N']==1 and peer.car.last_pulse['acknowledged'] is False


def test_lease_horizon_is_rechecked_under_wire_lock(monkeypatch):
    peer=Peer(monkeypatch);original=peer.car._send_raw
    def delayed(raw,**kw):
        if json.loads(raw)['N']==2:peer.now+=.06
        return original(raw,**kw)
    peer.car._send_raw=delayed
    with pytest.raises(InterruptedError):
        peer.pulse(lease=MotionLease('supervised_trial',10.15,'fixture','boot'))
    assert [p['N'] for p in peer.commands]==[1]


@pytest.mark.parametrize('stop_ack',['missing','bare'])
def test_completion_ack_never_substitutes_for_explicit_stop_ack(monkeypatch,stop_ack):
    peer=Peer(monkeypatch,stop_ack=stop_ack);result=peer.pulse()
    assert result['timed_completion'] and result['acknowledged']
    assert result['stop']['acknowledged'] is False
    assert result['stop']['physically_stopped'] is None


def executor(peer,tmp_path):
    class Base(MobileBase):
        def __init__(self):self.car=peer.car
        def connect(self):pass  # Already fake-connected; never open a device.
        def pulse(self,*args,**kw):return super().pulse(*args,clock=peer.clock,**kw)
    bus=StimulusBus();owner=object();bus.claim_observations('vision',owner,metadata={})
    bus.publish_observation('vision',owner,Observation('vision',1,peer.now,{}, {},'g'))
    authority=Mock();authority.safe.return_value=True
    authority.admit.side_effect=lambda r,e,boot_id:dict(group=r.group,request_id=r.id,
        lease=MotionLease('supervised_trial',11.,'fixture',boot_id),
        envelope=dict(max_pwm=35,max_duration=.2,directions=['LEFT','RIGHT']))
    service=QualifiedElegooExecutor(Base(),bus=bus,authority=authority,clock=peer.clock,fault_path=tmp_path/'uncertain')
    request=ActuatorRequest('r','fixture','chassis','pulse',peer.now,'vision','g:1',dict(direction='LEFT',pwm=30,seconds=.1))
    return service,request


@pytest.mark.parametrize('failure',['missing_completion','early_completion','missing_stop','bare_stop'])
def test_real_driver_through_executor_retains_ambiguity_and_restart_marker(monkeypatch,tmp_path,failure):
    peer=Peer(monkeypatch,ack={'missing_completion':'missing','early_completion':'early'}.get(failure,'valid'),
              stop_ack={'missing_stop':'missing','bare_stop':'bare'}.get(failure,'valid'))
    service,request=executor(peer,tmp_path)
    if failure in ('missing_completion','early_completion'):
        with pytest.raises(TimeoutError):service.request(request)
        receipt=service.bus.latest_observation('elegoo-actuator-state',clock=peer.clock)
        assert receipt.values['wire_attempt']['command']['N']==2
    else:
        result=service.request(request);assert result['acknowledged'] and not result['stop']['acknowledged']
    assert service.stop_uncertain and service.fault_path.exists()
    peer.stop_ack='valid';assert service.stop()['acknowledged']
    assert service.stop_uncertain and service.fault_path.exists()
    peer.now+=.001
    fresh=ActuatorRequest('new','fixture','chassis','pulse',peer.now,'vision','g:1',request.parameters)
    with pytest.raises(ValueError):service.request(fresh)
    assert sum(p['N']==2 for p in peer.commands)==1
    # The same durable incident blocks a new executor/facade as well.
    replacement,_=executor(Peer(monkeypatch),tmp_path)
    assert replacement.stop_uncertain
    with pytest.raises(ValueError):replacement.request(request)


def test_qualified_request_uses_only_timed_mode_and_preserves_unknown_physical_outcome(monkeypatch,tmp_path):
    peer=Peer(monkeypatch);service,request=executor(peer,tmp_path)
    result=service.request(request)
    assert [p['N'] for p in peer.commands]==[2,1]
    assert result['physically_observed'] is None and result['executed'] is None
    assert not service.fault_path.exists()


def test_ultrasonic_original_query_reply_path_is_unchanged(monkeypatch):
    peer=Peer(monkeypatch)
    reading=peer.car.read_ultrasonic(protocol=dict(ultrasonic_read_only=True,ultrasonic={'N':21,'D1':2}),clock=peer.clock)
    assert reading['meters']==1.23 and reading['field_of_view_verified'] is False
    assert peer.commands[0]['N']==21 and peer.commands[0]['D1']==2


def test_stop_exception_preserves_original_attempt(monkeypatch):
    peer=Peer(monkeypatch)
    peer.car.stop_verified=Mock(side_effect=RuntimeError('ambiguous STOP write'))
    with pytest.raises(RuntimeError):peer.pulse()
    assert peer.car.last_pulse['command']['N']==2
    assert peer.car.last_pulse['timed_completion'] is True
    assert peer.car.last_pulse['stop']['acknowledged'] is False


@pytest.mark.parametrize('bad',[None,{'N':3},{'N':2,'T_unit':'seconds'},
    {'N':2,'T_unit':'milliseconds','completion_ack':'immediate','zero_duration':'forbidden'}])
def test_generic_local_expiry_assertion_cannot_qualify_wrong_timed_protocol(tmp_path,bad):
    from test_actuator_authority import fixture_report,write
    from learning.actuator_safety import validate_actuator_report
    from test_pet_completion import qualification_control
    from learning.mobile_safety import validate_report
    # Both independently qualified chassis entry paths require the new contract.
    a=tmp_path/'actuator';a.mkdir();report=fixture_report(a,'chassis')
    protocol=json.load(open(report['protocol_artifact']['path']));protocol['timed_motion']=bad
    report['protocol_artifact']=write(a/'bad-protocol.json',protocol)
    with pytest.raises(ValueError,match='N2'):validate_actuator_report(report)
    b=tmp_path/'pet';b.mkdir();report,save=qualification_control(b)
    protocol=json.load(open(report['protocol_artifact']['path']));protocol['timed_motion']=bad
    report['protocol_artifact']=save('bad-protocol.json',protocol)
    with pytest.raises(ValueError,match='N2'):validate_report(report)


def test_existing_pet_executor_uses_timed_driver_and_retains_failed_command(monkeypatch,tmp_path):
    from experiments.ppal.mobile_navigation import QualifiedMobileExecutor
    peer=Peer(monkeypatch,ack='missing')
    # A different facade to the same simulated car exercises the original pet
    # adapter, not the unified request method. No application transport is opened.
    class Base(MobileBase):
        def __init__(self):self.car=peer.car
        def pulse(self,*a,**kw):return super().pulse(*a,clock=peer.clock,**kw)
    context=Mock();context.boot_id='boot';context.safe.return_value=True
    context.activation.return_value=({},dict(direction_envelopes={'FORWARD':dict(max_pwm=35,max_duration=.1)}))
    context.current=dict(observation=dict(frame={'id':'fixture'},sensors={}),tracking=dict(target={}),activation=dict(activation_key='fixture'))
    service=QualifiedMobileExecutor(Base(),context,clock=peer.clock)
    proposal=dict(id='pet-request',at=peer.now,action='advance',direction=None,speed=.15,duration=.1,
                  reasons=[],binding=service.binding(context.current))
    with pytest.raises(TimeoutError):service.execute_bounded(proposal,lease=MotionLease('supervised_trial',11.,'fixture','boot'))
    assert service.stop_uncertain
    assert service.last_attempt['wire_result']['command']['N']==2
    assert all(p['N']!=3 for p in peer.commands)

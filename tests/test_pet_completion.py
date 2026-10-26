"""Host-only regression; no physical qualification claims."""
import json
from dataclasses import replace
from unittest.mock import Mock
import pytest
from hardware.elegoo_mobile import ElegooMobileBase
from experiments.ppal.mobile_navigation import MotionLease
from learning.mobile_safety import validate_report, runtime_hash


def car_fixture():
    c=ElegooMobileBase();c.sock=Mock();c._running=True
    c._send=Mock(return_value={'ok':True});c.stop_verified=Mock(return_value={'sent':True,'physically_stopped':None})
    return c


def pulse(c,**kwargs):
    now=[1.]
    return c.pulse(kwargs.pop('direction','FORWARD'),pwm=kwargs.pop('pwm',30),seconds=kwargs.pop('seconds',.1),
        lease=kwargs.pop('lease',MotionLease('supervised_trial',2,'fixture','boot')),boot_id='boot',
        envelope={'max_pwm':35,'max_duration':.2},safety_check=kwargs.pop('safety_check',lambda:True),
        clock=lambda:now[0],wait=lambda dt:now.__setitem__(0,now[0]+dt),**kwargs)


@pytest.mark.parametrize('direction,d1',[('LEFT',1),('RIGHT',2),('FORWARD',3),('REVERSE',4)])
def test_bounded_directions_and_stop(direction,d1):
    c=car_fixture();result=pulse(c,direction=direction)
    payload=c._send.call_args.args[0]
    assert payload['D1']==d1 and payload['T']==100 and c._send.call_args.kwargs['retry'] is False
    assert result['executed'] is None and result['physically_observed'] is None
    c.stop_verified.assert_called_once()


@pytest.mark.parametrize('change',[{'pwm':True},{'pwm':36},{'seconds':float('nan')},{'seconds':.201},{'direction':'OTHER'},
 {'lease':MotionLease('supervised_trial',1.05,'fixture','boot')},{'lease':MotionLease('supervised_trial',2,'fixture','old')}])
def test_invalid_pulses_do_not_start(change):
    c=car_fixture()
    with pytest.raises(ValueError):pulse(c,**change)
    c._send.assert_not_called()


def test_ambiguous_ack_and_cancellation_stop():
    c=car_fixture();c._send.side_effect=TimeoutError('lost ACK')
    with pytest.raises(TimeoutError):pulse(c)
    assert c._send.call_count==1;c.stop_verified.assert_called_once()
    c=car_fixture();checks=iter([True,False])
    with pytest.raises(InterruptedError):pulse(c,safety_check=lambda:next(checks))
    c.stop_verified.assert_called_once()


def test_nonretry_wire_failure_never_reconnects():
    c=ElegooMobileBase();c.sock=Mock();c._running=True
    c._send_raw=Mock(side_effect=OSError('ambiguous write'));c.connect=Mock()
    with pytest.raises(OSError):c._send({'N':3},retry=False)
    assert c._send_raw.call_count==1;c.connect.assert_not_called()


def test_stop_failure_surfaces_uncertainty_and_sensor_is_never_speculative():
    c=ElegooMobileBase();c._send=Mock(side_effect=ConnectionError())
    assert c.stop_verified()==dict(sent=False,acknowledged=False,physically_stopped=None,error='ConnectionError')
    c._send.reset_mock()
    with pytest.raises(ValueError):c.read_ultrasonic(protocol={})
    c._send.assert_not_called()


def test_no_report_or_unsupported_runtime_can_qualify():
    assert len(runtime_hash())==64
    with pytest.raises(ValueError):validate_report({})
    with pytest.raises(ValueError):validate_report(dict(schema='charlie.mobile.qualification.v1',authentic=False))

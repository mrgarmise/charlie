"""Driver regressions against the owner UNO's actual reply/servo semantics."""
import json
from types import SimpleNamespace
import pytest
from hardware.elegoo_mobile import ElegooMobileBase


def peer(reply):
    car=ElegooMobileBase();car._running=True;commands=[]
    def send(raw):
        command=json.loads(raw);commands.append(command)
        car._handle_frame('{'+command['H']+'_'+reply+'}')
    car.sock=SimpleNamespace(sendall=send)
    return car,commands


@pytest.mark.parametrize('requested,effective',[(20,20),(29,20),(90,90),(95,90),(159,150),(160,160)])
@pytest.mark.parametrize('qualified',[False,True])
def test_pan_reports_representable_position(requested,effective,qualified):
    car,commands=peer('ok')
    if qualified and requested != effective:
        with pytest.raises(ValueError):car.pan_qualified(requested,safety_check=lambda:True)
        assert commands==[]
        return
    result=car.pan_qualified(requested,safety_check=lambda:True) if qualified else car.pan(requested)
    assert result==effective
    assert commands[0]['D2']==effective
    assert commands[0]['D1']==1


@pytest.mark.parametrize('value',['nan','inf','-inf','ok'])
def test_yaw_rejects_non_measurement_reply(value):
    car,_=peer(value)
    with pytest.raises(ValueError):car.yaw()


def test_yaw_accepts_owner_two_decimal_reply():
    car,commands=peer('-12.34')
    assert car.yaw()==-12.34
    assert commands[0]['N']==24


@pytest.mark.parametrize('value',['0','12.5','151','1000','nan','inf','true'])
def test_ultrasonic_rejects_unavailable_or_non_cm_reply(value):
    car,_=peer(value)
    with pytest.raises(ValueError):
        car.read_ultrasonic(protocol=dict(ultrasonic_read_only=True,ultrasonic={'N':21,'D1':2}))


def test_ultrasonic_marks_owner_saturation():
    car,commands=peer('150')
    reading=car.read_ultrasonic(protocol=dict(ultrasonic_read_only=True,ultrasonic={'N':21,'D1':2}))
    assert reading['meters']==1.5 and reading['saturated'] is True
    assert reading['target_association'] is False
    assert commands[0]['N']==21 and commands[0]['D1']==2

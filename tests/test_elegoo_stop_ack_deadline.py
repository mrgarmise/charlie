"""Deterministic transport deadlines; no device or physical-stop claim."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from hardware.elegoo_mobile import ElegooMobileBase


def stop_peer(monkeypatch, delay, reply='tagged'):
    now=[0.];events=[];command={};car=ElegooMobileBase()
    class Event:
        def __init__(self):self.flag=False
        def set(self):self.flag=True
        def is_set(self):return self.flag
        def wait(self,timeout):
            events.append(('wait',now[0],timeout))
            if delay<=timeout:
                now[0]+=delay
                message={'tagged':'{'+command['H']+'_ok}', 'bare':'{ok}',
                    'wrong':'{other_ok}', 'negative':'{'+command['H']+'_error}'}[reply]
                car._handle_frame(message)
                if self.flag:return True
                now[0]+=timeout-delay
            else:now[0]+=timeout
            return False
    def send(raw):
        command.update(json.loads(raw));events.append(('send',now[0],dict(command)))
    monkeypatch.setattr('hardware.elegoo_mobile.threading.Event',Event)
    monkeypatch.setattr('hardware.elegoo_mobile.time.monotonic',lambda:now[0])
    car._running=True;car.sock=SimpleNamespace(sendall=send)
    car.connect=Mock(side_effect=AssertionError('STOP must not reconnect/retry'))
    return car,command,events,now


@pytest.mark.parametrize('delay',[.085,.149])
def test_supported_reply_latency_uses_bounded_wait_after_immediate_dispatch(monkeypatch,delay):
    car,command,events,now=stop_peer(monkeypatch,delay)
    result=car.stop_verified()
    assert events[0][0:2]==('send',0.)
    assert events[1]==('wait',0.,.150)
    assert command=={'N':1,'H':command['H'],'D1':0,'D2':0,'D3':0}
    assert sum(e[0]=='send' for e in events)==1
    assert result['acknowledged'] is True and result['physically_stopped'] is None
    assert now[0]==delay and not car._pending
    car.connect.assert_not_called()


def test_reply_after_deadline_is_uncertain_even_if_received_later(monkeypatch):
    car,command,events,now=stop_peer(monkeypatch,.151)
    result=car.stop_verified()
    assert now[0]==.150
    assert result['acknowledged'] is False and result['physically_stopped'] is None
    assert result['error']=='TimeoutError'
    now[0]=.151;car._handle_frame('{'+command['H']+'_ok}')
    assert result['acknowledged'] is False and not car._pending
    assert sum(e[0]=='send' for e in events)==1
    car.connect.assert_not_called()


@pytest.mark.parametrize('reply',['bare','wrong','negative'])
def test_longer_wait_cannot_accept_ambiguous_reply(monkeypatch,reply):
    car,_,events,_=stop_peer(monkeypatch,.085,reply)
    result=car.stop_verified()
    assert result['acknowledged'] is False and result['physically_stopped'] is None
    assert result['error']=='TimeoutError'
    assert sum(e[0]=='send' for e in events)==1
    car.connect.assert_not_called()

import json
import pytest
from test_object_display import screen, transport
from test_active_vision_firmware import board
from hardware.rp2040_controller import RP2040Controller
from unittest.mock import Mock

SLOT='a'*32


def connected(board,screen):
    a,b,h,hb=board.create(calibrated=False,electrical=False,interlock=False);h.display=screen.d
    host=transport(h,board)
    board.command(h,'SESSION '+host.link_session)
    return host,a,h


def test_real_protocol_ack_scroll_clear_restore_and_no_actuation(board,screen):
    host,a,h=connected(board,screen);screen.d.message=None
    screen.d.show_object_label('DOG',10000)
    ack=host.meditation_notice(SLOT,1)
    assert ack['visible'] and screen.pixels
    for n in range(1,20):screen.now[0]=n*100;screen.d.update()
    assert screen.d.object_label=='DOG' and not screen.calls  # smooth pixels, no 3-char pages
    assert host.meditation_notice(SLOT,2,0,'CLEAR')['visible'] is False
    screen.now[0]=2000;screen.d.update();assert screen.d.object_label=='DOG'
    assert not board.pwms and not a.status()['armed']
    assert all(not any(w.startswith(c) for c in (b'ARM',b'MOVE',b'AUTHORIZE',b'LOOK')) for w in host.serial.writes)


def test_ttl_crash_stale_refresh_and_reboot(board,screen):
    host,a,h=connected(board,screen)
    assert host.meditation_notice(SLOT,1,500)
    screen.now[0]=300
    assert host.meditation_notice(SLOT,1,500)['remaining_ms']==200  # duplicate cannot renew
    screen.now[0]=501;assert not screen.d.meditation_status()['visible']
    assert host.meditation_notice(SLOT,2) is None  # expired slot cannot revive
    assert host.meditation_notice('b'*32,3)
    board.command(h,'SESSION new-session')
    assert screen.d.meditation_status()['phase']=='CLEAR'
    assert host.meditation_notice('b'*32,4) is None
    assert not board.pwms


@pytest.mark.parametrize('preempt',['STOP','ERROR','NO_BRAIN','CAL'])
def test_safety_preemption_and_no_stale_reappearance(board,screen,preempt):
    host,a,h=connected(board,screen);assert host.meditation_notice(SLOT,1)
    if preempt=='STOP':board.command(h,'STOP')
    elif preempt=='CAL':screen.d.capability_status('WAIT GP10')
    elif preempt=='ERROR':screen.d.feedback(screen.d.ERROR)
    else:screen.d.status(screen.d.NO_BRAIN)
    assert not screen.d.meditation_status()['visible']
    assert host.meditation_notice(SLOT,2) is None
    assert not board.pwms


def test_old_firmware_and_forged_ack_are_not_visibility():
    host=RP2040Controller.__new__(RP2040Controller);host.connected=True;host.link_session='session'
    host.display_capabilities=Mock(return_value={'object_labels':1})
    host._exchange=Mock();assert host.meditation_notice(SLOT,1) is None;host._exchange.assert_not_called()
    host.display_capabilities.return_value={'meditation_notice':1}
    host._exchange.return_value='MEDITATION_ACK '+json.dumps(dict(session='old',slot=SLOT,sequence=1,phase='PREPARING',visible=True,remaining_ms=2000))
    assert host.meditation_notice(SLOT,1) is None


@pytest.mark.parametrize('args', [('a',0,2000,'PREPARING'),(SLOT,1,10001,'PREPARING'),(SLOT,1,0,'THINKING'),(SLOT,1,2000,'ARM')])
def test_invalid_notice_cannot_be_a_command(args):
    from rp2040.meditation_notice import request
    with pytest.raises(ValueError):request('session',*args)


def test_legacy_display_session_and_stop_keep_safety_commands_working(board,capsys):
    calls=[]
    class LegacyDisplay:
        def __getattr__(self,name):return lambda *args:calls.append((name,args))
    a,b,h,hb=board.create(calibrated=False,electrical=False,interlock=False)
    h.display=LegacyDisplay()
    board.command(h,'SESSION legacy_session')
    assert 'OK SESSION' in capsys.readouterr().out
    board.command(h,'STOP')
    assert 'OK STOP' in capsys.readouterr().out
    assert not a.status()['armed'] and not board.pwms

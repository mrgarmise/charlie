import pytest
from experiments.ppal.controller_sandbox import ControllerSandbox, validate_controls, validate_bridge_message
from experiments.ppal.models import Action
from experiments.ppal.arcade_transport import ArcadeController
from tests.test_ppal_arcade_transport import LegacyServer
import threading

@pytest.mark.parametrize('token',['RT','rt','RT_DOWN','RT_UP','RIGHT_TRIGGER','RIGHT_TRIGGER_DOWN','R2','ABS_RZ','QUIT','PLAYER_ALEX','GUIDE+BACK','GUIDE BACK','A\nRT','A\rRT'])
def test_forbidden_commands_never_reach_wire(token):
    with LegacyServer(('127.0.0.1',0)) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with ArcadeController('127.0.0.1',server.server_address[1],sleep=lambda _:None) as c:
                with pytest.raises(ValueError):c._command(token)
            assert server.commands==['NEUTRAL','NEUTRAL']
        finally:server.shutdown();thread.join()

@pytest.mark.parametrize('first,second',[('GUIDE_DOWN','BACK'),('BACK_DOWN','GUIDE_DOWN'),('MODE_DOWN','COIN'),('SELECT_DOWN','BTN_MODE')])
def test_sequential_exit_combo_rejected(first,second):
    s=ControllerSandbox();wire,held=s.prepare(first);s.commit(held)
    with pytest.raises(ValueError):s.prepare(second)
    wire,held=s.prepare('NEUTRAL');s.commit(held)
    assert not s.held

@pytest.mark.parametrize('controls',[('GUIDE','COIN'),('RT',),('A','RIGHT_TRIGGER')])
def test_combination_validated_atomically(controls):
    with pytest.raises(ValueError):validate_controls(controls)


def test_repeated_buttons_combinations_and_release():
    with LegacyServer(('127.0.0.1',0)) as server:
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with ArcadeController('127.0.0.1',server.server_address[1],sleep=lambda _:None) as c:
                for _ in range(3):c.execute(Action('E','N',controls=('A','COIN','START')),80)
                assert not c.sandbox.held
            assert server.commands.count('A_DOWN')==3
            assert server.commands.count('BACK_UP')==3
            assert server.commands[-1]=='NEUTRAL'
        finally:server.shutdown();t.join()


def test_stopped_caller_hold_lease_neutralizes():
    with LegacyServer(('127.0.0.1',0)) as server:
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            with ArcadeController('127.0.0.1',server.server_address[1],sleep=lambda _:None) as c:
                c._command('A_DOWN');c._expire_hold()
                assert server.commands[-1]=='NEUTRAL' and not c.sandbox.held
        finally:server.shutdown();t.join()

@pytest.mark.parametrize('buttons',[['RT'],['GUIDE','BACK'],['right_trigger'],['fire_up','RT']])
def test_raw_json_bridge_rejects_bypass(buttons):
    with pytest.raises(ValueError):validate_bridge_message(dict(type='step',sequence=1,buttons=buttons,duration_ms=80))


def test_alternate_live_client_enforces_shared_boundary_without_socket():
    from experiments.robotron.live import ArcadeController as Other
    c=Other('not-connected')
    for token in ('RT_DOWN','GUIDE+BACK','A\nQUIT'):
        with pytest.raises(ValueError):c.command(token)
    c.sandbox.commit({'GUIDE'})
    with pytest.raises(ValueError):c.command('COIN')

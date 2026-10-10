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
    s=ControllerSandbox()
    if first in ('GUIDE_DOWN','MODE_DOWN'):
        with pytest.raises(ValueError):s.prepare(first)
    else:
        wire,held=s.prepare(first);s.commit(held)
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
    with pytest.raises(ValueError):c.sandbox.commit({'GUIDE'})
    assert not c.sandbox.held
    with pytest.raises(ValueError):c.command('GUIDE')


GUIDE_ALIASES = ('GUIDE','guide','HOME','home','MODE','BTN_MODE','BTN_HOME',
                 'GUIDE_BUTTON','HOME_BUTTON','XBOX_GUIDE','XBOX_HOME')

@pytest.mark.parametrize('alias', GUIDE_ALIASES)
@pytest.mark.parametrize('suffix', ('','_DOWN','_UP'))
def test_guide_home_all_state_transitions_rejected_before_wire(alias,suffix):
    # In-process stream mock: no actual arcade or controller connection.
    from unittest.mock import Mock
    c=ArcadeController.__new__(ArcadeController)
    c.sandbox=ControllerSandbox();c.closed=False;c.stream=Mock();c.connection=Mock()
    c._wire_lock=threading.RLock();c._hold_timer=None
    with pytest.raises(ValueError):c._command(alias+suffix)
    c.stream.write.assert_not_called()
    assert not c.sandbox.held

@pytest.mark.parametrize('controls',[('GUIDE',),('HOME','A'),('BACK','GUIDE'),('GUIDE','BACK'),('A','BTN_MODE')])
def test_both_gameplay_clients_reject_guide_actions_before_any_stick_output(controls):
    from experiments.robotron.live import ArcadeController as Other
    from unittest.mock import Mock
    a=ArcadeController.__new__(ArcadeController);a.closed=False;a.sandbox=ControllerSandbox();a._command=Mock()
    b=Other('not-connected');b.command=Mock()
    for c in (a,b):
        with pytest.raises(ValueError):c.execute(Action('E','N',controls=controls))
    a._command.assert_not_called();b.command.assert_not_called()

@pytest.mark.parametrize('alias',GUIDE_ALIASES)
def test_invalid_held_commit_fails_closed_and_neutral_can_recover(alias):
    s=ControllerSandbox()
    with pytest.raises(ValueError):s.commit({'A',alias})
    assert not s.held
    s.held={alias}  # Defensive check of an externally corrupted state.
    with pytest.raises(ValueError):s.prepare('LS_UP')
    wire,held=s.prepare('NEUTRAL');s.commit(held)
    assert wire=='NEUTRAL' and not s.held


def test_exploratory_planner_never_offers_guide_and_rejects_explicit_alias():
    from experiments.ppal.forebrain import Forebrain
    from experiments.ppal.controller import DryRunController
    from experiments.ppal.controller_sandbox import BUTTONS
    f=Forebrain()
    assert 'GUIDE' not in BUTTONS
    for _ in range(len(BUTTONS)+8):
        action=f.exploratory_action({'context':'unresolved'})
        validate_controls(action.controls)
        assert not any(c in GUIDE_ALIASES for c in action.controls)
    with pytest.raises(ValueError):f.exploratory_action({'context':'unresolved'},controls=['HOME'])
    with pytest.raises(ValueError):DryRunController().execute(Action(controls=('GUIDE',)))

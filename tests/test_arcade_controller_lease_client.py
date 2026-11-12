"""Client wire behavior only; no physical controller or gameplay."""
import threading

import pytest

from experiments.ppal.arcade_transport import ArcadeController
from experiments.ppal.models import Action
from tests.test_ppal_arcade_transport import LegacyServer


@pytest.fixture
def server():
    with LegacyServer(('127.0.0.1', 0)) as instance:
        thread = threading.Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        try:
            yield instance
        finally:
            instance.shutdown()
            thread.join(2)


def connect(server, **kw):
    return ArcadeController('127.0.0.1', server.server_address[1],
                            require_lease=True, pulse=False, sleep=lambda _: None, **kw)


def test_each_progressing_action_renews_even_when_positions_unchanged(server):
    with connect(server) as controller:
        controller.execute(Action('E', 'N'))
        before = list(server.commands)
        controller.execute(Action('E', 'N'))
        assert server.commands == before + ['LEASE']
        assert controller.positions == ('LS_RIGHT', 'RS_UP')
        controller.renew_lease()
        assert controller.positions == ('LS_RIGHT', 'RS_UP')
    assert server.commands[0:2] == ['NEUTRAL', 'LEASE']


def test_unsupported_lease_fails_closed_without_gameplay(server):
    server.reject.add('LEASE')
    with pytest.raises(ConnectionError):
        connect(server)
    assert server.commands == ['NEUTRAL', 'LEASE', 'NEUTRAL']


def test_expired_renewal_closes_connection(server):
    controller = connect(server)
    controller.execute(Action('E', 'N'))
    server.reject.add('LEASE')
    with pytest.raises(ConnectionError):
        controller.renew_lease()
    assert controller.closed
    assert server.commands[-1] == 'NEUTRAL'


def test_old_local_timer_cannot_interrupt_renewed_hold(server):
    with connect(server) as controller:
        controller.execute(Action('E', 'N'))
        generation = controller._hold_generation
        controller.renew_lease()
        before = list(server.commands)
        controller._expire_hold(generation)
        assert server.commands == before
        controller._expire_hold(controller._hold_generation)
        assert server.commands[-1] == 'NEUTRAL'
        assert controller.positions == ('LS_CENTER', 'RS_CENTER')
        controller.execute(Action('E', 'N'))
        assert server.commands[-2:] == ['LS_RIGHT', 'RS_UP']

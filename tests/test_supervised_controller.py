"""Published SELF discovery boundary, using real transport and synthetic wire/frames."""
import inspect
import threading
import time
from types import SimpleNamespace

import pytest
from PIL import Image

from experiments.ppal.arcade_transport import ArcadeController
from experiments.ppal.models import Action
from experiments.ppal.observation_stream import ObservationStream
from experiments.ppal.progress_supervision import Progress, SupervisedController
from experiments.ppal.robotron_agency import VisualAgency
from experiments.ppal.shot_capture import capture_window


@pytest.fixture
def rig(tmp_path, monkeypatch):
    progress = Progress(tmp_path/'progress.json')
    progress.enter('perception')
    stream = ObservationStream(None)
    def expose():
        at = time.monotonic()
        with stream.condition:
            stream._append(Image.new('RGB', (20, 20)),
                           dict(first_pixel_exposure_at=at, sensor_timestamp_ns=int(at*1e9)))
    expose()
    # This fixture now supplies a continuous source while protected frames drain.
    def acquire():
        time.sleep(.005)
        at=time.monotonic()
        return Image.new('RGB',(20,20)),dict(first_pixel_exposure_at=at,sensor_timestamp_ns=int(at*1e9))
    stream.acquire=acquire
    stream.start()
    class Wire:
        closed = False
        reject = None
        cancel_on = None
        commands = []
        def write(self, data):
            command = data.decode().strip()
            self.commands.append(command)
            if command == self.cancel_on:
                stream.failed.set()
        def readline(self, size):
            return b'ERROR\n' if self.commands[-1] == self.reject else b'OK\n'
        def close(self): self.closed = True
    wire = Wire()
    connection = SimpleNamespace(settimeout=lambda _: None, makefile=lambda *a, **kw: wire,
                                 close=lambda: setattr(wire, 'closed', True))
    monkeypatch.setattr('experiments.ppal.arcade_transport.socket.create_connection', lambda *a, **kw: connection)
    transport = ArcadeController('synthetic', require_lease=True)
    controller = SupervisedController(transport, progress)
    yield SimpleNamespace(controller=controller, transport=transport, progress=progress,
                          stream=stream, wire=wire)
    controller.close()
    stream.close()


@pytest.mark.parametrize('outcome', ['success', 'cancelled_before', 'cancelled_during', 'rejected'])
def test_self_discovery_capture_forwards_cancel_event_and_deadline(rig, outcome):
    """Exact live chain: VisualAgency.discover -> capture_window -> supervised execute."""
    if outcome == 'cancelled_before': rig.stream.failed.set()
    if outcome == 'cancelled_during': rig.wire.cancel_on = 'RS_RIGHT'
    if outcome == 'rejected': rig.wire.reject = 'RS_RIGHT'
    captured = []
    deadline = time.monotonic()+5
    def read_pairs(): return []
    read_pairs.accept_exposure = lambda packet: None
    def capture(controller, action, duration, until, stop):
        assert until == deadline
        result = capture_window(SimpleNamespace(stream=rig.stream), controller, action,
                                duration, until, stop, post_seconds=.001)
        captured.append(result)
        return result
    def discover():
        return VisualAgency().discover(read_pairs, rig.controller, capture_shots=capture,
                                       deadline=deadline, should_stop=lambda: bool(captured))
    if outcome == 'success':
        discover()
        assert captured[0][0]['fire'] == 'E'
        captured[0][1].close(replayed=True)
        assert rig.wire.commands == ['NEUTRAL', 'LEASE', 'LEASE', 'RS_RIGHT', 'LS_CENTER', 'RS_CENTER']
        assert not rig.transport.closed
        assert 'failure_kind' not in rig.progress.data
    else:
        error = ConnectionError if outcome == 'rejected' else InterruptedError
        with pytest.raises(error): discover()
        assert rig.transport.closed and rig.wire.closed
        assert rig.wire.commands[-1] == 'NEUTRAL'
        assert rig.transport.positions == ('LS_CENTER', 'RS_CENTER')
        assert not rig.transport.sandbox.held
        assert rig.progress.data['failure_kind'] == 'controller_failure'
        assert rig.transport._hold_timer is None or not rig.transport._hold_timer.is_alive() or rig.transport._hold_timer.finished.is_set()
        if outcome == 'cancelled_before': assert rig.wire.commands == ['NEUTRAL', 'LEASE', 'NEUTRAL']
    assert rig.stream.pin is None
    assert rig.progress.data['phase'] == 'perception'


def test_all_transport_execute_keywords_command_and_close(rig):
    """Bind every wrapped transport method's real keyword interface through the proxy."""
    for name, kwargs in [('execute', dict(action=Action('E', 'N'), duration_ms=30,
                                        cancel_event=threading.Event(), deadline=time.monotonic()+5)),
                         ('_command', dict(command='NEUTRAL')), ('close', {})]:
        inspect.signature(getattr(rig.transport, name)).bind(**kwargs)
        inspect.signature(getattr(rig.controller, name)).bind(**kwargs)
        getattr(rig.controller, name)(**kwargs)
        assert rig.progress.data['phase'] == 'perception'
    assert rig.transport.closed and rig.wire.commands[-1] == 'NEUTRAL'


def test_forwarded_lease_and_deadman_are_preserved(rig):
    rig.controller.execute(action=Action('E', 'N'), duration_ms=30)
    rig.controller.renew_lease()
    generation = rig.transport._hold_generation
    before = list(rig.wire.commands)
    rig.controller._expire_hold(generation-1)
    assert rig.wire.commands == before
    rig.controller._expire_hold(generation)
    assert rig.wire.commands[-1] == 'NEUTRAL'
    assert rig.controller.positions == ('LS_CENTER', 'RS_CENTER')


def test_expired_deadline_neutralizes_and_preserves_finalizing(rig):
    rig.progress.enter('finalizing')
    with pytest.raises(InterruptedError):
        rig.controller.execute(action=Action('E', 'N'), duration_ms=30, deadline=time.monotonic()-1)
    assert rig.transport.closed and rig.wire.commands == ['NEUTRAL', 'LEASE', 'NEUTRAL']
    assert rig.progress.data['phase'] == 'finalizing'
    assert rig.progress.data['failure_kind'] == 'controller_failure'


@pytest.mark.parametrize('name', ['execute', '_command', 'close'])
def test_proxy_preserves_additional_backend_keywords_and_return_values(tmp_path, name):
    progress = Progress(tmp_path/'progress.json')
    token = object()
    def method(*args, **kwargs):
        assert progress.data['phase'] == 'controller'
        assert args == (token,) and kwargs == dict(option=token)
        return token
    controller = SupervisedController(SimpleNamespace(**{name: method}), progress)
    assert getattr(controller, name)(token, option=token) is token
    assert progress.data['phase'] == 'perception'


def test_other_controller_backends_keep_their_supported_interfaces(tmp_path):
    from experiments.ppal.controller import DryRunController
    from experiments.ppal.hands import RecordingSink, TCPCommandSink
    from unittest.mock import Mock
    action = Action('E', 'N')
    for backend in (DryRunController(), RecordingSink()):
        progress = Progress(tmp_path/(type(backend).__name__+'.json'))
        proxy = SupervisedController(backend, progress)
        result = proxy.execute(action=action)
        assert result is action if isinstance(backend, DryRunController) else result['duration_ms'] == 100
        if hasattr(backend, 'close'): proxy.close()
        # These backends do not advertise cancellation; the proxy must not silently drop it.
        with pytest.raises(TypeError): proxy.execute(action=action, cancel_event=threading.Event())
        assert progress.data['failure_kind'] == 'controller_failure'
    backend = TCPCommandSink.__new__(TCPCommandSink)
    backend.closed = False
    backend.sequence = 0
    backend._send = Mock(side_effect=lambda message: message)
    backend.stream = Mock()
    backend.connection = Mock()
    proxy = SupervisedController(backend, progress)
    assert proxy.execute(action=action, duration_ms=60)['duration_ms'] == 60
    proxy.close()
    assert backend._send.call_args.args[0]['type'] == 'release'
    backend.stream.close.assert_called_once()
    backend.connection.close.assert_called_once()


@pytest.mark.parametrize('camera_failure', [False, True])
def test_lookahead_worker_forwards_keywords_and_is_joined(rig, camera_failure):
    from experiments.ppal.controller_overlap import execute_with_lookahead
    if camera_failure: rig.wire.cancel_on = 'RS_RIGHT'
    call = lambda: execute_with_lookahead(rig.controller, Action('STAY', 'E'), 60,
                                        rig.stream, rig.stream.sequence, lambda packet: packet,
                                        deadline=time.monotonic()+5)
    if camera_failure:
        with pytest.raises(RuntimeError): call()
        assert rig.transport.closed and rig.wire.commands[-1] == 'NEUTRAL'
    else:
        assert call().sequence > 0  # Continuous fixture supplies independent lookahead.
        assert not rig.transport.closed
    assert rig.progress.data['phase'] == 'perception'
    assert not any(t.name == 'charlie-bounded-controller' and t.is_alive() for t in threading.enumerate())

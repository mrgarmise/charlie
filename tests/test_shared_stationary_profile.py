"""Candidate composition and guarded Executive, without physical hardware."""
import subprocess
import sys
import time

import pytest

from learning.recognition_transport import RecognitionServer
from learning.shared_recognition import InferenceScheduler
from tools.runtime_adoption import shared_profile as profile


def test_private_session_rotation_and_failure(tmp_path):
    directory = tmp_path / 'shared'
    with pytest.raises(ArithmeticError):
        with profile.session_channel(directory) as (_, tokens):
            for role in ('recognize', 'display'):
                assert (directory / (role + '.token')).stat().st_mode & 0o777 == 0o600
            assert not (directory / 'executive.token').exists()
            with pytest.raises(FileExistsError):
                with profile.session_channel(directory):
                    pass
            raise ArithmeticError
    assert not directory.exists()
    with profile.session_channel(directory) as (_, fresh):
        assert all(fresh[role] != token for role, token in tokens.items())


@pytest.mark.parametrize('display', [True, False])
def test_fixed_composition(tmp_path, monkeypatch, display):
    import main
    recorded = {}
    directory = tmp_path / 'shared'
    state = tmp_path / 'existing-notebook'
    monkeypatch.setattr(profile, 'SESSION', directory)
    monkeypatch.setattr(profile, 'install', lambda stream, **kw: recorded.update(kw))
    monkeypatch.setattr(profile, 'install_stationary_stop', lambda cls: lambda: None)

    def application(args, arguments, *, admitted_channel):
        assert args.learning_state == state
        assert args.executive_recognition and args.learning_require_thermal
        assert args.shared_recognition_directory is None and args.object_seconds == 90
        assert args.object_label_display == ('rp2040' if display else 'off')
        assert not (args.abilities_dashboard or args.primary_vision or args.pet_follow)
        assert recorded['recognition_bind'] == admitted_channel[0]
        assert set(admitted_channel[1]) == {'executive', 'recognize', 'display'}

    monkeypatch.setattr(main, 'run_application', application)
    profile.run(state, tmp_path / 'manifest', 'http://127.0.0.1/stream', display=display)
    assert not directory.exists()


def test_guarded_executive_receives_and_releases_demand(tmp_path):
    from test_camera_sources import wait_until
    with profile.session_channel(tmp_path / 'ipc') as (endpoint, roles):
        scheduler = InferenceScheduler()
        server = RecognitionServer(endpoint, roles, scheduler)
        code = """
import sys
from tools.runtime_adoption.stationary_boundary import install
from learning.lifecycle import DevelopmentLifecycle
endpoint = sys.argv[1]
install(recognition_connect=endpoint)
worker = object.__new__(DevelopmentLifecycle)
worker.recognition_client = endpoint, input()
worker.yield_for_primary = lambda: None
print(worker.request_recognition()['frame_id'])
"""
        try:
            with subprocess.Popen([sys.executable, '-c', code, endpoint], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as child:
                child.stdin.write(roles['executive'] + '\n')
                child.stdin.flush()
                wait_until(scheduler.active)
                scheduler.publish(dict(observation=dict(source='elegoo-v4', stream_generation='g',
                                                        frame_id='g:1', at=time.monotonic()),
                                       provenance=dict(model=[dict(sha256='fixture')])))
                out, err = child.communicate(timeout=5)
                assert child.returncode == 0, err
                assert out.strip() == 'g:1'
                wait_until(lambda: not scheduler.clients)
        finally:
            server.close()
            scheduler.close()


def test_shared_control_queue_preserves_both_stops_when_full():
    from stimulus.bus import StimulusBus
    bus = StimulusBus(event_limit=8)
    for _ in range(1000):
        bus.emit('camera_source', 'pi')
    bus.emit('emergency_stop')
    bus.emit('object_recognition_stop')
    for _ in range(1000):
        bus.emit('camera_source', 'elegoo')
    events = bus.get_all()
    assert len(events) == 8
    assert events[-2:] == [('emergency_stop', None), ('object_recognition_stop', None)]


def test_count_native_dispatch_even_if_transport_fails():
    import threading
    from types import SimpleNamespace
    from hardware.hailo_session import HailoSession, measure_inferences

    session = HailoSession('/unused', sha256='fixture', input_shape=(1,))
    session.open = lambda: None
    session.owner = threading.get_ident()
    session.input_name = 'input'
    session.pipeline = SimpleNamespace(infer=lambda inputs: inputs['input'])
    with measure_inferences() as counts:
        assert session.infer('first') == 'first'
        def failure(inputs):
            raise TimeoutError()
        session.pipeline.infer = failure
        with pytest.raises(TimeoutError):
            session.infer('second')
    assert counts == dict(submitted=2, completed=1)


def test_inflight_serial_timeout_during_stop_has_no_late_ack():
    from threading import Event, Thread
    from learning.shared_recognition import DisplayBroker
    entered, resume = Event(), Event()
    class SlowSerial:
        def show_object_label(self, *args):
            entered.set()
            assert resume.wait(2)
            raise TimeoutError()
        def clear_object_label(self):
            return True
    broker = DisplayBroker(SlowSerial())
    first = broker.submit('first', 'DOG', time.monotonic() + 2)
    queued = broker.submit('second', 'CAT', time.monotonic() + 2)
    thread = Thread(target=broker.step)
    thread.start()
    try:
        assert entered.wait(1)
        broker.latch()
        assert queued.get(timeout=1) is False
    finally:
        resume.set()
        thread.join(2)
    assert not thread.is_alive()
    assert first.get(timeout=1) is False
    broker.stop()


def test_executive_optionally_displays_new_confident_class(monkeypatch):
    from learning.lifecycle import DevelopmentLifecycle
    from learning import recognition_transport
    worker = object.__new__(DevelopmentLifecycle)
    worker.recognition_client = '/local', 'read'
    messages = []
    def show(endpoint, token, label, *, timeout):
        messages.append((endpoint, token, label))
        return True
    monkeypatch.setattr(recognition_transport, 'display_label', show)
    result = dict(observation=dict(objects=[dict(label='chair', confidence=.9)]))
    worker.display_recognition(result)
    worker.recognition_display_token = 'display'
    worker.display_recognition(result)
    worker.display_recognition(result)
    assert messages == [('/local', 'display', 'CHAIR')]

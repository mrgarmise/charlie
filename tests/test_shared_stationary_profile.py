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

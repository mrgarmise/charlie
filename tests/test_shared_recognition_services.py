"""Device-free integration of the real bus, recognition loop and Unix peer transport."""
import json
from pathlib import Path
from queue import Empty
import subprocess
import sys
from threading import Event, Thread
import time
from types import SimpleNamespace

import pytest

from experiments.ppal.camera_session import CameraFeeder
from learning import object_runtime, recognition_transport, shared_recognition
from main import parser
from stimulus.bus import StimulusBus
from test_camera_sources import frame, wait_until
from tools.runtime_adoption.stationary_boundary import transport_policy
from vision.mobile_models import FixtureModel


def test_independent_clients_share_application_owners(tmp_path, monkeypatch):
    from attention import object_display_runtime
    from learning import resources
    from stimulus import keyboard
    from vision import mobile_models

    owners = {'camera': 0, 'hailo': 0, 'pico': 0}
    peak = owners.copy()
    opens = owners.copy()
    inferred = []

    def opened(name):
        owners[name] += 1
        opens[name] += 1
        peak[name] = max(peak[name], owners[name])

    def closed(name):
        assert owners[name] == 1
        owners[name] -= 1

    class Camera:
        sequence = 0

        def read(self):
            self.sequence += 1
            return frame(at=time.monotonic(), source='elegoo-v4', sequence=self.sequence)

        def close(self):
            closed('camera')

    def capture():
        opened('camera')
        return Camera()

    class Detector(FixtureModel):
        def infer(self, item):
            inferred.append(item.id)
            return super().infer(item)

        def close(self):
            if owners['hailo']:
                closed('hailo')

    def detector(**_):
        opened('hailo')
        model = Detector([dict(label='chair', confidence=.95, box=[1, 1, 4, 3])])
        model.metadata.update(classes=['chair'], sha256='fixture-model')
        return model

    display = object_display_runtime.DryRunDisplay()
    original_close = display.close

    def attach(*_, **__):
        opened('pico')
        return None, display

    def close_display():
        closed('pico')
        original_close()

    monkeypatch.setattr(display, 'close', close_display)
    monkeypatch.setattr(mobile_models, 'HailoObjects', detector)
    monkeypatch.setattr(object_display_runtime, 'attach', attach)
    monkeypatch.setattr(resources, 'ResourceGuard', lambda *_: SimpleNamespace(check=lambda **_: None))
    monkeypatch.setattr(keyboard, 'KeyboardStimulus', lambda *_, **__: SimpleNamespace(close=lambda: None))
    inference = shared_recognition.InferenceScheduler()
    monkeypatch.setattr(shared_recognition, 'InferenceScheduler', lambda **_: inference)
    directory = tmp_path / 'ipc'
    directory.mkdir(mode=0o700)
    endpoint, tokens = recognition_transport.channel(directory)
    manifest = tmp_path / 'models'
    manifest.write_text(json.dumps(dict(schema='charlie.mobile.models.v1', objects={'sha256': 'fixture-model'})))
    args = parser().parse_args(['--hardware', '--object-recognition', '--camera-source', 'elegoo',
                               '--object-model-manifest', str(manifest), '--object-label-display', 'rp2040',
                               '--learning-state', str(tmp_path / 'state'), '--object-seconds', '6'])
    args.shared_recognition = endpoint, tokens
    bus = StimulusBus()
    feeder = CameraFeeder(capture, bus, 'elegoo-v4', period=.01).start()
    preview = bus.subscribe_frames('elegoo-v4')
    observations = bus.subscribe_observations('object-detections:elegoo-v4')
    results = {}
    admitted = Event()
    done = Event()
    clients = []

    def collect():
        try:
            wait_until(lambda: Path(endpoint).is_socket())
            for extra in (['--frames', '2'], ['--frames', '2'], ['--label', 'CHAIR']):
                clients.append(subprocess.Popen(
                    [sys.executable, '-B', '-m', 'learning.recognition_transport', str(directory), *extra],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
            wait_until(lambda: len(inference.clients) == 2)
            admitted.set()
            started = time.monotonic()
            for idx, proc in enumerate(clients):
                out, error = proc.communicate(timeout=4)
                assert proc.returncode == 0, error
                results[idx] = [json.loads(line) for line in out.splitlines()]
            results['observation'] = observations.read().values
            results['seconds'] = time.monotonic() - started
        except BaseException as exc:
            results['error'] = exc
        finally:
            admitted.set()
            done.set()

    coordinator = Thread(target=collect)
    coordinator.start()

    def supervise():
        assert admitted.wait(4)
        if done.is_set():
            raise KeyboardInterrupt

    try:
        object_runtime.run_objects(args, None, bus, supervise=supervise)
        coordinator.join(5)
        assert 'error' not in results, results.get('error')
        first, second = results[0], results[1]
        assert len(first) == len(second) == 2
        assert first == second
        assert [r['frame_id'] for r in first] == inferred
        assert results[2] == [{'acknowledged': True}]
        assert results['observation']['frame_id'] == inferred[-1]
        assert preview.read() is not None
        assert bus.frame_owners['elegoo-v4'] is feeder
        assert peak == opens == dict(camera=1, hailo=1, pico=1)
        print(json.dumps(dict(client_results=4, inference_calls=len(inferred), frame_captures=feeder.frames,
                              peak_owners=peak, display_acks=1, duration=round(results['seconds'], 3))))
    finally:
        for proc in clients:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        coordinator.join(5)
        preview.close()
        observations.close()
        feeder.close()
    assert owners == dict(camera=0, hailo=0, pico=0)


def test_client_disconnect_cancels_only_its_own_demand(tmp_path):
    import socket

    tmp_path.chmod(0o700)
    endpoint, tokens = recognition_transport.channel(tmp_path)
    scheduler = shared_recognition.InferenceScheduler()
    server = recognition_transport.RecognitionServer(endpoint, tokens, scheduler)
    keep = scheduler.request('other', timeout=2)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as abandoned:
            abandoned.connect(endpoint)
            abandoned.sendall((json.dumps(dict(role='recognize', token=tokens['recognize'])) + '\n').encode())
            wait_until(lambda: len(scheduler.clients) == 2)
        wait_until(lambda: len(scheduler.clients) == 1)
        assert scheduler.clients['other'] is keep and scheduler.active()
        with pytest.raises(OSError, match='PermissionError'):
            next(recognition_transport.recognize(endpoint, 'denied'))
    finally:
        server.close()
        scheduler.close()


def test_display_fifo_rejects_expired_and_stop_discards_pending():
    from attention.object_display_runtime import DryRunDisplay
    transport = DryRunDisplay()
    broker = shared_recognition.DisplayBroker(transport)
    now = time.monotonic()
    first = broker.submit('first', 'CHAIR', now + 1)
    second = broker.submit('second', 'CAT', now + 1)
    broker.step()
    assert first.get_nowait()
    with pytest.raises(Empty):
        second.get_nowait()
    broker.latch()
    broker.step()
    assert not second.get_nowait()
    with pytest.raises(RuntimeError):
        broker.submit('third', 'DOG', now + 1)
    broker.stop()
    assert not any('CAT' in command for command in transport.commands)
    assert transport.commands[-1] == 'OBJECT_CLEAR'
    transport.close()


def test_guard_only_allows_explicit_unix_address_and_direction(tmp_path):
    import socket

    endpoint = str(tmp_path / 'recognition.sock')
    owner = transport_policy(None, recognition_bind=endpoint)
    client = transport_policy(None, recognition_connect=endpoint)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        owner('socket.bind', (sock, endpoint))
        client('socket.connect', (sock, endpoint))
        with pytest.raises(PermissionError):
            owner('socket.connect', (sock, endpoint))
        with pytest.raises(PermissionError):
            client('socket.bind', (sock, endpoint))
        with pytest.raises(PermissionError):
            client('socket.connect', (sock, endpoint + '.other'))

"""Shared-source tests use synthetic pixels and fake camera transports only."""
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
from hardware.camera_ownership import ElegooCameraLease
from vision.camera_source import CameraSources, PiCameraSource, ElegooCameraSource, TrackingCamera


def test_pi_rgb_converts_once_and_keeps_observed_identity():
    rgb = np.zeros((4, 6, 3), np.uint8); rgb[:] = [10, 20, 30]
    camera = SimpleNamespace(read=lambda: rgb, close=Mock(),
        picam2=SimpleNamespace(camera_properties={'Model': 'imx708', 'Id': 'fixture-pi'}))
    source = PiCameraSource(camera=camera, clock=lambda: 1.)
    first, second = source.read(), source.read()
    assert first.image[0, 0].tolist() == [30, 20, 10]
    assert first.source == 'pi-primary' and first.camera_identity['model'] == 'imx708'
    assert first.id != second.id and first.stream_generation == second.stream_generation
    assert first.metadata()['source_age_known'] is False
    source.close(); source.close(); camera.close.assert_called_once()
    with pytest.raises(InterruptedError): source.read()


def test_elegoo_keeps_bgr_receipt_source_and_generation():
    bgr = np.zeros((4, 6, 3), np.uint8); bgr[:] = [30, 20, 10]
    camera = SimpleNamespace(read=Mock(return_value=(bgr, dict(sequence=1, received_at=1.))),
        close=Mock(), stream_url='http://fixture-camera:81/stream', _generation=7, _thread=None)
    source = ElegooCameraSource(camera=camera, clock=lambda: 1.)
    frame = source.read()
    assert frame.source == 'elegoo-v4' and frame.image[0, 0].tolist() == [30, 20, 10]
    assert frame.stream_generation.endswith(':7')
    assert frame.metadata()['camera_identity']['endpoint'] == camera.stream_url
    with pytest.raises(ValueError, match='stale or reordered'): source.read()
    source.close()


def test_switch_releases_before_acquisition_no_old_frame_on_failure():
    events = []
    class Source:
        def __init__(self, name): self.name=name
        def read(self): return self.name
        def close(self): events.append('close:'+self.name)
    def factory(name):
        events.append('open:'+name)
        if name == 'elegoo': raise OSError('offline')
        return Source(name)
    owner = CameraSources(factory, on_change=lambda old, new: events.append('invalidate'))
    owner.switch('pi'); owner.switch('pi')
    with pytest.raises(OSError): owner.switch('elegoo')
    assert events == ['invalidate', 'open:pi', 'invalidate', 'close:pi', 'open:elegoo']
    with pytest.raises(InterruptedError): owner.read()
    owner.switch('pi'); assert owner.read() == 'pi'
    owner.close(); owner.close()
    with pytest.raises(InterruptedError): owner.switch('pi')


def test_failed_release_prevents_second_owner():
    source = SimpleNamespace(close=Mock(side_effect=TimeoutError('reader alive')))
    factory = Mock(return_value=source)
    owner = CameraSources(factory); owner.switch('elegoo')
    with pytest.raises(TimeoutError): owner.switch('pi')
    assert factory.call_count == 1 and owner.active is source


def test_tracking_view_preserves_legacy_rgb_coordinates():
    source = PiCameraSource(camera=SimpleNamespace(read=lambda: np.full((2, 3, 3), [10, 20, 30], np.uint8),
        close=Mock()), clock=lambda: 1.)
    owner = CameraSources(lambda name: source); owner.switch('pi')
    camera = TrackingCamera(owner); frame = camera.read()
    assert frame.shape == (720, 1280, 3) and frame[0, 0].tolist() == [10, 20, 30]
    camera.close()


def test_elegoo_lease_excludes_duplicate_endpoint_until_release():
    first = ElegooCameraLease('http://fixture-owner:81/stream')
    try:
        with pytest.raises(BlockingIOError): ElegooCameraLease('http://fixture-owner:82/other?x=1')
        other = ElegooCameraLease('http://different-fixture-owner:81/stream'); other.close()
    finally: first.close()
    again = ElegooCameraLease('http://fixture-owner:81/stream'); again.close(); again.close()


def test_failed_stream_open_releases_elegoo_ownership(monkeypatch):
    from hardware.elegoo_camera import ElegooCamera
    monkeypatch.setattr('urllib.request.urlopen', Mock(side_effect=OSError('fixture offline')))
    camera = ElegooCamera(stream_url='http://fixture-failed-open:81/stream')
    with pytest.raises(OSError): camera.open()
    assert camera._ownership is None
    lease = ElegooCameraLease(camera.stream_url); lease.close(); camera.close()

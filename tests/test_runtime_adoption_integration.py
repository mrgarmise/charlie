"""Reconcile completed donor source against existing physical-owner contracts."""
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import time
import numpy as np
from PIL import Image
import pytest


def test_gameplay_stream_reads_existing_publication_with_bounded_wait_and_source_identity(monkeypatch):
    from vision.camera import _PublishedPi
    from vision.camera_source import CameraFrame
    from experiments.ppal.eyes.sources import PiCameraSource
    pixels=np.frombuffer(bytes([30,20,10])*24,dtype=np.uint8).reshape(4,6,3)
    f=CameraFrame('original:7',pixels,1.1,source='pi-primary',sequence=7,stream_generation='existing-owner',
        capture_metadata=dict(SensorTimestamp=1000000000,ExposureTime=1000,LensPosition=2.,AfState=0))
    owner=SimpleNamespace(subscription=SimpleNamespace(wait=Mock(return_value=f)),_last_frame=None)
    facade=_PublishedPi(owner)
    source=PiCameraSource.__new__(PiCameraSource);source.camera=SimpleNamespace(picam2=facade,is_subscription=True)
    monkeypatch.setattr(time,'monotonic',lambda:1.1)
    image,capture=source._stream_capture()
    assert image.getpixel((0,0))==(10,20,30)
    assert capture['source_frame_id']=='original:7' and capture['source_sequence']==7
    assert capture['source_generation']=='existing-owner'
    owner.subscription.wait.assert_called_once_with(timeout=1.,captured_after=None)
    for invalid in (False,0,3,float('nan')):
        with pytest.raises(ValueError):facade.capture_request(wait=invalid)


def test_subscriber_timeout_does_not_flush_or_reconfigure_capture_owner():
    from experiments.ppal.eyes.sources import PiCameraSource
    source=PiCameraSource.__new__(PiCameraSource)
    source.camera=SimpleNamespace(is_subscription=True,picam2=SimpleNamespace(cancel_all_and_flush=Mock()))
    source._capture=Mock(side_effect=TimeoutError('no fresh publication'))
    with pytest.raises(TimeoutError):source._stream_capture()
    source.camera.picam2.cancel_all_and_flush.assert_not_called()


def test_published_causal_window_cannot_hide_source_drop_or_restart():
    from experiments.ppal.observation_stream import ObservationStream
    image=Image.new('RGB',(2,2));s=ObservationStream(lambda:None)
    def capture(seq):return dict(first_pixel_exposure_at=1.+seq*.01,sensor_timestamp_ns=1000000000+seq,
        source_sequence=seq,source_id='pi-primary',source_generation='original')
    with s.condition:
        s._append(image,capture(1));s._append(image,capture(3))
    assert s.stats()['source_exposures_not_delivered']==1
    s.begin_window()
    with s.condition:
        with pytest.raises(BufferError,match='causal'):s._append(image,capture(5))
        changed=capture(4);changed['source_generation']='replacement'
        with pytest.raises(RuntimeError,match='generation'):s._append(image,changed)


def test_score_device_lease_is_same_cross_process_gate_as_perception(tmp_path,monkeypatch):
    from hardware.hailo_session import accelerator_lease
    from experiments.ppal.neural_score.backends import shared_score_lease,Busy
    path=tmp_path/'shared-hailo.lock';monkeypatch.setenv('CHARLIE_HAILO_LOCK',str(path))
    with accelerator_lease():
        with pytest.raises(Busy):
            with shared_score_lease():raise AssertionError('a second accelerator owner was admitted')
    with shared_score_lease():pass

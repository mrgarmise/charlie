"""Offline fixtures only; these tests never connect to car/Hailo/camera."""
from types import SimpleNamespace
import io
import time
from unittest.mock import Mock
import numpy as np
import pytest
from vision.mobile_perception import MobileFrame, MobileFrameSource, MobilePerception
from vision.mobile_models import FixtureModel, HailoRelativeDepth, hailo_lease
from hardware.elegoo_camera import ElegooCamera


class Guard:
    def check(self, **kw):pass


def frame(at=1, ident='one'):
    return MobileFrame(ident,np.zeros((30,40,3),dtype=np.uint8),at)


def pipeline(clock=lambda:1):
    return MobilePerception(FixtureModel([dict(label='cat',box=[1,1,10,15],confidence=.9)]),
        FixtureModel(dict(kind='relative',clearance_certified=False)),resources=Guard(),revision='fixture',clock=clock)


def test_both_models_same_frame_and_no_physical_authority():
    f=frame(); p=pipeline(); result=p.observe(f)
    assert result['frame']['sha256'] and result['frame']['source_age_known'] is False
    assert result['model'][0]['backend']=='offline-fixture'
    assert result['motion_authorized'] is False
    with pytest.raises(ValueError):p.observe(f)


@pytest.mark.parametrize('at',[0,2,float('nan')])
def test_bad_time_rejected(at):
    with pytest.raises(ValueError):pipeline().observe(frame(at))


def test_late_inference_and_resource_preemption():
    times=iter([1,1,1.1,1.1,1.2,2])
    with pytest.raises(ValueError,match='late'):pipeline(lambda:next(times)).observe(frame())
    p=pipeline(); p.resources.check=Mock(side_effect=InterruptedError('primary owns resource'))
    p.detector.infer=Mock()
    with pytest.raises(InterruptedError):p.observe(frame())
    p.detector.infer.assert_not_called()


def test_cadence_reorder_and_invalid_detection():
    p=pipeline(lambda:1.1); p.observe(frame())
    assert p.observe(frame(1.1,'two')) is None
    with pytest.raises(ValueError):p.observe(frame(.9,'older'))
    p=pipeline(); p.detector.result[0]['confidence']=float('nan')
    with pytest.raises(ValueError):p.observe(frame())


def test_camera_source_drop_stale_reconnect():
    camera=Mock(); camera.read.side_effect=[(frame().image,dict(sequence=1,received_at=1)),
                                          (frame().image,dict(sequence=4,received_at=1.1)),
                                          (frame().image,dict(sequence=5,received_at=0))]
    source=MobileFrameSource(camera,clock=lambda:1.2)
    assert source.read().authentic
    assert source.read().sequence==4 and source.stats['dropped']==2
    with pytest.raises(ValueError):source.read()
    camera.close.assert_called_once()


def test_camera_legacy_read_and_atomic_metadata():
    c=ElegooCamera(); c._running=True; c._latest_frame=frame().image
    c._frame_id=1; c._received_at=1
    assert c.read().shape==(30,40,3)
    c._frame_id=2
    image,meta=c.read(with_metadata=True)
    assert meta['sequence']==2 and meta['received_at']==1
    assert meta['captured_at_source'] is None
    c._running=False


def test_mjpeg_corrupt_buffer_bounded_and_eof():
    c=ElegooCamera(); c._running=True
    c.response=SimpleNamespace(read=lambda n:b'X'*(2*1024*1024+1))
    c._reader_loop()
    assert isinstance(c._error,ValueError) and not c._running
    c=ElegooCamera();c._running=True;c.response=io.BytesIO(b'')
    c._reader_loop()
    assert isinstance(c._error,EOFError)


def test_depth_contract_rejects_nan_constant_wrong_layout():
    good=np.arange(12).reshape(1,3,4,1)
    assert HailoRelativeDepth.summarize(good,(3,4,1),True)['clearance_certified'] is False
    for bad in (np.zeros((1,3,4,1)),np.full((1,3,4,1),np.nan),good[0]):
        with pytest.raises(ValueError):HailoRelativeDepth.summarize(bad,(3,4,1),True)


def test_hailo_lease_yields_to_other_workload(tmp_path):
    with hailo_lease(tmp_path/'lock'):
        with pytest.raises(BlockingIOError):
            with hailo_lease(tmp_path/'lock'):pass
    with hailo_lease(tmp_path/'lock'):pass


def test_fixture_cannot_label_live_frame():
    from dataclasses import replace
    with pytest.raises(ValueError):pipeline().observe(replace(frame(),authentic=True))

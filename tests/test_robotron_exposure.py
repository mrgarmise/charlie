from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
from PIL import Image

from experiments.ppal.eyes.exposure import optimize_screen_exposure, screen_evidence
from experiments.ppal.eyes.settle import locate
from experiments.ppal.eyes.sources import PiCameraSource

FIXTURE = Path(__file__).parent/'fixtures/robotron-calibration-goodview/camera.png'


def test_real_goodview_border_survives_reduced_brightness():
    rgb = np.asarray(Image.open(FIXTURE))
    expected = np.array([(155,155),(880,78),(987,571),(169,685)])
    for scale in (1., .8, .65, .5):
        points = locate(Image.fromarray((rgb*scale).astype(np.uint8)))
        assert np.max(np.linalg.norm(points-expected, axis=1)) < 13
    evidence = screen_evidence(Image.open(FIXTURE), locate(Image.open(FIXTURE)))
    assert evidence['clipped_channel_fraction'] > .4


def test_white_border_on_saturated_blue_uses_rgb_contrast():
    rgb = np.zeros((480,640,3), dtype=np.uint8)
    rgb[:] = (0,0,255)
    points = np.array([(100,70),(540,70),(540,410),(100,410)])
    cv2.polylines(rgb, [points], True, (255,255,255), 5)
    measured = locate(Image.fromarray(rgb))
    assert np.max(np.linalg.norm(measured-points, axis=1)) < 12


def test_exposure_sweep_is_bounded_selects_detail_and_retains_rgb(tmp_path):
    original = np.array(Image.open(FIXTURE))
    class Source:
        capture = {'exposure_time_us':10000, 'analogue_gain':1., 'colour_gains':[1.2,1.5]}
        ev = 0
        history = []
        reads = 0
        def set_exposure_value(self, ev):
            self.ev = ev
            self.history.append(ev)
            return True
        def read(self):
            self.reads += 1
            # Synthetic camera response, not recovery of clipped real pixels.
            return Image.fromarray((original*(.8**-self.ev)).astype(np.uint8))
        def lock_exposure(self, capture):
            self.locked = capture
            return True
    source = Source()
    report = optimize_screen_exposure(source, tmp_path)
    assert report['selected_ev'] == -1
    assert report['exposure_locked']
    assert source.ev == -1
    assert source.reads <= 34
    assert np.array_equal(np.array(Image.open(tmp_path/'exposure-ev-0.png')), original)
    assert (tmp_path/'exposure.json').exists()


def test_absent_geometry_restores_default_ae(tmp_path):
    source = SimpleNamespace(capture=None, read=lambda:Image.new('RGB',(640,480)),
                             set_exposure_value=Mock(return_value=True))
    report = optimize_screen_exposure(source, tmp_path)
    assert report['selected_ev'] is None
    source.set_exposure_value.assert_called_with(0.)


def test_hardware_controls_preserve_awb_and_use_selected_metadata():
    picam = SimpleNamespace(camera_controls={
        'ExposureValue':(-8,8,0), 'AeEnable':(False,True,None),
        'ExposureTime':(1,100000,None), 'AnalogueGain':(1,16,None)}, set_controls=Mock())
    source = PiCameraSource.__new__(PiCameraSource)
    source.camera = SimpleNamespace(picam2=picam)
    assert source.set_exposure_value(-2)
    assert source.lock_exposure({'exposure_time_us':12000, 'analogue_gain':1.5})
    assert picam.set_controls.call_args.args[0] == {
        'AeEnable':False, 'ExposureTime':12000, 'AnalogueGain':1.5}
    assert all('AwbEnable' not in call.args[0] for call in picam.set_controls.call_args_list)

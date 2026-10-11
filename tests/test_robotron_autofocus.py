"""Mocked optics regressions. These tests do not qualify native image quality."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from experiments.ppal.eyes.autofocus import AutofocusConfig, establish_focus, verify_focus_lock


class FocusSource:
    def __init__(self, lens=2.4, state=2, interval=100_000_000):
        self.lens = lens
        self.state = state
        self.interval = interval
        self.sequence = 0
        self.calls = []
        self.capture = {}

    def focus_limits(self):
        return (0., 10.)

    def set_autofocus(self):
        self.calls.append('autofocus')

    def set_manual_focus(self, position):
        self.calls.append(('manual', position))
        self.state = 0
        self.lens = position

    def read(self):
        self.sequence += 1
        self.capture = dict(lens_position=self.lens, af_state=self.state,
                            sensor_timestamp_ns=self.sequence*self.interval)
        return Image.new('RGB', (64, 64))


def test_automatic_start_uses_observed_position_then_confirms_idle_manual_lock():
    source = FocusSource(interval=33_333_333)  # 30fps, six frames alone are too short
    report = {}
    position = establish_focus(source, report=report)
    assert position == 2.4
    assert source.calls == ['autofocus', ('manual', 2.4)]
    assert len(report['samples']) >= 9 and len(report['lock_samples']) >= 9
    assert 'unqualified' in report['image_sharpness']


@pytest.mark.parametrize('lens', [None, float('nan'), float('inf'), -1., 11., True])
def test_invalid_autofocus_lens_metadata_fails_without_manual_fallback(lens):
    source = FocusSource(lens=lens)
    report = {}
    with pytest.raises(ValueError, match='metadata'):
        establish_focus(source, report=report, config=AutofocusConfig(max_frames=8))
    assert source.calls == ['autofocus']
    assert report['status'] == 'failed'
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('state', [None, 0, 1, 3])
def test_stable_lens_is_not_successful_autofocus(state):
    with pytest.raises(ValueError, match='not focused'):
        establish_focus(FocusSource(state=state), report={}, config=AutofocusConfig(max_frames=8))


def test_repeated_or_unstable_metadata_cannot_settle():
    class Unstable(FocusSource):
        def read(self):
            self.lens = 2. if self.sequence%2 else 3.
            return super().read()
    for source in (Unstable(), FocusSource(interval=0)):
        with pytest.raises(ValueError):
            establish_focus(source, report={}, config=AutofocusConfig(max_frames=12))


def test_manual_lock_requires_reported_idle_and_matching_position():
    class Unlocked(FocusSource):
        def set_manual_focus(self, position):
            self.calls.append(('unacknowledged', position))
    with pytest.raises(ValueError, match='manual mode'):
        verify_focus_lock(Unlocked(), 2.4, config=AutofocusConfig(max_frames=8))
    class WrongLens(FocusSource):
        def set_manual_focus(self, position):
            self.state = 0
            self.lens = 4.
    with pytest.raises(ValueError, match='does not match'):
        verify_focus_lock(WrongLens(), 2.4, config=AutofocusConfig(max_frames=8))
    class BooleanState(FocusSource):
        def set_manual_focus(self, position):
            self.state = False  # boolean is not a libcamera Idle state
    with pytest.raises(ValueError, match='manual mode'):
        verify_focus_lock(BooleanState(), 2.4, config=AutofocusConfig(max_frames=8))


@pytest.mark.parametrize('limits', [(0., float('nan')), (4., 2.), (-1., 10.)])
def test_hardware_limits_are_required(limits):
    source = FocusSource()
    source.focus_limits = lambda:limits
    with pytest.raises(ValueError, match='limits'):
        establish_focus(source, report={})
    assert not source.calls


def test_diagnostic_manual_seed_is_explicit_validated_and_verified():
    source = FocusSource()
    report = {}
    assert establish_focus(source, report=report, manual_position=3.) == 3.
    assert source.calls == [('manual', 3.)]
    assert report['mode'] == 'manual diagnostic'
    with pytest.raises(ValueError):
        establish_focus(source, report={}, manual_position=float('nan'))


def test_camera_only_acceptance_closes_owner_on_failure(monkeypatch,tmp_path):
    from experiments.ppal import preflight
    from experiments.ppal.eyes import sources
    source = FocusSource()
    source.closed = False
    source.close = lambda:setattr(source, 'closed', True)
    monkeypatch.setattr(sources, 'PiCameraSource', lambda:source)
    def fail(*a, **kw):
        raise ValueError('optics not qualified')
    monkeypatch.setattr(preflight, 'sensory_preflight', fail)
    with pytest.raises(ValueError, match='not qualified'):
        preflight.main(['--output', str(tmp_path/'acceptance')])
    assert source.closed


def test_operational_defaults_and_reacquisition_do_not_inherit_manual_focus():
    # Audit parser defaults and every real call site; historical evidence remains.
    root = Path(__file__).parents[1]
    for name in ('play_robotron.py', 'marathon_robotron.py'):
        tree = ast.parse((root/'experiments/ppal'/name).read_text())
        declarations = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and node.func.attr=='add_argument'
                        and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value=='--focus']
        assert len(declarations)==1
        default = next(k.value for k in declarations[0].keywords if k.arg=='default')
        assert isinstance(default, ast.Constant) and default.value is None
    tree = ast.parse((root/'experiments/ppal/play_robotron.py').read_text())
    calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id=='sensory_preflight'),key=lambda n:n.lineno)
    assert len(calls)==2
    assert not any(k.arg=='seed_position' for k in calls[1].keywords)


def test_fresh_metadata_and_pixels_share_request_and_buffer_always_released():
    import numpy as np
    from experiments.ppal.eyes.sources import PiCameraSource
    from unittest.mock import Mock
    request=SimpleNamespace(get_metadata=lambda:dict(LensPosition=2.4, AfState=2,
                            SensorTimestamp=1_000_000_000, ExposureTime=1000),
                            make_array=lambda stream:np.zeros((2,2,3), dtype=np.uint8), release=Mock())
    source=PiCameraSource.__new__(PiCameraSource)
    source.camera=SimpleNamespace(picam2=SimpleNamespace(capture_request=Mock(return_value=request)))
    source.read_fresh()
    assert source.last_capture['af_state']==2 and source.last_capture['lens_position']==2.4
    source.camera.picam2.capture_request.assert_called_once_with(flush=True)
    request.release.assert_called_once()
    request.release.reset_mock()
    request.make_array=Mock(side_effect=RuntimeError('bad buffer'))
    with pytest.raises(RuntimeError):source.read_fresh()
    request.release.assert_called_once()

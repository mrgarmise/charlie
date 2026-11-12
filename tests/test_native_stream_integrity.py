"""Device-free controls for native metadata and meaningful-observation accounting."""
import time
import pytest
from experiments.ppal.eyes.sources import PiCameraSource
from experiments.ppal.gameplay_engine import CycleMetrics


@pytest.mark.parametrize('lens', [float('nan'), float('inf'), -float('inf'), True, None])
def test_stream_refuses_unverified_focus_without_touching_hardware(lens):
    source = object.__new__(PiCameraSource)
    source.last_capture = dict(lens_position=lens, af_state=0)
    source._capture = lambda **kw: object()
    with pytest.raises(ValueError, match='focus lock'):
        source._stream_capture()


def test_observation_alias_or_reordering_cannot_inflate_meaningful_rate(monkeypatch):
    monkeypatch.setattr(time, 'monotonic', lambda: 10.)
    metrics = CycleMetrics()
    assert metrics.decision('first', 9.9, supported=True)
    assert not metrics.decision('alias', 9.9, supported=True)
    assert not metrics.decision('older', 9.8, supported=True)
    assert metrics.decision('new', 9.95, supported=True)
    assert metrics.count == 2


def test_boolean_exposure_is_not_a_timestamp(monkeypatch):
    monkeypatch.setattr(time, 'monotonic', lambda: 1.1)
    assert not CycleMetrics().decision('invalid', True, supported=True)

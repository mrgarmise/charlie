"""A queued pre-command camera image must not become response evidence."""
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from PIL import Image
import pytest
from experiments.ppal.eyes.sources import PiCameraSource
from experiments.ppal.observation_camera import ObservedCamera
from experiments.ppal.robotron_agency import VisualAgency, VECTORS
from experiments.ppal.eyes.detectors import Detection


def test_fresh_request_pairs_pixels_metadata_and_releases_buffer(monkeypatch):
    from experiments.ppal.eyes import sources
    times = iter((10., 10.05))
    monkeypatch.setattr(sources.time, 'monotonic', lambda: next(times))
    bgr = np.array([[[9, 20, 80]]], dtype=np.uint8)
    request = Mock()
    request.make_array.return_value = bgr
    request.get_metadata.return_value = {'SensorTimestamp':10_030_000_000,
                                         'ExposureTime':10000, 'LensPosition':1.3}
    picam = Mock()
    picam.capture_request.return_value = request
    source = PiCameraSource.__new__(PiCameraSource)
    source.camera = SimpleNamespace(picam2=picam)
    frame = source.read_fresh()
    picam.capture_request.assert_called_once_with(flush=True)
    request.release.assert_called_once()
    bgr[:] = 0  # Reused camera buffers cannot corrupt the independent raw frame.
    assert frame.getpixel((0,0)) == (80,20,9)
    assert source.last_capture['first_pixel_exposure_at'] == pytest.approx(10.02)
    assert source.last_capture['capture_seconds'] == pytest.approx(.05)


def test_failed_pixel_copy_still_releases_camera_request():
    request = Mock()
    request.get_metadata.return_value = {}
    request.make_array.side_effect = RuntimeError('disconnected')
    picam = Mock()
    picam.capture_request.return_value = request
    source = PiCameraSource.__new__(PiCameraSource)
    source.camera = SimpleNamespace(picam2=picam)
    with pytest.raises(RuntimeError, match='disconnected'):
        source.read_fresh()
    request.release.assert_called_once()


def test_response_window_preserves_phase_for_fresh_and_one_frame_queue():
    points = [(20.,20.), (70.,70.)]
    class Camera:
        cached = list(points)
        last_capture = None
        def read(self):
            old = self.cached
            self.cached = list(points)
            return old
        def read_fresh(self):
            self.last_capture = {'first_pixel_exposure_at':None}
            return list(points)
    def experiment(fresh):
        points[:] = [(20.,20.), (70.,70.)]
        source = ObservedCamera(Camera(), require_fresh=fresh)
        visual = VisualAgency()
        def pairs():
            return [(Detection('unknown', p, (0,0,10,20),100), {}) for p in source.read()]
        class Controller:
            def execute(self, action, ms):
                u = VECTORS[action.move]
                p = points[0]
                points[0] = (p[0]+u[0], p[1]+u[1])
        player = visual.discover(pairs, Controller(), observation_time=lambda:source.timestamp)
        return player, visual
    stale, old = experiment(False)
    # The explicit two-endpoint response window also tolerates this one-frame
    # synthetic queue. Armed production still requires fresh capture metadata.
    assert stale == points[0]
    assert old.agency.beliefs[1].contradictions == 0
    fresh, visual = experiment(True)
    assert fresh == points[0]
    assert visual.agency.self_id == 1
    assert visual.tracker.next_id == 3  # One association pass preserves the same IDs.
    assert visual.agency.beliefs[1].hits >= 3
    assert visual.agency.beliefs[1].stops >= 2
    assert visual.agency.beliefs[1].reversed


def test_second_pi_run_is_phase_limited_without_player_track_fragmentation():
    import json
    from pathlib import Path
    from experiments.ppal.agency import AgencyTracker
    fixture = json.loads((Path(__file__).parent / 'fixtures/robotron-agency-second/probe-endpoints.json').read_text())
    rows = fixture['samples']
    player_id = fixture['likely_player_id']
    assert all(str(player_id) in row['positions'] for row in rows)
    original, shifted = AgencyTracker(), AgencyTracker()
    for index, row in enumerate(rows):
        positions = {int(key): value for key, value in row['positions'].items()}
        original.observe(positions, row['command'])
        # Offline counterfactual only: NOT a live command relabeling algorithm.
        shifted.observe(positions, rows[index-1]['command'] if index else None)
    assert original.self_id is None
    assert original.beliefs[player_id].hits == 0
    assert original.beliefs[player_id].contradictions == 12
    assert shifted.self_id == player_id
    belief = shifted.beliefs[player_id]
    assert belief.hits == 6 and belief.stops == 5 and belief.reversed

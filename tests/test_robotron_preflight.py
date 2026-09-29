import cv2
import numpy as np
from PIL import Image

from experiments.ppal.preflight import (
    PreflightConfig,
    focus_region,
    screen_sharpness,
    _focus_positions,
)


def test_focus_region_excludes_playfield_perimeter():
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    # Deliberately noisy perimeter that should not dominate optical scoring.
    image[:10] = 255
    image[-10:] = 255
    image[:, :20] = 255
    image[:, -20:] = 255

    region = focus_region(Image.fromarray(image), margin=.10)

    assert region.shape == (80, 160, 3)
    assert np.max(region) == 0


def test_screen_sharpness_responds_to_screen_detail():
    flat = Image.fromarray(
        np.full((480, 640, 3), 100, dtype=np.uint8)
    )

    detailed = np.full((480, 640, 3), 100, dtype=np.uint8)
    detailed[100:380:4, 100:540] = 255
    detailed = Image.fromarray(detailed)

    assert screen_sharpness(detailed) > screen_sharpness(flat)


def test_focus_positions_are_local_not_full_lens_sweep():
    cfg = PreflightConfig(
        focus_radius=1.0,
        focus_step=.5,
        lens_min=0.0,
        lens_max=32.0,
    )

    positions = _focus_positions(1.5, cfg)

    assert positions == [.5, 1.0, 1.5, 2.0, 2.5]
    assert 32.0 not in positions


def test_focus_positions_clamp_at_physical_limit():
    cfg = PreflightConfig(
        focus_radius=1.0,
        focus_step=.5,
        lens_min=0.0,
        lens_max=32.0,
    )

    assert _focus_positions(.25, cfg) == [0.0, .25, .75, 1.25]


class FakeFocusSource:
    """Camera whose image detail has a known optimum lens position."""

    def __init__(self, optimum=1.5):
        self.optimum = optimum
        self.position = 0.0
        self.focus_history = []

    def set_manual_focus(self, position):
        self.position = float(position)
        self.focus_history.append(self.position)

    def read(self):
        # Create vertical bars whose contrast peaks at the optical optimum.
        distance = abs(self.position - self.optimum)
        contrast = max(0.0, 1.0 - distance / 2.0)

        image = np.full((480, 640, 3), 100, dtype=np.uint8)
        value = int(round(100 + 155 * contrast))
        image[80:400, 80:560:4] = value

        return Image.fromarray(image)


class IdentityCalibration:
    def apply(self, frame):
        return frame


def test_optimizer_finds_known_screen_focus_and_locks_it():
    from experiments.ppal.preflight import optimize_screen_focus

    source = FakeFocusSource(optimum=1.5)
    cfg = PreflightConfig(
        focus_radius=1.0,
        focus_step=.25,
        focus_samples=1,
        keep_focus_ratio=.99,
    )

    result = optimize_screen_focus(
        source,
        IdentityCalibration(),
        seed_position=1.0,
        config=cfg,
    )

    assert result.changed
    assert result.lens_position == 1.5

    # Last camera operation must leave the selected focus manually locked.
    assert source.focus_history[-1] == 1.5


def test_optimizer_keeps_already_good_focus():
    from experiments.ppal.preflight import optimize_screen_focus

    source = FakeFocusSource(optimum=1.5)
    cfg = PreflightConfig(
        focus_radius=1.0,
        focus_step=.25,
        focus_samples=1,
        keep_focus_ratio=.94,
    )

    result = optimize_screen_focus(
        source,
        IdentityCalibration(),
        seed_position=1.5,
        config=cfg,
    )

    assert not result.changed
    assert result.lens_position == 1.5
    assert source.focus_history[-1] == 1.5


def test_optimizer_does_not_chase_small_improvement():
    from experiments.ppal.preflight import optimize_screen_focus

    source = FakeFocusSource(optimum=1.5)
    cfg = PreflightConfig(
        focus_radius=1.0,
        focus_step=.25,
        focus_samples=1,
        # Seed scores about 77% of optimum in this synthetic camera.
        # A 75% acceptance threshold should therefore keep it.
        keep_focus_ratio=.75,
    )

    result = optimize_screen_focus(
        source,
        IdentityCalibration(),
        seed_position=1.25,
        config=cfg,
    )

    # 1.5 is mathematically sharper, but 1.25 is already good enough.
    assert not result.changed
    assert result.lens_position == 1.25
    assert source.focus_history[-1] == 1.25


def _synthetic_robotron_border(striped=False):
    """Camera-like frame containing a large bright Robotron rectangle."""
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    # TL, TR, BR, BL-ish rectangle with a little perspective.
    tl = (105, 75)
    tr = (545, 82)
    br = (530, 405)
    bl = (115, 398)

    if striped:
        colors = [
            (255, 40, 255),   # top
            (40, 255, 255),   # right
            (255, 255, 40),   # bottom
            (40, 255, 80),    # left
        ]
    else:
        colors = [(255, 40, 255)] * 4

    points = [tl, tr, br, bl]
    for i in range(4):
        cv2.line(
            image,
            points[i],
            points[(i + 1) % 4],
            colors[i],
            8,
        )

    # settle.locate() accepts PIL images.
    return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def test_geometry_locator_accepts_uniform_gameplay_border():
    from experiments.ppal.eyes.settle import locate

    frame = _synthetic_robotron_border(striped=False)
    points = locate(frame, require_uniform_border=True)

    assert np.asarray(points).shape == (4, 2)


def test_geometry_only_locator_accepts_attract_style_border():
    from experiments.ppal.eyes.settle import locate

    frame = _synthetic_robotron_border(striped=True)
    points = locate(frame, require_uniform_border=False)

    assert np.asarray(points).shape == (4, 2)


def test_strict_locator_rejects_attract_style_border():
    from experiments.ppal.eyes.settle import locate

    frame = _synthetic_robotron_border(striped=True)

    try:
        locate(frame, require_uniform_border=True)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "strict gameplay-border locator unexpectedly accepted "
            "the multicolour attract-style border"
        )

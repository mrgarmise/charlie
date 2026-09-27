import numpy as np

from experiments.ppal.camera import (
    FocusConfig,
    FocusManager,
    FocusMode,
    sharpness_score,
)


class FakeCamera:
    def __init__(self):
        self.autofocus_calls = 0
        self.manual_positions = []
        self.frame = np.zeros((40, 40, 3), dtype=np.uint8)

    def set_autofocus(self):
        self.autofocus_calls += 1

    def set_manual_focus(self, lens_position):
        self.manual_positions.append(float(lens_position))

    def capture_frame(self):
        return self.frame.copy()


def detailed_frame():
    """High-contrast checkerboard gives Laplacian something to measure."""
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    frame[::2, ::2] = 255
    frame[1::2, 1::2] = 255
    return frame


def blurry_frame():
    return np.full((40, 40, 3), 127, dtype=np.uint8)


def test_sharpness_distinguishes_detail_from_flat_image():
    assert sharpness_score(detailed_frame()) > sharpness_score(blurry_frame())


def test_auto_requests_camera_autofocus():
    camera = FakeCamera()
    focus = FocusManager(camera)

    focus.auto()

    assert camera.autofocus_calls == 1
    assert focus.status.mode is FocusMode.AUTO


def test_lock_holds_requested_lens_position():
    camera = FakeCamera()
    focus = FocusManager(camera)

    focus.lock(2.5)

    assert camera.manual_positions[-1] == 2.5
    assert focus.status.mode is FocusMode.LOCK
    assert focus.status.lens_position == 2.5


def test_good_frame_establishes_baseline():
    camera = FakeCamera()
    focus = FocusManager(camera)

    score = focus.observe(detailed_frame())

    assert focus.status.baseline_sharpness == score
    assert score >= focus.config.minimum_sharpness


def test_sustained_blur_is_detected_without_automatic_recovery():
    camera = FakeCamera()
    config = FocusConfig(
        blur_ratio=0.55,
        blur_frames=3,
        recovery_enabled=False,
    )
    focus = FocusManager(camera, config)

    focus.observe(detailed_frame())

    for _ in range(3):
        focus.observe(blurry_frame())

    assert focus.status.blurry_frames == 3
    assert focus.status.recovery_count == 0
    assert focus.status.mode is FocusMode.AUTO


def test_recovery_can_be_explicitly_enabled():
    camera = FakeCamera()
    config = FocusConfig(
        blur_ratio=0.55,
        blur_frames=2,
        recovery_enabled=True,
        sweep_start=1.0,
        sweep_end=1.0,
        sweep_step=0.25,
        samples_per_position=1,
    )
    focus = FocusManager(camera, config)

    focus.observe(detailed_frame())
    camera.frame = detailed_frame()

    # Force two observations to look blurry without affecting the frame
    # that recover() obtains from FakeCamera.
    flat = blurry_frame()
    focus.observe(flat)
    focus.observe(flat)

    assert focus.status.recovery_count == 1
    assert camera.manual_positions[-1] == 1.0
    assert focus.status.mode is FocusMode.LOCK

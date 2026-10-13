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


def test_lock_holds_and_remembers_requested_lens_position():
    camera = FakeCamera()
    focus = FocusManager(camera)

    focus.lock(0.75)

    assert camera.manual_positions[-1] == 0.75
    assert focus.status.mode is FocusMode.LOCK
    assert focus.status.lens_position == 0.75
    assert focus.status.known_good_position == 0.75


def test_lock_clamps_to_physical_lens_range():
    camera = FakeCamera()
    focus = FocusManager(
        camera,
        FocusConfig(lens_min=0.0, lens_max=32.0),
    )

    focus.lock(100.0)

    assert camera.manual_positions[-1] == 32.0
    assert focus.status.lens_position == 32.0
    assert focus.status.known_good_position == 32.0


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


def test_recovery_without_known_good_position_returns_to_autofocus():
    camera = FakeCamera()
    focus = FocusManager(
        camera,
        FocusConfig(
            recovery_enabled=True,
            blur_frames=2,
        ),
    )

    focus.observe(detailed_frame())
    focus.observe(blurry_frame())
    focus.observe(blurry_frame())

    assert focus.status.recovery_count == 1
    assert camera.autofocus_calls == 1
    assert focus.status.mode is FocusMode.AUTO


def test_recovery_searches_near_known_good_position():
    camera = FakeCamera()
    config = FocusConfig(
        recovery_enabled=True,
        recovery_radius=0.25,
        sweep_step=0.25,
        samples_per_position=1,
    )
    focus = FocusManager(camera, config)

    # Approximately the position Charlie's real IMX708 selected for Robotron.
    focus.lock(0.75)

    camera.manual_positions.clear()
    camera.frame = detailed_frame()

    best_position, best_score = focus.recover()

    assert camera.manual_positions[:3] == [0.5, 0.75, 1.0]
    assert best_position in (0.5, 0.75, 1.0)
    assert best_score > 0
    assert focus.status.mode is FocusMode.LOCK
    assert focus.status.known_good_position == best_position


def test_recovery_near_zero_never_requests_negative_lens_position():
    camera = FakeCamera()
    focus = FocusManager(
        camera,
        FocusConfig(
            lens_min=0.0,
            lens_max=32.0,
            recovery_radius=1.5,
            sweep_step=0.5,
            samples_per_position=1,
        ),
    )

    focus.lock(0.25)
    camera.manual_positions.clear()
    camera.frame = detailed_frame()

    focus.recover()

    assert min(camera.manual_positions) >= 0.0

"""Robotron preflight: discover screen geometry and prepare task-aware optics.

Preflight runs immediately before START.

Important invariants:
* Discover Robotron from the CURRENT full camera field of view.
* Previous geometry is never required.
* Focus quality is measured on the Robotron playfield, not the whole frame.
* Geometry is rechecked after focus.
* Successful preflight leaves the camera in manual locked focus.
* Gameplay/SELF state is not involved in focus decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

import cv2
import numpy as np
from PIL import Image

from .eyes.calibration import Calibration
from .eyes.settle import locate


def sensory_preflight(source, output, *, seed_position=None, timeout=60.):
    """Reuse current camera owner/geometry/focus/exposure; no motion authority.

    White balance settles and locks measured gains only. Without an independent
    color chart we explicitly cannot qualify absolute color fidelity.
    """
    from dataclasses import asdict
    from learning.foundry import atomic_json
    from .eyes.exposure import optimize_screen_exposure, screen_evidence
    started=time.monotonic();deadline=started+timeout
    class BoundedSource:
        def read(self):
            if time.monotonic()>=deadline:raise ValueError('sensory preflight deadline; assistance required')
            return source.read()
        def __getattr__(self,name):return getattr(source,name)
    bounded=BoundedSource()
    report=dict(status='preparing',started_at=started,physical_motion=False,
                color_fidelity='unqualified without an independent color reference')
    try:
        exposure=optimize_screen_exposure(bounded,output)
        report['exposure']=exposure
        seed=seed_position if seed_position is not None else bounded.lens_position()
        if seed is None:raise ValueError('focus metadata unavailable; assistance required')
        optics=run_preflight(bounded,seed_position=seed)
        report.update(geometry=asdict(optics.geometry),focus=asdict(optics.focus))
        # Require actual detail, not a successful method return or zero-valued
        # focus optimum. Limits reuse established exposure qualification.
        frame=bounded.read()
        import numpy as np
        quality=screen_evidence(frame,np.array(optics.geometry.corners))
        report['quality']=quality
        if quality['detail_pixels']<50 or optics.focus.score<=0:
            raise ValueError('insufficient visual detail for meaningful observation; assistance required')
        lock=getattr(bounded,'lock_white_balance',None)
        report['white_balance_locked']=bool(lock(source.capture)) if callable(lock) else False
        report['status']='usable'
        report['finished_at']=time.monotonic()
        optics.calibration.save(output/'calibration.json')
        return optics.calibration,report
    except Exception as exc:
        report.update(status='failed',reason=str(exc),finished_at=time.monotonic(),request='restore a complete readable display view')
        raise
    finally:
        atomic_json(output/'sensory-preflight.json',report)


@dataclass(frozen=True)
class PreflightConfig:
    # Geometry must agree repeatedly before START is authorized.
    stable_views: int = 6
    max_jitter_pixels: float = 8.0
    geometry_attempts: int = 24
    geometry_interval: float = 0.10

    # Ignore a thin playfield perimeter for focus scoring.  The animated
    # Robotron border is useful for geometry/state but can distort focus scores.
    focus_margin: float = 0.08

    # Focus search.  We intentionally search a modest neighborhood around an
    # autofocus/known-good seed rather than treating the entire lens range as
    # equally plausible.
    focus_radius: float = 1.5
    focus_step: float = 0.25
    focus_samples: int = 3
    lens_min: float = 0.0
    lens_max: float = 32.0

    # If current locked focus remains close to the locally measured optimum,
    # keep it instead of needlessly changing focus every game.
    keep_focus_ratio: float = 0.94


@dataclass(frozen=True)
class GeometryResult:
    calibration: Calibration
    corners: tuple[tuple[float, float], ...]
    jitter_pixels: float
    observations: int


@dataclass(frozen=True)
class FocusResult:
    lens_position: float
    score: float
    previous_score: float | None
    changed: bool


@dataclass(frozen=True)
class PreflightResult:
    calibration: Calibration
    geometry: GeometryResult
    focus: FocusResult


def _as_rgb_array(frame: Image.Image) -> np.ndarray:
    return np.asarray(frame.convert("RGB"))


def focus_region(playfield: Image.Image, margin: float = 0.08) -> np.ndarray:
    """Return the interior Robotron region used only for optical focus scoring."""
    rgb = _as_rgb_array(playfield)
    h, w = rgb.shape[:2]

    margin = max(0.0, min(float(margin), 0.40))
    mx = int(round(w * margin))
    my = int(round(h * margin))

    if w - 2 * mx < 32 or h - 2 * my < 32:
        return rgb

    return rgb[my:h-my, mx:w-mx]


def screen_sharpness(playfield: Image.Image, margin: float = 0.08) -> float:
    """Variance-of-Laplacian measured only inside the normalized game screen."""
    region = focus_region(playfield, margin)

    if region.ndim == 3:
        gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)
    else:
        gray = region

    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def locate_stable_geometry(source, config: PreflightConfig | None = None) -> GeometryResult:
    """Find Robotron anew from full FOV and require repeated stable geometry.

    Color uniformity is deliberately disabled here: attract mode has the same
    physical rectangle with a striped/multicolour border.
    """
    cfg = config or PreflightConfig()

    observations: list[np.ndarray] = []
    frame = None
    last_reason = "No Robotron rectangle found"
    jitter = float("inf")

    for _attempt in range(cfg.geometry_attempts):
        frame = source.read()

        try:
            points = locate(frame, require_uniform_border=False)
        except ValueError as exc:
            observations.clear()
            last_reason = str(exc)
        else:
            observations.append(np.asarray(points, dtype=float))
            observations = observations[-cfg.stable_views:]

            corners = np.median(np.asarray(observations), axis=0)
            jitter = float(np.max(
                np.linalg.norm(np.asarray(observations) - corners, axis=2)
            ))

            if (
                len(observations) >= cfg.stable_views
                and jitter <= cfg.max_jitter_pixels
            ):
                calibration = Calibration.from_pixels(
                    corners.tolist(),
                    frame.size,
                )
                return GeometryResult(
                    calibration=calibration,
                    corners=tuple(
                        (float(x), float(y))
                        for x, y in corners
                    ),
                    jitter_pixels=jitter,
                    observations=len(observations),
                )

            if jitter > cfg.max_jitter_pixels and observations:
                observations.pop(0)
                last_reason = (
                    "Robotron geometry still moving "
                    f"({jitter:.1f}px)"
                )

        if cfg.geometry_interval:
            time.sleep(cfg.geometry_interval)

    raise ValueError(
        last_reason
        + "; preflight could not establish stable Robotron geometry"
    )


def score_current_focus(
    source,
    calibration: Calibration,
    *,
    samples: int,
    margin: float,
) -> float:
    """Median screen-local focus score across several fresh frames."""
    scores = []

    for _ in range(max(1, samples)):
        frame = source.read()
        playfield = calibration.apply(frame)
        scores.append(screen_sharpness(playfield, margin))

    return float(np.median(scores))


def _focus_positions(center: float, cfg: PreflightConfig) -> list[float]:
    """Candidate positions centered on the current/known-good lens position."""
    center = max(cfg.lens_min, min(cfg.lens_max, float(center)))
    positions = {round(center, 6)}

    step = cfg.focus_step
    if step <= 0:
        return [round(center, 6)]

    offset = step
    while offset <= cfg.focus_radius + 1e-9:
        positions.add(round(max(cfg.lens_min, center - offset), 6))
        positions.add(round(min(cfg.lens_max, center + offset), 6))
        offset += step

    return sorted(positions)


def optimize_screen_focus(
    source,
    calibration: Calibration,
    *,
    seed_position: float,
    config: PreflightConfig | None = None,
) -> FocusResult:
    """Search near seed focus using ONLY normalized Robotron imagery.

    `source` must provide set_manual_focus(position) and read().
    """
    cfg = config or PreflightConfig()

    seed = max(cfg.lens_min, min(cfg.lens_max, float(seed_position)))

    source.set_manual_focus(seed)
    previous_score = score_current_focus(
        source,
        calibration,
        samples=cfg.focus_samples,
        margin=cfg.focus_margin,
    )

    candidates: list[tuple[float, float]] = []

    for position in _focus_positions(seed, cfg):
        source.set_manual_focus(position)

        score = score_current_focus(
            source,
            calibration,
            samples=cfg.focus_samples,
            margin=cfg.focus_margin,
        )
        candidates.append((score, position))

    best_score, best_position = max(candidates)

    # Verification, not gratuitous refocusing: if the existing focus is already
    # effectively as good as the local optimum, retain it.
    if previous_score >= best_score * cfg.keep_focus_ratio:
        chosen_position = seed
        chosen_score = previous_score
        changed = False
    else:
        chosen_position = best_position
        chosen_score = best_score
        changed = abs(chosen_position - seed) > 1e-9

    # This is the lock.  Do not return to AF during the episode.
    source.set_manual_focus(chosen_position)

    return FocusResult(
        lens_position=float(chosen_position),
        score=float(chosen_score),
        previous_score=float(previous_score),
        changed=changed,
    )


def run_preflight(
    source,
    *,
    seed_position: float,
    config: PreflightConfig | None = None,
) -> PreflightResult:
    """Complete pre-START optics gate.

    1. Discover Robotron from full FOV.
    2. Build provisional geometry.
    3. Optimize/verify focus using only Robotron imagery.
    4. Rediscover geometry after focus.
    5. Leave focus manually locked.
    """
    cfg = config or PreflightConfig()

    provisional = locate_stable_geometry(source, cfg)

    focus = optimize_screen_focus(
        source,
        provisional.calibration,
        seed_position=seed_position,
        config=cfg,
    )

    # Focus changes can slightly alter apparent edge position.  Geometry used
    # for gameplay therefore comes from fresh post-focus observations.
    final_geometry = locate_stable_geometry(source, cfg)

    return PreflightResult(
        calibration=final_geometry.calibration,
        geometry=final_geometry,
        focus=focus,
    )

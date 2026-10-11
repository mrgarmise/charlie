"""Bounded optical starting point from fresh libcamera metadata, without geometry.

AfStateFocused is the driver's belief, not independent image-quality evidence.
The later playfield focus/detail and geometry gates remain mandatory.
"""
from dataclasses import dataclass
import math
import time

import numpy as np


@dataclass(frozen=True)
class AutofocusConfig:
    timeout: float = 10.
    max_frames: int = 90
    stable_frames: int = 6
    stable_seconds: float = .25
    tolerance: float = .05  # dioptres; also used to verify the commanded lock


def lens_limits(source):
    getter = getattr(source, 'focus_limits', None)
    if not callable(getter):
        raise ValueError('hardware LensPosition limits unavailable')
    limits = getter()
    if len(limits) != 2:
        raise ValueError('hardware LensPosition limits unavailable')
    low, high = map(float, limits)
    if not all(math.isfinite(v) for v in (low, high)) or low < 0 or low >= high:
        raise ValueError('invalid hardware LensPosition limits')
    return low, high


def _diagnostic(value):
    """Preserve invalid metadata descriptively in strict JSON, never as a number."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {key: _diagnostic(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_diagnostic(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return repr(value)


def _settle(source, report, *, config, limits, target=None):
    deadline = time.monotonic() + config.timeout
    observations = []
    previous_timestamp = None
    reason = 'no fresh autofocus metadata'
    rows = report.setdefault('lock_samples' if target is not None else 'samples', [])
    for _ in range(config.max_frames):
        if time.monotonic() >= deadline:
            break
        source.read_fresh()
        capture = getattr(source, 'capture', None)
        if not isinstance(capture, dict):
            capture = getattr(source, 'last_capture', None)
        row = dict(capture or {})
        diagnostic = _diagnostic(row)
        rows.append(diagnostic)
        lens, stamp, state = (row.get(k) for k in ('lens_position', 'sensor_timestamp_ns', 'af_state'))
        valid = (isinstance(lens, (int, float)) and not isinstance(lens, bool)
                 and math.isfinite(lens) and limits[0] <= lens <= limits[1]
                 and isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
                 and math.isfinite(stamp) and stamp > 0
                 and (previous_timestamp is None or stamp > previous_timestamp))
        if not valid:
            reason = 'missing, invalid, out-of-range or repeated fresh lens metadata'
            observations.clear()
            diagnostic['rejection'] = reason
            continue
        previous_timestamp = stamp
        # libcamera: continuous AF must report Focused (2); manual must report
        # Idle (0). Stable scanning/failed positions are never accepted.
        if isinstance(state, bool) or state != (0 if target is not None else 2):
            reason = 'manual mode not confirmed' if target is not None else 'autofocus not focused'
            observations.clear()
            diagnostic['rejection'] = reason
            continue
        if target is not None and abs(lens-target) > config.tolerance:
            reason = 'manual lens position does not match requested lock'
            observations.clear()
            diagnostic['rejection'] = reason
            continue
        observations.append((float(lens), float(stamp)/1e9))
        positions = [v[0] for v in observations]
        if max(positions)-min(positions) > config.tolerance:
            reason = 'lens position unstable'
            observations = observations[-1:]
            continue
        if (len(observations) >= config.stable_frames
                and observations[-1][1]-observations[0][1] >= config.stable_seconds):
            return float(np.median(positions))
        reason = 'insufficient stable fresh lens observations'
    raise ValueError(reason + '; optical starting point unavailable; assistance required')


def verify_focus_lock(source, position, *, report=None, config=None, limits=None):
    config = config or AutofocusConfig()
    limits = limits or lens_limits(source)
    if not math.isfinite(position) or not limits[0] <= position <= limits[1]:
        raise ValueError('manual diagnostic focus outside supported hardware limits')
    source.set_manual_focus(position)
    return _settle(source, report if report is not None else {},
                   config=config, limits=limits, target=position)


def establish_focus(source, *, report, manual_position=None, config=None):
    """Select an AF-derived seed, or an explicitly requested diagnostic lock."""
    cfg = config or AutofocusConfig()
    report.update(status='establishing', started_at=time.monotonic(),
                  mode='automatic' if manual_position is None else 'manual diagnostic',
                  image_sharpness='unqualified until playfield refinement and final quality gates')
    try:
        limits = lens_limits(source)
        report['hardware_limits'] = list(limits)
        if manual_position is None:
            # Restore AE for a reacquisition following a previous exposure lock.
            exposure = getattr(source, 'set_exposure_value', None)
            if callable(exposure):
                report['ae_reset'] = bool(exposure(0.))
            source.set_autofocus()
            position = _settle(source, report, config=cfg, limits=limits)
        else:
            position = float(manual_position)
        if not math.isfinite(position) or not limits[0] <= position <= limits[1]:
            raise ValueError('manual diagnostic focus outside supported hardware limits')
        report['selected_position'] = position
        report['locked_position'] = verify_focus_lock(source, position, report=report, config=cfg, limits=limits)
        report['status'] = 'stable manual starting point; image quality pending'
        return report['locked_position']
    except Exception as exc:
        report.update(status='failed', reason=str(exc))
        raise
    finally:
        report['finished_at'] = time.monotonic()

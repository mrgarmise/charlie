"""Bounded camera preflight; never runs in the tracking/control observation loop."""
import json
import time

import cv2
import numpy as np

from .calibration import Calibration
from .settle import locate


def screen_evidence(frame, corners):
    """Evaluate local detail, excluding border and dark room; retain original RGB."""
    board = Calibration.from_pixels(corners.tolist(), frame.size).apply(frame)
    rgb = np.asarray(board)
    margin = max(8, min(rgb.shape[:2]) // 20)
    rgb = rgb[margin:-margin, margin:-margin]
    background = cv2.medianBlur(rgb, 31).astype(np.int16)
    foreground = ((rgb.astype(np.int16)-background).max(axis=2) > 45)
    foreground &= rgb.max(axis=2) > 100
    count = int(foreground.sum())
    pixels = rgb[foreground]
    return {
        'detail_pixels': count,
        'clipped_channel_fraction': float((pixels.max(axis=1) >= 250).mean()) if count else None,
        'clipped_white_fraction': float((pixels.min(axis=1) >= 250).mean()) if count else None,
        'colored_fraction': float((np.ptp(pixels.astype(float), axis=1) > 30).mean()) if count else None,
    }


def optimize_screen_exposure(source, output):
    """Try 0..-3 EV before START, then retain the least dim unclipped view.

    Only complete arena geometry authorizes screen measurement. Unsupported
    controls or absent geometry retain default AE. AWB remains automatic: there
    is no known neutral color reference with which to calibrate it here.
    """
    output.mkdir(parents=True, exist_ok=True)
    report = {'status': 'unsupported', 'samples': [], 'selected_ev': None,
              'awb': 'unchanged; original RGB retained'}
    started = time.monotonic()
    setter = getattr(source, 'set_exposure_value', None)
    if not callable(setter):
        return report
    try:
        deadline = started + 12
        for ev in (0., -1., -2., -3.):
            if not setter(ev):
                break
            # Controls/AE take multiple requests to propagate. Record the
            # actual settings on the evaluated fresh exposures, not a cached
            # capture_metadata call or a claim that the EV is settled.
            for _ in range(6):
                source.read()
            frame = source.read()
            name = f'exposure-ev-{abs(int(ev))}.png'
            frame.save(output/name)
            capture = getattr(source, 'capture', None)
            row = {'ev': ev, 'frame': name,
                   'capture': capture if isinstance(capture, dict) else None}
            report['samples'].append(row)
            try:
                corners = locate(frame, require_uniform_border=False)
                row['corners'] = corners.tolist()
                row.update(screen_evidence(frame, corners))
            except ValueError as exc:
                row['reason'] = str(exc)
            if time.monotonic() >= deadline:
                break
        valid = [r for r in report['samples'] if r.get('detail_pixels', 0) >= 50]
        baseline = next((r for r in valid if r['ev'] == 0), None)
        if baseline is None and valid:
            # A clipped zero-EV frame can hide geometry entirely. Retain a
            # measured reference from the least dim valid view instead of
            # restoring the unreadable setting after a successful sweep.
            baseline = max(valid, key=lambda r:r['ev'])
            report['reference_note'] = 'zero EV lacked geometry; least dim measured valid view used'
        report['reference_ev'] = baseline['ev'] if baseline else None
        # A changing attract scene cannot justify arbitrarily darker settings.
        # Require ample remaining screen detail and meaningful improvement.
        if baseline:
            candidates = [r for r in valid if r['detail_pixels'] >= baseline['detail_pixels']*.5]
            acceptable = [r for r in candidates if r['clipped_channel_fraction'] <= .10]
            best = (max(acceptable, key=lambda r: r['ev']) if acceptable else
                    min(candidates, key=lambda r: (r['clipped_channel_fraction'], -r['ev'])))
            if best['clipped_channel_fraction'] > baseline['clipped_channel_fraction']*.75:
                best = baseline
            setter(best['ev'])
            for _ in range(6):
                source.read()
            # Lock the actual selected exposure/gain to prevent room/background
            # metering from changing it when gameplay starts. Do not lock AWB.
            capture = getattr(source, 'capture', None)
            lock = getattr(source, 'lock_exposure', None)
            locked = bool(lock(capture)) if callable(lock) and isinstance(capture, dict) else False
            report.update(status='selected', selected_ev=best['ev'],
                          exposure_locked=locked, selected_capture=capture)
            print(f"EXPOSURE: EV={best['ev']:+.0f} locked={locked}; RGB evidence saved")
        else:
            setter(0.)
            report['status'] = 'no complete arena; default AE retained'
    except Exception as exc:
        # Camera preflight failure must not conceal its provenance or leave a
        # partially swept setting behind. Actual capture failure is still fatal
        # on the next ordinary read, rather than fabricating a valid image.
        setter(0.)
        report.update(status='failed; default AE restored', error=f'{type(exc).__name__}: {exc}')
    finally:
        report['processing_seconds'] = time.monotonic()-started
        (output/'exposure.json').write_text(json.dumps(report, indent=2)+'\n')
    return report

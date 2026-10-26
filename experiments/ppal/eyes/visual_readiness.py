"""Observation-only handoff of a qualified screen view to its existing camera owner.

A durable lock is a candidate, never current readiness, START or motion authority.
Reuse Active Vision's Calibration/quality contract and Robotron's edge photometry.
"""
import json
import math
import os
from pathlib import Path
import time

import numpy as np

from .calibration import Calibration
from .settle import locate, verify_supported_border


def default_view_path():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'charlie/vision/robotron-view.json'


def calibration_from_record(record):
    if not isinstance(record, dict):
        raise ValueError('typed visual-readiness record required')
    schema = record.get('schema')
    if schema == 'charlie-active-vision-v1':
        if (record.get('state') != 'LOCKED' or record.get('resources_released') is not True
                or record.get('simulated') is not False):
            raise ValueError('released physical Active Vision LOCKED evidence required')
    elif schema == 'charlie-visual-readiness-v1':
        from memory.evidence import digest
        if (record.get('status') != 'qualified' or record.get('task') != 'robotron'
                or record.get('record_id') != digest({k:v for k,v in record.items() if k != 'record_id'})):
            raise ValueError('qualified visual-readiness evidence required')
    else:
        raise ValueError('neck profile or saved polygon is not visual-readiness evidence')
    c = record['calibration']
    calibration = Calibration(tuple(tuple(p) for p in c['corners']), tuple(c['output_size']))
    lens = record['focus']['lens_position']
    if isinstance(lens, bool) or not isinstance(lens, (int, float)) or not math.isfinite(lens):
        raise ValueError('finite qualified lens position required')
    return calibration, lens


def confirm_geometry(source, calibration, *, config=None, diagnostics=None,
                     require_metadata=False, frame_size=None):
    """Bounded fresh confirmation, independent of attract/gameplay semantics.

    Full discovery may miss Hough candidates intermittently. Its *same* four-edge
    and corner support gates can independently confirm the qualified rectangle.
    Three consecutive supported, readable fresh views terminate confirmation;
    no search for a more square angle is required. A discovered changed rectangle
    fails immediately. Missing/unreadable support resets the confirmation streak.
    """
    from ..preflight import PreflightConfig, screen_sharpness
    from .exposure import screen_evidence
    from .active_vision import Config, measure
    cfg = config or PreflightConfig()
    quality_cfg = Config()
    rows = diagnostics if diagnostics is not None else []
    deadline = time.monotonic()+15
    previous_stamp = None
    streak = 0
    for index in range(cfg.geometry_attempts):
        if time.monotonic() >= deadline: break
        frame = source.read()
        capture = getattr(source, 'capture', None) or getattr(source, 'last_capture', None) or {}
        row = dict(attempt=index+1, capture=dict(capture), status='checking')
        rows.append(row)
        stamp = capture.get('sensor_timestamp_ns')
        metadata_valid = (type(stamp) in (int, float) and math.isfinite(stamp) and stamp > 0
                          and (previous_stamp is None or stamp > previous_stamp))
        if require_metadata or stamp is not None:
            if not metadata_valid:
                row.update(status='stale_or_missing_capture');streak=0
                continue
            previous_stamp = stamp
        if frame_size is not None and tuple(frame.size) != tuple(frame_size):
            raise ValueError('camera frame size changed since qualified view')
        corners = np.asarray(calibration.corners)*frame.size
        row['geometry'] = {}
        try:
            observed = locate(frame, require_uniform_border=False, previous=corners,
                              max_jitter_pixels=cfg.max_jitter_pixels, diagnostics=row['geometry'])
        except ValueError as exc:
            row['discovery_miss'] = str(exc)
        else:
            jitter = float(np.max(np.linalg.norm(observed-corners, axis=1)))
            row['jitter_pixels'] = jitter
            if jitter > cfg.max_jitter_pixels:
                row['status'] = 'geometry_changed'
                raise ValueError('fresh geometry differs from qualified viewpoint')
        try:
            row.update(verify_supported_border(frame, corners))
            target = measure(frame, corners, min(row['edge_support']))
            quality = screen_evidence(frame, corners)
            quality['sharpness'] = screen_sharpness(calibration.apply(frame))
            row['quality'] = quality
            if (target.confidence < quality_cfg.min_confidence or target.area < quality_cfg.min_area
                    or quality['detail_pixels'] < 50 or not math.isfinite(quality['sharpness'])
                    or quality['sharpness'] < quality_cfg.min_sharpness):
                raise ValueError('fresh screen lacks readable visual detail')
        except ValueError as exc:
            row.update(status='unsupported_or_unreadable', reason=str(exc));streak=0
            save = getattr(source, 'save_rejected_final_image', None)
            if callable(save): row['rejected_frame']=save(frame, index+1)
            continue
        streak += 1
        row.update(status='supported', consecutive=streak)
        if streak >= 3:
            return frame, quality
    raise ValueError('qualified viewpoint lacks bounded fresh structural/readability confirmation')


def confirm_view(source, record, *, report):
    from .autofocus import verify_focus_lock
    calibration, lens = calibration_from_record(record)
    report.update(status='confirming', candidate_schema=record['schema'],
                  candidate_id=record.get('record_id'), physical_motion=False,
                  readiness_scope='screen readable before START; gameplay and SELF unqualified')
    lock = report.setdefault('focus_lock', {})
    verify_focus_lock(source, lens, report=lock)
    frame, quality = confirm_geometry(source, calibration,
        diagnostics=report.setdefault('observations', []), require_metadata=True,
        frame_size=record.get('frame_size'))
    report.update(status='confirmed', quality=quality, focus=dict(lens_position=lens, score=quality['sharpness'], changed=False))
    return calibration, frame


def record_view(calibration, focus, frame, *, origin, observations):
    from memory.evidence import digest
    record = dict(schema='charlie-visual-readiness-v1', task='robotron', status='qualified',
        calibration=dict(corners=calibration.corners, output_size=calibration.output_size),
        focus=focus, frame_size=frame.size, origin=str(Path(origin).resolve()),
        observations=observations, physical_motion=False,
        readiness_scope='screen readable before START; gameplay and SELF unqualified')
    # Canonical JSON normalizes tuples before hashing, including disk round trips.
    record=json.loads(json.dumps(record))
    return dict(record, record_id=digest(record))

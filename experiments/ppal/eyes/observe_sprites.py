"""Record real sprite candidates and timing without game controls."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import time
from .benchmark import summarize
from .cli import make_pipeline, make_source


def countdown(source, seconds, live):
    """Count down after calibration, draining live frames to avoid stale input."""
    for remaining in range(seconds, 0, -1):
        print(f'Recording starts in {remaining}...', flush=True)
        if live:
            deadline = time.perf_counter() + 1
            while time.perf_counter() < deadline:
                source.read()
                time.sleep(.01)
        else:
            time.sleep(1)
    print('RECORDING NOW — play your short sequence.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('pi', 'images'), default='pi')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--profile', type=Path, required=True)
    duration = parser.add_mutually_exclusive_group()
    duration.add_argument('--frames', type=int, help='record 1..200 frames (default: 60)')
    duration.add_argument('--seconds', type=float, help='record for 1..30 seconds after countdown')
    parser.add_argument('--countdown', type=int, default=0, help='0..15 seconds to get ready after calibration')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--auto-calibrate', action='store_true', help='settle camera and find current game border')
    args = parser.parse_args()
    if args.auto_calibrate and args.calibration:
        parser.error('choose auto-calibrate or an explicit calibration, not both')
    if args.frames is None and args.seconds is None:
        args.frames = 60
    if args.frames is not None and not 1 <= args.frames <= 200:
        parser.error('frames must be 1..200')
    if args.seconds is not None and not 1 <= args.seconds <= 30:
        parser.error('seconds must be 1..30')
    if not 0 <= args.countdown <= 15:
        parser.error('countdown must be 0..15')
    pipeline = make_pipeline(args.source, args.profile, args.calibration)
    if not getattr(pipeline.detector, 'observation_only', False):
        parser.error('This recorder requires an observation-only sprite profile')
    args.output.mkdir(parents=True, exist_ok=False)
    source = make_source(args.source, args.input)
    rows = []
    try:
        if args.auto_calibrate:
            from .settle import prepare
            pipeline.calibration = prepare(source, args.output)
        elif args.source == 'pi':
            for _ in range(15):
                source.read()
        countdown(source, args.countdown, args.source == 'pi')
        recording_start = time.perf_counter()
        tick = 0
        while args.frames is None or tick < args.frames:
            start = time.perf_counter()
            if args.seconds is not None and start-recording_start >= args.seconds:
                break
            try:
                frame = source.read()
            except EOFError:
                break
            captured = time.perf_counter()
            result = pipeline.process(frame, tick)
            processed = time.perf_counter()
            # Image writing is timed separately, not hidden in detector latency.
            frame.save(args.output / f'raw_{tick:03d}.jpg', quality=90)
            result.annotated.save(args.output / f'view_{tick:03d}.jpg', quality=90)
            finished = time.perf_counter()
            rows.append({'tick': tick, 'captured_at_seconds': captured-recording_start, 'counts': dict(Counter(d.kind for d in result.detections)),
                         'detections': [asdict(d) for d in result.detections],
                         'capture': captured-start, 'vision': processed-captured,
                         'save': finished-processed, 'total': finished-start})
            tick += 1
        recording_elapsed = time.perf_counter()-recording_start
        print(f'RECORDING COMPLETE — {len(rows)} frames in {recording_elapsed:.1f}s. Packaging next.', flush=True)
    finally:
        source.close()
    summary = {'frames': len(rows), 'controller': 'DISCONNECTED',
               'mode': 'OBSERVATION ONLY; labels are unvalidated candidates',
               'source': args.source, 'requested_seconds': args.seconds,
               'recording_seconds': recording_elapsed, 'countdown_seconds': args.countdown,
               'timing': {key: summarize([r[key] for r in rows])
                          for key in ('capture', 'vision', 'save', 'total')} if rows else {}}
    (args.output / 'detections.json').write_text(json.dumps({'summary': summary, 'frames': rows}, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

"""Record real sprite candidates and timing without game controls."""
import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import time
from .benchmark import summarize
from .cli import make_pipeline, make_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('pi', 'images'), default='pi')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=60)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--auto-calibrate', action='store_true', help='settle camera and find current game border')
    args = parser.parse_args()
    if args.auto_calibrate and args.calibration:
        parser.error('choose auto-calibrate or an explicit calibration, not both')
    if not 1 <= args.frames <= 200:
        parser.error('frames must be 1..200')
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
        for tick in range(args.frames):
            start = time.perf_counter()
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
            rows.append({'tick': tick, 'counts': dict(Counter(d.kind for d in result.detections)),
                         'detections': [asdict(d) for d in result.detections],
                         'capture': captured-start, 'vision': processed-captured,
                         'save': finished-processed, 'total': finished-start})
    finally:
        source.close()
    summary = {'frames': len(rows), 'controller': 'DISCONNECTED',
               'mode': 'OBSERVATION ONLY; labels are unvalidated candidates',
               'source': args.source,
               'timing': {key: summarize([r[key] for r in rows])
                          for key in ('capture', 'vision', 'save', 'total')} if rows else {}}
    (args.output / 'detections.json').write_text(json.dumps({'summary': summary, 'frames': rows}, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

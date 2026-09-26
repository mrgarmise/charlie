"""Bounded camera/vision timing; never imports or connects to game controls."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import statistics
import time

from .cli import make_pipeline, make_source


def summarize(samples):
    ordered = sorted(samples)
    return {'mean_ms': statistics.mean(samples) * 1000,
            'p95_ms': ordered[min(len(ordered) - 1, int(len(ordered) * .95))] * 1000}


def measure(source, pipeline, frames):
    rows = []
    for tick in range(frames):
        start = time.perf_counter()
        frame = source.read()
        captured = time.perf_counter()
        result = pipeline.process(frame, tick)
        processed = time.perf_counter()
        result.annotated.save(BytesIO(), format='JPEG', quality=75)
        encoded = time.perf_counter()
        rows.append({'capture': captured-start, 'vision': processed-captured,
                     'jpeg': encoded-processed, 'total': encoded-start})
    return {'frames': frames, 'fps_local_with_jpeg': frames / sum(r['total'] for r in rows),
            'timing': {key: summarize([r[key] for r in rows]) for key in rows[0]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('pi', 'synthetic'), default='pi')
    parser.add_argument('--frames', type=int, default=120)
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.frames <= 600:
        parser.error('frames must be 1..600')
    args.output.mkdir(parents=True, exist_ok=False)
    pipeline = make_pipeline(args.source, args.profile, args.calibration)
    source = make_source(args.source, None)
    try:
        for _ in range(15):
            source.read()  # Camera exposure/focus warm-up, excluded from timings.
        report = measure(source, pipeline, args.frames)
        frame = source.read()
        frame.save(args.output / 'raw.png')
        pipeline.process(frame, 0).playfield.save(args.output / 'playfield.png')
    finally:
        source.close()
    report.update(source=args.source, detector=('profile' if args.profile else
                  'synthetic' if args.source == 'synthetic' else 'none'),
                  calibration=str(args.calibration),
                  note='Local loop timing only: excludes network, browser, controller and action duration. Capture time is read latency, not sensor-to-action latency.')
    (args.output / 'timing.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

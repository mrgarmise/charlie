"""Replay v2 generic tracking inputs from a live agency log; no camera/controller.

Unlike re-detecting annotated screenshots, this reproduces the exact recorded
positions, boxes, observation clocks and tracker settings. It does not validate
physical identity against ground truth or infer agency from unrecorded controls.
"""
import argparse
import json
from pathlib import Path

from .eyes.detectors import Detection
from .eyes.tracking import SpriteTracker


def replay(path):
    samples=[json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not samples or any('tracking' not in sample for sample in samples):
        raise ValueError('exact replay requires v2 tracking inputs; legacy endpoint logs lack boxes and initial observations')
    configuration = dict(samples[0]['tracking']['configuration'])
    configuration.setdefault('association_version', 1)
    tracker=SpriteTracker(**configuration)
    mismatches=[]
    total_detections=0
    for sample in samples:
        row=sample['tracking']
        if row['configuration'] != samples[0]['tracking']['configuration']:
            raise ValueError('tracker configuration changed within the recording')
        detections=[Detection(d['kind'],tuple(d['center']),tuple(d['box']),d.get('pixels') or 0)
                    for d in row['detections']]
        assigned=tracker.update(row['tick'],detections,observed_at=row['observed_at'])
        expected={d['index']:d['track_id'] for d in row['detections']}
        if assigned != expected:
            mismatches.append({'sample':sample['sample'], 'expected':expected, 'replayed':assigned})
        total_detections+=len(detections)
    return {'samples':len(samples), 'detections':total_detections,
            'tracks_created':tracker.next_id-1, 'assignments_match':not mismatches,
            'mismatches':mismatches,
            'tracks':[tracker.describe(track) for track in tracker.finished+list(tracker.active.values())]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=replay(args.log)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:value for key,value in result.items() if key!='tracks'},indent=2))
    if not result['assignments_match']:
        raise SystemExit(1)


if __name__=='__main__':
    main()

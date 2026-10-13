"""Read-only original camera replay; never produces independent experience."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from memory.evidence import EvidenceJournal
from memory.episode_identity import inspect_capture
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.episode_end import EpisodeEndObserver
from experiments.ppal.robotron_screen_state import classify_screen_state


def replay(root):
    identity=inspect_capture(root)
    report=json.loads((root/'report.json').read_text())
    timing=report['session_timing'];transport=timing.get('start_transport') or {}
    ack=transport.get('ack_at')
    if type(ack) not in (int,float):raise ValueError('original acknowledged START is required')
    observer=EpisodeEndObserver(entry_evidence=dict(method='acknowledged_START',capture_timestamp=ack,transport=transport))
    calibration=Calibration.load(root/'calibration.json');trace=[];first=None
    journal=EvidenceJournal(root/'session-evidence.sqlite3',read_only=True)
    try:
        for record in journal.records('observation'):
            d=record.data;p=d['payload']
            if p.get('category')!='camera_observation' or d['at']<=ack:continue
            path=(root/p['source_path']).resolve()
            if not path.is_relative_to(root.resolve()):raise ValueError('source path escapes original capture')
            with Image.open(path) as image:screen=classify_screen_state(calibration.apply(image))
            screen['capture_timestamp']=d['at'];observer.observe_phase(screen)
            row=dict(observation_id=record.id,source_path=p['source_path'],
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                screen=screen,diagnostic=observer.diagnostic(screen,record.id))
            trace.append(row)
            if observer.confirmed and first is None:first=row
    finally:journal.close()
    return dict(schema='charlie-terminal-replay-v1',qualification='read-only diagnostic replay of one original episode; not new experience or native acceptance',
        physical_authorization=False,start_authorized=False,source_identity=identity,
        source_report_sha256=hashlib.sha256((root/'report.json').read_bytes()).hexdigest(),
        original_result=report['result'],original_episode_end=report['episode_end'],
        first_terminal=first,trace=trace)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.episode.resolve();output=args.output.resolve()
    if output.is_relative_to(root):parser.error('output must be outside the immutable original episode')
    result=replay(root)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(observations=len(result['trace']),first_terminal_at=(result['first_terminal'] or {}).get('screen',{}).get('capture_timestamp'),start_authorized=False)))

if __name__=='__main__':main()

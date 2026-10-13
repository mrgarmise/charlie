"""Offline attached/detached replay timing. No camera or controller is opened."""
import argparse
import json
from pathlib import Path
import platform
import random
import statistics
import tempfile
import threading
import time
from urllib.request import urlopen

from PIL import Image
from .calibration import Calibration
from .passive import PassivePublisher
from .passive_viewer import Viewer,make_server
from .camera_lease import CameraLease
from .taught_recognizer import TaughtRecognizer
from ..robotron_agency import VisualAgency
from ..forebrain import Forebrain
from ..hindbrain import Hindbrain
from ..models import Object,Position,WorldState


def trial(raw, calibration, recognizer, recorded, mode, seconds):
    with tempfile.TemporaryDirectory(prefix='eyes-benchmark-') as directory:
        directory=Path(directory)
        publisher=PassivePublisher(directory) if mode!='baseline' else None
        viewer=server=client=lease=None;stop=threading.Event();requests=[];received=[]
        if mode=='attached':
            lease=CameraLease(directory=directory)  # simulated owner, no camera
            viewer=Viewer(directory);server=make_server(viewer,0)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            def consume():
                while not stop.is_set():
                    with urlopen(f'http://127.0.0.1:{server.server_port}/frame',timeout=1) as response:
                        data=response.read();requests.append(len(data));received.append(json.loads(data)['status'])
                    stop.wait(1/3)
            client=threading.Thread(target=consume);client.start()
        agency=VisualAgency(bootstrap_body_fire=True);fore=Forebrain();hind=Hindbrain(explore_fire=True)
        times=[];actions=[];began=time.perf_counter()
        try:
            while time.perf_counter()-began<seconds:
                begin=time.perf_counter();timestamp=time.monotonic()
                crop=calibration.apply(raw);pairs=recognizer.detect(crop)
                snapshot=agency.observe(pairs,observed_at=timestamp)
                if publisher:publisher.submit(raw,timestamp=timestamp,playfield=crop,metadata={'agency':snapshot})
                # Replay the archived provisional world interpretation, without
                # certifying it or inserting it into the live AgencyTracker.
                def objects(key):
                    return tuple(Object(str(o['id']),Position(*o['position'])) for o in recorded.get('world_objects',{}).get(key,[]))
                world=WorldState(len(times),Position(*recorded['player']),objects('targets'),objects('threats'),True,objects('unresolved'))
                _,action=hind.decide(world,fore.update(world))
                actions.append((action.move,action.fire));times.append(time.perf_counter()-begin)
        finally:
            elapsed=time.perf_counter()-began;stop.set()
            if client:client.join(timeout=2)
            if server:server.shutdown();server.server_close();viewer.close()
            if publisher:publisher.close()
            if lease:lease.close()
        return dict(mode=mode,frames=len(times),elapsed_seconds=elapsed,fps=len(times)/elapsed,
            frame_to_action_ready_ms_mean=1000*statistics.mean(times),
            frame_to_action_ready_ms_p95=1000*sorted(times)[int(.95*(len(times)-1))],
            observer=publisher.report() if publisher else None,http_requests=len(requests),
            passive_frames_received=received.count('passive'),http_bytes=sum(requests),
            action_sequence_digest=__import__('hashlib').sha256(json.dumps(actions[:10]).encode()).hexdigest())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archive',type=Path);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--seconds',type=float,default=3);ap.add_argument('--rounds',type=int,default=3)
    args=ap.parse_args()
    if not 1<=args.seconds<=20 or not 1<=args.rounds<=5:ap.error('seconds 1..20; rounds 1..5')
    report=json.loads((args.archive/'report.json').read_text())
    candidates=sorted(args.archive.glob('score-raw-*.png')) or sorted(args.archive.glob('review-*.jpg'))
    if not candidates:ap.error('full raw camera evidence unavailable')
    raw=Image.open(candidates[0]).convert('RGB')
    calibration=Calibration(tuple(map(tuple,report['calibration']['corners'])),tuple(report['calibration']['output_size']))
    recognizer=TaughtRecognizer.load(Path('config/robotron/sprite-knowledge.json'))
    recorded=next(s for s in report['steps'] if 'player' in s)
    # Warm OpenCV, recognition and their allocators before randomized order.
    recognizer.detect(calibration.apply(raw))
    trials=[];rng=random.Random(718)
    for _ in range(args.rounds):
        modes=['baseline','detached','attached'];rng.shuffle(modes)
        for mode in modes:trials.append(trial(raw,calibration,recognizer,recorded,mode,args.seconds))
    doc=dict(schema='charlie-passive-eyes-benchmark-v1',platform=platform.platform(),
        methodology='unthrottled offline real-frame replay, normal calibration/detection/single tracker/agency and archived provisional world planning; localhost HTTP consumption at 3 FPS',
        limitations='No physical camera, sensor timing, display or controller transport. Replay action-ready latency is not measured live Pi command latency.',
        source=str(candidates[0]),rounds=args.rounds,trials=trials)
    doc['summary']={mode:dict(fps_mean=statistics.mean(t['fps'] for t in trials if t['mode']==mode),
        action_ready_ms_mean=statistics.mean(t['frame_to_action_ready_ms_mean'] for t in trials if t['mode']==mode))
        for mode in ('baseline','detached','attached')}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(doc,indent=2)+'\n')
    print(json.dumps(doc['summary'],indent=2))


if __name__=='__main__':main()

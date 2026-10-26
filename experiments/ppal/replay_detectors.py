"""Offline JSONL replay. No camera/controller imports or live activation."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from PIL import Image
from .detector_bridge import Frame, DetectorBridge, TemplateBackend, HailoBackend, LabBackend, tracking_pairs, rich_world
from .eyes.tracking import SpriteTracker


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path,help='JSONL: image, frame_id, exposure_at, timestamp_basis, provenance')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--backend',choices=['template','lab','hailo'],required=True)
    parser.add_argument('--profile',type=Path)
    parser.add_argument('--lab-state',type=Path)
    parser.add_argument('--model-id')
    parser.add_argument('--hef',type=Path)
    parser.add_argument('--contract',type=Path)
    args=parser.parse_args()
    if args.output.resolve()==args.manifest.resolve(): parser.error('output must differ from source')
    if args.backend=='template':
        from .eyes.sprites import SpriteDetector
        backend=TemplateBackend(SpriteDetector.load(args.profile));model={'profile_sha256':hashlib.sha256(args.profile.read_bytes()).hexdigest()}
    elif args.backend=='lab':
        from vision_lab.store import Lab
        from vision_lab.adapter import CandidateDetector
        candidate=CandidateDetector(Lab(args.lab_state),args.model_id)
        backend=LabBackend(candidate);model=candidate.record
    else:
        contract=json.loads(args.contract.read_text())
        if contract['architecture']!='hailo8l' or contract['decoder']!='hailo-nms-yxyx-score': raise ValueError('unsupported deployment contract')
        backend=HailoBackend(args.hef,sha256=contract['hef_sha256'],classes=contract['classes'],size=contract['imgsz'])
        model=contract
    tracker=SpriteTracker();last=None;count=0
    # Exclusive output protects source evidence; streaming bounds memory.
    with args.output.open('x') as out, args.manifest.open() as source:
        for line in source:
            row=json.loads(line); at=row['exposure_at']
            path=args.manifest.parent/row['image']
            with Image.open(path) as image:
                frame=Frame(row['frame_id'],image.convert('RGB'),at,row['timestamp_basis'],row['provenance'])
            # Replay historical exposure times, not fake native freshness. Actual
            # wall processing duration is recorded separately.
            if last is None:
                bridge=DetectorBridge(lambda:backend,model=model,max_age=1,clock=lambda:at)
            start=time.perf_counter();packet=bridge.observe(frame)
            packet['replay_processing_seconds']=time.perf_counter()-start
            packet['freshness_age']=None;packet['freshness_context']='historical replay; not native latency'
            assignments=tracker.update(count,[d for d,_ in tracking_pairs(packet)],observed_at=at)
            packet['world']=rich_world(tracker,at,hypotheses={identifier:packet['objects'][index] for index,identifier in assignments.items()})
            out.write(json.dumps(packet,sort_keys=True)+'\n');count+=1;last=at
    print(json.dumps({'frames':count,'output':str(args.output),'qualification':'offline observations only'}))


if __name__=='__main__': main()

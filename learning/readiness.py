"""Read-only offline handoff audit; never camera, controller, START or training.

Inference timing is only one input to candidate-specific physical readiness.
This report cannot grant readiness or deployment authority.
"""
import argparse
import importlib.util
import json
import platform
from pathlib import Path
import resource
import sys
import time
import numpy as np
from PIL import Image
from memory.evidence import EvidenceJournal
from .datasets import sha
from .foundry import atomic_json


def audit(*, root=None, manifest=None, crops=None, batches=16):
    from .cycle import gameplay_active
    if gameplay_active():raise RuntimeError('offline audit unavailable during gameplay')
    if type(batches) is not int or not 1<=batches<=128:raise ValueError('bounded inference batches required')
    report=dict(schema='ala-2-offline-readiness-v1',
        system=dict(python=sys.version.split()[0],machine=platform.machine(),platform=platform.platform(),
                    torch_available=importlib.util.find_spec('torch') is not None,numpy=np.__version__),
        physical_authorization=False,score_improvement='not demonstrated',gaps=[])
    if root is not None:
        path=Path(root)/'learning-evidence.sqlite3'
        if not path.is_file():report['gaps'].append('learning journal unavailable')
        else:
            journal=EvidenceJournal(path,read_only=True)
            try:
                rows=journal.records()
                examples=[r for r in rows if r.data['payload'].get('category')=='experience_example']
                annotations={r.data['payload']['example']:r.data['payload'] for r in rows if r.data['payload'].get('category')=='dataset_annotation'}
                verified=[r for r in examples if annotations.get(r.id,{}).get('status')=='verified' and
                          annotations[r.id].get('value') in ('human','threat') and
                          annotations[r.id].get('source') in ('external_annotation','independent_measurement') and
                          r.data['payload'].get('metadata',{}).get('domain')=='robotron-camera']
                report['evidence']=dict(records=len(rows),canonical_ids_verified=True,examples=len(examples),
                    verified_robotron_role_examples=len(verified),
                    source_episodes=sorted({r.data['payload']['source_episode'] for r in verified}),
                    journal_sha256=sha(path),historical_paths_unchanged=True)
                # Counts are not partition/leakage validation or independent accuracy.
                if not verified:report['gaps'].append('independent verified Robotron crop labels missing')
                if len({r.data['payload']['source_episode'] for r in verified})<3:
                    report['gaps'].append('three isolated Robotron label groups not established')
            finally:journal.close()
    if manifest is None:
        report['gaps'].append('no authorized operational candidate supplied')
    else:
        from .operational import load_manifest
        active,model=load_manifest(manifest)
        report['candidate']=dict(identifier=active['candidate_id'],activation=active['activation_key'],
            domains=active['contract']['domains'],physical_gate_qualified=False)
        try:
            load_manifest(manifest,physical=True)
            report['candidate']['physical_gate_qualified']=True
        except ValueError as exc:report['gaps'].append(str(exc))
        if crops is None:report['gaps'].append('candidate cadence on preserved crop inputs unmeasured')
        else:
            paths=sorted(Path(crops).glob('*.png'))[:16]
            if not paths:raise ValueError('preserved PNG crop inputs required')
            images=[]
            for path in paths:
                with Image.open(path) as im:images.append(im.convert('RGB').copy())
            images=[images[n%len(images)] for n in range(16)]
            samples=[]
            for _ in range(batches):
                start=time.perf_counter()
                for image in images:model.infer(image)
                samples.append(time.perf_counter()-start)
            report['inference_benchmark']=dict(batches=batches,crops_per_batch=16,
                median_seconds=float(np.median(samples)),p99_seconds=float(np.quantile(samples,.99)),
                maximum_seconds=max(samples),within_2fps_batch_budget=max(samples)<=.5,
                max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                inputs=[dict(name=p.name,sha256=sha(p)) for p in paths],
                limitations=['offline inference only; no camera/controller contention, thermals or terminal/recovery qualification',
                             'same examples reused for timing; zero additional independent evaluation credit'])
    report['gaps'].extend(['physical camera/controller/recovery/cadence evidence must be independently qualified',
        'official-score reader and complete-game boundaries need independent qualification',
        'preregistered frozen baseline/candidate score comparison and explicit armed authorization required'])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--crops',type=Path)
    parser.add_argument('--batches',type=int,default=16)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('refusing to overwrite an existing readiness report')
    report=audit(root=args.root,manifest=args.manifest,crops=args.crops,batches=args.batches)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    atomic_json(args.output,report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

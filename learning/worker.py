"""Offline worker for the existing independent progress supervisor."""
import argparse
import json
from pathlib import Path
import resource
import math
from experiments.ppal.progress_supervision import Progress
from .foundry import train, atomic_json


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('config',type=Path); args=parser.parse_args()
    config=json.loads(args.config.read_text()); root=Path(config['output']); root.mkdir(parents=True,exist_ok=True)
    progress=Progress(root/'progress.json'); progress.enter('processing')
    # CPU cap is independently enforced even if the training loop stops pulsing.
    cpu=math.ceil(config['budget_seconds']+30)
    resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu+5))
    def pulse(): progress.update(processing_units=progress.data.get('processing_units',0)+1)
    result=train(config['snapshot'],config['spec'],root,budget_seconds=config['budget_seconds'],on_progress=pulse)
    atomic_json(root/'result.json',result)
    return 75 if result['status']=='yielded' else 0

if __name__=='__main__': raise SystemExit(main())

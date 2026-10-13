"""Explicit offline candidate construction/replay; never physical activation."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory.evidence import EvidenceJournal
from memory.evaluator import MemoryEvaluator
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.score_feedback import build_candidate,ScoreFeedbackReader
from experiments.ppal.robotron_hud import RobotronHUDReader


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal',type=Path);parser.add_argument('--calibration',type=Path,required=True)
    parser.add_argument('--build',type=Path,help='export new unqualified candidate; copied journal only')
    parser.add_argument('--training-partition',choices=['training','diagnostic'],default='training')
    parser.add_argument('--evaluate',help='existing candidate evidence ID; independent validation/diagnostic')
    parser.add_argument('--partition',choices=['validation','diagnostic'],default='validation')
    args=parser.parse_args();cal=Calibration.load(args.calibration)
    if bool(args.build)==bool(args.evaluate):parser.error('exactly one of --build or --evaluate required')
    if (args.journal.parent/'capture-manifest.json').exists():raise ValueError('sealed original diary cannot be development output')
    j=EvidenceJournal(args.journal)
    try:
        if args.build:
            record,state=build_candidate(j,cal,args.build,partition=args.training_partition)
            print(json.dumps(dict(candidate_id=record.id,state_digest=state['state_digest'],prototypes=len(state['prototypes']),excluded=state['excluded'],qualification=state['qualification']),indent=2))
        else:
            candidate=j.get(args.evaluate).data['payload']
            model=ScoreFeedbackReader.load(candidate['artifact'],cal,expected_state_digest=candidate['state_digest'],expected_artifact_sha256=candidate['artifact_sha256'])
            # Evaluation receives camera pixels; it never retrieves label values.
            result=MemoryEvaluator.evaluate_score_reader(j,args.evaluate,lambda image:
                (lambda observed:(observed.player1_score,observed.player1_confidence))(model.read(image)),partition=args.partition)
            print(json.dumps(result.data,indent=2))
    finally:j.close()


if __name__=='__main__':main()

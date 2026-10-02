"""Isolated, progress-supervised invocation of the existing between-game path."""
import json
from pathlib import Path
import sys


def main():
    from memory.evidence import EvidenceJournal
    from memory.gateway import MemoryGateway
    from memory.evaluator import MemoryEvaluator
    from memory.marm import MarmOutbox
    from memory.learning_projects import LearningExecutive
    from .progress_supervision import Progress
    from .marathon_robotron import process_completed_episode, ProcessingYield
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',type=Path)
    parser.add_argument('--resume',action='store_true',help='bounded offline retry; no camera or START')
    args=parser.parse_args()
    config=json.loads(args.config.read_text())
    progress = Progress(config['progress'])
    progress.enter('processing')
    gateway = MemoryGateway(evaluator=MemoryEvaluator(config['evaluator']),
                            store=MarmOutbox(config['outbox'], project=config['project'], session=config['session']),
                            project=config['project'], session=config['session'])
    commitments = EvidenceJournal(config['commitments'])
    project = EvidenceJournal(config['project_evidence']) if config.get('project_evidence') else None
    executive = LearningExecutive(project, gateway) if project else None
    try:
        if args.resume:
            from .marathon_robotron import process_supervised
            process_supervised(Path(config['game']),Path(config['output']),gateway,commitments,
                config.get('plan'),executive,budget=config.get('work_budget',300.),ala_root=config.get('ala_root'),ala_budget=config.get('ala_budget',60.),ala_authority=config.get('ala_authority'))
            return
        process_completed_episode(Path(config['game']), Path(config['output']), gateway,
                                  commitments, config.get('plan'), executive, progress=progress, work_budget=config.get('work_budget'),ala_root=config.get('ala_root'),ala_budget=config.get('ala_budget',60.),ala_authority=config.get('ala_authority'))
    except ProcessingYield as exc:
        progress.update(stage='yielded',reason=str(exc))
        raise SystemExit(75)
    finally:
        commitments.close()
        if project: project.close()


if __name__ == '__main__':
    main()

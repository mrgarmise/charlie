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
    from .marathon_robotron import process_completed_episode
    config = json.loads(Path(sys.argv[1]).read_text())
    progress = Progress(config['progress'])
    progress.enter('processing')
    gateway = MemoryGateway(evaluator=MemoryEvaluator(config['evaluator']),
                            store=MarmOutbox(config['outbox'], project=config['project'], session=config['session']),
                            project=config['project'], session=config['session'])
    commitments = EvidenceJournal(config['commitments'])
    project = EvidenceJournal(config['project_evidence']) if config.get('project_evidence') else None
    executive = LearningExecutive(project, gateway) if project else None
    try:
        process_completed_episode(Path(config['game']), Path(config['output']), gateway,
                                  commitments, config.get('plan'), executive, progress=progress)
    finally:
        commitments.close()
        if project: project.close()


if __name__ == '__main__':
    main()

"""Read-only physical archive inventory and acceptance audit; never relabels it."""
import argparse
import json
from pathlib import Path
from memory.evidence import EvidenceJournal, digest
from .datasets import sha


def audit(root):
    root=Path(root)
    inventory={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
    report=json.loads((root/'game-01/report.json').read_text())
    episode='episode:'+inventory['game-01/report.json']
    history=json.loads((Path(__file__).resolve().parents[1]/'docs/ppal/ala-1-demonstration.json').read_text())['snapshot_split']
    role=history.get(episode,'unknown')
    scores=[json.loads(line) for line in (root/'game-01/score.jsonl').read_text().splitlines() if line]
    med=json.loads((root/'game-01-evidence/meditation.json').read_text())
    journals=[]
    for p in sorted(root.rglob('*.sqlite3')):
        journal=EvidenceJournal(p,read_only=True)
        try: journals.append(dict(path=str(p.relative_to(root)),records=len(journal.records()),verified=True))
        finally: journal.close()
    after={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
    if inventory!=after: raise ValueError('archive changed during read-only audit')
    return dict(schema='robotron-preserved-archive-audit-v1',source_episode=episode,
        inventory=inventory,inventory_digest=digest(inventory),preserved_bytes_unchanged=True,
        prior_partition=role,final_already_consulted=role=='test',journals=journals,
        learning_mode=report.get('learning_mode'),result=report.get('result'),
        recorded_score=report.get('score'),last_score_observation=scores[-1],
        score_rows=len(scores),terminal=report.get('episode_end'),
        meditation_artifact_sha256=inventory['game-01-evidence/meditation.json'],
        preserved_meditation_quality=med['quality'],
        admissibility=dict(diagnostic=True,unlabeled_training=True,
            independently_verified_training=False,fresh_final_evaluation=False,
            complete_game_score=False,physical_score_improvement=False),
        reasons=['TIME LIMIT is not a verified complete-game boundary',
            'Last score row is an unreadable observation with retained historical score',
            'Retrospective meditation links do not independently qualify physical identities',
            'Published ALA-1 partition history excludes these episodes from fresh final testing'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.episode)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')


if __name__=='__main__': main()

"""Read-only evidence snapshot for guarded normal-application acceptance."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory.evidence import EvidenceJournal
from learning.datasets import sha
from memory.learning_projects import LearningExecutive


def inspect(output):
    output=Path(output)
    if not (output/'learning-evidence.sqlite3').is_file():raise ValueError('existing notebook required')
    journal=EvidenceJournal(output/'learning-evidence.sqlite3',read_only=True)
    try:
        rows=journal.records();work={}
        for row in rows:
            p=row.data['payload']
            if p.get('op')=='developmental_progress':work[p['work_id']]=dict(p,record_id=row.id)
        return dict(schema='developmental-progress-inspection-v1',records=len(rows),
            original_records=[dict(id=r.id,document=r.document,committed_at=r.committed_at) for r in rows],
            projects=LearningExecutive.project_state(journal),
            developmental_records=[dict(id=r.id,kind=r.data['kind'],producer=r.data['producer'],
                sources=r.data['sources'],payload=r.data['payload']) for r in rows
                if r.data['payload'].get('category') in (
                    'preserved_meditation_rejection','acquisition_dependency_satisfied',
                    'learning_project_proposal','perceptual_experiment_proposal',
                    'learning_evidence_request','meditation_candidate_evaluation',
                    'offline_model_evaluation','model_deployment_proposal',
                    'qualified_policy_export_blocked','offline_operational_outcome')],
            work=work,commissions=[dict(id=r.id,**r.data['payload']) for r in rows if r.data['payload'].get('category')=='reflection_commission'],
            checkpoints=[dict(path=str(p),sha256=sha(p),document=json.loads(p.read_text())) for p in sorted((output/'meditations').glob('**/checkpoint.json'))],
            evidence_requests=[dict(id=r.id,**r.data['payload']) for r in rows if r.data['payload'].get('category')=='learning_evidence_request' or r.data['payload'].get('op')=='evidence_continuation'],
            outcomes=[dict(id=r.id,**r.data['payload']) for r in rows if r.data['kind']=='resolution'],
            status=json.loads((output/'development-status.json').read_text()) if (output/'development-status.json').is_file() else None,
            physical_authorization=False)
    finally:journal.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('state');args=parser.parse_args()
    print(json.dumps(inspect(args.state),indent=2))

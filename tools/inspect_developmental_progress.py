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
        historical=[];retained={r.id for r in rows}
        for context in journal.category_records('observation','learning_context_reference'):
            p=context.data['payload'];expected=p.get('inventory',{}).get('session-evidence.sqlite3')
            if not expected or not p.get('source_root'):continue
            path=Path(p['source_root'])/'session-evidence.sqlite3'
            try:
                if sha(path)!=expected:raise ValueError('original session journal hash changed')
                source=EvidenceJournal(path,read_only=True)
                try:
                    originals=[dict(id=r.id,document=r.document,committed_at=r.committed_at)
                        for r in source.records() if r.id in retained]
                finally:source.close()
                historical.append(dict(context_id=context.id,path=str(path),sha256=expected,
                    records=originals,status='hash_verified_original_history'))
            except (OSError,ValueError) as exc:
                historical.append(dict(context_id=context.id,path=str(path),sha256=expected,
                    records=[],status='unavailable',reason=str(exc)))
        for receipt in journal.category_records('event','preserved_session_history_import'):
            p=receipt.data['payload'];path=Path(p['source_path'])
            try:
                if sha(path)!=p['source_sha256']:raise ValueError('original session journal hash changed')
                source=EvidenceJournal(path,read_only=True)
                try:
                    originals=[dict(id=r.id,document=r.document,committed_at=r.committed_at)
                        for r in source.records() if r.id in p['record_ids'] and r.id in retained]
                finally:source.close()
                historical.append(dict(receipt_id=receipt.id,path=str(path),sha256=p['source_sha256'],
                    records=originals,status='hash_verified_original_history'))
            except (OSError,ValueError) as exc:
                historical.append(dict(receipt_id=receipt.id,path=str(path),sha256=p['source_sha256'],
                    records=[],status='unavailable',reason=str(exc)))
        for row in rows:
            p=row.data['payload']
            if p.get('op')=='developmental_progress':work[p['work_id']]=dict(p,record_id=row.id)
        return dict(schema='developmental-progress-inspection-v1',records=len(rows),
            original_records=[dict(id=r.id,document=r.document,committed_at=r.committed_at) for r in rows],
            historical_imports=historical,
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

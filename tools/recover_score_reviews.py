"""Read-only original review recovery, preserving IDs/documents/timestamps/images.

Exports a fresh immutable bundle. It does not import annotations, train, deploy,
start an Executive, or initialize camera/controller capabilities.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory.evidence import EvidenceJournal
from experiments.ppal.score_observer import ScoreObserver


def recover(journal_path,output,*,development=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=EvidenceJournal(journal_path,read_only=True)
    target=EvidenceJournal(output/'learning-evidence.sqlite3')
    try:
        source.conn.execute('BEGIN') # Consistent read-only SQLite snapshot, including WAL.
        source.verify();records=source.records();target.merge_from(source);target.verify()
        proposals={r.id:r for r in source.category_records('observation','score_review_proposal')}
        annotations=source.category_records('observation','score_human_annotation')
        superseded={r.data['payload'].get('supersedes') for r in annotations}
        active=[r for r in annotations if r.id not in superseded]
        consumed=set()
        if development:
            original=EvidenceJournal(development,read_only=True)
            try:consumed={r.id for r in original.records()}
            finally:original.close()
        images=[]
        for key,proposal in proposals.items():
            if not any(r.data['payload']['proposal_id']==key for r in annotations):continue
            p=proposal.data['payload'];item=dict(proposal_id=key,original_artifact=p['artifact'])
            try:
                path=ScoreObserver.review_artifact(source,p)
                destination=output/'images'/(p['artifact']['sha256']+path.suffix.lower());destination.parent.mkdir(exist_ok=True)
                shutil.copyfile(path,destination)
                if hashlib.sha256(destination.read_bytes()).hexdigest()!=p['artifact']['sha256']:raise ValueError('copy changed')
                item['recovered_path']=str(destination.relative_to(output))
            except (OSError,ValueError) as exc:item['missing_reason']=str(exc)
            images.append(item)
        statuses=source.category_records('observation','score_review_status')
        report=dict(schema='charlie-score-review-recovery-v1',source=str(Path(journal_path).resolve()),
            records=[dict(id=r.id,document=r.document,committed_at=r.committed_at) for r in records],
            status_records=len(statuses),annotation_records=len(annotations),active_annotation_records=len(active),
            distinct_reviewed_proposals=len({r.data['payload']['proposal_id'] for r in active}),
            distinct_reviewed_images=len({r.data['payload']['artifact_sha256'] for r in active}),
            accepted=[dict(id=r.id,**r.data['payload']) for r in active if r.data['payload']['verdict']=='confirm'],
            corrected=[dict(id=r.id,**r.data['payload']) for r in active if r.data['payload']['verdict']=='correct'],
            statuses=[dict(id=r.id,**r.data['payload']) for r in statuses],images=images,
            imported_to_development=[r.id for r in annotations if r.id in consumed] if development else None,
            consumption='Matching import IDs are not proof of training or inference; inspect candidate consultation/update artifacts separately',
            physical_authorization=False)
        (output/'recovery.json').write_text(json.dumps(report,indent=2)+'\n')
        # Copy location overlay does not amend any original proposal/history.
        (output/'image-locations.json').write_text(json.dumps({r['original_artifact']['sha256']:r['recovered_path'] for r in images if 'recovered_path' in r},indent=2)+'\n')
        return report
    finally:target.close();source.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('journal',type=Path);p.add_argument('output',type=Path);p.add_argument('--development',type=Path)
    args=p.parse_args();r=recover(args.journal,args.output,development=args.development)
    print(json.dumps({k:v for k,v in r.items() if k not in ('records','statuses','images','accepted','corrected')},indent=2))

"""Extract immutable unlabeled crops from existing observations, no vision pass."""
import json
from pathlib import Path
from memory.evidence import digest
from .datasets import sha,SCOPE


def collect_crops(root,dataset,*,max_crops=128):
    from .cycle import gameplay_active
    if gameplay_active():raise RuntimeError('offline acquisition unavailable during gameplay')
    if type(max_crops) is not int or not 1<=max_crops<=256:raise ValueError('bounded crop acquisition required')
    root=Path(root).resolve();agency=root/'agency.jsonl'
    report=root/'report.json'
    if not agency.exists() or not report.exists():return {'status':'unavailable','examples':[],'reason':'original tracking/frame evidence missing'}
    episode='episode:'+sha(report);source_hash=sha(agency);eligible=[]
    for line,text in enumerate(agency.read_text().splitlines(),1):
        row=json.loads(text);name=row.get('raw_frame')
        if not name:continue
        path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('frame escapes episode')
        if not path.exists():continue
        for detection in row.get('tracking',{}).get('detections',[]):
            box=detection.get('box')
            if isinstance(box,list) and len(box)==4:
                eligible.append((path,box,row,detection,line))
    if not eligible:return {'status':'unavailable','examples':[],'reason':'saved frame/box correspondence unavailable'}
    # Uniform retained-candidate sampling, not preferred appearance/role selection.
    step=max(1,len(eligible)/max_crops);selected=[eligible[int(i*step)] for i in range(min(max_crops,len(eligible)))];examples=[]
    for path,box,row,detection,line in selected:
        item=dataset.add(path,episode=episode,crop=box,
            source=dict(kind='recorded-candidate-box',agency_path=str(agency),agency_sha256=source_hash,
                        line=line,row_digest=digest(row),artifact=str(path),sha256=sha(path)),
            metadata=dict(domain='robotron-camera',track_id=detection.get('track_id'),
                capture_timestamp=row.get('capture_timestamp'),identity_status=row.get('identity_status','unknown'),
                candidate_semantics='unverified; never a target label',correlation='same original physical episode'))
        examples.append(item.id)
    request=dataset.journal.append('event',dict(category='learning_evidence_request',method='clarify-labels',
        question='Which independently verified semantic roles, if any, do these preserved candidate crops exhibit?',
        examples=examples,allowed_labels=['human','threat'],abstention='leave ambiguous crops unlabeled or weak; SELF is never inferred',
        source_episode=episode,source_hash=source_hash,selection='uniform retained candidate boxes; biased saved-frame subset'),
        episode=SCOPE,sources=examples,producer='existing-acquisition-capability',version='ala-2')
    return dict(status='collected',examples=examples,request_id=request.id,new_physical_experiments=0)


def apply_annotations(dataset,path):
    """Explicit external labels/corrections; no privileged person or silent rewrite."""
    path=Path(path);records=json.loads(path.read_text());outputs=[]
    if not isinstance(records,list):raise ValueError('annotation list required')
    with dataset.journal.batch():
        for row in records:
            if row.get('value') not in ('human','threat',None) or (row.get('value') is None and row.get('status')=='verified'):raise ValueError('supported role or abstention required; no SELF labels')
            if row.get('source') not in ('external_annotation','independent_measurement'):raise ValueError('independent annotation source required')
            if not row.get('evidence'):raise ValueError('external observation provenance required')
            evidence=dict(reference=row['evidence'],annotation_path=str(path.resolve()),annotation_sha256=sha(path))
            latest=next(x for x in dataset.examples() if x['id']==row['example_id'])['annotation']
            if latest and all(latest.get(k)==v for k,v in dict(value=row['value'],status=row['status'],source=row['source'],evidence=evidence).items()):
                outputs.append(latest['id']);continue
            outputs.append(dataset.annotate(row['example_id'],row['value'],status=row['status'],source=row['source'],
                evidence=evidence,supersedes=row.get('supersedes')).id)
    return outputs


def main():
    import argparse
    from memory.evidence import EvidenceJournal
    from .datasets import ExperienceDataset
    from .cycle import gameplay_active
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--episode',type=Path);p.add_argument('--annotations',type=Path)
    p.add_argument('--max-crops',type=int,default=128);a=p.parse_args()
    if gameplay_active():p.error('offline only')
    if bool(a.episode)==bool(a.annotations):p.error('choose one extraction or annotation operation')
    j=EvidenceJournal(a.output/'learning-evidence.sqlite3');ds=ExperienceDataset(j,a.output/'pixels')
    try:print(json.dumps(collect_crops(a.episode,ds,max_crops=a.max_crops) if a.episode else {'annotations':apply_annotations(ds,a.annotations)}))
    finally:j.close()


if __name__=='__main__':main()

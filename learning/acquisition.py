"""Extract immutable unlabeled crops from existing observations, no vision pass."""
import json
from pathlib import Path
from memory.evidence import digest
from .datasets import sha,SCOPE


def export_history(output):
    """Evidence-owned immutable transfer; exported copies are not new episodes."""
    import fcntl
    import tarfile
    from memory.evidence import EvidenceJournal
    from .foundry import atomic_json
    from .cycle import gameplay_active
    if gameplay_active():
        raise RuntimeError('offline export unavailable during gameplay')
    output = Path(output).resolve()
    if not (output/'learning-evidence.sqlite3').is_file():
        raise ValueError('existing persistent notebook required')
    with (output/'offline.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = EvidenceJournal(output/'learning-evidence.sqlite3', read_only=True)
        try:
            ids = [r.id for r in journal.records()]
        finally:
            journal.close()
        files = {p.relative_to(output).as_posix(): sha(p)
                 for p in sorted(output.rglob('*')) if p.is_file()
                 and 'exports' not in p.relative_to(output).parts
                 and not p.name.endswith(('.lock', '-wal', '-shm'))}
        if any(output.rglob('*-wal')):
            raise ValueError('uncheckpointed notebook WAL; no incomplete export')
        identity = digest(dict(files=files, original_content_ids=ids))
        directory = output/'exports'/'evidence'/identity
        directory.mkdir(parents=True, exist_ok=True)
        package = directory/'meditation-history.tar.gz'
        manifest = directory/'manifest.json'
        if not package.exists():
            temporary = directory/'transfer.partial'
            with tarfile.open(temporary, 'w:gz') as archive:
                for name in files:
                    archive.add(output/name, arcname='notebook/'+name, recursive=False)
                import io
                raw = json.dumps(dict(schema='charlie-evidence-history-transfer-v1',
                    files=files, original_content_ids=ids, export_is_copy=True,
                    new_physical_experience=False, physical_authorization=False), sort_keys=True).encode()
                metadata = tarfile.TarInfo('TRANSFER.json'); metadata.size = len(raw)
                archive.addfile(metadata, io.BytesIO(raw))
            # Source mutation or torn transfer never becomes a published package.
            if any(sha(output/name) != value for name, value in files.items()):
                raise ValueError('notebook changed during export')
            with tarfile.open(temporary) as archive:
                import hashlib
                if {m.name.removeprefix('notebook/'): hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                    for m in archive.getmembers() if m.name.startswith('notebook/')} != files:
                    raise ValueError('transfer bytes do not match notebook')
            temporary.rename(package)
        document = dict(schema='charlie-evidence-history-transfer-v1',
            original_content_ids=ids, files=files, package_sha256=sha(package),
            original_physical_episodes=False, export_is_copy=True, physical_authorization=False)
        if manifest.exists():
            if json.loads(manifest.read_text()) != document:
                raise ValueError('existing export changed')
        else:
            atomic_json(manifest, document)
        return dict(package=str(package), manifest=str(manifest), package_sha256=document['package_sha256'],
                    records=len(ids), new_physical_experience=False)


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
    from .cycle import gameplay_active
    if gameplay_active():raise RuntimeError('offline annotation unavailable during gameplay')
    path=Path(path);records=json.loads(path.read_text());outputs=[]
    if not isinstance(records,list):raise ValueError('annotation list required')
    if len(records)>512:raise ValueError('bounded annotation batch required (at most 512)')
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
    p.add_argument('--export-history',action='store_true')
    p.add_argument('--max-crops',type=int,default=128);a=p.parse_args()
    if gameplay_active():p.error('offline only')
    if sum((bool(a.episode), bool(a.annotations), a.export_history)) != 1:
        p.error('choose one extraction, annotation or history export operation')
    if a.export_history:
        print(json.dumps(export_history(a.output)))
        return
    j=EvidenceJournal(a.output/'learning-evidence.sqlite3');ds=ExperienceDataset(j,a.output/'pixels')
    try:print(json.dumps(collect_crops(a.episode,ds,max_crops=a.max_crops) if a.episode else {'annotations':apply_annotations(ds,a.annotations)}))
    finally:j.close()


if __name__=='__main__':main()

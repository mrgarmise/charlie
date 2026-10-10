"""Extract immutable unlabeled crops from existing observations, no vision pass."""
import json
from pathlib import Path
from memory.evidence import digest
from .datasets import sha,SCOPE


def retain_dependency_request(journal, evidence_id, *, work_id, required_evidence, reason):
    """Idempotent request at the existing acquisition boundary, never authority."""
    evidence=journal.get(evidence_id)
    key=digest(dict(work_id=work_id,required_evidence=required_evidence,reason=reason))
    old=next((r for r in journal.category_records('event','learning_evidence_request')
        if r.data['payload'].get('dependency_key')==key),None)
    if old:return old
    return journal.append('event',dict(category='learning_evidence_request',
        dependency_key=key,work_id=work_id,method='developmental-dependency',
        required_evidence=required_evidence,reason=reason,
        status='AWAITING_DEPENDENCY',request_kind='evidence_acquisition_only',
        fulfillment='Independently qualified acquisition delivery or recorded resource/capability change; Executive checks eligibility',
        physical_authorization=False,servo_authorization=False,firmware_authorization=False),
        episode=evidence.data['episode'],sources=[evidence_id],
        producer='existing-acquisition-capability',version='normal-lifecycle-v1')


def satisfy_artifact_requests(dataset):
    """Qualify delivery of original bytes, never independent new experience."""
    journal=dataset.journal
    satisfied={r.data['payload']['request_id'] for r in journal.category_records('event','acquisition_dependency_satisfied')}
    examples={r['id']:r for r in dataset.examples()};outputs=[]
    for request in journal.category_records('event','learning_evidence_request'):
        if request.id in satisfied:continue
        p=request.data['payload'];required=p.get('required_evidence',[])
        if len(required)!=1 or not isinstance(required[0],dict) or required[0].get('type')!='preserved_pixel_artifact':continue
        spec=required[0];row=examples.get(spec['example_id'])
        if not row or p['work_id']!='visual-artifact:'+row['id'] or row['pixel_sha256']!=spec['sha256']:continue
        try:
            if sha(row['pixel_path'])!=spec['sha256']:continue
        except OSError:continue
        receipt=journal.append('event',dict(category='acquisition_dependency_satisfied',request_id=request.id,
            work_id=p['work_id'],example_id=row['id'],path=row['pixel_path'],sha256=spec['sha256'],
            new_independent_experience=False,physical_authorization=False),episode=request.data['episode'],
            sources=[request.id,row.get('artifact_location_id',row['id'])],
            producer='existing-acquisition-capability',version='normal-lifecycle-v1')
        outputs.append(receipt.id)
    return outputs


def investigate_requests(dataset, roots, *, provenance, check=lambda: None):
    """Respond to retained requests using existing acquisition qualifications.

    A search result is not a qualification or an experiment. Only the existing
    artifact and independent corpus validators can deliver those. Changed source
    receipts permit reconsideration; identical failed searches survive restart.
    """
    journal = dataset.journal
    discoveries = discover_request_sources(dataset, roots, provenance=provenance, check=check)
    categories = ('episode_identity_binding', 'episode_identity_location',
                  'episode_identity_alias', 'episode_identity_quarantine',
                  'observation_qualification', 'independent_motion_corpus',
                  'experience_artifact_location', 'acquisition_delivery',
                  'acquisition_delivery_rejected', 'acquisition_dependency_satisfied')
    evidence = [r for r in journal.records() if r.data['payload'].get('category') in categories]
    availability = dict(roots=[dict(path=str(Path(r).resolve()), available=Path(r).is_dir()) for r in roots],
                        evidence=[r.id for r in evidence], discoveries=discoveries)
    signature = digest(availability)
    previous = {(r.data['payload']['request_id'], r.data['payload']['availability'])
                for r in journal.category_records('event', 'acquisition_search_result')}
    satisfied = {r.data['payload']['request_id']: r for r in evidence
                 if r.data['payload'].get('category') == 'acquisition_dependency_satisfied'}
    outputs = []
    for request in journal.category_records('event', 'learning_evidence_request'):
        p = request.data['payload']
        if p.get('method') != 'developmental-dependency' or (request.id, signature) in previous:
            continue
        # Delivery means exactly what its original validator certified. A raw
        # recording or retrospective tracker output never satisfies a trajectory
        # request merely because its filename or episode is recognizable.
        delivery = satisfied.get(request.id)
        result = journal.append('event', dict(category='acquisition_search_result',
            request_id=request.id, work_id=p['work_id'], availability=signature,
            searched_sources=availability['roots'], inspected_evidence=availability['evidence'],
            discovery_ids=discoveries,
            required_evidence=p['required_evidence'],
            status='delivered' if delivery else 'unsatisfied',
            delivery_id=delivery.id if delivery else None,
            reason='Existing validator delivered the requested original artifact' if delivery else
                'Configured source discovery completed; no validator has delivered evidence satisfying this exact dependency',
            next_requirement=p['required_evidence'] if not delivery else [],
            qualification_authority='existing artifact/corpus validators and independent Evaluator',
            new_independent_experience=False, physical_authorization=False,
            servo_authorization=False, firmware_authorization=False),
            episode=request.data['episode'], sources=[request.id, *[r.id for r in evidence
                if r.data['episode']==request.data['episode']]],
            producer='existing-acquisition-capability', version='request-investigation-v1', provenance=provenance)
        outputs.append(result.id)
    return outputs


def discover_request_sources(dataset, roots, *, provenance, check=lambda: None):
    """Request-driven inspection of original references, never trajectory truth.

    Content changes inside an existing root are acquisition availability changes.
    Each completed episode is retained before checking the next resource slice.
    Bounds are reported as deficiencies, not as an exhaustive successful search.
    """
    if not dataset.journal.category_records('event', 'learning_evidence_request'):
        return []
    from itertools import islice
    journal=dataset.journal; outputs=[]
    for root in dict.fromkeys(Path(r).resolve() for r in roots):
        check()
        reports=list(islice(root.rglob('report.json'), 129)) if root.is_dir() else []
        if len(reports)>128:
            result=journal.append('observation',dict(category='acquisition_source_discovery',
                root=str(root),status='incomplete',deficiencies=['128 episode search bound reached; remaining sources not inspected'],
                original_observations=[],independent_measurements=False),episode=SCOPE,
                producer='existing-acquisition-capability',version='request-source-v1',provenance=provenance)
            outputs.append(result.id)
        for report in sorted(reports[:128]):
            check()
            directory=report.parent; artifacts=[]; frames=[]; deficiencies=[]
            def original(path):
                path=Path(path).resolve()
                if not path.is_relative_to(root):raise ValueError('source reference escapes authorized root')
                if not path.is_file():raise ValueError('original source unavailable: '+str(path))
                if path.stat().st_size>8*1024*1024:raise ValueError('8MiB artifact inspection bound reached: '+str(path))
                return dict(path=str(path),sha256=sha(path))
            try:
                reference=original(report);artifacts.append(reference)
                header=json.loads(report.read_text())
                if not isinstance(header,dict):raise ValueError('report object required')
            except (OSError,ValueError) as exc:
                header={};deficiencies.append(str(exc))
            diary=directory/'session-evidence.sqlite3'
            if diary.exists():
                import sqlite3
                from memory.evidence import EvidenceJournal
                source=None
                try:
                    artifacts.append(original(diary))
                    source=EvidenceJournal(diary,read_only=True)
                    source.verify()
                    for capture in source.category_records('observation','camera_capture')[:256]:
                        check()
                        p=capture.data['payload'];frame=original(directory/p['artifact']['path'])
                        if frame['sha256']!=p['artifact']['sha256']:raise ValueError('camera capture bytes changed')
                        observation=source.get(p['observation_id'])
                        if observation.data['payload'].get('category')!='camera_observation':raise ValueError('camera descriptor required')
                        from PIL import Image
                        with Image.open(frame['path']) as image:image.verify()
                        frames.append(dict(artifact=frame,timestamp=observation.data['at'],
                            timestamp_status='recorded_unqualified',observation_id=observation.id,
                            capture_record_id=capture.id,source_kind='original_camera_pixels',
                            capture_provenance=capture.data['provenance'],identity_status='unverified',
                            measurement_status='original_pixels_only'))
                    if len(source.category_records('observation','camera_capture'))>256:
                        deficiencies.append('256 camera capture inspection bound reached')
                except (OSError,ValueError,KeyError,TypeError,sqlite3.Error) as exc:
                    deficiencies.append('Original camera diary: '+str(exc))
                finally:
                    if source:source.close()
            for name in ('agency.jsonl','observations.jsonl','score.jsonl'):
                path=directory/name
                if not path.exists():continue
                try:
                    reference=original(path);artifacts.append(reference)
                    with path.open() as stream:
                        for line,text in enumerate(stream,1):
                            if line>4096:
                                deficiencies.append(name+': 4096 row inspection bound reached');break
                            if not text.strip():continue
                            try:
                                row=json.loads(text)
                                if not isinstance(row,dict):raise ValueError('observation object required')
                                filename=row.get('raw_frame') or row.get('frame')
                                if not isinstance(filename,str):continue
                                if len(frames)>=256:
                                    deficiencies.append('256 original frame inspection bound reached');break
                                frame=original(directory/filename)
                                from PIL import Image
                                with Image.open(frame['path']) as image:
                                    image.verify()
                                timestamp=row.get('capture_timestamp',row.get('timestamp'))
                                import math
                                valid_time=type(timestamp) in (int,float) and math.isfinite(timestamp)
                                frames.append(dict(artifact=frame,timestamp=timestamp if valid_time else None,
                                    timestamp_status='recorded_unqualified' if valid_time else 'missing_or_invalid',
                                    source_stream=reference,line=line,row_sha256=digest(row),
                                    proposed_tracking=row.get('tracking'),
                                    commanded_action=row.get('control_execution'),
                                    source_kind='derived_rectified_playfield' if name=='agency.jsonl' else 'preserved_frame_unverified_origin',
                                    identity_status='unverified',measurement_status='original_pixels_only'))
                            except (OSError,ValueError,TypeError) as exc:
                                deficiencies.append(name+':'+str(line)+': '+str(exc))
                except (OSError,ValueError) as exc:deficiencies.append(str(exc))
            if not frames:deficiencies.append('No usable hash-bound original frame references in inspected streams')
            deficiencies.append('Persistent identity, calibrated board positions, independence and frozen partition remain unqualified')
            record=journal.append('observation',dict(category='acquisition_source_discovery',
                root=str(root),episode_path=str(directory),status='originals_found' if frames else 'unavailable',
                source_artifacts=artifacts,original_observations=frames,deficiencies=deficiencies,
                capture_identity=header.get('capture_identity') if isinstance(header.get('capture_identity'),str) else None,
                capture_code_revision=header.get('code_revision') if isinstance(header.get('code_revision'),str) else None,
                independence='originals may be consulted or overlapping; no new independent count',
                independent_measurements=False,physical_authorization=False),episode=SCOPE,
                producer='existing-acquisition-capability',version='request-source-v1',provenance=provenance)
            outputs.append(record.id)
    return sorted(set(outputs))


def qualification_inputs(path, journal):
    """Retry rejected delivery when referenced bytes or identity receipts change."""
    files=[]
    try:
        corpus=json.loads(Path(path).read_text())
        references=[corpus.get('qualification_artifact',{})]
        for episode in corpus.get('episodes',[]):
            references.append(episode.get('source_report',{}))
            references.extend(frame.get('artifact',{}) for frame in episode.get('frames',[]))
        for reference in references:
            name=reference.get('path')
            if not name:continue
            try:value=sha(name)
            except OSError:value=None
            files.append(dict(path=name,sha256=value))
    except (ValueError,TypeError,AttributeError):
        files=[] # Malformed unchanged inbox bytes are not repeatedly imported.
    identities=[r.id for r in journal.records('event') if r.data['payload'].get('category') in
        ('episode_identity_binding','episode_identity_location','episode_identity_alias','episode_identity_quarantine')]
    return digest(dict(inbox=sha(path),files=files,identities=identities))


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


def maintain_episode_identity(root, journal):
    """Permanent automatic acquisition capability; never an operator repair step."""
    from .episode_identity import reconcile
    return reconcile(root, journal)

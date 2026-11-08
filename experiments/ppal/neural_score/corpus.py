"""Immutable whole-string corpus. Reuse existing reviewed evidence, never relabel."""
import os
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .contract import sha,PREPROCESS
from ..score_digits import valid_display_digits


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def _freeze(rows,output,*,previous=(),commitments=()):
    output=Path(output)
    if output.exists():raise FileExistsError('frozen manifest exists')
    ownership={};sessions={};raw_ownership={};frozen=[];seen={};pixels=[]
    for r in commitments:
        ownership[r["pixel_sha256"]]=r["role"];sessions[r["session"]]=r["role"]
        if r.get("source_image_sha256"):raw_ownership[r["source_image_sha256"]]=r["role"]
    for path in previous:
        old=verify(path)
        for r in old['rows']:
            ownership[r['pixel_sha256']]=r['role'];sessions[r['session']]=r['role']
            if r.get('source_image_sha256'):raw_ownership[r['source_image_sha256']]=r['role']
            # Prior frozen manifests must participate in the same near-pixel
            # guard as rows in this batch. Exact hashes alone miss re-encodes.
            with Image.open(image_path(path,r)) as image:
                pixels.append((np.asarray(image.convert('RGB').resize((32,8)),dtype=np.int16),r['role'],None))
    for row in rows:
        r=dict(row);path=Path(r['image'])
        if r.get('verified') is not True or not r.get('reviewer') or not r.get('annotation_ids'):raise ValueError('explicit verified original human review required')
        label=r['label']
        if label is not None and label!='' and not valid_display_digits(label):
            raise ValueError('whole visible score digits required; only zero-padding of zero is supported')
        if r['role'] not in ('train','val','test') or not r.get('session'):raise ValueError('session split required')
        if r.get('consulted_test') and r['role']!='test':raise ValueError('consulted test cannot migrate')
        if r.get('review_partition')=='training' and r['role']!='train':raise ValueError('training review is not independent evaluation')
        if r.get('review_partition')=='diagnostic' and r['role']=='test':raise ValueError('consulted diagnostic is not final test')
        with Image.open(path) as image:
            rgb=image.convert('RGB');small=np.asarray(rgb.resize((32,8)),dtype=np.int16)
            pixel=hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
        if sha(path)!=r['sha256']:raise ValueError('original image hash mismatch')
        if pixel in ownership and ownership[pixel]!=r['role']:raise ValueError('duplicate/previous pixel split leakage')
        if r['session'] in sessions and sessions[r['session']]!=r['role']:raise ValueError('session split leakage')
        raw_sha=r.get('source_image_sha256')
        if raw_sha in raw_ownership and raw_ownership[raw_sha]!=r['role']:raise ValueError('original full-frame split leakage')
        if raw_sha:raw_ownership[raw_sha]=r['role']
        for other,role,other_label in pixels:
            if np.abs(small-other).mean()<2 and role!=r['role']:raise ValueError('near-duplicate split leakage')
        if pixel in seen:
            if seen[pixel]!=label:raise ValueError('conflicting duplicate labels')
            continue
        ownership[pixel]=r['role'];sessions[r['session']]=r['role'];seen[pixel]=label
        pixels.append((small,r['role'],label));r.update(pixel_sha256=pixel,image=os.path.relpath(path.resolve(),output.parent.resolve()),preprocessing=PREPROCESS)
        frozen.append(r)
    record=dict(schema='charlie-score-corpus-v1',rows=frozen,prior_manifests=[sha(p) for p in previous],
        authenticity='SYNTHETIC / NOT ROBOTRON-QUALIFIED' if any(r.get('synthetic') for r in frozen) else 'human-reviewed originals; qualification separate',
        correlation_risk='whole sessions plus exact/low-resolution near-duplicate rejection; visual review still required')
    record['digest']=digest(record)
    with output.open('x') as stream:json.dump(record,stream,indent=2)
    return record


def verify(path):
    record=json.loads(Path(path).read_text());claimed=record.pop('digest')
    if digest(record)!=claimed:raise ValueError('manifest digest mismatch')
    record['digest']=claimed
    for r in record['rows']:
        if sha(image_path(path,r))!=r['sha256']:raise ValueError('frozen image changed')
    return record


def from_reviews(journal,calibration,output,*,partition='training',previous=()):
    """Adapter to existing immutable whole-number review protocol; no glyph boxes."""
    from ..score_feedback import reviewed_labels
    from ..robotron_hud import RobotronHUDReader
    parts=('training','validation','final') if partition=='all' else (partition,)
    rows=[];excluded=[]
    for part in parts:
        accepted, rejected=reviewed_labels(journal,partition=part)
        rows.extend(dict(item,review_partition=part) for item in accepted)
        excluded.extend(dict(item,review_partition=part) for item in rejected)
    output=Path(output);output.mkdir(exist_ok=False)
    reader=RobotronHUDReader(calibration);result=[]
    for row in rows:
        p=row['proposal'];context=p.get('context',{});channel=context.get('score_channel')
        # Existing review geometry uses memory.evidence.digest canonical JSON.
        from memory.evidence import digest as evidence_digest
        expected=evidence_digest(dict(corners=calibration.corners,output_size=calibration.output_size))
        if channel not in (1,2) or context.get('calibration_geometry_digest')!=expected or not context.get('source_session'):
            excluded.append(dict(proposal_id=row['proposal_id'],reason='explicit channel/session/calibration binding required'));continue
        with Image.open(row['path']) as image:hud=reader.rectify(image)
        fraction=reader.P1_X if channel==1 else reader.P2_X
        box=(int(640*fraction[0]),0,int(640*fraction[1]),96)
        path=output/(row['proposal_id']+'.png');hud.crop(box).save(path)
        review_partition=row['review_partition']
        role={'training':'train','validation':'val','final':'test','diagnostic':'val'}[review_partition]
        result.append(dict(image=str(path),sha256=sha(path),label=row['display_digits'],channel=channel,
            verified=True,reviewer=','.join(sorted({str(journal.get(key).data['payload'].get('annotator','unrecorded reviewer')) for key in row['annotation_ids']})),annotation_ids=row['annotation_ids'],
            proposal_id=row['proposal_id'],review_partition=review_partition,role=role,
            session=context['source_session'],source_image_sha256=p['artifact']['sha256'],source_proposal=p,
            synthetic=False))
    (output/'review-exclusions.json').write_text(json.dumps(excluded,indent=2))
    return freeze(result,output/'manifest.json',previous=previous)


def ledger_path(manifest):return Path(manifest).parent/'score-corpus-ledger.jsonl'


def ledger_records(manifest):
    path=ledger_path(manifest)
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def freeze(rows,output,*,previous=()):
    import fcntl
    path=ledger_path(output)
    with path.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        lock.seek(0);old=[json.loads(line) for line in lock]
        commitments=[r for event in old if event['event']=='freeze' for r in event['rows']]
        record=_freeze(rows,output,previous=previous,commitments=commitments)
        event=dict(event='freeze',manifest_digest=record['digest'],rows=[
            {k:r.get(k) for k in ('pixel_sha256','session','role','source_image_sha256')} for r in record['rows']])
        lock.write(json.dumps(event,sort_keys=True)+'\n');lock.flush()
        import os
        os.fsync(lock.fileno())
        return record


def consult_test(manifest):
    import fcntl,os
    record=verify(manifest)
    with ledger_path(manifest).open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);lock.seek(0);old=[json.loads(line) for line in lock]
        if any(e['event']=='test-consulted' and e['manifest_digest']==record['digest'] for e in old):
            raise ValueError('final test already consulted; use fresh independent sessions')
        lock.write(json.dumps(dict(event='test-consulted',manifest_digest=record['digest']))+'\n');lock.flush();os.fsync(lock.fileno())


def assert_trainable(manifest):
    record=verify(manifest)
    if any(e['event']=='test-consulted' and e['manifest_digest']==record['digest'] for e in ledger_records(manifest)):
        raise ValueError('model selection dataset final test consulted; training closed')
    return record


def image_path(manifest,row):return Path(manifest).resolve().parent/row['image']


def main():
    import argparse
    from memory.evidence import EvidenceJournal
    from ..eyes.calibration import Calibration
    p=argparse.ArgumentParser(description='Read-only existing review journal -> frozen whole-score crops; no new review store')
    p.add_argument('--journal',type=Path,required=True);p.add_argument('--calibration',type=Path,required=True)
    p.add_argument('--prior-manifest',type=Path,action='append',default=[]);p.add_argument('--output',type=Path,required=True);p.add_argument('--partition',choices=['training','validation','final','diagnostic','all'],default='training')
    a=p.parse_args();journal=EvidenceJournal(a.journal,read_only=True)
    try:record=from_reviews(journal,Calibration.load(a.calibration),a.output,partition=a.partition,previous=a.prior_manifest)
    finally:journal.close()
    print(json.dumps(dict(manifest_digest=record['digest'],eligible_crops=len(record['rows']),qualification=record['authenticity'])))

if __name__=='__main__':main()

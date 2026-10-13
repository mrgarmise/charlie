"""Immutable manifests; global exact-pixel partition locks prevent alias leakage."""
import os
import json
from pathlib import Path
import random
import shutil
import time
import zipfile
from .store import canonical,digest,identifier,file_hash
from .sources import hydrate

ROLES=('train','val','test')


def quality(lab,selected):
    classes=lab.get('settings','classes');balance={k:0 for k in classes};issues=[];sessions={};duplicates={};verified=[]
    for fid in selected:
        f=lab.frame(fid);a=lab.annotation(fid)
        if a['status']!='verified':issues.append(dict(frame=fid,reason='Complete verified human review required'));continue
        if any(b['class_name'] not in classes or b['uncertain'] or not b['accepted'] for b in a['boxes']):issues.append(dict(frame=fid,reason='Unresolved or unaccepted objects'));continue
        if not f.get('pixel_sha'):issues.append(dict(frame=fid,reason='Pixels not verified'));continue
        for b in a['boxes']:balance[b['class_name']]+=1
        duplicates.setdefault(f['pixel_sha'],[]).append(fid);sessions.setdefault(f['session'],[]).append(fid)
        verified.append(fid)
    return dict(frames=len(selected),verified=len(verified),class_balance=balance,sessions=sessions,
                duplicate_groups=[v for v in duplicates.values() if len(v)>1],issues=issues,
                warnings=['No examples for '+k for k,v in balance.items() if not v])


def split_sessions(lab,selected,seed=7):
    if type(seed) is not int:raise ValueError('Integer seed required')
    q=quality(lab,selected)
    if q['issues']:raise ValueError('Review selected frames before partitioning')
    # Union source sessions connected by exact duplicate pixels, even across different roots.
    groups={s:{s} for s in q['sessions']}
    for duplicate in q['duplicate_groups']:
        joined=set().union(*(groups[lab.frame(fid)['session']] for fid in duplicate))
        for s in joined:groups[s]=joined
    units=sorted({tuple(sorted(v)) for v in groups.values()})
    if len(units)<3:raise ValueError('At least three independent configured session groups required')
    rng=random.Random(seed);rng.shuffle(units)
    split={}
    for i,unit in enumerate(units):
        role='test' if i==0 else 'val' if i==1 else 'train'
        for session in unit:split[session]=role
    return split


def freeze(lab,name,selected,assignments,seed=7):
    if not isinstance(name,str) or not name.strip() or len(name)>120:raise ValueError('Named dataset required')
    if not isinstance(selected,list) or not selected or len(selected)>10000 or len(set(selected))!=len(selected):raise ValueError('Distinct explicit frame inclusion required')
    for fid in selected:hydrate(lab,fid)
    q=quality(lab,selected)
    if q['issues']:raise ValueError('Dataset contains unverified/incomplete annotations')
    if assignments is None:assignments=split_sessions(lab,selected,seed)
    if not isinstance(assignments,dict) or set(assignments)!=set(q['sessions']) or set(assignments.values())!=set(ROLES):raise ValueError('Assign every session; train, val and test required')
    rows=[];seen={};class_names=lab.get('settings','classes')
    for fid in selected:
        f=lab.frame(fid);a=lab.annotation(fid);role=assignments[f['session']]
        if f['pixel_sha'] in seen:
            prior=seen[f['pixel_sha']]
            if prior['role']!=role:raise ValueError('Exact duplicate crosses partitions')
            if digest(prior['annotation']['boxes'])!=digest(a['boxes']):raise ValueError('Conflicting duplicate labels')
            continue # Explicitly recorded duplicate exclusion, never another independent example.
        row=dict(frame_id=fid,pixel_sha=f['pixel_sha'],pixel_file_sha=f['cache_sha256'],width=f['width'],height=f['height'],session=f['session'],role=role,annotation=a,provenance=f['provenance'],timestamp=f['timestamp'],timestamp_basis=f['timestamp_basis'])
        seen[f['pixel_sha']]=row;rows.append(row)
    with lab.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        # Session roles are sticky across versions as well as exact-pixel roles.
        for row in rows:
            prior=c.execute('SELECT role FROM partitions WHERE pixel_sha=?',(row['pixel_sha'],)).fetchone()
            session_roles={r[0] for r in c.execute('SELECT role FROM partitions WHERE session=?',(row['session'],))}
            if (prior and prior[0]!=row['role']) or (session_roles and session_roles!={row['role']}):raise ValueError('Frozen session/pixel partition cannot change across dataset versions')
        for row in rows:c.execute('INSERT OR IGNORE INTO partitions VALUES(?,?,?)',(row['pixel_sha'],row['role'],row['session']))
        versions=[json.loads(p) for p, in c.execute("SELECT payload FROM items WHERE kind='datasets'")]
        version=1+sum(v['name']==name for v in versions)
        m=dict(schema='charlie-vision-dataset-v1',id=identifier(),name=name,version=version,at=time.time(),seed=seed,classes=class_names,assignments=assignments,frames=rows,
            selected_frames=selected,excluded_duplicate_frames=[fid for fid in selected if fid not in {r['frame_id'] for r in rows}],quality=q,
            authenticity='synthetic-fixture' if any(r['provenance']['authenticity']=='synthetic-fixture' for r in rows) else 'operator-declared or unknown; not independently qualified',
            held_out_policy='test never used for training, selection or assisted annotation',physical_authorization=False)
        m['digest']=digest(m)
        c.execute('INSERT INTO items VALUES(?,?,?)',('datasets',m['id'],canonical(m)))
    folder=lab.root/'datasets'/m['id'];folder.mkdir()
    (folder/'manifest.json').write_text(canonical(m)+'\n')
    return m


def verify_manifest(lab,dataset_id):
    m=lab.get('datasets',dataset_id)
    if m['digest']!=digest({k:v for k,v in m.items() if k!='digest'}):raise ValueError('Dataset manifest corrupted')
    p=lab.root/'datasets'/m['id']/'manifest.json'
    if json.loads(p.read_text())!=m:raise ValueError('Stored manifest differs from registry')
    for r in m['frames']:
        if file_hash(lab.root/'pixels'/(r['pixel_sha']+'.png'))!=r['pixel_file_sha']:raise ValueError('Frozen pixels changed')
        if r['annotation']['digest']!=digest({k:v for k,v in r['annotation'].items() if k!='digest'}):raise ValueError('Frozen annotation corrupted')
    return m


def export_yolo(lab,dataset_id):
    m=verify_manifest(lab,dataset_id);out=lab.root/'datasets'/m['id']/'yolo'
    if out.exists():
        receipt=json.loads((out/'export-manifest.json').read_text())
        actual={str(p.relative_to(out)):file_hash(p) for p in out.rglob('*') if p.is_file() and p.name!='export-manifest.json'}
        if receipt['files']!=actual or receipt['dataset_digest']!=m['digest']:raise ValueError('Cached export integrity mismatch; preserve it and rebuild in an isolated copy')
        return out
    final=out;out=out.parent/('building-'+identifier());out.mkdir()
    for role in ROLES:
        for kind in ('images','labels'):(out/role/kind).mkdir(parents=True)
    for row in m['frames']:
        key=row['pixel_sha'];base=out/row['role'];shutil.copyfile(lab.root/'pixels'/(key+'.png'),base/'images'/(key+'.png'))
        labels=[]
        for b in row['annotation']['boxes']:
            labels.append(f"{m['classes'].index(b['class_name'])} {(b['x']+b['w']/2)/row['width']:.9f} {(b['y']+b['h']/2)/row['height']:.9f} {b['w']/row['width']:.9f} {b['h']/row['height']:.9f}")
        (base/'labels'/(key+'.txt')).write_text('\n'.join(labels)+'\n')
    # JSON is valid YAML; paths are relative to the exporter root. No test key is exposed to training.
    config=dict(path=str(final.resolve()),train='train/images',val='val/images',nc=len(m['classes']),names=m['classes'])
    (out/'train.yaml').write_text(canonical(config)+'\n')
    (out/'manifest.json').write_text(canonical(m)+'\n')
    receipt=dict(dataset_digest=m['digest'],files={str(p.relative_to(out)):file_hash(p) for p in out.rglob('*') if p.is_file()})
    (out/'export-manifest.json').write_text(canonical(receipt)+'\n')
    out.rename(final)
    return final


def export_zip(lab,dataset_id):
    out=export_yolo(lab,dataset_id);archive=out.parent/'dataset.zip'
    # Stable ordering and timestamps; portable config uses path='.' in the ZIP.
    temporary=archive.with_name('dataset-'+identifier()+'.tmp')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as z:
        files={}
        for p in sorted(out.rglob('*')):
            if not p.is_file() or p.name=='export-manifest.json':continue
            raw=p.read_bytes()
            if p.name=='train.yaml':
                d=json.loads(raw);d.pop('path',None);raw=(canonical(d)+'\n').encode()
            info=zipfile.ZipInfo(p.relative_to(out).as_posix(),date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,raw);files[p.relative_to(out).as_posix()]=__import__('hashlib').sha256(raw).hexdigest()
        info=zipfile.ZipInfo('export-manifest.json',date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
        z.writestr(info,(canonical(dict(dataset_digest=lab.get('datasets',dataset_id)['digest'],files=files))+'\n').encode())
    os.replace(temporary,archive)
    return archive


def held_out(lab,pixel_sha):
    with lab.connect() as c:r=c.execute('SELECT role FROM partitions WHERE pixel_sha=?',(pixel_sha,)).fetchone()
    return bool(r and r[0]=='test')

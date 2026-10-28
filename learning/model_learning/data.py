"""Content-addressed retained observations and attributed label reviews."""
from pathlib import Path
import hashlib
import json
from PIL import Image
import numpy as np
from memory.evidence import digest
from .contracts import DatasetCandidate, document

SCOPE='model-learning-v1'
LABELS=('title_menu','gameplay','terminal','unknown')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprints(path):
    with Image.open(path) as image:
        if image.width*image.height>4_000_000: raise ValueError('image too large')
        rgb=image.convert('RGB')
        pixels=hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
        small=np.asarray(rgb.convert('L').resize((9,8)),dtype=int)
        bits=(small[:,1:]>small[:,:-1]).flatten()
        dhash=sum(int(bit)<<i for i,bit in enumerate(bits))
    return pixels,format(dhash,'016x')


class DatasetStore:
    def __init__(self,journal,root):
        self.journal=journal; self.root=Path(root).resolve(); self.root.mkdir(parents=True,exist_ok=True)

    def events(self,category):
        return [r for r in self.journal.records() if r.data['episode']==SCOPE and r.data['payload'].get('category')==category]

    def append(self,category,payload,*,sources=(),producer='model-learning'):
        return self.journal.append('event',dict(category=category,**payload),episode=SCOPE,
            sources=sources,producer=producer,version=SCOPE)

    def add(self,path,*,session,provenance,authentic,partition=None,calibration=None,task='robotron.screen_state'):
        if not session or not provenance or type(authentic) is not bool or partition not in (None,'train','validation','test'):
            raise ValueError('source session, provenance, authenticity and explicit partition required')
        if len(json.dumps(provenance,allow_nan=False).encode())>16*1024:raise ValueError("provenance byte budget exceeded")
        if not isinstance(session,str) or len(session)>256:raise ValueError("bounded session required")
        if task!="robotron.screen_state": raise ValueError("task adapter not registered")
        path=Path(path)
        if path.stat().st_size>8*1024**2: raise ValueError("image byte budget exceeded")
        raw=sha(path); pixels,near=fingerprints(path)
        payload=dict(task=task,session=session,provenance=provenance,authentic=authentic,partition=partition,
                     sha256=raw,pixel_sha256=pixels,dhash=near,calibration=calibration)
        for row in self.events('model_observation'):
            old=row.data['payload']
            if old['pixel_sha256']==pixels:
                if any(old[k]!=payload[k] for k in ('task','session','authentic','partition','calibration')):
                    raise ValueError('duplicate pixels have conflicting ownership')
                return row
            if old['session']==session and old['partition']!=partition:
                raise ValueError('capture session cannot cross partitions')
        if len(self.events('model_observation'))>=256: raise ValueError('retained frame budget reached')
        if sum(p.stat().st_size for p in self.root.glob('*.image'))+path.stat().st_size>64*1024**2:
            raise ValueError('retained disk budget reached')
        target=self.root/(raw+'.image')
        if target.exists() and sha(target)!=raw: raise ValueError('retained content changed')
        if not target.exists():
            with target.open('xb') as stream: stream.write(path.read_bytes())
            target.chmod(0o444)
        return self.append('model_observation',dict(payload,path=str(target)))

    def label(self,observation_id,label,*,reviewer,reason,supersedes=None):
        row=self.journal.get(observation_id)
        if row.data['payload'].get('category')!='model_observation' or label not in LABELS or not reviewer or not reason:
            raise ValueError('typed attributed review required')
        prior=[r for r in self.events('model_label') if r.data['payload']['observation_id']==observation_id]
        if prior and prior[-1].id!=supersedes: raise ValueError('explicit supersession required')
        if not prior and supersedes: raise ValueError('no review to supersede')
        return self.append('model_label',dict(observation_id=observation_id,label=label,reviewer=reviewer,
            reason=reason,supersedes=supersedes,truth='fallible attributed evidence'),sources=[observation_id]+([supersedes] if supersedes else []))

    def exclude(self,observation_id,*,reviewer,reason):
        if not reviewer or not reason: raise ValueError("attributed retention/exclusion reason required")
        row=self.journal.get(observation_id)
        if row.data["payload"].get("category")!="model_observation": raise ValueError("observation required")
        return self.append("model_exclusion",dict(observation_id=observation_id,reviewer=reviewer,reason=reason),sources=[observation_id])

    def partition(self,session,partition,*,reviewer):
        if partition not in ("train","validation","test") or not reviewer:
            raise ValueError("explicit session split and reviewer required")
        rows=[r for r in self.rows() if r["session"]==session]
        if not rows: raise ValueError("unknown session")
        frozen_sessions={r["session"] for snapshot in self.events("model_dataset") for r in snapshot.data["payload"]["dataset"]["rows"]}
        if session in frozen_sessions: raise ValueError("frozen split cannot change; retire old observations and use a new session")
        return self.append("model_partition",dict(session=session,partition=partition,reviewer=reviewer),sources=[r["observation_id"] for r in rows])

    def rows(self):
        labels={r.data['payload']['observation_id']:r for r in self.events('model_label')}
        partitions={r.data["payload"]["session"]:r.data["payload"]["partition"] for r in self.events("model_partition")}
        excluded={r.data["payload"]["observation_id"] for r in self.events("model_exclusion")}
        return [dict(r.data['payload'],observation_id=r.id,effective_partition=partitions.get(r.data["payload"]["session"],r.data["payload"]["partition"]),label=labels[r.id].data['payload']['label'] if r.id in labels else None,
            label_id=labels[r.id].id if r.id in labels else None) for r in self.events('model_observation') if r.id not in excluded]

    def inspect(self,*,allow_synthetic=False):
        rows=self.rows(); issues=[]
        for row in rows: row["partition"]=row.pop("effective_partition")
        if not rows: issues.append('no retained observations')
        for row in rows:
            if sha(row['path'])!=row['sha256'] or fingerprints(row['path'])[0]!=row['pixel_sha256']:
                raise ValueError('observation integrity changed')
            if not row['authentic'] and not allow_synthetic: issues.append('synthetic observation excluded from authentic qualification')
            if row['label'] is None or row['partition'] is None: issues.append('missing labels or session partition')
        for partition in ('train','validation','test'):
            present={r['label'] for r in rows if r['partition']==partition}
            if not set(LABELS[:-1])<=present: issues.append(partition+' needs every known class')
        if not any(r['label']=='unknown' and r['partition']=='test' for r in rows): issues.append('test needs authentic unknown/OOD examples')
        for i,left in enumerate(rows):
            for right in rows[i+1:]:
                if left['partition']!=right['partition'] and left['partition'] and right['partition']:
                    if left['session']==right['session'] or (int(left['dhash'],16)^int(right['dhash'],16)).bit_count()<=4:
                        issues.append('session or near-duplicate leakage across partitions')
        return dict(status='NEEDS_LABELS' if issues else 'READY',issues=sorted(set(issues)),
            counts=dict(total=len(rows),authentic=sum(r['authentic'] for r in rows),labeled=sum(r['label'] is not None for r in rows),
                        sessions=len({r['session'] for r in rows})),rows=rows)

    def freeze(self,*,allow_synthetic=False):
        report=self.inspect(allow_synthetic=allow_synthetic)
        if report['status']!='READY': raise ValueError('NEEDS_LABELS: '+str(report['issues']))
        payload=document(DatasetCandidate('robotron.screen_state',tuple(report['rows']),LABELS))
        # Exact same split/version is reused on restart, rather than renewed holdout.
        key=digest(payload)
        prior=next((r for r in self.events('model_dataset') if r.data['payload']['dataset_digest']==key),None)
        return prior or self.append('model_dataset',dict(dataset=payload,dataset_digest=key),
            sources=[r['label_id'] for r in report['rows']])

    def review_queue(self):
        return [dict(observation_id=r['observation_id'],session=r['session'],path=r['path'],reason='unresolved screen label or split')
                for r in self.rows() if r['label'] is None or r['effective_partition'] is None][:256]

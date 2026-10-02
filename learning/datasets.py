"""Versioned experience datasets projected from the existing evidence journal.

Pixels are immutable content-addressed artifacts, not a second memory store.
Annotations are separate evidence. Model/replay labels cannot become verification.
"""
from pathlib import Path
import hashlib
import io
import os
from PIL import Image
from memory.evidence import digest

SCOPE = 'autonomous-learning-v1'
VERSION = 'experience-dataset-v1'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class ExperienceDataset:
    def __init__(self, journal, artifacts):
        self.journal = journal
        self.artifacts = Path(artifacts)
        self.artifacts.mkdir(parents=True, exist_ok=True)

    def add(self, path, *, episode, source, crop=None, metadata=None):
        path = Path(path)
        original_hash = sha(path)
        with Image.open(path) as image:
            image = image.convert('RGB')
            if crop is not None:
                if len(crop)!=4 or any(type(v) is not int for v in crop) or not (0 <= crop[0] < crop[2] <= image.width and 0 <= crop[1] < crop[3] <= image.height):
                    raise ValueError('crop must lie inside the preserved RGB frame')
                image = image.crop(crop)
            stream=io.BytesIO(); image.save(stream,format='PNG'); pixels=stream.getvalue()
        pixel_hash=hashlib.sha256(pixels).hexdigest()
        target=self.artifacts/(pixel_hash+'.png')
        if not target.exists():
            tmp=target.with_suffix('.tmp')
            with tmp.open('wb') as stream:
                stream.write(pixels); stream.flush(); os.fsync(stream.fileno())
            tmp.replace(target)
            descriptor=os.open(str(target.parent),os.O_DIRECTORY)
            try: os.fsync(descriptor)
            finally: os.close(descriptor)
        if sha(target)!=pixel_hash: raise ValueError('pixel artifact modified')
        return self.journal.append('observation',dict(category='experience_example',
            source_episode=episode,source=source,original_path=str(path.resolve()),original_sha256=original_hash,
            pixel_sha256=pixel_hash,pixel_path=str(target.resolve()),crop=crop,
            metadata=metadata or {},identity_status=(metadata or {}).get('identity_status','unknown'),
            label_status='unlabeled'),episode=SCOPE,producer='ExperienceDataset',version=VERSION)

    def annotate(self, example, value, *, status, source, evidence, supersedes=None):
        row=self.journal.get(example)
        if row.data['payload'].get('category')!='experience_example': raise ValueError('example required')
        if status not in ('weak','verified','retracted') or source not in ('external_annotation','independent_measurement','model_prediction','replay_interpretation','agency_belief'):
            raise ValueError('explicit annotation status and source required')
        if source in ('model_prediction','replay_interpretation','agency_belief') and status=='verified':
            raise ValueError('predictions and provisional/reconstructed identities are not ground truth')
        if not evidence: raise ValueError('annotation provenance required')
        sources=[example]
        if supersedes:
            old=self.journal.get(supersedes)
            if old.data['payload'].get('example')!=example: raise ValueError('correction escaped example')
            latest=next(r for r in self.examples() if r['id']==example)['annotation']
            if latest is None or latest['id']!=supersedes: raise ValueError('correction must supersede the latest interpretation')
            sources.append(supersedes)
        elif any(r.data['payload'].get('example')==example for r in self.journal.records('event') if r.data['payload'].get('category')=='dataset_annotation'):
            raise ValueError('annotation correction must explicitly supersede prior evidence')
        return self.journal.append('event',dict(category='dataset_annotation',example=example,value=value,
            status=status,source=source,evidence=evidence,supersedes=supersedes),episode=SCOPE,
            sources=sources,producer='ExperienceDataset',version=VERSION)

    def examples(self):
        rows={r.id:dict(r.data['payload'],id=r.id,annotation=None) for r in self.journal.records('observation')
              if r.data['payload'].get('category')=='experience_example'}
        for record in self.journal.records('event'):
            p=record.data['payload']
            if p.get('category')=='dataset_annotation' and p['example'] in rows:
                rows[p['example']]['annotation']=dict(p,id=record.id)
        return list(rows.values())

    def snapshot(self, *, objective='reconstruction', split=None):
        if objective not in ('reconstruction','classification'): raise ValueError('unsupported training objective')
        rows=self.examples()
        if objective=='classification':
            rows=[r for r in rows if r['annotation'] and r['annotation']['status']=='verified']
        # Connected episodes sharing any original capture or identical pixels must
        # travel together. Temporal neighbors also share their episode partition.
        parent={r['source_episode']:r['source_episode'] for r in rows}
        def find(x):
            while parent[x]!=x: x=parent[x]
            return x
        seen={}
        for r in rows:
            for key in (r['original_sha256'],r['pixel_sha256']):
                if key in seen: parent[find(r['source_episode'])]=find(seen[key])
                seen[key]=r['source_episode']
        groups=sorted(set(find(x) for x in parent))
        if len(groups)<3: raise ValueError('need three independent episode groups for train/validation/test')
        prior_roles={}
        for previous in self.journal.records('event'):
            doc=previous.data['payload']
            if doc.get('category')!='experience_dataset_snapshot': continue
            for example in doc['examples']:
                if example['source_episode'] in parent:
                    group=find(example['source_episode'])
                    prior_roles.setdefault(group,set()).add(example['partition'])
        if any(len(roles)>1 for roles in prior_roles.values()):
            raise ValueError('new duplicate joins previously isolated evaluation partitions')
        if split is None:
            if prior_roles:
                split={g:next(iter(prior_roles[g])) if g in prior_roles else 'train' for g in groups}
            else:
                split={g:('test' if i==len(groups)-1 else 'validation' if i==len(groups)-2 else 'train') for i,g in enumerate(groups)}
        if any(split.get(g) not in roles for g,roles in prior_roles.items()):
            raise ValueError('preserved evaluation groups cannot enter another partition')
        if set(split)!=set(groups) or set(split.values())!={'train','validation','test'}:
            raise ValueError('all groups must be assigned exactly one independent partition')
        unique={}
        for r in rows:
            if sha(r['pixel_path'])!=r['pixel_sha256']: raise ValueError('pixel artifact modified')
            item=dict(r,partition=split[find(r['source_episode'])],independence_group=find(r['source_episode']))
            key=r['pixel_sha256']
            if key in unique:
                a=unique[key]['annotation']; b=r['annotation']
                if objective=='classification' and a['value']!=b['value']: raise ValueError('conflicting verified labels')
            else: unique[key]=item
        selected=list(unique.values())
        if objective=='classification':
            classes={str(r['annotation']['value']) for r in selected if r['partition']=='train'}
            if len(classes)<2 or any(str(r['annotation']['value']) not in classes for r in selected):
                raise ValueError('training vocabulary does not cover independent evaluation labels')
        document=dict(category='experience_dataset_snapshot',objective=objective,examples=selected,
            split=split,independent_groups=len(groups),physical_experiments=len(parent),
            note='offline reuse is correlated evidence, not another physical experiment')
        sources=[r['id'] for r in selected]+[r['annotation']['id'] for r in selected if r['annotation']]
        return self.journal.append('event',document,episode=SCOPE,sources=sources,
            producer='ExperienceDataset',version=VERSION)

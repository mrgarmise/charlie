"""Controlled PyTorch CNN foundry. Imported only by an offline worker.

No generated Python, plugins, camera, controller, or automatic production swap.
"""
from pathlib import Path
import json
import math
import os
import time
import resource
import numpy as np
from PIL import Image
from memory.evidence import digest
from .datasets import sha


def atomic_json(path, data):
    path=Path(path); tmp=path.with_suffix('.tmp')
    with tmp.open('w') as stream:
        stream.write(json.dumps(data,indent=2,allow_nan=False)+'\n'); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)
    descriptor=os.open(str(path.parent),os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def validate_spec(spec):
    allowed={'family','objective','channels','kernel','activation','size','epochs','lr','seed','patience'}
    if set(spec)-allowed or spec.get('family')!='small-cnn' or spec.get('objective') not in ('classification','reconstruction'):
        raise ValueError('supported declarative family and objective required')
    channels=spec.get('channels')
    if not isinstance(channels,list) or not 1<=len(channels)<=3 or any(type(c) is not int or not 2<=c<=32 for c in channels):
        raise ValueError('bounded channel/depth vocabulary required')
    for name,low,high in [('size',16,64),('epochs',1,100),('seed',0,2**31-1),('patience',1,20)]:
        if type(spec.get(name)) is not int or not low<=spec[name]<=high: raise ValueError('invalid '+name)
    if spec['size'] % 2**len(channels): raise ValueError('size must divide encoder stride')
    if spec.get('kernel') not in (3,5) or spec.get('activation') not in ('relu','gelu'): raise ValueError('unsupported component')
    if type(spec.get('lr')) not in (int,float) or not math.isfinite(spec['lr']) or not 1e-5<=spec['lr']<=.05: raise ValueError('invalid lr')


def build(spec, classes=0):
    validate_spec(spec)
    import torch
    from torch import nn
    layers=[]; before=3
    for channel in spec['channels']:
        layers += [nn.Conv2d(before,channel,spec['kernel'],stride=2,padding=spec['kernel']//2),nn.ReLU() if spec['activation']=='relu' else nn.GELU()]
        before=channel
    encoder=nn.Sequential(*layers)
    if spec['objective']=='classification':
        if classes<2: raise ValueError('classification needs independently verified vocabulary')
        model=nn.Sequential(encoder,nn.AdaptiveAvgPool2d(1),nn.Flatten(),nn.Linear(before,classes))
    else:
        layers=[]
        outputs=list(reversed(spec['channels'][:-1]))+[3]
        for i,channel in enumerate(outputs):
            layers.append(nn.ConvTranspose2d(before,channel,4,stride=2,padding=1))
            layers.append(nn.Sigmoid() if i==len(outputs)-1 else nn.ReLU())
            before=channel
        model=nn.Sequential(encoder,nn.Sequential(*layers))
    if sum(x.numel() for x in model.parameters())>250000: raise ValueError('parameter budget exceeded')
    return model


def load_data(snapshot, size, partitions=('train','validation','test')):
    import torch
    rows=snapshot['examples']
    if len(rows)>512: raise ValueError('dataset exceeds this worker memory envelope; prepare a versioned subset')
    values={p:[] for p in ('train','validation','test')}; labels={p:[] for p in values}
    classes=sorted({str(r['annotation']['value']) for r in rows if snapshot['objective']=='classification' and r['partition']=='train'})
    for row in rows:
        if row['partition'] not in partitions: continue
        if sha(row['pixel_path'])!=row['pixel_sha256']: raise ValueError('dataset pixels changed')
        with Image.open(row['pixel_path']) as im:
            x=np.array(im.convert('RGB').resize((size,size),Image.Resampling.BILINEAR),dtype=np.float32)/255.
        p=row['partition']; values[p].append(x.transpose(2,0,1))
        if classes: labels[p].append(classes.index(str(row['annotation']['value'])))
    if any(not values[p] for p in partitions): raise ValueError('empty independent evaluation partition')
    return {p:torch.from_numpy(np.stack(values[p])) for p in partitions}, {p:torch.tensor(labels[p],dtype=torch.long) for p in partitions}, classes


def checkpoint(path, value):
    import torch
    path=Path(path); tmp=path.with_suffix('.tmp'); torch.save(value,tmp)
    with tmp.open('rb') as stream: os.fsync(stream.fileno())
    fingerprint=sha(tmp); target=path.parent/(fingerprint+'.pt')
    if target.exists(): tmp.unlink()
    else: tmp.replace(target)
    atomic_json(path.with_suffix('.pointer.json'),dict(path=str(target.resolve()),sha256=fingerprint))


def weight_path(path):
    path=Path(path); pointer=path.with_suffix('.pointer.json')
    if pointer.exists():
        value=json.loads(pointer.read_text()); target=Path(value['path'])
        if sha(target)!=value['sha256']: raise ValueError('model checkpoint modified')
        return target
    if len(path.stem)!=64 or sha(path)!=path.stem: raise ValueError('unverified tensor artifact')
    return path


def checked_load(path):
    import torch
    return torch.load(weight_path(path),map_location='cpu',weights_only=True)


def train(snapshot, spec, root, *, budget_seconds=60., on_progress=None, interrupt_after=None):
    """Atomic epoch checkpoints; resume the identical frozen experiment only."""
    validate_spec(spec)
    if snapshot['objective']!=spec['objective']: raise ValueError('objective escaped frozen dataset')
    if not math.isfinite(budget_seconds) or not 1<=budget_seconds<=3600: raise ValueError('offline budget 1..3600 seconds')
    import torch
    torch.set_num_threads(1); torch.manual_seed(spec['seed']); torch.use_deterministic_algorithms(True)
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    config=dict(spec=spec,dataset_digest=digest(snapshot)); identifier=digest(config)
    if (root/'config.json').exists() and json.loads((root/'config.json').read_text())!=config: raise ValueError('resume config changed')
    atomic_json(root/'config.json',config)
    x,y,classes=load_data(snapshot,spec['size'],('train','validation')); model=build(spec,len(classes))
    optimizer=torch.optim.Adam(model.parameters(),lr=spec['lr'])
    loss_fn=torch.nn.MSELoss() if spec['objective']=='reconstruction' else torch.nn.CrossEntropyLoss()
    def loss(p): return loss_fn(model(x[p]),x[p] if spec['objective']=='reconstruction' else y[p])
    start=0; history=[]; best=float('inf'); stale=0
    if (root/'last.pointer.json').exists():
        saved=checked_load(root/'last.pt')
        if saved['identifier']!=identifier: raise ValueError('checkpoint experiment mismatch')
        model.load_state_dict(saved['weights']); optimizer.load_state_dict(saved['optimizer']); torch.set_rng_state(saved['rng'])
        start=saved['epoch']; history=saved['history']; best=saved['best']; stale=saved['stale']
    began=time.monotonic()
    for epoch in range(start,spec['epochs']):
        if stale>=spec['patience']: break
        model.train(); optimizer.zero_grad(); train_loss=loss('train'); train_loss.backward(); optimizer.step()
        model.eval()
        with torch.no_grad(): validation=float(loss('validation'))
        if not math.isfinite(validation) or not math.isfinite(float(train_loss.detach())): raise ValueError('nonfinite training result')
        history.append(dict(epoch=epoch+1,train_loss=float(train_loss.detach()),validation_loss=validation))
        if validation<best:
            best=validation; stale=0
            checkpoint(root/'best.pt',dict(weights=model.state_dict(),identifier=identifier,spec=spec,classes=classes))
        else: stale+=1
        checkpoint(root/'last.pt',dict(weights=model.state_dict(),optimizer=optimizer.state_dict(),rng=torch.get_rng_state(),identifier=identifier,epoch=epoch+1,history=history,best=best,stale=stale))
        if on_progress: on_progress()
        if interrupt_after is not None and epoch+1==interrupt_after: raise InterruptedError('controlled checkpoint interruption')
        if time.monotonic()-began>=budget_seconds:
            return dict(status='yielded',identifier=identifier,epochs=epoch+1,history=history)
    result=dict(status='trained',identifier=identifier,spec=spec,classes=classes,validation_loss=best,
        history=history,checkpoint=str(weight_path(root/'best.pt')),checkpoint_sha256=sha(weight_path(root/'best.pt')),
        dataset_digest=digest(snapshot),torch_version=str(torch.__version__),threads=1,
        elapsed=time.monotonic()-began,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        parameters=sum(p.numel() for p in model.parameters()),test_consulted=False)
    atomic_json(root/'training.json',result)
    return result


def evaluate(snapshot, candidate):
    """Final test once after architecture/epoch selection on validation only."""
    import torch
    spec=candidate['spec']; x,y,classes=load_data(snapshot,spec['size'])
    if candidate['dataset_digest']!=digest(snapshot) or sha(candidate['checkpoint'])!=candidate['checkpoint_sha256']: raise ValueError('evaluation inputs changed')
    model=build(spec,len(classes)); model.load_state_dict(checked_load(candidate['checkpoint'])['weights']); model.eval()
    operational=None
    with torch.no_grad():
        predictions=model(x['test'])
        if spec['objective']=='reconstruction':
            error=float(torch.nn.functional.mse_loss(predictions,x['test']))
            baseline=float(torch.nn.functional.mse_loss(x['train'].mean(0).expand_as(x['test']),x['test']))
            metric='reconstruction_mse'; improved=error<baseline; score=error
        else:
            predicted=predictions.argmax(1)
            present=y['test'].unique()
            score=float(torch.stack([(predicted[y['test']==c]==c).float().mean() for c in present]).mean())
            modal=y['train'].bincount(minlength=len(classes)).argmax()
            baseline=float(torch.stack([(y['test'][y['test']==c]==modal).float().mean() for c in present]).mean())
            metric='balanced_accuracy'; improved=score>baseline
            if set(classes)=={'human','threat'} and all(r.get('crop') is not None and
                    r.get('annotation',{}).get('status')=='verified' for r in snapshot['examples']):
                # Admission thresholds are selected on validation, never test.
                vp=model(x['validation']).softmax(1); vc,vi=vp.max(1)
                wrong=vc[vi!=y['validation']]
                threshold=max(.5,float(wrong.max())+1e-6) if len(wrong) else .5
                tp=predictions.softmax(1);confidence,labels=tp.max(1)
                accepted=confidence>=threshold
                count=int(accepted.sum());coverage=count/len(labels)
                accuracy=float((labels[accepted]==y['test'][accepted]).float().mean()) if count else None
                operational=dict(target='ppal-semantics',input='RGB-candidate-crop',classes=classes,
                    threshold=threshold,threshold_partition='validation',test_coverage=coverage,
                    accepted_accuracy=accuracy,verified_targets=True,
                    domains=sorted({r.get('metadata',{}).get('domain','unspecified') for r in snapshot['examples']}),
                    eligible=bool(improved and coverage>=.8 and accuracy==1.),
                    limitations=['finite held-out admission test; no safety guarantee or score utility',
                                 'semantic metadata only; never SELF or physical identity'])
    return dict(metric=metric,candidate=score,baseline=baseline,improved=improved,
        examples=len(x['test']),independence_groups=sorted({r['independence_group'] for r in snapshot['examples'] if r['partition']=='test'}),operational=operational,
        limitations=['one held-out partition; no physical gameplay utility established','no semantic discovery or SELF certification inferred'])


def discover_groups(snapshot,candidate,output):
    """Train-only latent clustering; category names remain opaque hypotheses."""
    import torch
    spec=candidate['spec']; x,_,classes=load_data(snapshot,spec['size'])
    model=build(spec,len(classes)); model.load_state_dict(checked_load(candidate['checkpoint'])['weights']); model.eval()
    arrays={}
    with torch.no_grad():
        for partition in x: arrays[partition]=model[0](x[partition]).flatten(1).numpy()
    # Centers fitted only on train. No new label is added to ExperienceDataset.
    train_vectors=arrays['train']; count=min(4,len(train_vectors))
    centers=train_vectors[np.linspace(0,len(train_vectors)-1,count,dtype=int)].copy()
    for _ in range(12):
        assignments=((train_vectors[:,None]-centers[None])**2).mean(2).argmin(1)
        new=np.stack([train_vectors[assignments==i].mean(0) if (assignments==i).any() else centers[i] for i in range(count)])
        if np.allclose(new,centers): break
        centers=new
    groups={}
    for partition,vectors in arrays.items():
        groups[partition]=((vectors[:,None]-centers[None])**2).mean(2).argmin(1).tolist()
    path=Path(output)/'embeddings.npz'; tmp=path.with_suffix('.tmp')
    with tmp.open('wb') as stream:
        np.savez_compressed(stream,centers=centers,**arrays); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)
    return dict(candidate_id=candidate['identifier'],artifact=str(path.resolve()),sha256=sha(path),groups=groups,
        vocabulary=[f"opaque:{candidate['identifier'][:12]}:{i}" for i in range(count)],
        label_status='unverified interpretation; not training labels',fit_partition='train')

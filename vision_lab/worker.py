"""Local worker dispatch. Heavy ML dependencies never enter discovery/server imports."""
import fcntl
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from .store import Lab,canonical,digest,file_hash,identifier
from .datasets import verify_manifest,export_yolo,held_out


def run(lab,job_id):
    job=lab.get('jobs',job_id);p=job['parameters'];folder=lab.root/'jobs'/job_id
    folder.mkdir(exist_ok=True);job.update(status='running',started_at=time.time(),worker_pid=os.getpid(),worker_start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]);lab.put('jobs',job_id,job)
    def progress(**fields):
        current=lab.get('jobs',job_id);current['progress']=fields;lab.put('jobs',job_id,current)
    if job['kind']=='index':
        from .sources import index_source
        result=index_source(lab,p['source_id'],cancel=lambda:(folder/'cancel').exists(),progress=progress)
    elif job['kind']=='train':
        import torch
        from ultralytics import YOLO
        from .jobs import preflight
        torch.set_num_threads(p['threads']);torch.manual_seed(p['seed'])
        m=verify_manifest(lab,p['dataset_id']);frozen=export_yolo(lab,p['dataset_id'])
        data=folder/'training-data';data.mkdir(exist_ok=True)
        for role in ('train','val'):shutil.copytree(frozen/role,data/role,dirs_exist_ok=True)
        config=json.loads((frozen/'train.yaml').read_text());config['path']=str(data.resolve());(data/'train.yaml').write_text(canonical(config)+'\n')
        if m['digest']!=p['dataset_digest']:raise ValueError('Frozen training dataset changed')
        resume=p.get('resume_job_id')
        if resume:
            old=lab.get('jobs',resume)
            if old['parameters']['dataset_digest']!=m['digest']:raise ValueError('Resume dataset identity mismatch')
            path=lab.root/'jobs'/resume/'run'/'weights'/'last.pt'
            if file_hash(path)!=p['resume_sha256']:raise ValueError('Resume checkpoint changed')
            checkpoint=torch.load(path,map_location='cpu',weights_only=False)
            if checkpoint.get('epoch',-1)+1>=p['epochs']:raise ValueError('Resume target epochs must exceed the completed checkpoint epoch')
            checkpoint['train_args'].update(project=str(folder),name='run',save_dir=str(folder/'run'),epochs=p['epochs'],device=p['device'],data=str(data/'train.yaml'))
            resumed=folder/'resume.pt';torch.save(checkpoint,resumed);model=YOLO(str(resumed))
        else:model=YOLO('yolov8n.yaml') # Architecture only; no implicit pretrained/cloud download.
        h=hashlib.sha256()
        for value in model.model.state_dict().values():h.update(value.detach().cpu().numpy().tobytes())
        initial=h.hexdigest()
        def on_epoch(trainer):
            loss=trainer.loss_items.detach().cpu().tolist()
            progress(epoch=trainer.epoch+1,total_epochs=p['epochs'],loss=loss,scope='training/validation only; never held-out test')
            if (folder/'cancel').exists():trainer.stop=True
        steps=[0]
        def instrument(trainer):
            original=trainer.optimizer_step
            def step():
                original();steps[0]+=1
            trainer.optimizer_step=step
        model.add_callback('on_train_start',instrument)
        model.add_callback('on_fit_epoch_end',on_epoch)
        options=dict(data=str(data/'train.yaml'),epochs=p['epochs'],imgsz=p['imgsz'],batch=p['batch'],device=p['device'],workers=0,
                     project=str(folder),name='run',exist_ok=True,seed=p['seed'],deterministic=True,pretrained=False,amp=False,plots=False,save=True,save_period=1,verbose=True)
        if resume:
            # Ultralytics resume restores optimizer/epoch; the optimizer/epoch is restored into a new isolated output directory.
            model.train(resume=True)
            weights=folder/'run'/'weights'
        else:
            model.train(**options);weights=folder/'run'/'weights'
        if (folder/'cancel').exists():raise InterruptedError('Training cancelled; epoch checkpoint retained')
        best=weights/'best.pt'
        if not best.is_file():raise ValueError('Training produced no best checkpoint')
        model_id=identifier();out=lab.root/'models'/model_id;out.mkdir()
        shutil.copyfile(best,out/'best.pt')
        loaded=YOLO(str(out/'best.pt'));h=hashlib.sha256()
        for value in loaded.model.state_dict().values():h.update(value.detach().cpu().numpy().tobytes())
        record=dict(schema='charlie-vision-model-v1',id=model_id,version=1,architecture='yolov8n',job_id=job_id,dataset_id=m['id'],dataset_digest=m['digest'],classes=m['classes'],parameters=p,
            optimizer_steps=steps[0],checkpoint_sha256=file_hash(out/'best.pt'),initial_weights_sha256=initial,trained_weights_sha256=h.hexdigest(),
            authenticity=m['authenticity'],training_kind='actual optimizer training; fixture-only if declared by dataset',
            environment=preflight(),at=time.time(),baseline_id=p.get('baseline_id'),qualification='unqualified offline candidate',physical_authorization=False)
        (out/'model.json').write_text(canonical(record)+'\n');lab.put('models',model_id,record,immutable=True);result=record
    elif job['kind'] in ('evaluate','suggest'):
        from .adapter import CandidateDetector
        from .sources import hydrate
        from PIL import Image,ImageDraw
        from .evaluation import measure
        detector=CandidateDetector(lab,p['model_id'])
        if job['kind']=='suggest':
            proposals=[]
            known={k:0 for k in lab.get('settings','classes')}
            for f in lab.frames():
                for b in (lab.annotation(f['id'])['boxes'] if lab.annotation(f['id'])['status']=='verified' else []):
                    if b['class_name'] in known:known[b['class_name']]+=1
            ids=p.get('frame_ids',[])
            if len(ids)>500:raise ValueError('Bounded suggestion batch <=500 required')
            for i,fid in enumerate(ids):
                if (folder/'cancel').exists():raise InterruptedError('Suggestion job cancelled')
                f=hydrate(lab,fid)
                if held_out(lab,f['pixel_sha']):raise ValueError('Held-out test image cannot enter assisted annotation')
                if lab.annotation(fid)['status']=='verified':continue
                with Image.open(lab.root/'pixels'/(f['pixel_sha']+'.png')) as im:packet=detector.observe(im,source_frame_id=fid,timestamp=f['timestamp'])
                packet['priority']=sum(1-b['confidence']+1/(1+known.get(b['class_name'],0)) for b in packet['objects']) or 1.
                lab.put('suggestions',fid,packet);proposals.append(packet);progress(frames=i+1,total=len(ids))
            result=dict(proposals=sorted(proposals,key=lambda r:r['priority'],reverse=True),verified_ground_truth_created=False)
        else:
            m=verify_manifest(lab,p['dataset_id']);role=p.get('partition','test')
            if role not in ('val','test'):raise ValueError('Validation or held-out test evaluation required')
            # Training baseline is frozen before any held-out candidate inspection.
            record=detector.record;baseline=record.get('baseline_id')
            if p.get('baseline_id')!=baseline:raise ValueError('Use the baseline frozen at candidate training start')
            if m['digest']!=record['dataset_digest']:raise ValueError('Evaluation dataset must match the frozen training manifest')
            key=digest(dict(model_id=p['model_id'],dataset_digest=m['digest'],partition=role))
            if lab.get('evaluations',key,optional=True):raise ValueError('Frozen evaluation already exists; reuse retained result')
            if role=='test':
                with lab.connect() as c:
                    c.execute('BEGIN IMMEDIATE')
                    for row in m['frames']:
                        if row['role']!='test':continue
                        prior=c.execute('SELECT evaluation FROM consulted_tests WHERE pixel_sha=?',(row['pixel_sha'],)).fetchone()
                        if prior and prior[0]!=key:raise ValueError('Held-out outcome already consulted by another evaluation; collect a fresh sealed test set')
                        c.execute('INSERT OR IGNORE INTO consulted_tests VALUES(?,?)',(row['pixel_sha'],key))
            base=CandidateDetector(lab,baseline) if baseline else None
            if base and base.record['checkpoint_sha256']!=record['parameters']['baseline_sha256']:raise ValueError('Frozen baseline changed')
            rows=[];before=[];evaldir=lab.root/'evaluations'/key;evaldir.mkdir(exist_ok=True)
            for row in m['frames']:
                if row['role']!=role:continue
                if (folder/'cancel').exists():raise InterruptedError('Evaluation cancelled')
                with Image.open(lab.root/'pixels'/(row['pixel_sha']+'.png')) as im:
                    packet=detector.observe(im,source_frame_id=row['frame_id'],timestamp=row['timestamp'])
                    rows.append(dict(frame_id=row['frame_id'],ground_truth=row['annotation']['boxes'],predictions=packet['objects'],latency_ms=packet['processing_latency_ms']))
                    if base:
                        b=base.observe(im,source_frame_id=row['frame_id'],timestamp=row['timestamp']);before.append(dict(frame_id=row['frame_id'],ground_truth=row['annotation']['boxes'],predictions=b['objects'],latency_ms=b['processing_latency_ms']))
                    overlay=im.convert('RGB');draw=ImageDraw.Draw(overlay)
                    for boxes,color in [(row['annotation']['boxes'],'#00cc88'),(packet['objects'],'#ff4444')]:
                        for b in boxes:draw.rectangle((b['x'],b['y'],b['x']+b['w'],b['y']+b['h']),outline=color,width=2)
                    overlay.thumbnail((900,600));overlay.save(evaldir/(row['frame_id']+'.jpg'))
                progress(frames=len(rows),scope=role)
            result=dict(id=key,model_id=p['model_id'],dataset_id=m['id'],dataset_digest=m['digest'],partition=role,confidence_threshold=.25,nms_iou=.7,baseline_id=baseline,
                candidate=measure(rows,m['classes']),baseline=measure(before,m['classes']) if base else None,
                authenticity=m['authenticity'],qualification='descriptive offline measurement; not ALA acceptance',at=time.time(),physical_authorization=False)
            (evaldir/'report.json').write_text(canonical(result)+'\n');lab.put('evaluations',key,result,immutable=True)
    elif job['kind']=='export':
        from ultralytics import YOLO
        from .jobs import preflight
        from .sources import hydrate
        m=lab.get('models',p['model_id']);out=lab.root/'models'/m['id'];pt=out/'best.pt'
        if file_hash(pt)!=m['checkpoint_sha256']:raise ValueError('Checkpoint integrity mismatch')
        model=YOLO(str(pt))
        from .exporting import export_onnx
        exported=out/'best.onnx'
        export_check=export_onnx(model,exported,m['parameters']['imgsz'],m['classes'])
        manifest=verify_manifest(lab,m['dataset_id']);cal=out/'hailo-calibration';cal.mkdir(exist_ok=True)
        # Quantization calibration uses train only; test/validation stay unconsulted.
        for r in [r for r in manifest['frames'] if r['role']=='train'][:128]:
            shutil.copyfile(lab.root/'pixels'/(r['pixel_sha']+'.png'),cal/(r['pixel_sha']+'.png'))
        result=dict(export_check=export_check,model_id=m['id'],checkpoint_sha256=m['checkpoint_sha256'],onnx_sha256=file_hash(exported),onnx_name=exported.name,
            target='hailo8l',input_shape=[1,3,m['parameters']['imgsz'],m['parameters']['imgsz']],input_dtype='float32',preprocessing='RGB letterbox, /255, NCHW; map output xywh back to source pixels',
            postprocessing='YOLOv8 raw boxes/class probabilities; external confidence filtering and NMS; Hailo parser/end nodes/NMS must be validated with Model Zoo v2.x',
            compiler_available=preflight()['hailo_compiler'],hef_created=False,hardware_validated=False,qualification='ONNX prepared; Hailo compatibility not established')
        (out/'deployment.json').write_text(canonical(result)+'\n')
        import zipfile
        archive=out/'deployment.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for f in [pt,exported,out/'model.json',out/'deployment.json',*sorted(cal.glob('*.png'))]:z.write(f,f.relative_to(out))
        lab.put('exports',m['id'],result)
    else:raise ValueError('Unknown worker kind')
    current=lab.get('jobs',job_id);current.update(status='completed',result=result,finished_at=time.time());lab.put('jobs',job_id,current)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--state',type=Path,required=True);ap.add_argument('--job',required=True);args=ap.parse_args();lab=Lab(args.state)
    lock=(lab.root/'worker.lock').open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        run(lab,args.job)
    except BaseException as e:
        job=lab.get('jobs',args.job);job.update(status='cancelled' if isinstance(e,InterruptedError) else 'failed',error=f'{type(e).__name__}: {e}',finished_at=time.time());lab.put('jobs',args.job,job)
        import traceback;traceback.print_exc();raise
    finally:lock.close()

if __name__=='__main__':main()

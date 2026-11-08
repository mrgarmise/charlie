"""Training-only saved-image crop/CTC audit. No camera, controller or final test.

Writes derived diagnostics to a new directory. Source images, annotations,
manifests, checkpoints and consultation ledgers are never rewritten.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image,ImageDraw

from .contract import PREPROCESS,PADDED_PREPROCESS,BLANK,OUTPUT,preprocess,decode,sha
from .corpus import verify,image_path
from .evaluate import metrics
from ..robotron_hud import RobotronHUDReader


def pixel_sha(image):return hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()


def channel_geometry(raw,calibration,channel):
    if channel not in (1,2):raise ValueError('explicit score channel 1 or 2 required')
    reader=RobotronHUDReader(calibration);hud=reader.rectify(raw)
    fraction=reader.P1_X if channel==1 else reader.P2_X
    box=(int(hud.width*fraction[0]),0,int(hud.width*fraction[1]),hud.height)
    tl,tr,br,bl=np.asarray(calibration.corners,dtype=np.float32)*raw.size
    quad=np.float32((tl-(bl-tl)*.1,tr-(br-tr)*.1,tr,tl))
    target=np.float32(((0,0),(hud.width-1,0),(hud.width-1,hud.height-1),(0,hud.height-1)))
    matrix=cv2.getPerspectiveTransform(quad,target)
    roi=np.float32([[[box[0],0],[box[2]-1,0],[box[2]-1,box[3]-1],[box[0],box[3]-1]]])
    projected=cv2.perspectiveTransform(roi,np.linalg.inv(matrix))[0]
    valid=cv2.warpPerspective(np.full((raw.height,raw.width),255,np.uint8),matrix,hud.size,flags=cv2.INTER_NEAREST)
    coverage=float((valid[:,box[0]:box[2]]==255).mean())
    crop=hud.crop(box)
    return hud,crop,dict(hud_size=list(hud.size),crop_box_hud=list(box),crop_size=list(crop.size),
        raw_hud_quad=quad.tolist(),raw_channel_quad=projected.tolist(),camera_pixel_coverage=coverage,
        crop_pixel_sha256=pixel_sha(crop),**illumination(crop))


def illumination(image):
    level=np.asarray(image.convert('RGB')).max(axis=2)
    mask=level>=200  # diagnostic only; does not change ROI or recognition gates
    y,x=np.nonzero(mask)
    return dict(bright_threshold=200,bright_bbox=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)] if len(x) else None,
        bright_fraction=float(mask.mean()),bright_touches_edge=bool(mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any()))


def candidate_rois(hud,channel):
    """Fixed diagnostic hypotheses only; never per-label/per-image ROI fitting."""
    if hud.size!=(640,96) or channel not in (1,2):raise ValueError('fixed HUD/channel required')
    x0,x1=(64,179) if channel==1 else (460,576)
    boxes={'remove-top-bezel-bottom-border':[x0,48,x1,92],
           'widen-inner-margin-and-trim':[x0 if channel==1 else 434,48,205 if channel==1 else x1,92]}
    return {name:(hud.crop(box),dict(crop_box_hud=box,**illumination(hud.crop(box)))) for name,box in boxes.items()}


def ctc_trace(values):
    result=decode(values)
    a=np.asarray(values)[0,:,0,:].T.astype(np.float64)
    probabilities=np.exp(a-a.max(1,keepdims=True));probabilities/=probabilities.sum(1,keepdims=True)
    order=np.sort(probabilities,axis=1);path=probabilities.argmax(1)
    return dict(prediction=result,path=path.tolist(),token_probabilities=order[:,-1].tolist(),
        margins=(order[:,-1]-order[:,-2]).tolist(),first_token=int(path[0]),last_token=int(path[-1]),
        first_blank=bool(path[0]==BLANK),last_blank=bool(path[-1]==BLANK),
        time_axis='canonical [0,class,0,time]; 64 distinct timesteps',blank_token=BLANK)


def _original(row,export):
    proposal=row.get('source_proposal') or {};artifact=proposal.get('artifact') or {}
    expected=row.get('source_image_sha256')
    if not expected or artifact.get('sha256')!=expected:raise ValueError('missing/conflicting original image provenance')
    paths=[]
    if export:
        root=Path(export).resolve();mapping=json.loads((root/'image-locations.json').read_text())
        relative=mapping.get(expected)
        if relative:
            path=(root/relative).resolve()
            if not path.is_relative_to(root):raise ValueError('original image overlay escapes export')
            paths.append(path)
    if artifact.get('path'):paths.append(Path(artifact['path']))
    for path in paths:
        if path.is_file() and sha(path)==expected:return path
    raise ValueError('original full frame unavailable; provide existing portable export')


def _thumbnail(image,size):
    canvas=Image.new('RGB',size,'#171717');copy=image.copy();copy.thumbnail(size)
    canvas.paste(copy,((size[0]-copy.width)//2,(size[1]-copy.height)//2));return canvas


def historical_geometry(examples,output):
    """Trace existing diagnostic originals without inventing a training split."""
    from ..eyes.calibration import Calibration
    examples=Path(examples);items=json.loads(examples.read_text())
    if not 1<=len(items)<=12:raise ValueError('1..12 explicit historical examples required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    sheet=Image.new('RGB',(1500,40+210*len(items)),'#101010');draw=ImageDraw.Draw(sheet)
    draw.text((8,5),'DERIVED HISTORICAL GEOMETRY | original ROI / HUD ROI / channel crop / v1 CNN input / experimental padded input',fill='white')
    records=[]
    for index,item in enumerate(items):
        path=examples.parent/item['image']
        if sha(path)!=item['sha256']:raise ValueError('historical original hash mismatch')
        data=item['calibration'];cal=Calibration(tuple(tuple(p) for p in data['corners']),tuple(data['output_size']))
        with Image.open(path) as image:raw=image.convert('RGB')
        hud,crop,geometry=channel_geometry(raw,cal,item['channel'])
        geometry.update(source_image=item['image'],source_sha256=item['sha256'],source_size=list(raw.size),
            calibration=data,provenance=item.get('provenance'),inputs={},scope='historical diagnostic only; not corpus-005 training or verified score truth')
        geometry['candidate_rois']={}
        for name,(candidate,meta) in candidate_rois(hud,item['channel']).items():
            filename=f'{index:02d}-{name}.png';candidate.save(output/filename)
            geometry['candidate_rois'][name]=dict(meta,derived_png=filename,qualification='diagnostic hypothesis only')
        views=[]
        for profile in (PREPROCESS,PADDED_PREPROCESS):
            x,meta=preprocess(crop,profile=profile)
            view=Image.fromarray(np.rint(x[0].transpose(1,2,0)*255).astype(np.uint8));views.append(view)
            name=f'{index:02d}-{profile}.png';view.save(output/name)
            geometry['inputs'][profile]=dict(metadata=meta,png=name,tensor_sha256=hashlib.sha256(x.tobytes()).hexdigest())
        source=raw.copy();points=[tuple(p) for p in geometry['raw_channel_quad']]
        ImageDraw.Draw(source).line(points+[points[0]],fill='lime',width=3)
        overlay=hud.copy();ImageDraw.Draw(overlay).rectangle(geometry['crop_box_hud'],outline='lime',width=2)
        for x,size,image in zip((0,320,640,880,1190),((310,170),(310,170),(230,170),(300,170),(300,170)),(source,overlay,crop,*views)):
            sheet.paste(_thumbnail(image,size),(x,40+210*index))
        draw.text((8,40+210*index+175),f"{path.name} source SHA {item['sha256'][:16]} | historical diagnostic pixels; no new labels",fill='white')
        records.append(geometry)
    sheet.save(output/'contact-sheet.png')
    report=dict(scope='historical diagnostic originals; not the private 64 training images',
        examples_sha256=sha(examples),images=records,originals_modified=False,final_test_consulted=False)
    (output/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def run(manifest,output,*,checkpoint=None,onnx=None,model_record=None,export=None,calibration=None,limit=12):
    if not 1<=limit<=24:raise ValueError('contact sheet limit must be 1..24')
    if checkpoint and onnx:raise ValueError('choose one exact model artifact')
    corpus=verify(manifest)
    rows=sorted((r for r in corpus['rows'] if r['role']=='train'),key=lambda r:r['sha256'])
    if not rows:raise ValueError('no training rows; final/validation diagnostics are not admitted')
    infer=None;profile=PREPROCESS;identity=None
    if checkpoint:
        import torch
        from .model import load
        model,state=load(checkpoint);torch.set_num_threads(2)
        if state['dataset_digest']!=corpus['digest']:raise ValueError('checkpoint/corpus digest mismatch')
        profile=state.get('preprocessing',PREPROCESS);identity=dict(checkpoint_sha256=sha(checkpoint))
        def infer(x):
            with torch.no_grad():return model(torch.from_numpy(x)).numpy()
    if onnx:
        from .backends import CPU
        if not model_record:raise ValueError('ONNX diagnostics require matching training.json')
        record=json.loads(Path(model_record).read_text())
        if record['onnx_sha256']!=sha(onnx) or record['dataset_digest']!=corpus['digest']:raise ValueError('ONNX/model/corpus provenance mismatch')
        profile=record.get('preprocessing',PREPROCESS);backend=CPU(onnx,record['onnx_sha256'],preprocessing=profile)
        infer=lambda x:backend.infer(x)[0]
        identity=dict(onnx_sha256=sha(onnx),model_record_sha256=sha(model_record))
        import onnx as onnx_module
        graph=onnx_module.load(onnx)
        identity['actual_opset_imports']={o.domain:o.version for o in graph.opset_import}
        from .compile import validate_graph
        try:
            validate_graph(onnx);identity['fixed_compiler_graph_contract']='PASS; actual DFC/native execution still required'
        except ValueError as exc:identity['fixed_compiler_graph_contract']='FAIL: '+str(exc)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    pictures=output/'derived';pictures.mkdir()
    # Contact selection uses training labels only, deterministically. Every
    # image receives the same fixed ROI and preprocessing variants.
    representatives=[]
    for label in ('00','1200','800','300','100'):
        match=next((r for r in rows if r['label']==label),None)
        if match and match not in representatives:representatives.append(match)
    representatives=(representatives+[r for r in rows if r not in representatives])[:limit]
    selected={r['sha256'] for r in representatives};panels={};audit=[];evaluated=[]
    for index,row in enumerate(rows):
        with Image.open(image_path(manifest,row)) as image:crop=image.convert('RGB')
        record=dict(image_sha256=row['sha256'],source_image_sha256=row.get('source_image_sha256'),
            proposal_id=row.get('proposal_id'),annotation_ids=row.get('annotation_ids'),label=row['label'],
            session=row['session'],role='train',crop_size=list(crop.size),crop_pixel_sha256=pixel_sha(crop),
            geometry_status='original/calibration not supplied',illumination=illumination(crop),inputs={})
        text=row.get('label') or ''
        record['ctc_minimum_target_timesteps']=len(text)+sum(a==b for a,b in zip(text,text[1:]))
        source=None;hud=None
        if calibration:
            try:
                source_path=_original(row,export)
                from memory.evidence import digest
                expected=digest(dict(corners=calibration.corners,output_size=calibration.output_size))
                context=(row.get('source_proposal') or {}).get('context',{})
                if context.get('calibration_geometry_digest')!=expected:raise ValueError('source calibration mismatch')
                with Image.open(source_path) as image:source=image.convert('RGB')
                hud,recrop,geometry=channel_geometry(source,calibration,row.get('channel'))
                record.update(geometry=geometry,source_size=list(source.size),source_sha256=sha(source_path),
                    geometry_status='verified' if recrop.size==crop.size and pixel_sha(recrop)==pixel_sha(crop) else 'frozen crop differs from calibrated source')
                record['candidate_rois']={}
                for name,(candidate,meta) in candidate_rois(hud,row['channel']).items():
                    path=pictures/f'{index:04d}-{name}.png';candidate.save(path)
                    record['candidate_rois'][name]=dict(meta,derived_png=str(path.relative_to(output)),
                        qualification='fixed diagnostic hypothesis; not selected or qualified by labels')
                if record['geometry_status']!='verified':record['geometry_error']='preserve old corpus; investigate calibration/crop version before retraining'
            except (OSError,ValueError,KeyError) as exc:
                record['geometry_error']=str(exc);source=None;hud=None
        views={}
        for variant in (PREPROCESS,PADDED_PREPROCESS):
            x,meta=preprocess(crop,profile=variant)
            view=Image.fromarray(np.rint(x[0].transpose(1,2,0)*255).astype(np.uint8))
            path=pictures/f'{index:04d}-{variant}.png';view.save(path)
            record['inputs'][variant]=dict(metadata=meta,tensor_sha256=hashlib.sha256(x.tobytes()).hexdigest(),
                derived_png=str(path.relative_to(output)),**illumination(view))
            views[variant]=view
        if infer:
            begin=time.perf_counter();x,_=preprocess(crop,profile=profile);trace=ctc_trace(infer(x))
            record['ctc']=trace
            evaluated.append(dict(label=row['label'],prediction=trace['prediction'],wall_seconds=time.perf_counter()-begin))
        if row['sha256'] in selected:
            raw_view=source.copy() if source else Image.new('RGB',(320,180),'#222222')
            hud_view=hud.copy() if hud else Image.new('RGB',(640,96),'#222222')
            if source:
                points=[tuple(p) for p in record['geometry']['raw_channel_quad']]
                ImageDraw.Draw(raw_view).line(points+[points[0]],fill='lime',width=3)
                ImageDraw.Draw(hud_view).rectangle(record['geometry']['crop_box_hud'],outline='lime',width=2)
            panels[row['sha256']]=(raw_view,hud_view,crop,views[PREPROCESS],views[PADDED_PREPROCESS])
        audit.append(record)
    sheet=Image.new('RGB',(1500,40+len(representatives)*210),'#101010');draw=ImageDraw.Draw(sheet)
    draw.text((8,5),'DERIVED TRAINING DIAGNOSTICS | source ROI / HUD ROI / frozen crop / exact v1 input / fixed padded experimental input',fill='white')
    for n,row in enumerate(representatives):
        y=40+n*210
        for x,size,image in zip((0,320,640,880,1190),((310,170),(310,170),(230,170),(300,170),(300,170)),panels[row['sha256']]):
            sheet.paste(_thumbnail(image,size),(x,y))
        draw.text((8,y+175),f"TRAIN label={row['label']!r} hash={row['sha256'][:16]} | absent source panels mean unavailable, never reconstructed",fill='white')
    sheet.save(output/'contact-sheet.png')
    summary=dict(schema='charlie-score-crop-ctc-audit-v1',manifest_digest=corpus['digest'],manifest_sha256=sha(manifest),
        qualification=corpus['authenticity'],scope='training-set diagnostics only; no generalization claim',model=identity,preprocessing=profile,
        training_images=len(rows),label_counts=dict(Counter(r['label'] for r in rows)),
        geometry_status=dict(Counter(r['geometry_status'] for r in audit)),
        metrics=metrics(evaluated) if evaluated else None,
        nonblank_edges=sum(not r['ctc']['first_blank'] or not r['ctc']['last_blank'] for r in audit) if infer else None,
        output_shape=list(OUTPUT),horizontal_stride=4,horizontal_receptive_field=15,
        final_test_consulted=False,originals_modified=False,hardware_accessed=False)
    (output/'audit.json').write_text(json.dumps(dict(summary=summary,images=audit),indent=2)+'\n')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--manifest',type=Path);source.add_argument('--historical-examples',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--checkpoint',type=Path);p.add_argument('--onnx',type=Path);p.add_argument('--model-record',type=Path)
    p.add_argument('--review-export',type=Path);p.add_argument('--calibration',type=Path);p.add_argument('--limit',type=int,default=12)
    a=p.parse_args()
    if a.historical_examples:
        print(json.dumps(historical_geometry(a.historical_examples,a.output),indent=2));return
    from ..eyes.calibration import Calibration
    result=run(a.manifest,a.output,checkpoint=a.checkpoint,onnx=a.onnx,model_record=a.model_record,
        export=a.review_export,calibration=Calibration.load(a.calibration) if a.calibration else None,limit=a.limit)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

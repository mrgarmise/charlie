"""Fixed-IoU detection metrics, confidence-ranked AP50 and geometric confusion."""
import time
from .store import digest


def iou(a,b):
    left=max(a['x'],b['x']);top=max(a['y'],b['y']);right=min(a['x']+a['w'],b['x']+b['w']);bottom=min(a['y']+a['h'],b['y']+b['h'])
    intersection=max(0,right-left)*max(0,bottom-top)
    return intersection/(a['w']*a['h']+b['w']*b['h']-intersection) if intersection else 0.


def measure(samples,classes,threshold=.5):
    stats={c:dict(tp=0,fp=0,fn=0,ground_truth=0) for c in classes};ranked={c:[] for c in classes};confusion={};errors=[]
    for sample in samples:
        gt=sample['ground_truth'];pred=sorted(sample['predictions'],key=lambda b:b['confidence'],reverse=True);used=set();wrong=[]
        for b in gt:stats[b['class_name']]['ground_truth']+=1
        for p in pred:
            choices=[(iou(p,g),i) for i,g in enumerate(gt) if i not in used and g['class_name']==p['class_name']]
            overlap,index=max(choices,default=(0.,-1));hit=overlap>=threshold
            if hit:used.add(index);stats[p['class_name']]['tp']+=1
            else:stats[p['class_name']]['fp']+=1;wrong.append(p)
            ranked[p['class_name']].append((p['confidence'],hit))
        missed=[g for i,g in enumerate(gt) if i not in used]
        for g in missed:stats[g['class_name']]['fn']+=1
        geometry=set()
        for p in pred:
            choices=[(iou(p,g),i) for i,g in enumerate(gt) if i not in geometry]
            overlap,index=max(choices,default=(0.,-1));key=(gt[index]['class_name'],p['class_name']) if overlap>=threshold else ('background',p['class_name'])
            if overlap>=threshold:geometry.add(index)
            confusion[' → '.join(key)]=confusion.get(' → '.join(key),0)+1
        for i,g in enumerate(gt):
            if i not in geometry:
                key=g['class_name']+' → background';confusion[key]=confusion.get(key,0)+1
        if wrong or missed:errors.append(dict(frame_id=sample['frame_id'],false_positives=wrong,missed=missed,ground_truth=gt,predictions=pred))
    for name,s in stats.items():
        s['precision']=s['tp']/(s['tp']+s['fp']) if s['tp']+s['fp'] else None
        s['recall']=s['tp']/s['ground_truth'] if s['ground_truth'] else None
        values=sorted(ranked[name],reverse=True);tp=0;curve=[(0.,0.)]
        for i,(_,hit) in enumerate(values,1):
            tp+=int(hit);curve.append((tp/max(1,s['ground_truth']),tp/i))
        # VOC all-points interpolated area. No ground truth means undefined AP.
        area=0.;previous=0.
        for i,(recall,precision) in enumerate(curve):
            if recall>previous:area+=(recall-previous)*max(p for _,p in curve[i:]);previous=recall
        s['ap50']=area if s['ground_truth'] else None
    total={k:sum(s[k] for s in stats.values()) for k in ('tp','fp','fn')}
    total.update(precision=total['tp']/(total['tp']+total['fp']) if total['tp']+total['fp'] else None,recall=total['tp']/(total['tp']+total['fn']) if total['tp']+total['fn'] else None)
    aps=[s['ap50'] for s in stats.values() if s['ap50'] is not None]
    latencies=[s['latency_ms'] for s in samples]
    return dict(schema='charlie-vision-metrics-v1',iou_threshold=threshold,samples=len(samples),micro=total,per_class=stats,map50=sum(aps)/len(aps) if aps else None,confusion=confusion,error_examples=errors[:50],mean_latency_ms=sum(latencies)/len(latencies) if latencies else None,latency_scope='local end-to-end prediction calls, includes preprocessing/postprocessing; not Pi/Hailo throughput')

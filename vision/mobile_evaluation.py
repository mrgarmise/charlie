"""Independent labeled replay scoring. Metrics never confer physical authority."""
from collections import Counter
from .mobile_tracking import iou


def evaluate_frames(predictions, labels, *, label_provenance):
    """Labels are supplied independently, never inferred from predictions.

    Each row: frame_id, objects[{label, box, identity}] for labels,
    tracks[{label, box, id, observed, ambiguous}] for predictions.
    """
    if not label_provenance or len(predictions)!=len(labels):raise ValueError('aligned independent labels required')
    totals=Counter();by_class={};previous={}
    for pred,truth in zip(predictions,labels):
        if pred['frame_id']!=truth['frame_id']:raise ValueError('frame alignment mismatch')
        tracks=[t for t in pred['tracks'] if t['observed'] and not t['ambiguous']]
        used=set()
        for obj in truth['objects']:
            c=by_class.setdefault(obj['label'],Counter())
            candidates=[(iou(obj['box'],t['box']),i,t) for i,t in enumerate(tracks)
                        if i not in used and t['label']==obj['label']]
            score,index,t=max(candidates,key=lambda x:x[0],default=(0,None,None))
            if score<.5:
                c['misses']+=1;continue
            used.add(index);c['true_positives']+=1
            identity=obj.get('identity')
            if identity:
                if identity in previous and previous[identity]!=t['id']:totals['track_switches']+=1
                previous[identity]=t['id']
        for i,t in enumerate(tracks):
            if i not in used:by_class.setdefault(t['label'],Counter())['false_positives']+=1
    for category,c in by_class.items():
        tp,fp,fn=c['true_positives'],c['false_positives'],c['misses']
        c['precision']=tp/(tp+fp) if tp+fp else None
        c['recall']=tp/(tp+fn) if tp+fn else None
    return dict(frames=len(labels),by_class={k:dict(v) for k,v in by_class.items()},
                track_switches=totals['track_switches'],label_provenance=label_provenance,
                physical_authorization=False)


def overlay(frame, packet):
    """Inspection helper, BGR output, conspicuous unarmed/unqualified legend."""
    import cv2
    result=frame.image.copy()
    for obj in packet['objects']:
        x,y,r,b=map(round,obj['box'])
        cv2.rectangle(result,(x,y),(r,b),(0,200,255),1)
        cv2.putText(result,f"{obj['label']} {obj['confidence']:.2f}",(x,max(12,y)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,200,255),1)
    cv2.putText(result,'UNARMED / UNQUALIFIED',(4,16),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,255),1)
    return result

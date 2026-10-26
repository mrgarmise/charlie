"""Normalize existing inference packets without another camera or model pass."""
import math


def object_observation(observation, tracking=None):
    frame=observation['frame'];w,h=frame['geometry']
    if type(w) is not int or type(h) is not int or w<=0 or h<=0:raise ValueError('invalid object geometry')
    objects=[];target=(tracking or {}).get('target')
    for index,row in enumerate(observation['objects'][:128]):
        box=row['box'];label=row['label'];confidence=row['confidence']
        if (not isinstance(label,str) or not 1<=len(label)<=128 or type(confidence) not in (int,float)
                or not math.isfinite(confidence) or not 0<=confidence<=1 or len(box)!=4
                or not all(type(v) in (int,float) and math.isfinite(v) for v in box)
                or not 0<=box[0]<box[2]<=w or not 0<=box[1]<box[3]<=h):continue
        identifier=str(row.get('id') or label)
        if target is not None:
            from vision.mobile_tracking import iou
            if iou(box,target['box'])>=.5:identifier=target['id']
        objects.append(dict(id=identifier,label=label,confidence=float(confidence),box=list(box),
                            prominence=(box[2]-box[0])*(box[3]-box[1])/(w*h)))
    return dict(schema='charlie.object-observation.v1',source=frame['source'],frame_id=frame['id'],
                at=frame['received_at'],clock_domain=frame['clock_domain'],geometry=[w,h],objects=objects,
                attention_target=dict(source=frame['source'],id=target['id']) if target else None,
                camera_identity=frame.get('camera_identity'), stream_generation=frame.get('stream_generation'),
                exposure_age_known=frame.get('source_age_known',False),qualification=observation['qualification'],
                identity='class hypothesis only; no individual recognition')

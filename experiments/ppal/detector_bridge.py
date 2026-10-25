"""Synchronous observation-only detector boundary. No camera, controller or policy API."""
from dataclasses import dataclass
import hashlib
import math
import time
from pathlib import Path
from .eyes.detectors import Detection

LABELS = ['player', 'grunt', 'hulk', 'tank', 'human', 'mine', 'other_enemy', 'projectile', 'unknown']
ENEMIES = {'grunt', 'hulk', 'tank', 'mine', 'other_enemy', 'brain', 'enforcer'}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class Frame:
    id: str
    image: object
    exposure_at: float
    timestamp_basis: str
    provenance: dict

    def validate(self):
        if (not isinstance(self.id,str) or not self.id or not finite(self.exposure_at)
                or not isinstance(self.timestamp_basis,str) or not self.timestamp_basis.strip()
                or not isinstance(self.provenance,dict)):
            raise ValueError('actual finite exposure timestamp and basis required')
        if min(self.image.size) <= 0:
            raise ValueError('invalid frame geometry')


@dataclass(frozen=True)
class Letterbox:
    width: int
    height: int
    size: int

    def __post_init__(self):
        if any(type(v) is not int or v<=0 for v in (self.width,self.height,self.size)):
            raise ValueError('positive integer letterbox geometry required')

    @property
    def scale(self): return min(self.size/self.width, self.size/self.height)

    @property
    def padding(self):
        return ((self.size-round(self.width*self.scale))//2,
                (self.size-round(self.height*self.scale))//2)

    def restore(self, box):
        px, py = self.padding
        values = [(box[i]-(px if i%2 == 0 else py))/self.scale for i in range(4)]
        return tuple(float(max(0., min(float(self.width if i%2 == 0 else self.height), v))) for i,v in enumerate(values))


def semantic(label):
    # Appearance is never BODY identity. Unknown labels remain visible candidates.
    return 'human' if label == 'human' else 'threat' if label in ENEMIES or label == 'threat' else 'unknown'


class TemplateBackend:
    name = 'cpu-template'
    def __init__(self, detector): self.detector = detector
    def infer(self, frame):
        return [dict(label=d.kind, box=d.box, confidence=None, class_scores=None)
                for d in self.detector.detect(frame.image)]


class LabBackend:
    name = 'cpu-yolo-lab'
    def __init__(self, candidate): self.candidate = candidate
    def infer(self, frame):
        packet = self.candidate.observe(frame.image, source_frame_id=frame.id, timestamp=frame.exposure_at)
        return [dict(label=b['class_name'], box=(b['x'],b['y'],b['x']+b['w'],b['y']+b['h']),
                     confidence=b['confidence'],class_scores=None) for b in packet['objects']]


class HailoBackend:
    """Actual HailoRT HEF inference, lazy and explicitly unqualified.

    Requires YOLO Hailo NMS (per-class y/x/y/x/score) output. Restores letterbox
    coordinates on the host; raw-head HEFs are rejected. No CPU device emulation.
    """
    name = 'hailort-hef'
    def __init__(self, path, *, sha256, classes, size=640, timeout_seconds=1., persistent=False, lock=None):
        path = Path(path)
        if path.suffix.lower() != '.hef' or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise ValueError('HEF integrity mismatch')
        if (not classes or any(not isinstance(c,str) or not c for c in classes)
                or len(set(classes))!=len(classes) or not 0 < timeout_seconds <= 5):
            raise ValueError('classes and bounded timeout required')
        import subprocess
        report = subprocess.run(['hailortcli','parse-hef',str(path)], capture_output=True, text=True, timeout=5, check=True).stdout
        import re
        if not re.search(r'Architecture[^\n]*\bHAILO[-_ ]?8L\b',report,re.I):
            raise ValueError('HEF must target hailo8l')
        from hailo_platform import HEF, Device
        hef = HEF(str(path))
        if not Device.scan(): raise RuntimeError('no Hailo device')
        inputs = hef.get_input_vstream_infos()
        outputs = hef.get_output_vstream_infos()
        if len(inputs) != 1 or tuple(inputs[0].shape) != (size,size,3):
            raise ValueError('HEF input shape mismatch')
        if len(outputs)!=1 or 'NMS' not in str(outputs[0].format.order):
            raise ValueError('only one Hailo NMS output supported')
        self.path,self.classes,self.size,self.timeout = str(path),list(classes),size,timeout_seconds
        self.input_name=inputs[0].name
        self.sha256,self.persistent,self.lock=sha256,persistent,lock
        self._session=None

    def preprocessing(self, frame):
        transform=Letterbox(*frame.image.size,self.size)
        return dict(input_shape=[1,self.size,self.size,3],layout='NHWC',dtype='float32',
            host_value_range=[0,255],normalization='must be embedded in verified HEF',
            color='RGB',letterbox_scale=transform.scale,letterbox_padding=transform.padding,
            padding_rgb=[114,114,114],resize='Pillow bicubic')

    def infer(self, frame):
        import numpy as np
        from hailo_platform import (HEF,VDevice,ConfigureParams,HailoStreamInterface,
            InputVStreamParams,OutputVStreamParams,FormatType,InferVStreams)
        transform=Letterbox(*frame.image.size,self.size)
        from PIL import Image
        canvas=Image.new('RGB',(self.size,self.size),(114,114,114))
        canvas.paste(frame.image.convert('RGB').resize((round(frame.image.width*transform.scale),round(frame.image.height*transform.scale))),transform.padding)
        from hardware.hailo_session import HailoSession
        if self.persistent:
            if self._session is None:
                self._session=HailoSession(self.path,sha256=self.sha256,input_shape=(self.size,self.size,3),timeout=self.timeout,lock=self.lock)
            results=self._session.infer(np.asarray(canvas,dtype=np.float32)[None])
        else:
            with HailoSession(self.path,sha256=self.sha256,input_shape=(self.size,self.size,3),timeout=self.timeout,lock=self.lock) as session:
                results=session.infer(np.asarray(canvas,dtype=np.float32)[None])
        classes=next(iter(results.values()))[0]
        if len(classes)!=len(self.classes): raise ValueError('HEF NMS class count mismatch')
        rows=[]
        for name,boxes in zip(self.classes,classes):
            for y,x,b,r,score in boxes:
                if score<.25: continue
                box=transform.restore((x*self.size,y*self.size,r*self.size,b*self.size))
                if box[2]<=box[0] or box[3]<=box[1]: continue
                rows.append(dict(label=name,box=box,confidence=float(score),class_scores=None))
        return rows

    def close(self):
        if self._session is not None:self._session.close()



class DetectorBridge:
    observation_only = True
    def __init__(self, factory, *, model, fallback=None, mode='strict', max_age=.25, clock=time.monotonic):
        if mode not in ('strict','fallback') or not 0 < max_age <= 1:
            raise ValueError('explicit mode and freshness bound required')
        self.factory,self.model,self.fallback,self.mode = factory,model,fallback,mode
        self.max_age,self.clock = max_age,clock
        self.backend = None
        self.last_time = None
        self.last_id = None
        self.events = []

    def observe(self, frame):
        frame.validate()
        age = self.clock()-frame.exposure_at
        if not 0 <= age <= self.max_age or (self.last_time is not None and frame.exposure_at <= self.last_time) or frame.id == self.last_id:
            raise ValueError('stale, repeated or reordered source observation')
        self.last_time,self.last_id = frame.exposure_at,frame.id
        start = self.clock()
        failure = None
        backend = self.backend
        try:
            if backend is None: backend = self.backend = self.factory()
            rows = backend.infer(frame)
            objects = self._normalize(rows,frame)
        except Exception as exc:
            failure = dict(error=type(exc).__name__,message=str(exc),frame_id=frame.id)
            self.events = (self.events+[failure])[-64:]
            if self.mode != 'fallback' or self.fallback is None: raise
            backend = self.fallback
            objects = self._normalize(backend.infer(frame),frame)
        end = self.clock()
        if not 0 <= end-frame.exposure_at <= self.max_age:
            raise ValueError('late inference discarded')
        return dict(schema='charlie-detector-observation-v1',source_frame_id=frame.id,
            exposure_at=frame.exposure_at,timestamp_basis=frame.timestamp_basis,
            geometry=list(frame.image.size),coordinate_transform='corrected playfield pixels -> x/width*100,y/height*100',
            preprocessing=backend.preprocessing(frame) if hasattr(backend,'preprocessing') else dict(input='corrected RGB',transform='backend owned; no additional metadata available'),postprocessing=dict(conf=.25,nms='compiled HEF; inspect export contract',semantic_min_score=.5) if backend.name=='hailort-hef' else None,
            provenance=frame.provenance,model=self.model if failure is None else None,
            backend=backend.name,objects=objects,inference_seconds=end-start,freshness_age=end-frame.exposure_at,
            fallback_event=failure,observation_only=True,physical_authorization=False,self_authorization=False)

    @staticmethod
    def _normalize(rows, frame):
        if len(rows)>512: raise ValueError('too many detections')
        output=[]; w,h=frame.image.size
        for row in rows:
            box=tuple(row['box']); score=row.get('confidence'); scores=row.get('class_scores')
            if len(box)!=4 or not all(finite(v) for v in box) or not 0<=box[0]<box[2]<=w or not 0<=box[1]<box[3]<=h:
                raise ValueError('invalid original-pixel bbox')
            if score is not None and (not finite(score) or not 0<=score<=1): raise ValueError('invalid confidence')
            if scores is not None and (not isinstance(scores,dict) or not all(finite(v) for v in scores.values())):
                raise ValueError('invalid score vector')
            label=row.get('label') or 'unknown'
            if not isinstance(label,str): raise ValueError('class label must be a string')
            output.append(dict(label=label,legacy_kind=semantic(label) if score is None or score>=.5 else 'unknown',bbox_pixels=box,
                bbox_board=[box[i]/(w if i%2==0 else h)*100 for i in range(4)],
                confidence=score,class_scores=scores,score_interpretation='uncalibrated; not causal SELF evidence'))
        return output


def tracking_pairs(packet):
    """Feed the existing SpriteTracker/VisualAgency boundary; never authorize SELF."""
    pairs=[]
    for row in packet['objects']:
        x,y,r,b=row['bbox_board']; box=tuple(round(v) for v in row['bbox_pixels'])
        metadata=dict(row)
        if metadata.get('class_scores') is None: metadata.pop('class_scores',None)
        pairs.append((Detection(row['legacy_kind'],((x+r)/2,(y+b)/2),box,max(1,(box[2]-box[0])*(box[3]-box[1]))),metadata))
    return pairs


def rich_world(tracker, at, *, horizon=.1, hypotheses=None):
    if not finite(at) or not 0<=horizon<=1 or tracker._seconds_mode is not True or (tracker._last_time is not None and at<tracker._last_time):
        raise ValueError('elapsed-time tracker and bounded horizon required')
    return dict(schema='charlie-rich-world-v1',timestamp=at,observation_only=True,tracks=[dict(
        id=t.track_id,class_hypothesis=(hypotheses or {}).get(t.track_id,{}).get('label',t.kinds[-1] if t.kinds else 'unknown'),
        observed_position=t.center,observed_at=t.last_time,location_status='occluded' if t.missed else 'observed',
        velocity=t.velocity,velocity_units='board units/second',history=list(t.timed_path),
        prediction=tracker.predict(t,at+horizon),horizon_seconds=horizon,
        ambiguity=t.identity_uncertain,missed=t.missed,association_cost=t.association_cost,
        class_confidence=(hypotheses or {}).get(t.track_id,{}).get('confidence')) for t in sorted(tracker.active.values(),key=lambda t:t.track_id)])

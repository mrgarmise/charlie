"""Read-only candidate perception. No tracker, agency, action or deployment API."""
import time
import os
from .store import file_hash


class CandidateDetector:
    observation_only=True
    def __init__(self,lab,model_id):
        os.environ.setdefault('YOLO_OFFLINE','true');os.environ.setdefault('YOLO_CONFIG_DIR',str(lab.root/'dependency-config'))
        from ultralytics import YOLO
        self.record=lab.get('models',model_id);self.lab=lab
        path=lab.root/'models'/model_id/'best.pt'
        if file_hash(path)!=self.record['checkpoint_sha256']:raise ValueError('Model checkpoint integrity mismatch')
        self.model=YOLO(str(path));self.model_id=model_id;self.last_packet=None

    def observe(self,image,*,source_frame_id,timestamp):
        import math
        if type(timestamp) not in (int,float) or not math.isfinite(timestamp):raise ValueError('Finite source timestamp required')
        start=time.perf_counter();result=self.model.predict(image,imgsz=self.record['parameters']['imgsz'],device='cpu',conf=.25,iou=.7,verbose=False)[0]
        boxes=[]
        if result.boxes is not None:
            for xy,conf,cls in zip(result.boxes.xyxy.cpu().tolist(),result.boxes.conf.cpu().tolist(),result.boxes.cls.cpu().tolist()):
                x,y,right,bottom=xy;name=self.record['classes'][int(cls)]
                boxes.append(dict(class_name=name,x=x,y=y,w=right-x,h=bottom-y,confidence=float(conf),uncertain=float(conf)<.5,accepted=False,origin='model',model_id=self.model_id))
        packet=dict(schema='charlie-perception-candidate-v1',objects=boxes,frame_timestamp=timestamp,source_frame_id=source_frame_id,model_id=self.model_id,model_version=self.record['version'],processing_latency_ms=(time.perf_counter()-start)*1000,provenance=dict(dataset_digest=self.record['dataset_digest'],checkpoint_sha256=self.record['checkpoint_sha256'],authenticity=self.record['authenticity'],qualification='unqualified offline candidate'),uncertainty='Detected player is not verified SELF; no gameplay identity or action authority',observation_only=True,physical_authorization=False)
        self.last_packet=packet;return packet

    def detect(self,frame):
        """Existing VisionPipeline protocol; observation_only prevents WorldState creation."""
        from experiments.ppal.eyes.detectors import Detection
        packet=self.observe(frame,source_frame_id='caller-supplied-offline-frame',timestamp=time.time())
        def kind(c):return 'player' if c=='player' else 'human' if c in ('human','mom','dad','kid') else 'threat'
        return [Detection(kind(b['class_name']),(b['x']+b['w']/2,b['y']+b['h']/2),(round(b['x']),round(b['y']),round(b['x']+b['w']),round(b['y']+b['h'])),round(b['w']*b['h'])) for b in packet['objects']]

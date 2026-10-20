"""Raw-camera extended HUD -> independent neural proposals -> existing tracker API."""
import json
import hashlib
import time
import numpy as np
from ..robotron_hud import RobotronHUDReader,RobotronHUDObservation
from .contract import SCHEMA,PREPROCESS,PREPROCESS_PROFILES,DECODER,preprocess,decode,crop_quality,finite


class NeuralHUDReader:
    observation_only=True
    def __init__(self,calibration,backend,model,*,max_age=.75,clock=time.monotonic):
        if not 0<max_age<=2:raise ValueError('bounded freshness required')
        self.calibration=calibration;self.backend=backend;self.model=model
        self.clock=clock;self.max_age=max_age;self.source=None;self.last_at=None;self.last_packet=None
        self.preprocessing=(model.get('training_record') or {}).get('preprocessing',PREPROCESS)
        if self.preprocessing not in PREPROCESS_PROFILES:raise ValueError('unknown model preprocessing')
        if model.get('hef') and model['hef'].get('preprocessing',PREPROCESS)!=self.preprocessing:raise ValueError('HEF/model preprocessing mismatch')

    def bind_source(self,*,t,source):
        self.source=dict(source or {},exposure_at=t)

    def read(self,raw):
        source=self.source;self.source=None
        started=self.clock();cpu=time.process_time()
        packet=dict(schema=SCHEMA,model=self.model,mode=self.backend.mode,channels=[],
            source=source,raw_size=list(raw.size),calibration=dict(corners=self.calibration.corners,
            output_size=self.calibration.output_size),preprocessing_version=self.preprocessing,decoder_version=DECODER,
            source_pixel_sha256=hashlib.sha256(raw.convert('RGB').tobytes()).hexdigest(),
            observation_only=True,physical_authorization=False,official_game_score=False)
        reason=None
        at=(source or {}).get('exposure_at')
        if not source or not source.get('observation_id') or not isinstance(source.get('timestamp_basis'),str) or not source['timestamp_basis'].strip() or not finite(at):reason='missing source identity/exposure basis'
        elif not 0<=started-at<=self.max_age or (self.last_at is not None and at<=self.last_at):reason='stale/future/nonmonotonic source'
        if reason is None:self.last_at=at
        corners=np.asarray(self.calibration.corners);tl,tr,br,bl=corners
        extended=np.array([tl-(bl-tl)*.1,tr-(br-tr)*.1,tr,tl])
        if (extended<0).any() or (extended>1).any():reason='extended HUD outside captured image'
        packet['raw_hud_quad']=(extended*np.asarray(raw.size)).tolist()
        packet['calibration_identifier']=hashlib.sha256(json.dumps(packet['calibration'],sort_keys=True).encode()).hexdigest()
        begin=time.perf_counter()
        hud=None if reason else RobotronHUDReader(self.calibration).rectify(raw)
        packet['rectify_seconds']=time.perf_counter()-begin
        for player,fraction in ((1,RobotronHUDReader.P1_X),(2,RobotronHUDReader.P2_X)):
            box=[int(640*fraction[0]),0,int(640*fraction[1]),96]
            row=dict(channel=player,crop_box_hud=box,score=None,digits=None,confidence=0.,reason=reason,
                     diagnostic_logits=None,timing=None)
            if hud is not None:
                crop=hud.crop(box);row['crop_pixel_sha256']=hashlib.sha256(crop.tobytes()).hexdigest()
                row['reason']=crop_quality(crop)
                if row['reason'] is None:
                    try:
                        begin=time.perf_counter();x,meta=preprocess(crop,profile=self.preprocessing);pre=time.perf_counter()-begin
                        logits,timing=self.backend.infer(x)
                        begin=time.perf_counter();result=decode(logits);decode_seconds=time.perf_counter()-begin
                        row.update(result);row['preprocessing']=meta
                        row['timing']=dict(timing,preprocess_seconds=pre,decode_seconds=decode_seconds)
                    except Exception as exc:
                        row.update(reason=f'{type(exc).__name__}: {exc}',health_event=dict(error=type(exc).__name__,message=str(exc)))
            packet['channels'].append(row)
        completed=self.clock()
        if finite(at) and not 0<=completed-at<=self.max_age:
            for row in packet['channels']:row.update(score=None,digits=None,confidence=0.,reason='late inference discarded')
        packet.update(inference_completed_at=completed,wall_seconds=completed-started,
            cpu_seconds=time.process_time()-cpu,image_age_seconds=completed-at if finite(at) else None,
            queue_wait_seconds=(source or {}).get('queue_wait_seconds'),device_time_measured=False)
        self.last_packet=packet
        a,b=packet['channels']
        return RobotronHUDObservation(a['score'],b['score'],a['confidence'],b['confidence'])

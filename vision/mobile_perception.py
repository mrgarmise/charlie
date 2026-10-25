"""Mobile observations share the existing camera transport; no actuator imports."""
from dataclasses import dataclass, fields
import hashlib
import math
import time
import threading
from uuid import uuid4


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


@dataclass(frozen=True)
class MobileFrame:
    id: str
    image: object  # BGR ndarray, existing ELEGOO camera convention
    received_at: float
    source: str = 'elegoo-v4'
    sequence: int = 0
    pan_deg: float | None = None
    yaw_deg: float | None = None
    authentic: bool = False
    captured_at_source: float | None = None
    clock_domain: str = 'pi-monotonic'
    sync_uncertainty_seconds: float | None = None
    compression: str = 'MJPEG'
    artifact: dict | None = None

    def validate(self):
        import numpy as np
        if (not self.id or not self.source or not finite(self.received_at) or self.received_at < 0
                or self.clock_domain != 'pi-monotonic' or type(self.sequence) is not int or self.sequence < 0
                or not isinstance(self.image, np.ndarray) or self.image.dtype != np.uint8
                or self.image.ndim != 3 or self.image.shape[2] != 3 or min(self.image.shape[:2]) <= 0):
            raise ValueError('invalid mobile frame')
        for x in (self.pan_deg, self.yaw_deg):
            if x is not None and not finite(x): raise ValueError('invalid pose')

    def metadata(self):
        d = {f.name:getattr(self,f.name) for f in fields(self) if f.name!='image'}
        d.update(sha256=hashlib.sha256(self.image.tobytes()).hexdigest(),
                 geometry=list(self.image.shape[:2][::-1]), pixel_format='BGR uint8',
                 calibration='unknown', timestamp_basis='local decode receipt, NOT exposure',
                 source_age_known=False)
        return d


class MobileFrameSource:
    """Wrap an existing ElegooCamera; consume no primary-camera lease.

    Source exposure time is unknown. Receipt age cannot certify capture age.
    """
    def __init__(self, camera=None, *, max_age=.5, clock=time.monotonic, reconnect_attempts=0, backoff=.1, cancel=None, on_fault=None):
        if not finite(max_age) or not 0 < max_age <= 5: raise ValueError('invalid max age')
        if camera is None:
            from hardware.elegoo_camera import ElegooCamera
            camera = ElegooCamera(timeout=2)
        self.camera, self.max_age, self.clock = camera, max_age, clock
        if type(reconnect_attempts) is not int or not 0<=reconnect_attempts<=10 or not finite(backoff) or not 0<=backoff<=2:
            raise ValueError('bounded camera recovery required')
        self.reconnect_attempts,self.backoff=reconnect_attempts,backoff
        self.cancel=cancel or threading.Event()
        self.on_fault=on_fault
        self.session = uuid4().hex
        self.last_sequence = -1
        self.stats = dict(frames=0, dropped=0, faults=0, reconnects=0)

    def read(self):
        for attempt in range(self.reconnect_attempts+1):
            if self.cancel.is_set():raise InterruptedError('mobile source cancelled')
            started=self.clock()
            try:return self._read_once()
            except (OSError,EOFError,TimeoutError,ValueError) as exc:
                if self.on_fault:self.on_fault(exc,dict(self.stats,attempt=attempt,read_seconds=self.clock()-started))
                if attempt==self.reconnect_attempts:raise
                if self.cancel.wait(min(2,self.backoff*2**attempt)):raise InterruptedError('mobile recovery cancelled')

    def _read_once(self):
        try:
            image, m = self.camera.read(timeout=2, with_metadata=True)
            if self.cancel.is_set():raise InterruptedError('mobile source cancelled')
            age = self.clock() - m['received_at']
            if not finite(age) or not 0 <= age <= self.max_age or m['sequence'] <= self.last_sequence:
                raise ValueError('stale or reordered mobile frame')
            self.stats['dropped'] += max(0, m['sequence']-self.last_sequence-1) if self.last_sequence >= 0 else 0
            self.last_sequence = m['sequence']
            frame = MobileFrame(f'{self.session}:{m["sequence"]}', image, m['received_at'],
                                sequence=m['sequence'], authentic=True)
            frame.validate()
            self.stats['frames'] += 1
            return frame
        except Exception:
            self.stats['faults'] += 1
            self.camera.close()  # Next caller's read reconnects; no unbounded retry loop.
            self.stats['reconnects'] += 1
            raise

    def close(self):
        self.cancel.set()
        self.camera.close()


class MobilePerception:
    """Bounded synchronous worker boundary, kept off the attention/safety loop.

    Latest-frame transport supplies backpressure. Both models see ONE frame.
    Resource guard checks before each model; hardware scheduler may yield.
    """
    def __init__(self, detector, depth, *, resources, revision, cadence=.2, max_age=.5, clock=time.monotonic):
        if not revision or not finite(cadence) or cadence <= 0 or not finite(max_age) or max_age <= 0:
            raise ValueError('revision and positive budgets required')
        self.detector, self.depth, self.resources, self.revision = detector, depth, resources, revision
        self.cadence, self.max_age, self.clock = cadence, max_age, clock
        self.last_at = None
        self.last_id = None
        self.effective_cadence = cadence
        self.stats = dict(processed=0, cadence_skipped=0)

    def observe(self, frame):
        frame.validate()
        start = self.clock()
        if not 0 <= start-frame.received_at <= self.max_age or frame.id == self.last_id:
            raise ValueError('stale or duplicate frame')
        if self.last_at is not None and frame.received_at <= self.last_at: raise ValueError('reordered frame')
        if self.last_at is not None and frame.received_at-self.last_at < self.effective_cadence:
            self.stats['cadence_skipped'] += 1
            return None
        self.last_at, self.last_id = frame.received_at, frame.id
        outputs = {}
        timings = {}
        for name, model in (('objects', self.detector), ('depth', self.depth)):
            self.resources.check(force=True)
            if name=='depth' and model.metadata.get('backend') not in ('unavailable','offline-fixture'):
                # Until native multi-network scheduling is qualified, release
                # the persistent detector before the depth network takes lease.
                if hasattr(self.detector,'close'):self.detector.close()
            at = self.clock()
            outputs[name] = model.infer(frame)
            timings[name] = self.clock()-at
        if isinstance(outputs['depth'],dict):
            outputs['depth']=dict(outputs['depth'],frame_id=frame.id,received_at=frame.received_at,
                                  source_pose=dict(pan_deg=frame.pan_deg,yaw_deg=frame.yaw_deg))
        end = self.clock()
        if not 0 <= end-frame.received_at <= self.max_age: raise ValueError('late inference discarded')
        self.effective_cadence = max(self.cadence, min(self.max_age, (end-start)*1.2))
        self.stats['processed'] += 1
        rows = outputs['objects']
        if not isinstance(rows, list) or len(rows) > 128: raise ValueError('bounded objects required')
        w,h = frame.image.shape[:2][::-1]
        for r in rows:
            box,score = r['box'],r['confidence']
            if (len(box)!=4 or not all(finite(v) for v in box) or not 0<=box[0]<box[2]<=w
                    or not 0<=box[1]<box[3]<=h or not finite(score) or not 0<=score<=1
                    or r['label'] not in self.detector.metadata.get('classes',('cat','dog','person','human_face','unknown'))):
                raise ValueError('invalid object contract')
        return dict(schema='charlie.mobile.perception.v1', frame=frame.metadata(), objects=rows,
                    depth=outputs['depth'], model=[self.detector.metadata, self.depth.metadata],
                    inference_seconds=timings, receipt_to_decision_seconds=end-frame.received_at,
                    completed_at=end, software_revision=self.revision, motion_authorized=False,
                    qualification='unqualified', sensors={},
                    resources=dict(getattr(self.resources,'sample',{})),
                    scheduling=dict(self.stats, effective_cadence_seconds=self.effective_cadence))


class FrameArtifactStore:
    """Bounded content-addressed authentic pixels for later independent replay."""
    def __init__(self, directory, *, max_bytes=64*1024*1024):
        from pathlib import Path
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.max_bytes=max_bytes
        self.used=sum(p.stat().st_size for p in self.directory.glob('*.png'))

    def retain(self, frame):
        import cv2
        from dataclasses import replace
        ok,encoded=cv2.imencode('.png',frame.image)
        if not ok:raise ValueError('frame encoding failed')
        raw=encoded.tobytes();digest=hashlib.sha256(raw).hexdigest()
        path=self.directory/(digest+'.png')
        if not path.exists():
            if self.used+len(raw)>self.max_bytes:raise OSError('mobile pixel budget exhausted; acquisition paused')
            with path.open('xb') as out:out.write(raw)
            self.used+=len(raw)
        return replace(frame,artifact=dict(path=str(path.resolve()),sha256=digest,encoding='PNG',bytes=len(raw)))


class RecordingFrameSource:
    def __init__(self,source,store):self.source,self.store=source,store
    @property
    def on_fault(self):return self.source.on_fault
    @on_fault.setter
    def on_fault(self,callback):self.source.on_fault=callback
    def read(self):
        frame=self.source.read()
        return self.store.retain(frame) if frame.authentic else frame
    def close(self):self.source.close()

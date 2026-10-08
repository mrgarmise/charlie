"""Retain completed player steps even if report finalization is interrupted."""
import json
import os


class CaptureEvidence:
    """Bounded evidence writer under the existing camera owner, no decisions.

    Lossless raw frames and the existing append-only journal share one ordered
    writer. Recording congestion stops exploration rather than dropping frames.
    """
    def __init__(self, output, episode, provenance, capacity=4):
        from concurrent.futures import ThreadPoolExecutor
        self.output=output;self.episode=episode;self.provenance=provenance
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='camera-evidence')
        self.pending=[];self.capacity=capacity;self.preparing=True;self.count=0;self.overflow=None
        try:self.pool.submit(self._open).result(timeout=10)
        except BaseException:
            self.pool.shutdown(wait=False,cancel_futures=True)
            raise

    def _open(self):
        from memory.evidence import EvidenceJournal
        self.journal=EvidenceJournal(self.output/'session-evidence.sqlite3')
        self.latest=None
        rows=self.journal.records('observation')
        captures=[r for r in rows if r.data['payload'].get('category')=='camera_capture']
        if captures:self.latest=captures[-1]
        # Include orphaned, already durable pixels after a process interruption;
        # do not overwrite them or manufacture a missing journal observation.
        self.count=max((int(p.stem.split('-')[-1]) for p in (self.output/'observations').glob('camera-*.png')),default=0)

    def _collect(self):
        unfinished=[]
        for f in self.pending:
            if f.done():f.result()
            else:unfinished.append(f)
        self.pending=unfinished

    def capture(self, image, metadata):
        import copy
        self._collect();self.count+=1
        item=(image.copy(),copy.deepcopy(metadata),self.count)
        if len(self.pending)>=self.capacity:
            if self.preparing:self.pending.pop(0).result(timeout=10)
            else:
                self.overflow=item
                from .progress_supervision import ObservationFailure
                raise ObservationFailure('evidence writer saturated; controls must yield; current frame retained for finalization')
        self.pending.append(self.pool.submit(self._capture,*item))

    def _capture(self,image,metadata,number):
        import hashlib
        directory=self.output/'observations';directory.mkdir(exist_ok=True)
        name=f'observations/camera-{number:06d}.png';path=self.output/name
        with path.open('xb') as stream:
            image.save(stream,format='PNG',compress_level=1);stream.flush();os.fsync(stream.fileno())
        self.latest=self.journal.append('observation',dict(category='camera_capture',
            artifact=dict(path=name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()),
            sample=number,metadata=metadata,interpretation='camera pixels; no semantic truth or independent episode'),
            episode=self.episode,at=metadata['timestamp'],producer='ObservedCamera',version='1',provenance=self.provenance)
        return self.latest.id

    def event(self,kind,payload,*,at):
        import copy
        payload=copy.deepcopy(payload)
        def write():
            if kind.endswith('_prediction'):
                import time
                now=time.monotonic()
                return self.journal.predict(dict(category=kind,**payload),episode=self.episode,at=now,
                    deadline=now+5.,sources=(self.latest.id,),producer='PPAL',version='1',mode='live_prospective').id
            if kind.endswith('_outcome') and payload.get('prediction_id'):
                prediction=self.journal.get(payload['prediction_id'])
                current=self.latest
                timely=current is not None and prediction.data['at']<current.data['at']<=prediction.data['payload']['deadline']
                self.journal.resolve(prediction.id,sources=(current.id,) if timely else (),
                    result=(payload.get('resolved_result','supported' if payload.get('scene_changed') else 'unresolved')
                        if timely and payload.get('eligible',True) else 'unresolved'),
                    reason='observed visual association only; independent causation unqualified' if timely else 'late, missing or ambiguous observation')
            return self.journal.append('observation',dict(category=kind,**payload),
                episode=self.episode,at=at,sources=(self.latest.id,) if self.latest else (),
                producer='PPAL',version='1',provenance=self.provenance).id
        return self.pool.submit(write).result(timeout=10)

    def flush(self):
        for f in self.pending:f.result(timeout=10)
        self.pending=[]
        if self.overflow:
            self.pool.submit(self._capture,*self.overflow).result(timeout=10);self.overflow=None

    def ready(self):
        self.flush();self.preparing=False

    def close(self):
        try:self.flush()
        finally:
            self.pool.submit(self.journal.close).result(timeout=10)
            self.pool.shutdown(wait=True)


class DurableRows(list):
    def __init__(self, path):
        super().__init__()
        self.path = path

    def append(self, row):
        with self.path.open('a') as stream:
            stream.write(json.dumps(row)+'\n')
            stream.flush();os.fsync(stream.fileno())
        super().append(row)

"""Bounded recording through the existing journal; no camera or policy ownership."""
import json
import os
import time
import threading
import queue
from collections import deque
from concurrent.futures import Future
from pathlib import Path


class CaptureEvidence:
    """Single FIFO writer for lossless pixels, predictions and normal run logs.

    Enqueue only snapshots/canonicalizes in memory. Encoding, compression, file
    writes and journal commits are owned by the writer. RAM acknowledgement is
    not durability. A finite emergency slot preserves the item causing a pause.
    """
    def __init__(self, output, episode, provenance, capacity=16, *, record_capacity=512,
                 byte_capacity=128*1024*1024, flush_timeout=10.):
        if capacity<1 or record_capacity<capacity or byte_capacity<1 or not 0<flush_timeout<=120:
            raise ValueError('invalid bounded recording budget')
        self.output=Path(output);self.episode=episode;self.provenance=provenance
        self.capacity=capacity;self.record_capacity=record_capacity;self.byte_capacity=byte_capacity
        self.flush_timeout=flush_timeout;self.preparing=True;self.count=0;self.overflow=None
        self.pending=deque();self._queue=queue.Queue(maxsize=record_capacity)
        self._lock=threading.Lock();self._abort=threading.Event();self._closed=False
        self._fatal=None;self._frames=0;self._bytes=0;self._records=0;self.latest_observation=None
        self._uncommitted={};self._largest_frame=0
        self._started=time.perf_counter();self._stats=dict(accepted=0,written=0,captures_written=0,
            max_occupancy=0,max_bytes=0,backpressure=0,enqueue_ns=0,encode_ns=0,write_ns=0)
        self.state_path=self.output/'recording-state.json'
        previous=json.loads(self.state_path.read_text()) if self.state_path.exists() else None
        self._recovery_gap=bool(previous and previous.get('status')!='complete')
        self._gap_reason='previous interrupted flush; unknown RAM tail' if self._recovery_gap else None
        self.recovery=dict(previous_status=(previous or {}).get('status'),
            interrupted_flush=self._recovery_gap,uncommitted_tail='unknown after process death' if self._recovery_gap else None)
        self._inspection=bool((self.output/'capture-manifest.json').exists() or (previous and previous.get('status')=='complete'))
        opened=Future();self.thread=threading.Thread(target=self._run,args=(opened,),name='camera-evidence',daemon=True)
        self.thread.start()
        try:
            opened.result(timeout=flush_timeout)
            if not self._inspection:self._save_state('open')
        except BaseException:
            self._abort.set();self._queue.put_nowait(None)
            raise

    def _open(self):
        from memory.evidence import EvidenceJournal
        self.journal=EvidenceJournal(self.output/'session-evidence.sqlite3',read_only=self._inspection)
        captures=self.journal.category_records('observation','camera_capture')
        if captures:
            last=captures[-1]
            self.latest_observation=self.journal.get(last.data['sources'][0]) if last.data['sources'] else last
        self.count=max((int(p.name.split('-')[-1].split('.')[0]) for p in (self.output/'observations').glob('camera-*.png*')),default=0)
        if self._inspection:
            from memory.episode_identity import verify_recording_completion
            verify_recording_completion(self.output)

    def _run(self,opened):
        try:
            self._open();opened.set_result(True)
            while True:
                item=self._queue.get()
                if item is None:break
                future,fn,args,size,is_frame=item
                error=None
                try:
                    if self._abort.is_set():raise RuntimeError('writer interrupted; queued tail not committed')
                    fn(*args)
                    with self._lock:
                        self._stats['written']+=1;self._uncommitted.pop(future,None)
                except BaseException as exc:
                    self._fatal=self._fatal or exc;self._abort.set();error=exc
                finally:
                    with self._lock:
                        self._records-=1;self._frames-=int(is_frame);self._bytes-=size
                    self._queue.task_done()
                # Capacity and completion must agree before waking the producer.
                if error:future.set_exception(error)
                else:future.set_result(True)
                item=None;args=None # release completed pixel snapshots before waiting
        except BaseException as exc:
            self._fatal=exc
            if not opened.done():opened.set_exception(exc)
        finally:
            if hasattr(self,'journal'):self.journal.close()

    def telemetry(self):
        with self._lock:
            stats=dict(self._stats,occupancy=self._records,frame_occupancy=self._frames,
                buffered_bytes=self._bytes,record_capacity=self.record_capacity,frame_capacity=self.capacity,
                byte_capacity=self.byte_capacity,emergency_slots=1,schema='charlie-buffered-recording-v1',
                worker_encoding_allowance_bytes=2*self._largest_frame,
                emergency_byte_allowance=self._largest_frame)
        seconds=max(1e-9,time.perf_counter()-self._started)
        return dict(stats,throughput_records_per_second=stats['written']/seconds,
            writer_error=str(self._fatal) if self._fatal else None,paused=bool(self.overflow),
            recovery=self.recovery,writer_alive=self.thread.is_alive())

    def _save_state(self,status,**extra):
        from learning.foundry import atomic_json
        atomic_json(self.state_path,dict(schema='charlie-buffered-recording-v1',status=status,
            episode=self.episode,telemetry=self.telemetry(),**extra))

    def _collect(self):
        while self.pending and self.pending[0].done():self.pending.popleft().result()
        if self._fatal:raise RuntimeError(f'evidence writer failed: {self._fatal}')

    def _submit(self,fn,args,*,size=0,is_frame=False):
        item=(Future(),fn,args,size,is_frame)
        if size>self.byte_capacity:
            self._recovery_gap=True;self._gap_reason='required record exceeded configured memory budget'
            raise ValueError('required record exceeds memory budget; recording incomplete')
        if self._closed or self._inspection:raise RuntimeError('completed recorder is immutable')
        if self.overflow:raise RuntimeError('recording paused; drain before new observations')
        with self._lock:
            full=(self._records>=self.record_capacity or self._bytes+size>self.byte_capacity or
                  (is_frame and self._frames>=self.capacity))
        if full and self.preparing:
            self.pending[0].result(timeout=self.flush_timeout);self._collect()
            return self._submit(fn,args,size=size,is_frame=is_frame)
        if full or self._fatal:
            self.overflow=item
            with self._lock:self._stats['backpressure']+=1
            from .progress_supervision import ObservationFailure
            raise ObservationFailure('evidence writer saturated or failed; controls must pause; emergency item retained')
        try:self._collect()
        except BaseException:
            self.overflow=item
            raise
        with self._lock:
            identifier=args[1].id if fn in (self._capture,self._event) else f'log:{self._stats["accepted"]+1}'
            self._uncommitted[item[0]]=identifier
            self._records+=1;self._frames+=int(is_frame);self._bytes+=size
            self._stats['accepted']+=1
            self._stats['max_occupancy']=max(self._stats['max_occupancy'],self._records)
            self._stats['max_bytes']=max(self._stats['max_bytes'],self._bytes)
        self.pending.append(item[0]);self._queue.put_nowait(item)
        return item[0]

    def capture(self,image,metadata):
        from memory.evidence import EvidenceJournal
        began=time.perf_counter_ns();self.count+=1
        size=image.width*image.height*len(image.getbands())*(4 if image.mode in ('I','F') else 2 if image.mode.startswith('I;16') else 1)
        if size>self.byte_capacity:
            self._recovery_gap=True;self._gap_reason='source frame exceeded configured memory budget'
            raise ValueError('source frame exceeds configured memory budget; recording incomplete')
        self._largest_frame=max(self._largest_frame,size)
        prepared=EvidenceJournal.prepare_observation(dict(category='camera_observation',sample=self.count,
            metadata=metadata,source_path=f'observations/camera-{self.count:06d}.png',
            size=list(image.size),mode=image.mode,interpretation='observed pixels queued; artifact integrity verified by writer'),
            episode=self.episode,at=metadata['timestamp'],producer='ObservedCamera',version='2',provenance=self.provenance)
        self._submit(self._capture,(image.copy(),prepared,self.count),
            size=size+len(prepared.document.encode()),is_frame=True)
        self.latest_observation=prepared
        with self._lock:self._stats['enqueue_ns']+=time.perf_counter_ns()-began
        return prepared.id

    def _capture(self,image,prepared,number):
        import hashlib
        self.journal.commit_prepared(prepared)
        directory=self.output/'observations';directory.mkdir(exist_ok=True)
        name=f'observations/camera-{number:06d}.png';path=self.output/name
        # Encode only in this worker. Never publish a torn PNG as a complete one.
        temporary=path.with_suffix('.png.pending');began=time.perf_counter_ns()
        import io
        buffer=io.BytesIO();image.save(buffer,format='PNG',compress_level=1)
        encoded=buffer.getvalue();encode_ns=time.perf_counter_ns()-began;began=time.perf_counter_ns()
        with temporary.open('xb') as stream:
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path);temporary.unlink()
        fd=os.open(directory,os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.journal.append('observation',dict(category='camera_capture',
            artifact=dict(path=name,sha256=hashlib.sha256(encoded).hexdigest()),sample=number,
            observation_id=prepared.id,metadata=prepared.data['payload']['metadata'],
            interpretation='camera pixels; no semantic truth or independent episode'),
            episode=self.episode,at=prepared.data['at'],sources=[prepared.id],producer='ObservedCamera',version='2',provenance=self.provenance)
        with self._lock:
            self._stats['captures_written']+=1;self._stats['encode_ns']+=encode_ns
            self._stats['write_ns']+=time.perf_counter_ns()-began

    def event(self,kind,payload,*,at):
        from memory.evidence import EvidenceJournal
        if self.latest_observation is None:raise ValueError('event needs a source observation')
        began=time.perf_counter_ns();source=self.latest_observation.id
        if kind.endswith('_prediction'):
            now=time.monotonic()
            prepared=EvidenceJournal.prepare_buffered_prediction(dict(category=kind,observation_id=source,**payload),
                episode=self.episode,at=now,deadline=now+5.,sources=[source],producer='PPAL',version='2')
        else:
            prepared=EvidenceJournal.prepare_observation(dict(category=kind,observation_id=source,**payload),
                episode=self.episode,at=at,sources=[source],producer='PPAL',version='2',provenance=self.provenance)
        self._submit(self._event,(kind,prepared),size=len(prepared.document.encode()))
        with self._lock:self._stats['enqueue_ns']+=time.perf_counter_ns()-began
        return prepared.id

    def _event(self,kind,prepared):
        payload=prepared.data['payload']
        if kind.endswith('_outcome') and payload.get('prediction_id'):
            prediction=self.journal.get(payload['prediction_id']);current=self.journal.get(prepared.data['sources'][0])
            timely=prediction.data['at']<current.data['at']<=prediction.data['payload']['deadline']
            self.journal.resolve(prediction.id,sources=[current.id] if timely else [],
                result=payload.get('resolved_result','supported' if payload.get('scene_changed') else 'unresolved')
                    if timely and payload.get('eligible',True) else 'unresolved',
                reason='observed association only; causation unqualified' if timely else 'late or missing observation')
        self.journal.commit_prepared(prepared)

    def append_line(self,path,row):
        # Canonical snapshot is immutable even if the caller reuses its objects.
        from memory.evidence import canonical
        text=canonical(row)+'\n';path=Path(path)
        if path.parent!=self.output or path.suffix!='.jsonl':raise ValueError('recording log outside session')
        self._submit(self._line,(path,text),size=len(text.encode()))

    @staticmethod
    def _line(path,text):
        with path.open('a') as stream:
            stream.write(text);stream.flush();os.fsync(stream.fileno())

    def flush(self):
        deadline=time.perf_counter()+self.flush_timeout
        for future in list(self.pending):future.result(timeout=max(0.,deadline-time.perf_counter()))
        self._collect()
        if self.overflow:
            _,fn,args,size,is_frame=self.overflow;self.overflow=None
            self._submit(fn,args,size=size,is_frame=is_frame)
            self.pending[-1].result(timeout=max(0.,deadline-time.perf_counter()));self._collect()

    def ready(self):
        self.flush();self.preparing=False

    def close(self):
        if self._closed:return
        error=None
        try:self.flush()
        except BaseException as exc:error=exc;self._abort.set()
        self._closed=True
        # No later enqueue is permitted. Writer closes its own SQLite connection.
        try:self._queue.put(None,timeout=self.flush_timeout)
        except queue.Full:error=error or TimeoutError('writer termination queue blocked')
        self.thread.join(timeout=self.flush_timeout)
        if self.thread.is_alive():error=error or TimeoutError('writer did not finish')
        if not self._inspection:
            if error or self._recovery_gap:
                self._save_state('incomplete',error=str(error) if error else self._gap_reason,
                    uncommitted_records=len(self._uncommitted),uncommitted_ids=list(self._uncommitted.values()),
                    emergency_item_uncommitted=bool(self.overflow))
            else:
                from memory.episode_identity import recording_completion
                completion=recording_completion(self.output)
                self._save_state('complete',completion=completion)
        if error:raise error


class DurableRows(list):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.recorder = None

    def append(self, row):
        if self.recorder is not None:
            self.recorder.append_line(self.path,row)
            super().append(row)
            return
        with self.path.open('a') as stream:
            stream.write(json.dumps(row)+'\n')
            stream.flush();os.fsync(stream.fileno())
        super().append(row)

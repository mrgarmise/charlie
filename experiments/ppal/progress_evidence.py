"""Bounded recording through the existing journal; no camera or policy ownership."""
import json
import os
import time
import threading
import queue
import math
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
                 byte_capacity=128*1024*1024, flush_timeout=10., visual_hz=None, rolling_seconds=0., rolling_frames=60, rolling_bytes=32*1024*1024):
        if capacity<1 or record_capacity<capacity or byte_capacity<1 or not 0<flush_timeout<=120:
            raise ValueError('invalid bounded recording budget')
        if visual_hz is not None and (not math.isfinite(visual_hz) or not 0<visual_hz<=30):
            raise ValueError('visual retention Hz must be positive and <=30')
        if not math.isfinite(rolling_seconds) or not 0<=rolling_seconds<=10 or not 1<=rolling_frames<=300 or rolling_bytes<1:
            raise ValueError('invalid rolling frame budget')
        self.rolling_seconds=rolling_seconds;self.rolling_frames=rolling_frames;self.rolling_byte_capacity=rolling_bytes
        self._rolling=deque();self._rolling_bytes=0;self._rolling_peak=0;self._rolling_evictions=0
        self._incidents=[];self._incident_count=0;self._incident_frame_count=0
        self.visual_hz=visual_hz;self._sample_origin=None;self._sample_slot=-1
        self._contract_recorded=False;self._last_source_at=None
        self._retention_counts=dict(selected=0,not_selected=0,unavailable=0)
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
            recovery=self.recovery,writer_alive=self.thread.is_alive(),
            visual_contract='sampled-visual-v1' if self.visual_hz is not None else 'strict-full-frame-v1',
            visual_hz=self.visual_hz,retention_counts=dict(self._retention_counts),
            rolling=dict(seconds=self.rolling_seconds,capacity_frames=self.rolling_frames,capacity_bytes=self.rolling_byte_capacity,
                frames=len(self._rolling),bytes=self._rolling_bytes,peak_bytes=self._rolling_peak,evictions=self._rolling_evictions),
            incidents=dict(requests=self._incident_count,active=len(self._incidents),extra_frames=self._incident_frame_count),
            total_accounted_snapshot_bytes=stats['buffered_bytes']+self._rolling_bytes)

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
            identifier=args[1].id if fn in (self._capture,self._event,self._descriptor) else f'log:{self._stats["accepted"]+1}'
            self._uncommitted[item[0]]=identifier
            self._records+=1;self._frames+=int(is_frame);self._bytes+=size
            self._stats['accepted']+=1
            self._stats['max_occupancy']=max(self._stats['max_occupancy'],self._records)
            self._stats['max_bytes']=max(self._stats['max_bytes'],self._bytes)
        self.pending.append(item[0]);self._queue.put_nowait(item)
        return item[0]

    def capture(self,image,metadata):
        from memory.evidence import EvidenceJournal
        began=time.perf_counter_ns();at=metadata['timestamp']
        if not math.isfinite(at) or (self._last_source_at is not None and at<self._last_source_at):
            raise ValueError('source timestamps must be finite and monotonic')
        self._last_source_at=at;self.count+=1
        if self.visual_hz is not None and not self._contract_recorded:
            contract=EvidenceJournal.prepare_observation(dict(category='camera_retention_contract',
                schema='sampled-visual-v1',hz=self.visual_hz,schedule='first source + fixed exposure-clock slots; no catch-up duplication',
                pixel_claim='only hashed camera_capture artifacts independently inspectable',
                critical_trace='every source descriptor and retention disposition required'),
                episode=self.episode,at=at,producer='CaptureEvidence',version='3',provenance=self.provenance)
            self._submit(self._event,('camera_retention_contract',contract),size=len(contract.document.encode()))
            self._contract_recorded=True
        selected=True
        if self.visual_hz is not None:
            if self._sample_origin is None:self._sample_origin=at
            slot=math.floor((at-self._sample_origin)*self.visual_hz+1e-7)
            selected=slot>self._sample_slot
            if selected:self._sample_slot=slot
        size=image.width*image.height*len(image.getbands())*(4 if image.mode in ('I','F') else 2 if image.mode.startswith('I;16') else 1)
        status='selected' if selected else 'not_selected'
        reason='scheduled original' if selected else 'not selected by predictable visual policy'
        if selected and self.visual_hz is not None and not self.preparing:
            with self._lock:
                optional_full=(self._frames>=max(1,self.capacity-1) or self._bytes+size+4096>self.byte_capacity*0.8
                               or self._records>=max(1,self.record_capacity-8))
            if optional_full:
                selected=False;status='unavailable';reason='optional payload budget; critical trace reserved'
        if selected and size>self.byte_capacity:
            self._recovery_gap=True;self._gap_reason='source frame exceeded configured memory budget'
            raise ValueError('source frame exceeds configured memory budget; recording incomplete')
        self._largest_frame=max(self._largest_frame,size if selected else 0)
        payload=dict(category='camera_observation',sample=self.count,metadata=metadata,
            source_path=f'observations/camera-{self.count:06d}.png' if selected else None,
            size=list(image.size),mode=image.mode,interpretation='camera source descriptor; semantics unverified')
        if self.visual_hz is not None:
            payload.update(visual_contract='sampled-visual-v1',retention=dict(status=status,reason=reason),
                clock=metadata.get('clock','monotonic; exposure or disclosed read completion'))
        prepared=EvidenceJournal.prepare_observation(payload,episode=self.episode,at=at,
            producer='ObservedCamera',version='3' if self.visual_hz is not None else '2',provenance=self.provenance)
        if selected:
            self._submit(self._capture,(image.copy(),prepared,self.count),size=size+len(prepared.document.encode()),is_frame=True)
        else:
            self._submit(self._descriptor,(None,prepared),size=len(prepared.document.encode()))
        self._retention_counts[status]+=1;self.latest_observation=prepared
        while self._rolling and at-self._rolling[0][0]>self.rolling_seconds:
            self._rolling_bytes-=self._rolling.popleft()[4];self._rolling_evictions+=1
        if self.rolling_seconds and size<=self.rolling_byte_capacity:
            # Snapshot immutable camera pixels; writer/ring never mutate ownership.
            owned=image.copy()
            entry=[at,prepared,self.count,owned,size,selected]
            self._rolling.append(entry);self._rolling_bytes+=size
            while self._rolling and (len(self._rolling)>self.rolling_frames or self._rolling_bytes>self.rolling_byte_capacity
                                     or at-self._rolling[0][0]>self.rolling_seconds):
                self._rolling_bytes-=self._rolling.popleft()[4];self._rolling_evictions+=1
            self._rolling_peak=max(self._rolling_peak,self._rolling_bytes)
            for request in list(self._incidents):
                if at>request['end']:
                    self._finish_incident(request,'observed interval ended');continue
                if at>=request['trigger_at'] and entry in self._rolling:self._retain_incident(entry,request)
        else:
            for request in list(self._incidents):
                if at>request['end']:self._finish_incident(request,'observed interval ended')
                elif selected:request['available'].append(prepared.id)
                else:request['shortfalls'].append(dict(observation_id=prepared.id,reason='rolling originals unavailable (disabled or oversized)'))
        with self._lock:self._stats['enqueue_ns']+=time.perf_counter_ns()-began
        return prepared.id

    def _descriptor(self,unused,prepared):
        self.journal.commit_prepared(prepared)

    def _capture(self,image,prepared,number,request_id=None):
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
            retention_reason='incident' if request_id else 'baseline',incident_request_id=request_id,
            interpretation='camera pixels; no semantic truth or independent episode'),
            episode=self.episode,at=prepared.data['at'],sources=[prepared.id]+([request_id] if request_id else []),producer='ObservedCamera',version='2',provenance=self.provenance)
        with self._lock:
            self._stats['captures_written']+=1;self._stats['encode_ns']+=encode_ns
            self._stats['write_ns']+=time.perf_counter_ns()-began

    def request_incident(self,reason,*,preceding=1.,following=.5,prediction_id=None):
        """Bounded request through current recorder; no agenda or physical authority."""
        if not reason or not all(math.isfinite(v) and 0<=v<=10 for v in (preceding,following)):
            raise ValueError('incident requires reason and bounded 0..10 second intervals')
        if self.latest_observation is None:raise ValueError('incident requires current observation')
        trigger=self.latest_observation.data['at'];available=[e[1].id for e in self._rolling if e[0]>=trigger-preceding]
        rejected=len(self._incidents)>=4 or self._incident_count>=128
        identifier=self.event('incident_request',dict(schema='incident-preservation-v1',reason=reason,
            trigger_observation_id=self.latest_observation.id,prediction_id=prediction_id,
            requested_interval=[trigger-preceding,trigger+following],available_original_ids=available,
            admission='rejected bounded request budget' if rejected else 'accepted',
            selection='Charlie-requested diagnostics; never a substitute for fixed independent samples'),
            at=time.monotonic(),sources=[prediction_id] if prediction_id else None)
        self._incident_count+=1
        request=dict(id=identifier,start=trigger-preceding,end=trigger+following,trigger_at=trigger,
                     available=[],shortfalls=[],retained=[])
        if rejected:
            request['shortfalls'].append(dict(reason='request budget exhausted'));self._finish_incident(request,'rejected');return identifier
        self._incidents.append(request)
        if not self._rolling or self._rolling[0][0]>request['start']:
            request['shortfalls'].append(dict(reason='preceding originals unavailable or evicted',
                requested_start=request['start'],available_start=self._rolling[0][0] if self._rolling else None))
        for entry in self._rolling:
            if entry[0]>=request['start']:self._retain_incident(entry,request)
        if not following:self._finish_incident(request,'no following interval requested')
        return identifier

    def _retain_incident(self,entry,request):
        at,prepared,number,image,size,selected=entry
        if len(request['available'])>=300:
            if not any(x.get('reason')=='incident source count budget' for x in request['shortfalls']):
                request['shortfalls'].append(dict(reason='incident source count budget'))
            return
        request['available'].append(prepared.id)
        if selected:
            request['retained'].append(prepared.id);return
        with self._lock:
            full=(self._frames>=max(1,self.capacity-2) or self._bytes+size+4096>self.byte_capacity*.6
                  or self._records>=max(1,self.record_capacity-16))
        if full:
            request['shortfalls'].append(dict(observation_id=prepared.id,reason='incident budget; baseline/critical reserve'));return
        self._submit(self._capture,(image,prepared,number,request['id']),size=size+len(prepared.document.encode()),is_frame=True)
        entry[5]=True;request['retained'].append(prepared.id);self._incident_frame_count+=1

    def _finish_incident(self,request,reason):
        if request in self._incidents:self._incidents.remove(request)
        if reason=='recording stopped' and (self._last_source_at or 0)<request['end']:
            request['shortfalls'].append(dict(reason='following interval interrupted',last_source_at=self._last_source_at))
        self.event('incident_resolution',dict(request_id=request['id'],end_reason=reason,
            available_original_ids=list(dict.fromkeys(request['available'])),
            selected_for_retention_ids=list(dict.fromkeys(request['retained'])),shortfalls=request['shortfalls'],
            verification='selected IDs require final writer completion; no new independent experience'),
            at=time.monotonic(),sources=[request['id']])

    def event(self,kind,payload,*,at,sources=None):
        from memory.evidence import EvidenceJournal
        if self.latest_observation is None:raise ValueError('event needs a source observation')
        began=time.perf_counter_ns();source=self.latest_observation.id
        dependencies=list(dict.fromkeys([source]+list(sources or [])))
        if kind.endswith('_prediction'):
            now=time.monotonic()
            prepared=EvidenceJournal.prepare_buffered_prediction(dict(category=kind,observation_id=source,**payload),
                episode=self.episode,at=now,deadline=now+5.,sources=dependencies,producer='PPAL',version='2')
        else:
            prepared=EvidenceJournal.prepare_observation(dict(category=kind,observation_id=source,**payload),
                episode=self.episode,at=at,sources=dependencies,producer='PPAL',version='2',provenance=self.provenance)
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
        try:
            for request in list(self._incidents):self._finish_incident(request,'recording stopped')
            self.flush()
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
        self._rolling.clear();self._rolling_bytes=0
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

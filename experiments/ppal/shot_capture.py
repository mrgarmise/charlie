"""Drain protected exposures losslessly while the existing transport pulses.

The sole camera producer still only acquires. A bounded disk archive, not an
inference queue or an expanding image list, bridges capture and causal replay.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading
import time
import traceback

from PIL import Image


@dataclass(frozen=True)
class ArchivedExposure:
    sequence: int
    path: Path
    capture: dict
    rgb_sha256: str
    size: tuple
    mode: str
    offset: int
    length: int

    @property
    def at(self):return self.capture['first_pixel_exposure_at']

    @property
    def image(self):
        # One original at a time; no replay cache of full-size images.
        with self.path.open('rb') as saved:
            saved.seek(self.offset);pixels=saved.read(self.length)
        if len(pixels)!=self.length or hashlib.sha256(pixels).hexdigest()!=self.rgb_sha256:
            raise ValueError('protected causal pixels changed before replay')
        return Image.frombytes(self.mode,self.size,pixels)


class CapturedFrames:
    """Finite append-only archive plus lazy originals; no camera or worker owner.

    Each complete write transfers pixels out of the RAM ring. One fsync commits
    the entire bounded archive before successful replay, matching the existing
    recorder's distinction between accepted bytes and durable completion.
    """
    def __init__(self, source, *, max_frames, max_bytes):
        recorder=getattr(source,'recorder',None)
        output=getattr(recorder,'output',None)
        self.temporary=None
        if output is None:
            self.temporary=tempfile.TemporaryDirectory(prefix='charlie-causal-')
            self.directory=Path(self.temporary.name)
        else:
            parent=Path(output)/'causal-windows';parent.mkdir(parents=True,exist_ok=True)
            self.directory=Path(tempfile.mkdtemp(prefix='window-',dir=parent))
        self.path=self.directory/'frames.raw'
        self.file=self.path.open('xb',buffering=0)
        self.max_frames=max_frames;self.max_bytes=max_bytes
        self.frames=[];self.bytes=0;self.disk_bytes=0;self.closed=False;self.metadata={};self.partial_records=[]

    def __len__(self):return len(self.frames)
    def __iter__(self):return iter(self.frames)
    def __getitem__(self,key):return self.frames[key]

    def _write(self,data):
        view=memoryview(data)
        while view:
            written=self.file.write(view)
            if not written:raise OSError('protected archive short write')
            view=view[written:]

    def append(self, packet):
        if (len(self.frames)>=self.max_frames or self.bytes+packet.nbytes+8192>self.max_bytes):
            raise BufferError('protected causal archive budget exhausted; no evidence silently discarded')
        image=packet.image;pixels=image.tobytes();checksum=hashlib.sha256(pixels).hexdigest()
        header=json.dumps(dict(sequence=packet.sequence,capture=packet.capture,
            pixel_sha256=checksum,size=image.size,mode=image.mode,length=len(pixels))).encode('utf8')
        prefix=struct.pack('!I',len(header))+header
        start=self.file.tell();offset=start+len(prefix)
        if offset+len(pixels)>self.max_bytes:
            raise BufferError('protected causal archive disk budget exhausted')
        try:
            self._write(prefix);self._write(pixels)
        except BaseException:
            self.partial_records.append(dict(sequence=packet.sequence,offset=start))
            raise
        finally:self.disk_bytes=self.file.tell()
        self.frames.append(ArchivedExposure(packet.sequence,self.path,dict(packet.capture),checksum,
                                            image.size,image.mode,offset,len(pixels)))
        self.bytes+=packet.nbytes

    def seal(self):
        if not self.file.closed:
            try:os.fsync(self.file.fileno())
            finally:self.file.close()

    def manifest(self, **fields):
        from learning.foundry import atomic_json
        self.seal()
        self.metadata.update(fields)
        atomic_json(self.directory/'manifest.json',dict(schema='protected-causal-window-v1',
            max_frames=self.max_frames,max_bytes=self.max_bytes,
            accounted_bytes=self.bytes,disk_bytes=self.disk_bytes,partial_records=self.partial_records,
            durability='archive fsync completes before capture_complete; no causal replay before commit',
            frames=[dict(sequence=p.sequence,path=p.path.name,capture=p.capture,
                         pixel_sha256=p.rgb_sha256,size=p.size,mode=p.mode,offset=p.offset,length=p.length)
                    for p in self.frames],**self.metadata))

    def close(self, *, replayed=False):
        if self.closed:return
        self.manifest(replay='consumed' if replayed else 'incomplete_or_not_requested')
        if self.temporary is not None:self.temporary.cleanup()
        # Native archives are durable originals in the existing evidence root,
        # not orphaned scratch buffers. All file handles are already closed.
        self.closed=True


def capture_window(source,controller,action,duration_ms,deadline=None,should_stop=None,*,post_seconds=.25,
                   max_frames=128,max_bytes=256*1024*1024):
    if not 30<=duration_ms<=400:raise ValueError('firing duration must be explicitly bounded at 30..400 ms')
    if not 0<post_seconds<=.35:raise ValueError('post-fire window must be bounded')
    if (type(max_frames) is not int or not 3<=max_frames<=128
            or type(max_bytes) is not int or not 1<=max_bytes<=256*1024*1024):
        raise ValueError('finite protected archive budget required')
    def stopped():return should_stop is not None and should_stop()
    if stopped() or (deadline is not None and time.monotonic()+duration_ms/1000+post_seconds>=deadline):
        raise InterruptedError('insufficient existing acquisition budget; no FIRE sent')
    stream=source.stream
    archive=None
    cancel=threading.Event();done=threading.Event();errors=[];execution={};worker=None;begun=False
    submitted=time.monotonic();window={}
    # Bound even a slow/blocked transport/window independently of a discovery's
    # overall deadline. Underlying socket timeout and server/local deadmen remain.
    window_deadline=min(deadline if deadline is not None else float('inf'),submitted+2.5)
    class Cancellation:
        def is_set(self):return cancel.is_set() or stream.failed.is_set() or stopped()
        def wait(self,seconds):
            until=time.monotonic()+seconds
            while not self.is_set():
                remaining=until-time.monotonic()
                if remaining<=0:break
                cancel.wait(min(.01,remaining))
            return self.is_set()
    cancellation=Cancellation()
    def execute():
        try:
            controller.execute(action,duration_ms,cancel_event=cancellation,deadline=window_deadline-post_seconds)
            execution.update(controller.last_execution or {})
            # End protection by exposure time, including the full declared
            # post-release interval, irrespective of disk/replay scheduling.
            window['end_exposure_at']=time.monotonic()+post_seconds
            stream.limit_window(window['end_exposure_at'])
        except BaseException as exc:errors.append(exc)
        finally:done.set()
    try:
        archive=CapturedFrames(source,max_frames=max_frames,max_bytes=max_bytes)
        baseline=stream.begin_window();begun=True
        if baseline.nbytes+8192>max_bytes:raise BufferError('baseline exceeds protected archive budget')
        # Baseline is already independently exposed and protected. Drain it
        # concurrently with the pulse, rather than spending buffer runway on a
        # synchronous pre-command disk flush.
        submitted=time.monotonic()
        worker=threading.Thread(target=execute,name='charlie-causal-controller',daemon=False)
        worker.start()
        while True:
            if stopped():raise InterruptedError('shot observation cancelled')
            if errors:raise errors[0]
            if time.monotonic()>=window_deadline:raise TimeoutError('protected causal window deadline exhausted')
            try:packet=stream.next_window(timeout=.02)
            except TimeoutError:continue
            if packet is None:break
            archive.append(packet)
            stream.acknowledge_window(packet.sequence)
        if not done.wait(.05):raise RuntimeError('causal window ended before controller completion')
        if errors:raise errors[0]
        stream.end_window();begun=False
        if stopped():raise InterruptedError('shot observation cancelled')
        status=dict(schema='pinned-shot-window-v2',submitted_at=submitted,
            baseline_at=baseline.at,completed_at=time.monotonic(),frames=len(archive),
            first_exposure_at=archive[0].at,last_exposure_at=archive[-1].at,
            post_seconds=post_seconds,end_exposure_at=window['end_exposure_at'],
            controller_execution=execution,stream=stream.stats(),
            archive=str(archive.directory),archive_max_frames=max_frames,archive_max_bytes=max_bytes,
            latency='acknowledgment is transport evidence, not display response time')
        archive.manifest(status='capture_complete',window=status)
        return execution,archive,status
    except BaseException as exc:
        cancel.set()
        if worker is not None:
            worker.join(.1)
            if worker.is_alive():
                connection=getattr(controller,'connection',None)
                if connection is not None:
                    try:connection.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                worker.join(2.5)
            if worker.is_alive():exc.add_note('controller worker did not stop; session invalid; no further control allowed')
        if worker is not None and worker.is_alive():
            # Do not block on a wire lock still held by a broken worker. Socket
            # shutdown was attempted above; close the link and fail the session.
            connection=getattr(controller,'connection',None)
            if connection is not None:
                try:connection.close()
                except OSError:pass
        else:
            try:controller.close()
            except Exception as cleanup:exc.add_note(f'controller neutralization cleanup: {cleanup}')
        # Preserve available protected originals after neutralization. A full or
        # failed archive is explicit; do not acknowledge or pretend it is complete.
        recovery_error=None
        if begun:
            remaining=stream.abort_window()
            try:
                for packet in remaining:
                    if not archive.frames or packet.sequence>archive.frames[-1].sequence:archive.append(packet)
            except Exception as recovery:recovery_error=f'{type(recovery).__name__}: {recovery}'
        try:
            if archive is not None:archive.manifest(status='invalid',error_type=type(exc).__name__,error=str(exc),
                error_traceback=''.join(traceback.format_exception(exc))[-65536:],
                recovery_error=recovery_error,
                unarchived_sequences=[p.sequence for p in remaining if p.sequence not in {q.sequence for q in archive.frames}] if begun else [],
                controller_execution=dict(getattr(controller,'last_execution',None) or {}),
                stream=stream.stats(),worker_alive=worker.is_alive() if worker is not None else False)
        except Exception as evidence_error:exc.add_note(f'causal failure manifest: {evidence_error}')
        if archive is not None and archive.temporary is not None:archive.temporary.cleanup()
        raise
    finally:
        if worker is not None:worker.join(.1)
        if archive is not None and not archive.file.closed:archive.file.close()

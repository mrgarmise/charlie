"""Single camera producer; bounded ordinary history and pinned causal windows.

No inference, image encoding, publishing, or journal writes run on the producer.
Ordinary history eviction is counted. A pinned-window overflow fails closed.
"""
from collections import deque
from dataclasses import dataclass
import math
import threading
import time
import traceback


@dataclass(frozen=True)
class Exposure:
    sequence: int
    image: object
    capture: dict

    @property
    def at(self):return self.capture['first_pixel_exposure_at']
    @property
    def nbytes(self):return self.image.width*self.image.height*max(4,len(self.image.getbands()))


class ObservationStream:
    def __init__(self, acquire, *, capacity=24, byte_capacity=64*1024*1024):
        if capacity<3 or byte_capacity<1:raise ValueError('invalid capture bounds')
        self.acquire=acquire;self.capacity=capacity;self.byte_capacity=byte_capacity
        self.frames=deque();self.bytes=0;self.pin=None;self.error=None
        self.window_end_at=None;self.window_end_sequence=None
        self.window_drained=0;self.last_capture=None;self.error_traceback=None
        self.condition=threading.Condition();self.stop_event=threading.Event();self.failed=threading.Event()
        self.sequence=0;self.evicted=0;self.first_at=None;self.intervals=deque(maxlen=2048);self.maximum_bytes=0;self.previous_sensor=None;self.previous_at=None
        self.thread=threading.Thread(target=self._run,name='charlie-camera-owner',daemon=False)

    def start(self):self.thread.start();return self

    def _append(self,image,capture):
        capture=dict(capture or {});at=capture.get('first_pixel_exposure_at');sensor=capture.get('sensor_timestamp_ns')
        if (not isinstance(at,(int,float)) or isinstance(at,bool) or not math.isfinite(at) or
            not isinstance(sensor,(int,float)) or isinstance(sensor,bool) or not math.isfinite(sensor) or
            sensor<=0 or (self.previous_sensor is not None and sensor<=self.previous_sensor) or
            (self.previous_at is not None and at<=self.previous_at)):
            raise ValueError('missing, repeated, or nonmonotonic exposure metadata')
        completed=capture.get('completed_at')
        if completed is not None and (not math.isfinite(completed) or not 0<=completed-at<=1.):
            raise ValueError('stale or future exposure relative to capture completion')
        self.sequence+=1;packet=Exposure(self.sequence,image,capture)
        if packet.nbytes>self.byte_capacity:raise BufferError('camera image exceeds memory bound')
        if self.pin is not None and self.window_end_at is not None and at>self.window_end_at and self.window_end_sequence is None:
            self.window_end_sequence=packet.sequence-1
        retain=True
        while self.frames and (len(self.frames)>=self.capacity or self.bytes+packet.nbytes>self.byte_capacity):
            ordinary=next((i for i,p in enumerate(self.frames) if not self._protected(p.sequence)),None)
            if ordinary is None:
                if self._protected(packet.sequence):
                    raise BufferError('critical capture window overflow; no frames silently discarded')
                # The closed causal interval owns the remaining RAM. Acquisition
                # continues; explicitly count this *ordinary* frame as unretained.
                self.evicted+=1;retain=False
                break
            old=self.frames[ordinary];del self.frames[ordinary]
            self.bytes-=old.nbytes;self.evicted+=1
        if retain:
            self.frames.append(packet);self.bytes+=packet.nbytes
            self.maximum_bytes=max(self.maximum_bytes,self.bytes)
        self.last_capture=capture
        if self.previous_at is not None:self.intervals.append(at-self.previous_at)
        if self.first_at is None:self.first_at=at
        self.previous_at=at;self.previous_sensor=sensor
        self.condition.notify_all()

    def _run(self):
        try:
            while not self.stop_event.is_set():
                image,capture=self.acquire()
                if self.stop_event.is_set():break
                with self.condition:self._append(image,capture)
        except BaseException as exc:
            with self.condition:
                if not self.stop_event.is_set():
                    self.error=exc;self.error_traceback=traceback.format_exc()[-65536:];self.failed.set()
                self.condition.notify_all()

    def latest(self, *, after=0, not_before=None, timeout=1.):
        end=time.monotonic()+timeout
        with self.condition:
            while True:
                if self.error is not None:raise RuntimeError('camera stream failed') from self.error
                if self.stop_event.is_set():raise RuntimeError('camera stream stopped')
                if self.frames:
                    p=self.frames[-1]
                    if p.sequence>after and (not_before is None or p.at>not_before):return p
                remaining=end-time.monotonic()
                if remaining<=0:raise TimeoutError('no new independent camera exposure')
                self.condition.wait(remaining)

    def begin_window(self):
        with self.condition:
            if self.pin is not None:raise RuntimeError('nested capture window')
            if self.error is not None:raise RuntimeError('camera stream failed') from self.error
            if not self.frames:raise RuntimeError('capture must precede command submission')
            self.pin=self.frames[-1].sequence
            self.window_end_at=self.window_end_sequence=None
            self.window_drained=0
            return self.frames[-1]

    def _protected(self, sequence):
        return (self.pin is not None and sequence>=self.pin
                and (self.window_end_sequence is None or sequence<=self.window_end_sequence))

    def limit_window(self, end_at):
        """Controller completion sets an exposure-time cutoff, not caller wakeup time."""
        if not math.isfinite(end_at):raise ValueError('finite causal cutoff required')
        with self.condition:
            if self.pin is None:raise RuntimeError('no protected capture window')
            self.window_end_at=end_at
            if self.previous_at is not None and self.previous_at>end_at:
                self.window_end_sequence=max((p.sequence for p in self.frames if p.at<=end_at),default=self.pin-1)
            self.condition.notify_all()

    def next_window(self, *, timeout=.02):
        """Oldest unacknowledged protected exposure; never newest-frame sampling."""
        until=time.monotonic()+timeout
        with self.condition:
            while True:
                if self.error is not None:raise RuntimeError('causal capture failed') from self.error
                if self.stop_event.is_set():raise RuntimeError('camera stream stopped')
                if self.pin is None:raise RuntimeError('no protected capture window')
                packet=next((p for p in self.frames if self._protected(p.sequence)),None)
                if packet is not None:return packet
                if self.window_end_sequence is not None:return None
                remaining=until-time.monotonic()
                if remaining<=0:raise TimeoutError('waiting for protected exposure')
                self.condition.wait(remaining)

    def acknowledge_window(self, sequence):
        """Release RAM after lossless transfer; the archive commits before replay."""
        with self.condition:
            first=next((p for p in self.frames if self._protected(p.sequence)),None)
            if first is None or first.sequence!=sequence:
                raise ValueError('protected evidence must be acknowledged in sequence')
            self.pin=sequence+1;self.window_drained+=1
            self.condition.notify_all()

    def abort_window(self):
        """Atomically detach available evidence on failure; it cannot qualify a probe."""
        with self.condition:
            packets=[p for p in self.frames if self._protected(p.sequence)]
            self.pin=None
            self.window_end_at=self.window_end_sequence=None
            self.condition.notify_all()
            return packets

    def end_window(self):
        packets=self.abort_window()
        if self.error is not None:raise RuntimeError('causal capture failed') from self.error
        return packets

    def stats(self):
        with self.condition:return dict(acquired=self.sequence,ordinary_history_evictions=self.evicted,
            retained=len(self.frames),retained_bytes=self.bytes,maximum_bytes=self.maximum_bytes,
            capacity=self.capacity,byte_capacity=self.byte_capacity,failed=self.error is not None,
            error=str(self.error) if self.error else None,
            error_type=type(self.error).__name__ if self.error else None,
            error_traceback=self.error_traceback,last_capture=self.last_capture,
            protected_retained=sum(self._protected(p.sequence) for p in self.frames),
            protected_drained=self.window_drained,window_end_at=self.window_end_at,
            worker_alive=self.thread.is_alive(),
            producer_hz=(self.sequence-1)/(self.previous_at-self.first_at)
                if self.sequence>1 and self.previous_at>self.first_at else None,
            first_exposure_at=self.first_at,last_exposure_at=self.previous_at,
            largest_exposure_gap=max(self.intervals) if self.intervals else None)

    def close(self):
        self.stop_event.set()
        with self.condition:self.condition.notify_all()
        self.thread.join(2.) # native acquire itself has a one-second timeout
        if self.thread.is_alive():raise RuntimeError('camera acquisition owner did not stop')

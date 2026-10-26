"""Existing stimuli plus source-bound, latest-only frame subscriptions.

Frame delivery never invokes consumers or performs I/O on the publisher thread.
"""
import queue
import threading
import time


class FrameSubscription:
    def __init__(self, bus, source, *, max_age, clock):
        self.bus, self.source, self.max_age, self.clock = bus, source, max_age, clock
        self.pending = queue.Queue(maxsize=1)
        self.closed = False
        self.dropped = 0

    def _offer(self, value):
        if self.closed:
            return
        try:
            self.pending.put_nowait(value)
        except queue.Full:
            try:
                self.pending.get_nowait()
                self.dropped += 1
            except queue.Empty:
                pass
            try:
                self.pending.put_nowait(value)
            except queue.Full:
                self.dropped += 1

    def read(self):
        if self.closed:
            raise InterruptedError('frame subscription closed')
        try:
            value = self.pending.get_nowait()
        except queue.Empty:
            return None
        if isinstance(value, Exception):
            raise value
        age = self.clock() - value.received_at
        if not 0 <= age <= self.max_age:
            raise TimeoutError('stale subscribed frame')
        # Mutable provenance dictionaries are private to each subscriber; pixels
        # retain the shared immutable snapshot without an additional image copy.
        from dataclasses import fields, replace
        from copy import deepcopy
        changes = {f.name: deepcopy(getattr(value, f.name)) for f in fields(value)
                   if isinstance(getattr(value, f.name), (dict, list))}
        return replace(value, **changes)

    def wait(self, timeout=2., *, captured_after=None):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            frame = self.read()
            if frame is not None and (captured_after is None or
                    getattr(frame, 'capture_requested_at', None) is not None and
                    frame.capture_requested_at >= captured_after):
                return frame
            time.sleep(.005)
        raise TimeoutError('waiting for a fresh published frame')

    def close(self):
        with self.bus.lock:
            self.closed = True
            self.bus.subscribers.discard(self)
        while not self.pending.empty():
            try:
                self.pending.get_nowait()
            except queue.Empty:
                break


class StimulusBus:
    def __init__(self):
        self.events = []
        self.lock = threading.RLock()
        self.subscribers = set()
        self.frame_owners = {}

    def emit(self, event_type, data=None):
        with self.lock:
            self.events.append((event_type, data))

    def get_all(self):
        with self.lock:
            events, self.events = self.events, []
        return events

    def subscribe_frames(self, source, *, max_age=.5, clock=time.monotonic):
        import math
        if (not isinstance(source, str) or not source or not math.isfinite(max_age)
                or not 0 < max_age <= 5):
            raise ValueError('source identity and bounded freshness required')
        with self.lock:
            if len(self.subscribers) >= 64:
                raise RuntimeError('frame subscriber limit reached')
            subscription = FrameSubscription(self, source, max_age=max_age, clock=clock)
            self.subscribers.add(subscription)
        return subscription

    def claim_frames(self, source, owner):
        with self.lock:
            if source in self.frame_owners:
                raise RuntimeError('physical camera already has an authoritative feeder')
            self.frame_owners[source] = owner

    def publish_frame(self, source, owner, frame):
        if frame.source != source:
            raise ValueError('camera source identity mismatch')
        frame.validate()
        # Owned immutable snapshots only. Each subscriber receives the same frame.
        if frame.image.flags.writeable:
            raise ValueError('frame publisher must own immutable pixels')
        self._deliver_frame(source, owner, frame)

    def _deliver_frame(self, source, owner, value):
        with self.lock:
            if self.frame_owners.get(source) is not owner:
                raise PermissionError('frame publication requires the existing feeder owner')
            for subscriber in self.subscribers:
                if subscriber.source == source:
                    subscriber._offer(value)

    def frame_fault(self, source, owner, reason):
        self._deliver_frame(source, owner, OSError(str(reason)))

    def release_frames(self, source, owner):
        with self.lock:
            if self.frame_owners.get(source) is owner:
                self.frame_fault(source, owner, 'camera feeder stopped')
                del self.frame_owners[source]


# The application installs a bus; capabilities never install or start feeders.
_application_frames = None


def application_frames():
    return _application_frames


def install_application_frames(bus):
    global _application_frames
    if _application_frames is not None and _application_frames is not bus:
        raise RuntimeError('application frame bus already installed')
    _application_frames = bus


def remove_application_frames(bus):
    global _application_frames
    if _application_frames is bus:
        _application_frames = None


def subscribe_to_frames(source, **kwargs):
    if _application_frames is not None:
        return _application_frames.subscribe_frames(source, **kwargs)
    from experiments.ppal.eyes.passive import PublishedFrameSubscription
    return PublishedFrameSubscription(source, **kwargs)

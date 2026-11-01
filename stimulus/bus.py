"""Existing stimuli plus source-bound, latest-only frame subscriptions.

Frame delivery never invokes consumers or performs I/O on the publisher thread.
"""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, fields, replace
import queue
import threading
import time


def _private_frame(value):
    """Share immutable pixels, isolate mutable provenance at every boundary."""
    changes = {f.name: deepcopy(getattr(value, f.name)) for f in fields(value)
               if isinstance(getattr(value, f.name), (dict, list))}
    return replace(value, **changes)


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
        return _private_frame(value)

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


@dataclass(frozen=True)
class Observation:
    source: str
    sequence: int
    received_at: float
    values: dict
    provenance: dict
    generation: str
    captured_at: float | None = None


class ObservationSubscription(FrameSubscription):
    def close(self):
        with self.bus.lock:
            self.closed = True
            self.bus.observation_subscribers.discard(self)
        while not self.pending.empty():
            try:
                self.pending.get_nowait()
            except queue.Empty:
                break


class StimulusBus:
    def __init__(self, *, history_frames=4, history_bytes=32*1024*1024):
        # Per-source RAM caps, deliberately conservative host defaults; native
        # retention/cadence must be measured rather than inferred from these.
        if (type(history_frames) is not int or not 1 <= history_frames <= 64
                or type(history_bytes) is not int or not 1 <= history_bytes <= 256*1024*1024):
            raise ValueError('bounded frame history required')
        self.history_frames, self.history_bytes = history_frames, history_bytes
        self.frame_history = {}
        self.frame_order = {}
        self.frame_health = {}
        self.frame_evictions = {}
        self.events = []
        self.lock = threading.RLock()
        self.subscribers = set()
        self.frame_owners = {}
        self.observation_owners = {}
        self.observation_history = {}
        self.observation_order = {}
        self.observation_health = {}
        self.observation_fault_counts = {}
        self.observation_metadata = {}
        self.observation_subscribers = set()

    def claim_observations(self, source, owner, *, metadata):
        # A directory entry is never an actuator authority or safety certificate.
        import json
        if len(json.dumps(metadata, allow_nan=False).encode()) > 4096:
            raise ValueError('source metadata exceeds 4 KiB')
        if not isinstance(source, str) or not 1 <= len(source) <= 128 or owner is None:
            raise ValueError('source and owner required')
        with self.lock:
            if source in self.observation_owners:
                raise RuntimeError('observation source already owned')
            if source not in self.observation_metadata and len(self.observation_metadata) >= 64:
                raise RuntimeError('source limit reached')
            self.observation_owners[source] = owner
            self.observation_metadata[source] = deepcopy(metadata)
            self.observation_history[source] = deque(maxlen=32)
            self.observation_order[source] = None
            self.observation_health[source] = 'waiting'
            self.observation_fault_counts.setdefault(source,0)

    def publish_observation(self, source, owner, observation):
        import json
        import math
        if (not isinstance(observation, Observation) or observation.source != source
                or type(observation.sequence) is not int or observation.sequence < 0
                or not isinstance(observation.generation, str) or not 1 <= len(observation.generation) <= 128
                or not math.isfinite(observation.received_at)
                or (observation.captured_at is not None and not math.isfinite(observation.captured_at))):
            raise ValueError('invalid source observation')
        # Bound every payload and reject NaN rather than manufacturing values.
        if len(json.dumps([observation.values, observation.provenance], allow_nan=False).encode()) > 16384:
            raise ValueError('observation payload exceeds 16 KiB')
        with self.lock:
            if self.observation_owners.get(source) is not owner:
                raise PermissionError('observation publication requires source owner')
            previous = self.observation_order[source]
            order = (observation.generation, observation.sequence, observation.received_at)
            history = self.observation_history[source]
            if previous and previous[0] == order[0] and (order[1] <= previous[1] or order[2] < previous[2]):
                raise ValueError('duplicate or regressing observation')
            if previous and previous[0] != order[0]:
                history.clear()
            snapshot = _private_frame(observation)
            history.append(snapshot)
            self.observation_order[source] = order
            self.observation_health[source] = 'available'
            for subscriber in self.observation_subscribers:
                if subscriber.source == source:
                    subscriber._offer(snapshot)

    def observation_fault(self, source, owner, reason):
        with self.lock:
            if self.observation_owners.get(source) is not owner:
                raise PermissionError('observation fault requires source owner')
            fault = OSError(str(reason))
            self.observation_health[source] = fault
            self.observation_fault_counts[source] += 1
            self.observation_history[source].clear()
            for subscriber in self.observation_subscribers:
                if subscriber.source == source:
                    subscriber._offer(fault)

    def subscribe_observations(self, source, *, max_age=.25, clock=time.monotonic):
        import math
        if not isinstance(source, str) or not source or not math.isfinite(max_age) or not 0 < max_age <= 5:
            raise ValueError('source and bounded freshness required')
        with self.lock:
            if len(self.observation_subscribers) >= 64:
                raise RuntimeError('observation subscriber limit reached')
            subscription = ObservationSubscription(self, source, max_age=max_age, clock=clock)
            self.observation_subscribers.add(subscription)
            health = self.observation_health.get(source)
            if isinstance(health, Exception):
                subscription._offer(health)
            elif self.observation_history.get(source):
                subscription._offer(self.observation_history[source][-1])
            return subscription

    def recent_observations(self, source, *, max_age=.25, clock=time.monotonic):
        import math
        if not math.isfinite(max_age) or not 0 < max_age <= 5:
            raise ValueError('bounded freshness required')
        now = clock()
        with self.lock:
            health = self.observation_health.get(source)
            if isinstance(health, Exception):
                raise OSError(str(health))
            return tuple(_private_frame(o) for o in self.observation_history.get(source, ())
                         if 0 <= now-o.received_at <= max_age)

    def latest_observation(self, source, **kwargs):
        values = self.recent_observations(source, **kwargs)
        return values[-1] if values else None

    def release_observations(self, source, owner):
        with self.lock:
            if self.observation_owners.get(source) is owner:
                self.observation_fault(source, owner, 'source stopped')
                del self.observation_owners[source]

    def describe_observations(self):
        with self.lock:
            return {source: dict(deepcopy(metadata), source_id=source,
                    health=str(self.observation_health[source]),
                    failures=self.observation_fault_counts[source],
                    retained=len(self.observation_history[source]), history_limit=32,
                    payload_limit_bytes=16384, physical_authorization=False)
                    for source, metadata in self.observation_metadata.items()}

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
            # A late subscriber can see the last healthy frame, without capture
            # being coupled to subscription demand. read() still enforces age.
            health = self.frame_health.get(source)
            if isinstance(health, Exception):
                subscription._offer(health)
            elif self.frame_history.get(source):
                subscription._offer(self.frame_history[source][-1])
        return subscription

    def claim_frames(self, source, owner):
        with self.lock:
            if source in self.frame_owners:
                raise RuntimeError('physical camera already has an authoritative feeder')
            self.frame_owners[source] = owner
            self.frame_history[source] = deque()
            self.frame_order[source] = None
            self.frame_health[source] = None
            self.frame_evictions.setdefault(source, 0)

    def publish_frame(self, source, owner, frame):
        if frame.source != source:
            raise ValueError('camera source identity mismatch')
        frame.validate()
        # Owned immutable snapshots only. Each subscriber receives the same frame.
        if frame.image.flags.writeable:
            raise ValueError('frame publisher must own immutable pixels')
        with self.lock:
            if self.frame_owners.get(source) is not owner:
                raise PermissionError('frame publication requires the existing feeder owner')
            history = self.frame_history[source]
            previous = self.frame_order[source]
            generation = getattr(frame, 'stream_generation', None)
            if (previous is not None and previous[0] == generation
                    and (frame.sequence <= previous[1] or frame.received_at < previous[2])):
                raise ValueError('duplicate or out-of-order source frame')
            if previous is not None and previous[0] != generation:
                self.frame_evictions[source] += len(history)
                history.clear()
            # Freeze producer provenance as well as isolating each consumer.
            snapshot = _private_frame(frame)
            history.append(snapshot)
            used = sum(f.image.nbytes for f in history)
            while history and (len(history) > self.history_frames or used > self.history_bytes):
                used -= history.popleft().image.nbytes
                self.frame_evictions[source] += 1
            self.frame_order[source] = (generation, frame.sequence, frame.received_at)
            self.frame_health[source] = 'available'
            self._deliver_frame(source, owner, snapshot)

    def _deliver_frame(self, source, owner, value):
        with self.lock:
            if self.frame_owners.get(source) is not owner:
                raise PermissionError('frame publication requires the existing feeder owner')
            for subscriber in self.subscribers:
                if subscriber.source == source:
                    subscriber._offer(value)

    def frame_fault(self, source, owner, reason):
        with self.lock:
            if self.frame_owners.get(source) is not owner:
                raise PermissionError('frame publication requires the existing feeder owner')
            fault = OSError(str(reason))
            self.frame_health[source] = fault
            self.frame_evictions[source] += len(self.frame_history[source])
            self.frame_history[source].clear()
            self._deliver_frame(source, owner, fault)

    def recent_frames(self, source, *, max_age=.5, clock=time.monotonic):
        """Healthy bounded history only; never promote historical frames to live.

        Original receipt/clock provenance is retained. Empty means unavailable or
        expired, and faults raise explicitly. No device I/O, disk writes or owner
        creation occurs. Callers can retain selected frames using FrameArtifactStore.
        """
        import math
        if not math.isfinite(max_age) or not 0 < max_age <= 5:
            raise ValueError('bounded freshness required')
        now = clock()
        with self.lock:
            health = self.frame_health.get(source)
            if isinstance(health, Exception):
                raise OSError(str(health))
            return tuple(_private_frame(f) for f in self.frame_history.get(source, ())
                         if 0 <= now - f.received_at <= max_age)

    def latest_frame(self, source, **kwargs):
        frames = self.recent_frames(source, **kwargs)
        return frames[-1] if frames else None

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

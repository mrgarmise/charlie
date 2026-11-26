"""Bounded demand and fan-out for the application-owned recognition pipeline."""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from threading import Lock
import time


@dataclass(eq=False)
class Demand:
    deadline: float
    frames: int
    pending: Queue = field(default_factory=lambda: Queue(1))


class InferenceScheduler:
    """All clients share the configured source/model and one owner-side inference step."""
    def __init__(self, clock=time.monotonic, *, current=None):
        self.clock = clock
        self.current = current
        self.lock = Lock()
        self.clients = {}
        self.latest = None
        self.closed = False

    def request(self, client, *, timeout, frames=1):
        if type(frames) is not int or not 1 <= frames <= 16 or not 0 < timeout <= 10:
            raise ValueError('bounded recognition request required')
        with self.lock:
            if self.closed or client in self.clients or len(self.clients) >= 8:
                raise RuntimeError('recognition capacity unavailable')
            demand = Demand(self.clock() + timeout, frames)
            if self.latest and self.fresh(self.latest):
                demand.pending.put_nowait(deepcopy(self.latest))
                demand.frames -= 1
            self.clients[client] = demand
            return demand

    def fresh(self, result):
        return (not self.closed and 0 <= self.clock() - result['at'] <= .5 and
                (self.current is None or self.current(result)))

    def cancel(self, client):
        with self.lock:
            self.clients.pop(client, None)

    def active(self):
        with self.lock:
            return any(d.frames and not d.pending.full() and d.deadline > self.clock()
                       for d in self.clients.values())

    def publish(self, result):
        packet = result['observation']
        model = result['provenance']['model'][0]['sha256']
        observation = dict(schema='charlie.recognition.result.v1', source=packet['source'],
                           generation=packet['stream_generation'], frame_id=packet['frame_id'],
                           model_sha256=model, at=packet['at'], observation=packet,
                           motion_authorized=False)
        with self.lock:
            if self.closed:
                return
            now = self.clock()
            if self.latest and all(self.latest[k] == observation[k]
                                   for k in ('source', 'generation', 'frame_id', 'model_sha256')):
                return
            self.latest = observation
            for demand in self.clients.values():
                if not demand.frames or demand.deadline <= now:
                    continue
                try:
                    demand.pending.put_nowait(deepcopy(observation))
                except Full:
                    # A slow client cannot block publication or consume its remaining quota.
                    continue
                demand.frames -= 1

    def invalidate(self):
        with self.lock:
            self.latest = None
            for demand in self.clients.values():
                try:
                    demand.pending.get_nowait()
                except Empty:
                    continue
                demand.frames += 1

    def close(self):
        with self.lock:
            self.closed = True
            self.latest = None
            self.clients.clear()


class DisplayBroker:
    """One serial owner. Per-producer queue slots, FIFO fairness and a latched STOP."""
    def __init__(self, transport, clock=time.monotonic):
        self.transport = transport
        self.clock = clock
        self.lock = Lock()
        self.queue = deque()
        self.pending = {}
        self.stopped = False
        self.displayed = None
        self.cleared = False

    def submit(self, producer, text, deadline):
        from rp2040.object_label import label_request
        if text is not None:
            label_request(text, 4500, 100)
        with self.lock:
            if self.stopped or producer in self.pending or len(self.pending) >= 8:
                raise RuntimeError('display capacity unavailable')
            receipt = Queue(1)
            self.pending[producer] = (text, deadline, receipt)
            self.queue.append(producer)
            return receipt

    def cancel(self, producer):
        with self.lock:
            self.pending.pop(producer, None)
            if producer in self.queue:
                self.queue.remove(producer)
            # A completed display intent retains its hardware TTL. Cancelling a
            # client must not clear an unrelated producer's accepted label.

    def step(self):
        with self.lock:
            if self.stopped or not self.queue:
                return
            producer = self.queue.popleft()
            text, deadline, receipt = self.pending.pop(producer)
            owns_display = self.displayed == producer
        if self.clock() > deadline:
            receipt.put_nowait(False)
            return
        try:
            if text is None:
                accepted = owns_display and self.transport.clear_object_label()
            else:
                accepted = self.transport.show_object_label(text, 4500, 100)
        except OSError:
            accepted = False
        with self.lock:
            if accepted:
                self.displayed = producer if text is not None else None
            receipt.put_nowait(bool(accepted and not self.stopped))

    def latch(self):
        with self.lock:
            self.stopped = True
            for _, _, receipt in self.pending.values():
                receipt.put_nowait(False)
            self.pending.clear()
            self.queue.clear()

    def stop(self):
        self.latch()
        with self.lock:
            if self.cleared:
                return
            self.cleared = True
        self.transport.clear_object_label()

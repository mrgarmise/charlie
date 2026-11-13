"""Best-effort latest-frame publication; never captures or interprets pixels."""
from __future__ import annotations
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import queue
import threading
import time


def runtime_dir():
    parent = Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp'))
    path = parent / f'charlie-eyes-{os.getuid()}'
    path.mkdir(mode=0o700, exist_ok=True)
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise OSError('Charlie Eyes runtime directory must be private to this user')
    return path


def atomic_json(path, data):
    temporary = path.with_name(path.name+f'.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        temporary.write_text(json.dumps(data, separators=(',', ':'), allow_nan=False))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


class PassivePublisher:
    """One replaceable pending reference, encoded only by the worker at ≤3 FPS.

    PIL capture images are owned immutable snapshots, not borrowed camera buffers.
    Submit never copies pixels, serializes evidence, accesses disk or waits on I/O.
    """
    def __init__(self, directory=None, fps=3, context=None):
        if not 2 <= fps <= 5:
            raise ValueError('passive FPS must be 2..5')
        self.directory = directory or runtime_dir()
        self.period = 1/fps
        self.context = context or {}
        self.pending = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.offers = self.dropped = self.published = self.errors = 0
        self.attached = False
        self.demand_checked_at = None
        self.submit_seconds = self.encode_seconds = 0.
        self.thread = threading.Thread(target=self._run, daemon=True, name='passive-eyes')
        self.thread.start()

    def submit(self, raw, *, timestamp, metadata=None, playfield=None):
        begin = time.perf_counter()
        try:
            self.offers += 1
            if self.pending.full():
                try:self.pending.get_nowait(); self.dropped += 1
                except queue.Empty:pass
            self.pending.put_nowait((raw, playfield, timestamp, metadata or {}))
        except Exception:
            self.errors += 1
        finally:
            self.submit_seconds += time.perf_counter()-begin

    @staticmethod
    def jpeg(frame):
        shown = frame.copy()
        shown.thumbnail((800, 600))
        stream = BytesIO(); shown.save(stream, 'JPEG', quality=65)
        return dict(image=base64.b64encode(stream.getvalue()).decode(),
                    size=list(frame.size))

    def _run(self):
        while not self.stop.wait(self.period):
            # Demand expires when a browser/launcher disappears, even if server
            # teardown is interrupted. Detached publication has no JPEG work.
            demand = read_json(self.directory/'demand.json') or {}
            self.demand_checked_at = time.monotonic()
            self.attached = self.demand_checked_at-demand.get('at', -100) <= 2
            if not self.attached:
                continue
            try:raw, crop, timestamp, metadata = self.pending.get_nowait()
            except queue.Empty:continue
            begin = time.perf_counter()
            try:
                # Preserve only existing measured output; no association/classifier.
                agency = metadata.get('agency') or {}
                tracks = (agency.get('tracking') or {}).get('detections', [])
                state = dict(metadata)
                state['learning_project'] = self.context.get('project')
                state['episode'] = self.context.get('episode')
                state.pop('agency', None)
                state['agency'] = {k:agency.get(k) for k in
                    ('identity_status','controlled_track_id','self_track_id','candidate_track_id',
                     'confidence','runner_up_confidence','event','phase','global_motion','evidence')}
                state['tracks'] = tracks[:128]
                state['omitted_tracks'] = max(0, len(tracks)-128)
                packet = dict(producer_pid=os.getpid(), capture_timestamp=timestamp,
                    published_at=time.monotonic(), raw=self.jpeg(raw),
                    playfield=self.jpeg(crop) if crop is not None else None, evidence=state)
                if metadata.get('frame_subscription'):
                    # Lossless full-resolution extension of the existing passive
                    # publication, encoded on this worker, never by a subscriber.
                    stream = BytesIO()
                    raw.save(stream, 'PNG')
                    packet['subscription_frame'] = dict(metadata['frame_subscription'],
                        png=base64.b64encode(stream.getvalue()).decode())
                atomic_json(self.directory/'latest.json', packet)
                self.published += 1
            except Exception:
                self.errors += 1
            self.encode_seconds += time.perf_counter()-begin

    def report(self):
        return dict(offers=self.offers, dropped=self.dropped, published=self.published,
            errors=self.errors, submit_seconds=self.submit_seconds,
            encode_seconds=self.encode_seconds, max_pending=1, fps_limit=1/self.period,
            attached=self.attached,demand_checked_at=self.demand_checked_at)

    def close(self):
        self.stop.set(); self.thread.join(timeout=.5)


class PublishedFrameSubscription:
    """Cross-process subscriber to existing passive publication; never a preview owner."""
    def __init__(self, source, *, max_age=.5, clock=time.monotonic, directory=None):
        self.source, self.max_age, self.clock = source, max_age, clock
        self.directory = directory or runtime_dir()
        if source == 'elegoo-v4' and directory is None:
            self.directory = self.directory/'elegoo-v4'
        if source not in ('pi-primary', 'elegoo-v4') or not 0 < max_age <= 5:
            raise ValueError('known source and bounded age required')
        self.closed = False
        self.last_id = None
        self.last_demand = None

    def read(self):
        if self.closed:
            raise InterruptedError('frame subscription closed')
        now = self.clock()
        if self.last_demand is None or now-self.last_demand >= .5:
            if self.directory.is_dir():
                atomic_json(self.directory/'demand.json', dict(at=now))
            self.last_demand = now
        path = self.directory/'latest.json'
        if not path.is_file():
            return None
        if path.stat().st_size > 32*1024*1024:
            raise ValueError('published frame exceeds bounded snapshot')
        packet = read_json(path) or {}
        data = packet.get('subscription_frame')
        if not data:
            return None  # Legacy preview JPEG cannot invent full-resolution provenance.
        if data.get('source') != self.source:
            raise ValueError('published source identity mismatch')
        if data.get('host_boot_id') != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
            raise ValueError('published frame from another boot')
        if not 0 <= now-data['received_at'] <= self.max_age:
            raise TimeoutError('stale published frame')
        if data['id'] == self.last_id:
            return None
        from PIL import Image
        import numpy as np
        import hashlib
        from vision.camera_source import CameraFrame
        raw = base64.b64decode(data['png'], validate=True)
        with Image.open(BytesIO(raw)) as image:
            if image.width*image.height > 4096*4096:
                raise ValueError('published frame geometry exceeds bound')
            bgr = np.asarray(image.convert('RGB'))[:, :, ::-1].copy()
        if hashlib.sha256(bgr.tobytes()).hexdigest() != data['sha256']:
            raise ValueError('published pixels changed')
        pixels = np.frombuffer(bgr.tobytes(), dtype=np.uint8).reshape(bgr.shape)
        from dataclasses import fields
        values = {f.name:data[f.name] for f in fields(CameraFrame) if f.name in data and f.name != 'image'}
        frame = CameraFrame(image=pixels, **values)
        frame.validate()
        if not 0 <= self.clock()-frame.received_at <= self.max_age:
            raise TimeoutError('published frame became stale during decode')
        self.last_id = frame.id
        return frame

    def wait(self, timeout=2., *, captured_after=None):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            frame = self.read()
            if frame is not None and (captured_after is None or
                    getattr(frame, 'capture_requested_at', None) is not None and
                    frame.capture_requested_at >= captured_after):
                return frame
            time.sleep(.01)
        raise TimeoutError('waiting for an authoritative camera feeder')

    def close(self):
        self.closed = True

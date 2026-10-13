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

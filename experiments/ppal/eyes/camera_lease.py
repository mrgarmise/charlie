"""Cooperative camera ownership; preview yields only at camera initialization."""
import fcntl
import os
import signal
import time
from .passive import runtime_dir, atomic_json, read_json


def camera_owner(directory):
    """A stale PID marker cannot establish live camera ownership."""
    with (directory/'camera.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return read_json(directory/'owner.json') or {}
        return {}


class CameraLease:
    def __init__(self, purpose='active', directory=None):
        if purpose not in ('active','preview'):
            raise ValueError('invalid camera purpose')
        self.directory = directory or runtime_dir()
        self.file = (self.directory/'camera.lock').open('a+')
        self.closed = False
        begin = time.monotonic()
        if purpose == 'active':
            atomic_json(self.directory/'active-request.json', dict(pid=os.getpid(),at=begin))
        try:
            while True:
                try:
                    fcntl.flock(self.file, fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    owner = read_json(self.directory/'owner.json') or {}
                    if purpose != 'active' or owner.get('purpose') != 'preview':
                        raise RuntimeError('camera already owned; passive observation only')
                    # Before any capture/control: wake the idle preview's release.
                    try:os.kill(owner['pid'],signal.SIGUSR1)
                    except (ProcessLookupError,KeyError):pass
                    if time.monotonic()-begin > 1:
                        raise RuntimeError('idle preview did not release camera; no second capture')
                    time.sleep(.01)
            self.handoff_seconds = time.monotonic()-begin
            atomic_json(self.directory/'owner.json',dict(pid=os.getpid(),purpose=purpose,at=begin))
        except Exception:
            self.file.close(); raise
        finally:
            request = read_json(self.directory/'active-request.json') or {}
            if purpose=='active' and request.get('pid')==os.getpid():
                (self.directory/'active-request.json').unlink(missing_ok=True)

    def close(self):
        if self.closed:return
        self.closed=True
        owner=read_json(self.directory/'owner.json') or {}
        if owner.get('pid')==os.getpid():
            (self.directory/'owner.json').unlink(missing_ok=True)
        fcntl.flock(self.file,fcntl.LOCK_UN);self.file.close()

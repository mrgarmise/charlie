"""Single cooperative camera lease; primary tasks preempt Active Vision safely."""
import fcntl
import os
import signal
import time
import uuid
from .passive import runtime_dir, atomic_json, read_json


def camera_owner(directory):
    with (directory/'camera.lock').open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return read_json(directory/'owner.json') or {}
        return {}


class CameraLease:
    def __init__(self, purpose='active', directory=None, *, role=None):
        if purpose not in ('active','preview'):raise ValueError('invalid camera purpose')
        self.role=role or ('primary' if purpose=='active' else 'preview')
        if self.role not in ('primary','active_vision','preview') or (purpose=='preview')!=(self.role=='preview'):
            raise ValueError('invalid camera role')
        self.directory=directory or runtime_dir()
        self.identifier=uuid.uuid4().hex
        self.file=(self.directory/'camera.lock').open('a+')
        self.closed=False
        begin=time.monotonic()
        if purpose=='active':
            atomic_json(self.directory/'active-request.json',dict(pid=os.getpid(),at=begin,
                role=self.role,request_id=self.identifier))
        try:
            while True:
                try:
                    fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    owner=read_json(self.directory/'owner.json') or {}
                    preview=purpose=='active' and owner.get('purpose')=='preview'
                    preempt=(self.role=='primary' and owner.get('role')=='active_vision')
                    if not preview and not preempt:
                        raise RuntimeError('camera already owned; passive observation only')
                    if preview:
                        try:os.kill(owner['pid'],signal.SIGUSR1)
                        except (ProcessLookupError,KeyError):pass
                    # Active Vision checks the same lease request at bounded
                    # observation/movement boundaries. No new camera or signal.
                    if time.monotonic()-begin>2:
                        raise RuntimeError('camera owner did not yield; no second capture')
                    time.sleep(.01)
            self.handoff_seconds=time.monotonic()-begin
            atomic_json(self.directory/'owner.json',dict(pid=os.getpid(),purpose=purpose,
                role=self.role,lease_id=self.identifier,at=begin))
        except Exception:
            self.file.close();raise
        finally:
            request=read_json(self.directory/'active-request.json') or {}
            if purpose=='active' and request.get('request_id')==self.identifier:
                (self.directory/'active-request.json').unlink(missing_ok=True)

    def should_yield(self):
        request=read_json(self.directory/'active-request.json') or {}
        return (self.role=='active_vision' and request.get('role')=='primary'
                and request.get('request_id')!=self.identifier
                and 0<=time.monotonic()-request.get('at',0)<2.5)

    def close(self):
        if self.closed:return
        self.closed=True
        owner=read_json(self.directory/'owner.json') or {}
        if owner.get('lease_id')==self.identifier:
            (self.directory/'owner.json').unlink(missing_ok=True)
        fcntl.flock(self.file,fcntl.LOCK_UN);self.file.close()

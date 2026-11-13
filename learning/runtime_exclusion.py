"""Same-process nested runtime exclusion; subprocesses cannot inherit ownership."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import threading

_guard=threading.RLock()
_held={}


@contextmanager
def runtime_exclusion(path):
    key=(os.getpid(),str(Path(path).resolve()))
    # Serializes threads too: a reentrant lock permits nesting only in the owner.
    if not _guard.acquire(blocking=False):
        raise BlockingIOError('runtime exclusion owned by another thread')
    try:
        if key in _held:
            yield
            return
        fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
                raise ValueError('private runtime lock required')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            _held[key]=fd
            try:yield
            finally:_held.pop(key,None)
        finally:os.close(fd)

    finally:_guard.release()

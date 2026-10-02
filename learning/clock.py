"""Explicit monotonic-clock provenance for restartable offline experiments."""
from pathlib import Path
import uuid

_process_domain = 'process-' + str(uuid.uuid4())


def domain():
    try:
        return 'boot-' + Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        # An unidentifiable new process may not claim continuity of deadlines.
        return _process_domain

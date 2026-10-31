"""Cooperative ELEGOO transport ownership; independent of all motion authority."""
from hashlib import sha256
from pathlib import Path
import fcntl
import tempfile
from urllib.parse import urlsplit


class ElegooCameraLease:
    def __init__(self, stream_url):
        url = urlsplit(stream_url)
        # Paths and query parameters may vary while using the same physical camera.
        identity = (url.hostname or '').lower()
        if not identity:
            raise ValueError('camera endpoint hostname required')
        path = Path(tempfile.gettempdir()) / ('charlie-elegoo-camera-' + sha256(identity.encode()).hexdigest() + '.lock')
        self.file = path.open('a')
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.file.close()
            raise

    def close(self):
        if not self.file.closed:
            fcntl.flock(self.file, fcntl.LOCK_UN)
            self.file.close()

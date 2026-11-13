"""Software tests must explicitly fake physical capture/serial and nonlocal video I/O."""
import urllib.request
from urllib.parse import urlsplit
import pytest


@pytest.fixture(autouse=True)
def no_unmocked_physical_io(monkeypatch):
    # Specific driver tests install their fake Picamera2/serial/HTTP dependencies
    # after this guard. Native loopback HTTP/socket fixtures remain usable.
    from vision.camera import _PiCameraDevice
    import serial
    original = urllib.request.urlopen
    def forbidden(*args, **kwargs):
        raise AssertionError('software test attempted unmocked physical device I/O')
    def local_urlopen(request, *args, **kwargs):
        url = request.full_url if hasattr(request, 'full_url') else str(request)
        if urlsplit(url).hostname not in ('127.0.0.1', 'localhost', '::1'):
            forbidden()
        return original(request, *args, **kwargs)
    monkeypatch.setattr(_PiCameraDevice, '__init__', forbidden)
    monkeypatch.setattr(serial, 'Serial', forbidden)
    monkeypatch.setattr(urllib.request, 'urlopen', local_urlopen)

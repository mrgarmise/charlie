"""Raw camera observations and exposure provenance, independent of HUD scoring."""
import time


class ObservedCamera:
    """Retain the full camera frame without changing calibration/capture callers."""
    def __init__(self, source, *, require_fresh=False):
        self.source = source
        self.require_fresh = require_fresh
        self.capture = None
        self.raw = None
        self.timestamp = None

    def read(self):
        read = getattr(self.source, 'read_fresh', None) if self.require_fresh else None
        self.raw = read() if read is not None else self.source.read()
        self.capture = getattr(self.source, 'last_capture', None) if read is not None else None
        # Pixel/exposure timestamp is shared with score evidence. Non-Pi mocks
        # and portable sources explicitly use read completion without claiming
        # exposure freshness.
        self.timestamp = (self.capture.get('first_pixel_exposure_at')
                          if self.capture else None)
        if self.timestamp is None:
            self.timestamp = time.monotonic()
        return self.raw

    def __getattr__(self, name):
        return getattr(self.source, name)

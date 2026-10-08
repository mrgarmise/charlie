"""Raw camera observations and exposure provenance, independent of HUD scoring."""
import time


class ObservedCamera:
    """Retain the full camera frame without changing calibration/capture callers."""
    def __init__(self, source, *, require_fresh=False, publisher=None, progress=None):
        self.progress = progress
        self.source = source
        self.require_fresh = require_fresh
        self.capture = None
        self.raw = None
        self.timestamp = None
        self.publisher = publisher
        self.viewer_state = None
        self.read_failures = 0
        self.recorder = None
        self.sequence = 0
        self.observation_id = None

    def read(self):
        if self.progress: self.progress.enter('camera')
        read = getattr(self.source, 'read_fresh', None) if self.require_fresh else None
        for attempt in range(3):
            try:
                self.raw = read() if read is not None else self.source.read()
                break
            except OSError as exc:
                self.read_failures += 1
                if self.progress: self.progress.update(read_failures=self.read_failures)
                if attempt == 2:
                    from .progress_supervision import ObservationFailure
                    raise ObservationFailure('camera failed three reads; evidence retained') from exc
                time.sleep(.05)
        self.capture = getattr(self.source, 'last_capture', None) if read is not None else None
        # Pixel/exposure timestamp is shared with score evidence. Non-Pi mocks
        # and portable sources explicitly use read completion without claiming
        # exposure freshness.
        self.timestamp = (self.capture.get('first_pixel_exposure_at')
                          if self.capture else None)
        if self.timestamp is None:
            self.timestamp = time.monotonic()
        self.sequence += 1
        if self.recorder is not None:
            self.observation_id=self.recorder.capture(self.raw,dict(timestamp=self.timestamp,capture=self.capture,
                sequence=self.sequence,read_failures_total=self.read_failures,
                timestamp_origin='first_pixel_exposure_at' if self.capture and self.capture.get('first_pixel_exposure_at') is not None else 'read_completion',
                clock='source monotonic exposure' if self.capture else 'process monotonic read completion'))
        if self.progress: self.progress.fresh(self.timestamp)
        if self.publisher is not None:
            self.viewer_state = {'attached':self.publisher.attached,
                                 'checked_at':self.publisher.demand_checked_at}
            self.publisher.submit(self.raw, timestamp=self.timestamp,
                                  metadata={'phase':'capture/preflight', 'identity_status':'unknown'})
        return self.raw

    def __getattr__(self, name):
        return getattr(self.source, name)

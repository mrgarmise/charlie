"""Authoritative feeder adapters and subscriber views of one BGR frame contract."""
from dataclasses import dataclass, fields
import time
from typing import Protocol
from uuid import uuid4

from vision.mobile_perception import MobileFrame, MobileFrameSource


@dataclass(frozen=True)
class CameraFrame(MobileFrame):
    camera_identity: dict | None = None
    stream_generation: str | None = None
    capture_metadata: dict | None = None
    capture_requested_at: float | None = None


class CameraSource(Protocol):
    def read(self) -> MobileFrame: ...
    def close(self): ...


class _PiCapture:
    """Existing Pi/libcamera lease and owner; no focus or calibration commands."""
    def __init__(self, *, camera=None, clock=time.monotonic, role='primary'):
        if camera is None:
            from vision.camera import _PiCameraDevice
            camera = _PiCameraDevice(role=role)
        self.camera, self.clock = camera, clock
        self.session, self.sequence, self.closed = uuid4().hex, 0, False
        properties = getattr(getattr(camera, 'picam2', None), 'camera_properties', {})
        self.identity = dict(source='pi-primary', transport='libcamera',
                             model=properties.get('Model', 'unknown'),
                             device_id=properties.get('Id', 'primary camera'))

    def read(self):
        if self.closed:
            raise InterruptedError('Pi source closed')
        # Picamera2 RGB888 uses BGR byte order (existing Eyes source contract).
        requested_at = self.clock()
        metadata = {}
        if hasattr(getattr(self.camera, 'picam2', None), 'capture_request'):
            request = self.camera.picam2.capture_request(flush=True)
            try:
                rgb = request.make_array('main').copy()
                metadata = dict(request.get_metadata())
            finally:
                request.release()
        else:
            rgb = self.camera.read()
        at = self.clock()
        self.sequence += 1
        frame = CameraFrame(f'{self.session}:{self.sequence}', rgb.copy(), at,
            source='pi-primary', sequence=self.sequence, authentic=True, compression='raw',
            camera_identity=dict(self.identity), stream_generation=self.session,
            capture_requested_at=requested_at, capture_metadata=metadata)
        frame.validate()
        return frame

    def close(self):
        if not self.closed:
            self.closed = True
            self.camera.close()


class _ElegooCapture(MobileFrameSource):
    """Reuse latest-frame MJPEG reader and its bounded freshness/recovery checks."""
    def __init__(self, *, stream_url='http://192.168.4.1:81/stream', camera=None, **kwargs):
        if camera is None:
            from hardware.elegoo_camera import _ElegooCameraDevice
            camera = _ElegooCameraDevice(stream_url=stream_url, timeout=2)
        super().__init__(camera, **kwargs)
        self.identity = dict(source='elegoo-v4', transport='MJPEG',
                             endpoint=getattr(camera, 'stream_url', stream_url), model='ELEGOO camera')

    def read(self):
        frame = super().read()
        values = {f.name: getattr(frame, f.name) for f in fields(frame)}
        return CameraFrame(**values, camera_identity=dict(self.identity),
            stream_generation=f'{self.session}:{getattr(self.camera, "_generation", 0)}')

    def close(self):
        super().close()
        thread = getattr(self.camera, '_thread', None)
        if thread is not None and thread.is_alive():
            raise TimeoutError('ELEGOO reader has not released ownership')


def capture_factory(name, *, stream_url='http://192.168.4.1:81/stream', pi_role='primary'):
    if name == 'pi':
        return _PiCapture(role=pi_role)
    if name == 'elegoo':
        return _ElegooCapture(stream_url=stream_url, reconnect_attempts=0)
    raise ValueError('unknown camera source')


class CameraSubscription:
    """Perception selects a bus subscription, never a camera lifetime."""
    def __init__(self, bus=None, *, on_change=None, clock=time.monotonic):
        self.bus, self.on_change, self.clock = bus, on_change, clock
        self.active = self.name = None
        self.closed = False

    def switch(self, name):
        if self.closed:
            raise InterruptedError('camera subscription closed')
        sources = {'pi': 'pi-primary', 'elegoo': 'elegoo-v4'}
        if name not in sources:
            raise ValueError('unknown camera source')
        if self.active is not None and self.name == name:
            return
        if self.on_change:
            self.on_change(self.name, name)
        if self.active is not None:
            self.active.close()
        if self.bus is None:
            from stimulus.bus import subscribe_to_frames
            self.active = subscribe_to_frames(sources[name], clock=self.clock)
        else:
            self.active = self.bus.subscribe_frames(sources[name], clock=self.clock)
        self.name = name

    def read(self):
        if self.closed or self.active is None:
            raise InterruptedError('no active camera subscription')
        return self.active.read()

    def close(self):
        if self.active is not None:
            self.active.close()
            self.active = self.name = None
        self.closed = True


class TrackingCamera:
    """Legacy RGB tracking view of a subscription, with unchanged coordinates."""
    def __init__(self, subscription):
        self.subscription = subscription

    def read(self):
        import cv2
        frame = self.subscription.read()
        if frame is None:
            return None
        # Preserve the established primary VisionStimulus byte contract. Object
        # inference always consumes the canonical BGR frame directly.
        rgb = frame.image.copy() if frame.source == 'pi-primary' else frame.image[:, :, ::-1].copy()
        if rgb.shape[:2] != (720, 1280):
            rgb = cv2.resize(rgb, (1280, 720))
        return rgb

    def close(self):
        self.subscription.close()

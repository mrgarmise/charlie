"""One owned camera, one BGR frame contract; adapters do not authorize motion."""
from dataclasses import dataclass, fields
import time
from typing import Protocol
from uuid import uuid4

from vision.mobile_perception import MobileFrame, MobileFrameSource


@dataclass(frozen=True)
class CameraFrame(MobileFrame):
    camera_identity: dict | None = None
    stream_generation: str | None = None


class CameraSource(Protocol):
    def read(self) -> MobileFrame: ...
    def close(self): ...


class PiCameraSource:
    """Existing Pi/libcamera lease and owner; no focus or calibration commands."""
    def __init__(self, *, camera=None, clock=time.monotonic):
        if camera is None:
            from vision.camera import Camera
            camera = Camera()
        self.camera, self.clock = camera, clock
        self.session, self.sequence, self.closed = uuid4().hex, 0, False
        properties = getattr(getattr(camera, 'picam2', None), 'camera_properties', {})
        self.identity = dict(source='pi-primary', transport='libcamera',
                             model=properties.get('Model', 'unknown'),
                             device_id=properties.get('Id', 'primary camera'))

    def read(self):
        if self.closed:
            raise InterruptedError('Pi source closed')
        # Camera.read is RGB; HailoObjects and the shared frame contract are BGR.
        rgb = self.camera.read()
        at = self.clock()
        self.sequence += 1
        frame = CameraFrame(f'{self.session}:{self.sequence}', rgb[:, :, ::-1].copy(), at,
            source='pi-primary', sequence=self.sequence, authentic=True, compression='raw',
            camera_identity=dict(self.identity), stream_generation=self.session)
        frame.validate()
        return frame

    def close(self):
        if not self.closed:
            self.closed = True
            self.camera.close()


class ElegooCameraSource(MobileFrameSource):
    """Reuse latest-frame MJPEG reader and its bounded freshness/recovery checks."""
    def __init__(self, *, stream_url='http://192.168.4.1:81/stream', camera=None, **kwargs):
        if camera is None:
            from hardware.elegoo_camera import ElegooCamera
            camera = ElegooCamera(stream_url=stream_url, timeout=2)
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


def create_camera_source(name, *, stream_url='http://192.168.4.1:81/stream'):
    if name == 'pi':
        return PiCameraSource()
    if name == 'elegoo':
        return ElegooCameraSource(stream_url=stream_url, reconnect_attempts=3)
    raise ValueError('unknown camera source')


class CameraSources:
    """Close-before-open switching. Failed release prevents a second acquisition."""
    def __init__(self, factory=create_camera_source, *, on_change=None):
        self.factory, self.on_change = factory, on_change
        self.active = self.name = None
        self.closed = False

    def switch(self, name):
        if self.closed:
            raise InterruptedError('camera sources closed')
        if name not in ('pi', 'elegoo'):
            raise ValueError('unknown camera source')
        if self.active is not None and self.name == name:
            return
        if self.on_change:
            self.on_change(self.name, name)
        if self.active is not None:
            self.active.close()  # Keep owner reference if release raises.
        self.active = self.name = None
        source = self.factory(name)  # Failure leaves no fallback or old frame.
        self.active, self.name = source, name

    def read(self):
        if self.closed or self.active is None:
            raise InterruptedError('no active camera source')
        return self.active.read()

    def close(self):
        if self.active is not None:
            self.active.close()
            self.active = self.name = None
        self.closed = True


class TrackingCamera:
    """Legacy VisionStimulus view of the same source; preserve 1280x720 coordinates."""
    def __init__(self, sources):
        self.sources = sources

    def read(self):
        import cv2
        frame = self.sources.read()
        rgb = frame.image[:, :, ::-1].copy()
        if rgb.shape[:2] != (720, 1280):
            rgb = cv2.resize(rgb, (1280, 720))
        return rgb

    def close(self):
        self.sources.close()

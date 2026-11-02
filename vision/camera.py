"""Charlie's Raspberry Pi camera hardware interface."""

from __future__ import annotations

import time



class _PiCameraDevice:
    def __init__(self, width=1280, height=720, *, purpose='active', role=None):
        from picamera2 import Picamera2
        from experiments.ppal.eyes.camera_lease import CameraLease
        self.lease_error = None
        self.lease = CameraLease(purpose) if role is None else CameraLease(purpose, role=role)
        self.closed = False
        try:
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(
                main={"size": (width, height), "format": "RGB888"})
            self.picam2.configure(config)
            self.picam2.start()
        except Exception:
            try:
                if hasattr(self, 'picam2'):self.picam2.close()
            finally:
                if self.lease:self.lease.close()
            raise

    def read(self):
        return self.picam2.capture_array()

    def autofocus(self):
        """Enable continuous hardware autofocus."""
        from libcamera import controls
        self.picam2.set_controls({
            "AfMode": controls.AfModeEnum.Continuous,
        })

    def manual_focus(self, lens_position: float, settle_time: float = 0.08):
        """Put the lens in manual mode and move it to a requested position."""
        from libcamera import controls
        self.picam2.set_controls({
            "AfMode": controls.AfModeEnum.Manual,
            "LensPosition": float(lens_position),
        })

        if settle_time > 0:
            time.sleep(settle_time)

    def lens_position(self):
        """Return the lens position reported by libcamera."""
        value = self.picam2.capture_metadata().get("LensPosition")
        return None if value is None else float(value)

    def metadata(self):
        return dict(self.picam2.capture_metadata())

    def close(self):
        if self.closed:return
        self.closed = True
        try:
            try:self.picam2.stop()
            finally:self.picam2.close()
        finally:
            if self.lease:self.lease.close()


class _SnapshotRequest:
    def __init__(self, frame):self.frame=frame
    def get_metadata(self):return dict(self.frame.capture_metadata or {})
    def make_array(self, name):
        if name != 'main':raise ValueError('published main stream only')
        return self.frame.image.copy()
    def release(self):pass


class _PublishedPi:
    def __init__(self, camera):self.camera=camera
    @property
    def camera_controls(self):return dict(self.camera._information().get('controls',{}))
    @property
    def camera_properties(self):return dict(self.camera._information().get('properties',{}))
    def capture_request(self, *, flush=False):
        after=time.monotonic() if flush else None
        frame=self.camera.subscription.wait(timeout=2,captured_after=after)
        self.camera._last_frame=frame
        return _SnapshotRequest(frame)
    def capture_metadata(self):
        self.camera._last_frame=self.camera.subscription.wait(timeout=2)
        return dict(self.camera._last_frame.capture_metadata or {})
    def set_controls(self, settings):
        owner=self.camera._owner()
        if owner is None:raise PermissionError('remote subscriber cannot configure a physical camera')
        owner.configure(settings,role=self.camera.role)


class Camera:
    """Legacy camera API backed EXCLUSIVELY by authoritative published frames.

    This facade never instantiates Picamera2 or acquires a physical camera lease.
    Focus/exposure requests are sent to the feeder's bounded, role-checked queue.
    """
    def __init__(self,width=1280,height=720,*,purpose='active',role=None):
        from stimulus.bus import subscribe_to_frames
        self.role=role or ('preview' if purpose=='preview' else 'primary')
        if self.role not in ('preview','primary','active_vision'):
            raise ValueError('invalid camera role')
        self.is_subscription=True
        self.subscription=subscribe_to_frames('pi-primary')
        self.subscription.role=self.role
        self.picam2=_PublishedPi(self)
        self.closed=False
        self.lease_error=None
        self._last_frame=None

    def _owner(self):
        from stimulus.bus import application_frames
        bus=application_frames()
        return bus.frame_owners.get('pi-primary') if bus is not None else None

    def _information(self):
        owner=self._owner()
        if owner is not None and not getattr(owner,'camera_info',{}):
            self._last_frame=self.subscription.wait(timeout=2)
        return getattr(owner,'camera_info',{}) if owner is not None else {}

    @property
    def lease(self):
        owner=self._owner()
        info=self._information()
        if owner is None or owner.source is None or not owner.thread.is_alive() or not info.get('role'):return None
        class LeaseView:
            role=info['role']
            def should_yield(self):
                if self.role!='active_vision':return False
                with owner.bus.lock:
                    primary=any(getattr(s,'role',None)=='primary' and not s.closed for s in owner.bus.subscribers)
                return primary or bool(owner.camera_info.get('yield_requested'))
        return LeaseView()

    def read(self):
        self._last_frame=self.subscription.wait(timeout=2)
        return self._last_frame.image.copy()

    def autofocus(self):
        from libcamera import controls
        self.picam2.set_controls({'AfMode':controls.AfModeEnum.Continuous})

    def manual_focus(self,lens_position,settle_time=.08):
        from libcamera import controls
        self.picam2.set_controls({'AfMode':controls.AfModeEnum.Manual,'LensPosition':float(lens_position)})
        if settle_time>0:time.sleep(settle_time)

    def metadata(self):return self.picam2.capture_metadata()
    def lens_position(self):
        value=self.metadata().get('LensPosition')
        return None if value is None else float(value)
    def close(self):
        if not self.closed:
            self.subscription.close()
            self.closed=True

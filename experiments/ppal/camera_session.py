"""One live camera and current-observation calibration per marathon.

No persisted profile is loaded. Episode borrowers cannot close the hardware.
The owner must be closed before offline learning or another marathon.
"""
from uuid import uuid4


class CameraSession:
    def __init__(self, factory):
        self.factory = factory
        self.id = 'camera-session:' + uuid4().hex
        self.source = None
        self.calibration = None
        self.report = None
        self.reference = None
        self.origin = None
        self.closed = False
        self.invalid = False

    def borrow(self):
        if self.closed or self.invalid:
            raise RuntimeError('camera session closed or invalid; new marathon preflight required')
        if self.source is None:
            self.source = self.factory()
        return _BorrowedCamera(self)

    def establish(self, source, output, preflight, *, seed_position=None):
        if self.closed or self.invalid:
            raise RuntimeError('invalid camera session')
        reused = self.calibration is not None
        if not reused:
            self.calibration, self.report = preflight(source, output, seed_position=seed_position)
            if self.calibration is None or self.report.get('status')!='usable':
                self.invalid=True
                raise ValueError('current camera preflight did not qualify a usable view')
            frame=getattr(source,'raw',None)
            if frame is not None:self.reference=self.calibration.apply(frame).copy()
            self.origin = str(output.resolve())
        return self.calibration, dict(self.report, camera_session=dict(
            id=self.id, reused=reused, qualification_origin=self.origin,
            scope='current uninterrupted live camera session; not a saved profile'))

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.source is not None:
            self.source.close()


class _BorrowedCamera:
    def __init__(self, owner):
        self.owner = owner

    def __getattr__(self, name):
        return getattr(self.owner.source, name)

    def close(self):
        # Episode recorder and controller are closed separately by the player.
        pass


class CameraFeeder(CameraSession):
    """Application-owned capture extension of the existing borrowed-camera session.

    Only this owner opens/configures/recovers/closes a physical transport. Frame
    consumers subscribe to StimulusBus; subscriber close/switch never closes us.
    Existing physical leases remain the cross-process admission authority.
    """
    def __init__(self, factory, bus, source_id, *, recovery_attempts=3, period=.02, publisher=None):
        super().__init__(factory)
        import threading
        if type(recovery_attempts) is not int or not 0 <= recovery_attempts <= 10 or not .01 <= period <= 1:
            raise ValueError('bounded feeder recovery/cadence required')
        self.bus, self.source_id = bus, source_id
        self.recovery_attempts, self.period = recovery_attempts, period
        self.stop = threading.Event()
        self.thread = None
        self.frames = self.faults = 0
        self.publisher = publisher
        import queue
        self.commands = queue.Queue(maxsize=8)
        self.camera_info = {}

    def borrow(self):
        return self.bus.subscribe_frames(self.source_id)

    def start(self):
        import threading
        if self.closed or self.thread is not None:
            raise RuntimeError('feeder already started or closed')
        self.bus.claim_frames(self.source_id, self)
        self.thread = threading.Thread(target=self._capture, name='camera-feeder:'+self.source_id, daemon=True)
        try:
            self.thread.start()
        except BaseException:
            self.bus.release_frames(self.source_id, self)
            self.thread = None
            raise
        return self

    def _capture(self):
        import time
        consecutive = 0
        try:
            while not self.stop.is_set():
                try:
                    if self.source is None:
                        self.source = self.factory()
                        camera = getattr(self.source, 'camera', None)
                        native = getattr(camera, 'picam2', None)
                        self.camera_info = dict(controls=dict(getattr(native,'camera_controls',{})),
                            properties=dict(getattr(native,'camera_properties',{})),
                            role=getattr(getattr(camera,'lease',None),'role',None))
                    while not self.commands.empty():
                        command, role, deadline, cancelled, reply = self.commands.get_nowait()
                        try:
                            if cancelled.is_set() or time.monotonic() >= deadline:
                                raise TimeoutError('expired camera configuration request')
                            camera = getattr(self.source, 'camera', None)
                            lease = getattr(camera, 'lease', None)
                            if lease is None or lease.role != role or role not in ('primary', 'active_vision'):
                                raise PermissionError('existing camera role/lease required for configuration')
                            camera.picam2.set_controls(command)
                            reply.put_nowait(None)
                        except Exception as exc:
                            reply.put_nowait(exc)
                    lease = getattr(getattr(self.source,'camera',None),'lease',None)
                    if lease is not None:
                        self.camera_info['yield_requested'] = lease.should_yield()
                    frame = self.source.read()
                    if self.stop.is_set():
                        break
                    # Capture adapters copy borrowed buffers before publishing.
                    from dataclasses import replace
                    import numpy as np
                    pixels = np.frombuffer(frame.image.tobytes(), dtype=frame.image.dtype).reshape(frame.image.shape)
                    frame = replace(frame, image=pixels)
                    self.bus.publish_frame(self.source_id, self, frame)
                    self.frames += 1
                    if self.publisher is not None and self.publisher.attached:
                        try:
                            from PIL import Image
                            self.publisher.submit(Image.fromarray(frame.image[:, :, ::-1]),
                                timestamp=frame.received_at, metadata=dict(frame_subscription=dict(frame.metadata(),
                                    host_boot_id=__import__('pathlib').Path('/proc/sys/kernel/random/boot_id').read_text().strip())))
                        except Exception:
                            pass  # Passive observer cannot interrupt authoritative capture.
                    consecutive = 0
                    self.stop.wait(self.period)
                except Exception as exc:
                    self.faults += 1
                    self.bus.frame_fault(self.source_id, self, type(exc).__name__+': '+str(exc))
                    if self.source is not None:
                        # Failed release prevents a second physical capture.
                        try:
                            self.source.close()
                            self.source = None
                        except Exception as release_error:
                            self.bus.frame_fault(self.source_id,self,'capture release failed: '+str(release_error))
                            break
                    if self.stop.is_set() or consecutive >= self.recovery_attempts:
                        break
                    consecutive += 1
                    self.stop.wait(min(2., .1 * 2**consecutive))
        finally:
            if self.source is not None:
                try:
                    self.source.close()
                    self.source = None
                except Exception as exc:
                    self.bus.frame_fault(self.source_id, self, 'capture release failed: '+str(exc))

    def configure(self, settings, *, role):
        import queue
        allowed = {'AfMode', 'LensPosition', 'ExposureValue', 'AeEnable', 'ExposureTime',
                   'AnalogueGain', 'AwbEnable', 'ColourGains'}
        if not settings or not set(settings) <= allowed or self.closed:
            raise PermissionError('unsupported feeder configuration request')
        reply = queue.Queue(maxsize=1)
        import threading, time
        cancelled = threading.Event()
        self.commands.put_nowait((dict(settings), role, time.monotonic()+2, cancelled, reply))
        try:
            result = reply.get(timeout=2)
        except queue.Empty:
            cancelled.set()
            raise TimeoutError('camera configuration not acknowledged by feeder')
        if isinstance(result, Exception):
            raise result

    def close(self):
        if self.closed:
            return
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=3)
            if self.thread.is_alive():
                # Application shutdown may interrupt a blocked network capture.
                if self.source is not None:
                    self.source.close()
                self.thread.join(timeout=3)
                if self.thread.is_alive():
                    raise TimeoutError('camera feeder did not stop; ownership retained')
        if self.source is not None:
            self.source.close()
            self.source = None
        self.bus.release_frames(self.source_id, self)
        self.closed = True

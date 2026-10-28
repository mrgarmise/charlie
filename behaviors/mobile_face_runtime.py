"""Normal application face perception and request adapter, no hardware owners."""
from behaviors.mobile_face_track import MobileFaceTrackBehavior
from motion.mobile_requests import MobileRequests


class MobileFaceRuntime:
    def __init__(self, frame_bus, event_bus, executor, *, detector=None):
        if detector is None:
            from vision.mobile_face import MobileFaceDetector
            detector = MobileFaceDetector()
        self.detector, self.bus = detector, event_bus
        self.subscription = frame_bus.subscribe_frames('elegoo-v4', max_age=.25)
        self.mobile = MobileRequests(executor=executor)
        self.behavior = MobileFaceTrackBehavior(mobile=self.mobile)
        self.last_status = None

    def observe(self):
        try:
            frame = self.subscription.read()
            if frame is None:
                return
            face = self.detector.detect(frame.image)
            self.bus.emit('elegoo_face_observation', dict(service=self,frame=frame,face=face))
        except (OSError,ValueError) as exc:
            self.behavior.face_lost()
            self.mobile.stop()
            self.last_status = dict(state='SOURCE_FAULT',reason=str(exc))

    def attend(self, observation):
        self.mobile.bind_frame(observation['frame'])
        try:
            self.last_status = self.behavior.update_face(observation['face'])
        except (PermissionError,ValueError,RuntimeError,OSError) as exc:
            self.mobile.stop()
            self.last_status = dict(state='MOTION_UNAVAILABLE',reason=str(exc),physical_qualification=False)
        return self.last_status

    def yield_attention(self):
        # Do not issue a global STOP merely because an idle face observer yields
        # to a selected pet behavior. Cancel only face-owned alignment/search.
        self.behavior.face_lost()
        if getattr(self.behavior, '_sentry_turn_state', None) is not None:
            self.mobile.stop()
            self.behavior._sentry_turn_state = None

    def close(self):
        try:
            self.behavior.stop()
        finally:
            self.subscription.close()

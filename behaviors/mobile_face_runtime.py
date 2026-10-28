"""Normal application face perception and request adapter, no hardware owners."""
from behaviors.mobile_face_track import MobileFaceTrackBehavior
from motion.mobile_requests import MobileRequests


class MobileFaceRuntime:
    def __init__(self, frame_bus, event_bus, executor, *, detector=None, memory_gateway=None):
        if detector is None:
            from vision.mobile_face import MobileFaceDetector
            detector = MobileFaceDetector()
        self.detector, self.bus = detector, event_bus
        self.subscription = frame_bus.subscribe_frames('elegoo-v4', max_age=.25)
        self.mobile = MobileRequests(executor=executor)
        self.behavior = MobileFaceTrackBehavior(mobile=self.mobile)
        self.search_memory = None
        self.memory_gateway = memory_gateway
        self.preference_loaded = False
        if memory_gateway is not None:
            from memory.head_search import HeadSearchMemory
            self.search_memory = HeadSearchMemory(memory_gateway)
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
            # Preserve the original search-memory preference only when the
            # real local sweep has reached its sentry decision. No memory
            # access grants physical authority or runs on the producer thread.
            if (self.memory_gateway is not None and not self.preference_loaded
                    and observation['frame'].authentic is True and observation['face'] is None
                    and self.behavior.search_mode == 'DONE'):
                self.preference_loaded = True
                try:
                    from memory.head_search import preferred_direction
                    from uuid import uuid4
                    self.behavior.search_preference = preferred_direction(
                        self.memory_gateway, decision_id='head:'+uuid4().hex)
                except Exception as exc:
                    self.memory_error = type(exc).__name__
            self.last_status = self.behavior.update_face(observation['face'])
            if self.search_memory is not None and observation['frame'].authentic is True:
                try:self.search_memory.observe(self.behavior,observation['face'],self.last_status)
                except Exception as exc:
                    # Memory availability must not conceal or change motion.
                    self.memory_error = type(exc).__name__
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

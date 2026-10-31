import time

class VisionStimulus:

    def __init__(self, camera, detector, bus, *, neck_observer=None, frame_observer=None):
        self.camera = camera
        self.detector = detector
        self.bus = bus
        self.target_visible = False
        self.neck_observer = neck_observer
        self.frame_observer = frame_observer
        self.corrected_frame = None
        self.last_frame_at = None

    def update(self):
        frame = self.camera.read()
        if frame is None:
            if self.target_visible and self.last_frame_at is not None and time.monotonic()-self.last_frame_at>.5:
                self.bus.emit('vision_lost')
                self.target_visible=False
            return
        self.last_frame_at=time.monotonic()
        target = self.detector.detect(frame)
        source_frame = getattr(self.camera, "last_frame", None)
        if source_frame is not None:
            self.bus.emit("vision_source_frame", source_frame)

        if self.frame_observer is not None:
            corrected = self.frame_observer(frame, target)
            self.corrected_frame = frame if corrected is None else corrected
        elif self.neck_observer is not None:
            # A moving color target is not a fixed-scene neck reference.
            self.neck_observer(visual_tracking_available=bool(target),
                observation_evidence=dict(frame_available=frame is not None,
                    target_visible=bool(target), fixed_scene_displacement='unavailable; target may move'))

        if target:
            x = target["x"]
            y = target["y"]

            self.bus.emit("vision_target", (x, y))

            if not self.target_visible:
                self.target_visible = True

        else:
            if self.target_visible:
                self.bus.emit("vision_lost")
                self.target_visible = False

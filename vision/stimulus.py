class VisionStimulus:

    def __init__(self, camera, detector, bus, *, neck_observer=None):
        self.camera = camera
        self.detector = detector
        self.bus = bus
        self.target_visible = False
        self.neck_observer = neck_observer

    def update(self):
        frame = self.camera.read()
        target = self.detector.detect(frame)

        if self.neck_observer is not None:
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

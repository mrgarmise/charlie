class VisionStimulus:

    def __init__(self, camera, detector, bus):
        self.camera = camera
        self.detector = detector
        self.bus = bus
        self.target_visible = False

    def update(self):
        frame = self.camera.read()
        target = self.detector.detect(frame)

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
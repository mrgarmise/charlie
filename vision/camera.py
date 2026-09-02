from picamera2 import Picamera2


class Camera:
    def __init__(self, width=1280, height=720):
        self.picam2 = Picamera2()

        config = self.picam2.create_preview_configuration(
            main={
                "size": (width, height),
                "format": "RGB888",
            }
        )

        self.picam2.configure(config)
        self.picam2.start()

    def read(self):
        return self.picam2.capture_array()

    def close(self):
        self.picam2.stop()

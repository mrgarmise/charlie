from vision.camera import Camera
from vision.detector import ColorDetector
from vision.stimulus import VisionStimulus
from stimulus.bus import StimulusBus


lower = [105, 150, 70]
upper = [125, 255, 160]

camera = Camera()
detector = ColorDetector(lower, upper)
bus = StimulusBus()

vision = VisionStimulus(camera, detector, bus)

try:
    while True:
        vision.update()

        for event, data in bus.get_all():
            print(event, data, flush=True)

finally:
    camera.close()
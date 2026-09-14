import time

from motion.controller import Deck
from attention.manager import AttentionManager

from stimulus.bus import StimulusBus
from stimulus.keyboard import KeyboardStimulus

from behaviors.idle import IdleBehavior

from vision.camera import Camera
from vision.detector import ColorDetector
from vision.stimulus import VisionStimulus


deck = Deck()

bus = StimulusBus()
attention = AttentionManager(bus)

KeyboardStimulus(bus)

camera = Camera()

detector = ColorDetector(
    lower=[105, 150, 70],
    upper=[125, 255, 160],
)

vision = VisionStimulus(
    camera,
    detector,
    bus
)

# Start idle explicitly.
bus.emit("idle")

try:
    while True:
        vision.update()
        attention.update(deck)
        time.sleep(0.02)

finally:
    attention.close()
    camera.close()

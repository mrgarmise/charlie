import time
import os
from pathlib import Path

from motion.controller import Deck
from attention.manager import AttentionManager

from stimulus.bus import StimulusBus
from stimulus.keyboard import KeyboardStimulus

from behaviors.idle import IdleBehavior

from vision.camera import Camera
from vision.detector import ColorDetector
from vision.stimulus import VisionStimulus


deck = Deck()
from hardware.calibration_service import CalibrationService
neck = CalibrationService.open(deck.body, Path(os.environ.get(
    'CHARLIE_NECK_STATE', str(Path.home() / '.local/share/charlie/neck'))))
deck.calibration = neck
neck.refresh()
neck.attach_brain(authorized=os.environ.get('CHARLIE_NECK_MOTION_AUTHORIZED') == '1',
    supervised=os.environ.get('CHARLIE_NECK_SUPERVISED') == '1')

bus = StimulusBus()
attention = AttentionManager(bus, mobile_enabled=os.environ.get('CHARLIE_MOBILE_ENABLED') == '1')

KeyboardStimulus(bus)

camera = Camera()

detector = ColorDetector(
    lower=[105, 150, 70],
    upper=[125, 255, 160],
)
if os.environ.get('CHARLIE_VISION_TARGET') == 'face':
    from vision.detector import FaceDetector
    detector = FaceDetector(Path(__file__).resolve().parent / 'face_detection_yunet.onnx')

vision = VisionStimulus(
    camera,
    detector,
    bus,
    frame_observer=deck.observe_frame
)

# Start idle explicitly.
bus.emit("idle")
attention.update(deck)

try:
    while True:
        vision.update()
        attention.update(deck)
        time.sleep(0.02)

finally:
    attention.close()
    camera.close()
    try:
        neck.close()
    finally:
        try:
            deck.stop()
        finally:
            deck.body.close()

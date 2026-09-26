#!/usr/bin/env python3
import time
import sqlite3
from uuid import uuid4

from hardware.elegoo_camera import ElegooCamera
from vision.mobile_face import MobileFaceDetector
from behaviors.mobile_face_track import MobileFaceTrackBehavior
from memory.gateway import MemoryGateway
from memory.head_search import HeadSearchMemory, preferred_direction


camera = ElegooCamera()

detector = MobileFaceDetector(
    model_path="face_detection_yunet.onnx"
)

memory = MemoryGateway()
behavior = MobileFaceTrackBehavior(search_preference=preferred_direction(memory, decision_id=f"head:{uuid4().hex}"))
search_memory = HeadSearchMemory(memory)

print("Charlie Elegoo Head 2")
print("Face tracking + yaw-guided ATTEND")
print("Forward movement disabled")
print("Ctrl+C to stop")

behavior.start()

try:
    with camera:
        while True:
            frame = camera.read()
            face = detector.detect(frame)
            status = behavior.update_face(
                face
            )
            try:
                search_memory.observe(behavior, face, status)
            except (OSError, sqlite3.Error) as error:
                print(f"\nHead memory queue unavailable: {error}")

            if face is not None:
                print(
                    f"{status['state']:12s} "
                    f"x={face['normalized_x']:.2f} "
                    f"score={face['score']:.2f} "
                    f"pan={behavior.pan:3d}",
                    end="\r",
                    flush=True,
                )

except KeyboardInterrupt:
    print("\nStopping.")

finally:
    behavior.stop()
    camera.close()
    print("Head 2 stopped.")

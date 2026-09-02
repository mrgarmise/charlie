import cv2
import time
from vision.camera import Camera

camera = Camera()

last_print = 0

while True:
    frame = camera.read()
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

    height, width = frame.shape[:2]
    x = width // 2
    y = height // 2

    now = time.time()

    if now - last_print >= 0.5:
        print("RGB:", frame[y, x], "HSV:", hsv[y, x])
        last_print = now

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.close()

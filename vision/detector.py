import cv2
import numpy as np


class ColorDetector:
    def __init__(self, lower, upper):
        self.lower = np.array(lower, dtype=np.uint8)
        self.upper = np.array(upper, dtype=np.uint8)

    def detect(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

        mask = cv2.inRange(hsv, self.lower, self.upper)

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        if area < 500:
            return None

        x, y, w, h = cv2.boundingRect(largest)

        return {
            "x": x + w // 2,
            "y": y + h // 2,
            "width": w,
            "height": h,
            "area": area,
        }

import cv2

from vision.camera import Camera
from vision.detector import ColorDetector


# Orange color range
lower = [105, 150, 70]
upper = [125, 255, 160]

camera = Camera()
detector = ColorDetector(lower, upper)
try:
    while True:
        frame = camera.read()
        target = detector.detect(frame)

        center_x = frame.shape[1] // 2

        if target:
            x = target["x"]
            error = x - center_x

            print(
                f"Target x={x:4d}  "
                f"Center={center_x:4d}  "
                f"Error={error:+4d}"
            )

            cv2.line(
                frame,
                (center_x, 0),
                (center_x, frame.shape[0]),
                (0, 255, 0),
                2,
            )

            cv2.drawMarker(
                frame,
                (x, target["y"]),
                (255, 0, 0),
                cv2.MARKER_CROSS,
                40,
                3,
            )
        else:
            print("Target: not detected")

        cv2.imshow(
            "Charlie Vision",
            cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    camera.close()
    cv2.destroyAllWindows()
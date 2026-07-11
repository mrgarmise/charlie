import cv2

class Tracker:
    def __init__(self, cam_index=0):
        self.cap = cv2.VideoCapture(cam_index)

    def get_frame_and_error(self):
        ret, frame = self.cap.read()
        if not ret:
            return None, 0

        h, w, _ = frame.shape

        # Frame center
        cx = w // 2

        # Placeholder "target"
        # (later we replace this with real detection)
        object_x = w // 2 + 100  # pretend object is right of center

        error = object_x - cx

        # -----------------------------
        # VISUAL OVERLAY (HUD)
        # -----------------------------

        # center line
        cv2.line(frame, (cx, 0), (cx, h), (0, 255, 0), 2)

        # fake object marker
        cv2.circle(frame, (object_x, h // 2), 10, (0, 0, 255), -1)

        # error text
        cv2.putText(
            frame,
            f"Error: {error}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        return frame, error

import cv2

class Tracker:
    def __init__(self, cam_index=0):
        if cam_index!=0:raise ValueError('explicit published camera identity required')
        from stimulus.bus import subscribe_to_frames
        self.subscription=subscribe_to_frames('pi-primary')

    def get_frame_and_error(self):
        packet = self.subscription.read()
        if packet is None:
            return None, 0

        frame=packet.image.copy()
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

    def close(self):
        self.subscription.close()

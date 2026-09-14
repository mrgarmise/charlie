import cv2


class MobileFaceDetector:
    """
    YuNet face detector + stable face selection for the Elegoo head.

    Initial acquisition:
        largest visible face

    Continued tracking:
        prefer the face nearest the previously tracked horizontal
        position, reducing target switching when multiple faces exist.
    """

    def __init__(
        self,
        model_path="face_detection_yunet.onnx",
        min_score=0.80,
        match_max_distance=0.35,
    ):
        self.model_path = model_path
        self.min_score = min_score
        self.match_max_distance = (
            match_max_distance
        )

        self.detector = cv2.FaceDetectorYN.create(
            self.model_path,
            "",
            (240, 240),
            self.min_score,
            0.3,
            5000,
        )

        self.previous_center = None

    def reset(self):
        self.previous_center = None

    def _choose_face(
        self,
        faces,
        frame_width,
    ):
        if (
            faces is None
            or len(faces) == 0
        ):
            return None

        if self.previous_center is None:
            return max(
                faces,
                key=lambda f: f[2] * f[3],
            )

        best = None
        best_distance = None

        for face in faces:
            x, y, w, h = face[:4]

            center = (
                x + w / 2
            ) / frame_width

            distance = abs(
                center
                - self.previous_center
            )

            if (
                best is None
                or distance < best_distance
            ):
                best = face
                best_distance = distance

        if (
            best_distance
            > self.match_max_distance
        ):
            return max(
                faces,
                key=lambda f: f[2] * f[3],
            )

        return best

    def detect(self, frame):
        height, width = frame.shape[:2]

        self.detector.setInputSize(
            (width, height)
        )

        _, faces = self.detector.detect(
            frame
        )

        face = self._choose_face(
            faces,
            width,
        )

        if face is None:
            return None

        x, y, w, h = face[:4]
        score = float(face[-1])

        center_x = x + w / 2
        center_y = y + h / 2

        normalized_x = (
            center_x / width
        )

        self.previous_center = (
            normalized_x
        )

        return {
            "x": float(center_x),
            "y": float(center_y),
            "width": float(w),
            "height": float(h),
            "score": score,
            "normalized_x": float(
                normalized_x
            ),
            "frame_width": width,
            "frame_height": height,
        }

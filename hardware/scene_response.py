"""Observe broad scene motion on the primary camera's existing frames.

Distributed background agreement is visual evidence, not a measured servo pose
or proof of mechanical clearance. Moving target pixels are excluded.
"""
import hashlib
import math


class SceneResponse:
    def snapshot(self, frame, target=None):
        import cv2
        import numpy as np
        if not isinstance(frame, np.ndarray) or frame.ndim != 3:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        mask = np.full(gray.shape, 255, dtype=np.uint8)
        if target:
            x, y = int(target['x']), int(target['y'])
            w, h = int(target.get('width', 80)), int(target.get('height', 80))
            cv2.rectangle(mask, (x-w, y-h), (x+w, y+h), 0, -1)
        return dict(gray=gray.copy(), mask=mask, size=[gray.shape[1], gray.shape[0]],
                    sha256=hashlib.sha256(gray.tobytes()).hexdigest(),
                    capture_sha256=hashlib.sha256(frame.tobytes()).hexdigest())

    def compare(self, before, after):
        import cv2
        import numpy as np
        fail = dict(reliable=False, reason='distributed background motion unavailable')
        if before is None or after is None or before['size'] != after['size']:
            return fail
        evidence = dict(before_sha256=before['sha256'], after_sha256=after['sha256'],
            observation_size=before['size'], method='distributed_LK_RANSAC',
            assumptions=['background is stationary'], physical_position_measured=False)
        points = cv2.goodFeaturesToTrack(before['gray'], 160, .02, 12, mask=before['mask'])
        if points is None or len(points) < 16:
            return dict(fail, **evidence)
        dest, valid, _ = cv2.calcOpticalFlowPyrLK(before['gray'], after['gray'], points, None)
        if dest is None or valid is None:
            return dict(fail, **evidence)
        back, backward_valid, _ = cv2.calcOpticalFlowPyrLK(after['gray'], before['gray'], dest, None)
        if back is None or backward_valid is None:
            return dict(fail, **evidence)
        select = (valid.ravel() == 1) & (backward_valid.ravel() == 1)
        select &= np.linalg.norm(back-points, axis=2).ravel() < 1
        source, destination = points.reshape(-1, 2)[select], dest.reshape(-1, 2)[select]
        w, h = before['size']
        inside = ((destination[:, 0] >= 0) & (destination[:, 0] < w) &
                  (destination[:, 1] >= 0) & (destination[:, 1] < h))
        source, destination = source[inside], destination[inside]
        if len(source):
            keep = after['mask'][destination[:, 1].astype(int), destination[:, 0].astype(int)] > 0
            source, destination = source[keep], destination[keep]
        if len(source) < 12:
            return dict(fail, **evidence)
        matrix, inliers = cv2.estimateAffinePartial2D(source, destination, method=cv2.RANSAC,
                                                   ransacReprojThreshold=1.5)
        if matrix is None or inliers is None or not np.isfinite(matrix).all():
            return dict(fail, **evidence)
        selected = source[inliers.ravel() == 1]
        coverage = {(int(x >= w/2), int(y >= h/2)) for x, y in selected}
        scale = math.hypot(matrix[0, 0], matrix[1, 0])
        rotation = abs(math.atan2(matrix[1, 0], matrix[0, 0]))
        reliable = (len(selected) >= 12 and len(coverage) >= 3 and
                    inliers.mean() >= .7 and .9 <= scale <= 1.1 and rotation <= .1)
        # Evaluate the affine transform at image center, not its corner offset.
        center = np.array([w/2, h/2])
        shift = matrix[:, :2] @ center + matrix[:, 2] - center
        return dict(evidence, reliable=bool(reliable), displacement=shift.tolist(),
            inliers=len(selected), background_quadrants=len(coverage),
            reason='visual scene agreement' if reliable else fail['reason'])

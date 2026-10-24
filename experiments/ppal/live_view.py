"""Conservative symptoms from ordinary frames, never a movement diagnosis."""
import cv2
import numpy as np
from .preflight import ImagingMonitor


class LiveViewMonitor:
    def __init__(self, frame):
        self.imaging = ImagingMonitor(frame)
        self.detail = self.border_detail(frame)
        self.blur_streak = 0
        self.last_timestamp = None
        from .eyes.active_vision import DegradationGate
        self.geometry = DegradationGate()
        self.geometry_checked_at = -float('inf')

    @staticmethod
    def border_detail(frame):
        gray = cv2.cvtColor(np.asarray(frame.convert('RGB')), cv2.COLOR_RGB2GRAY)
        gradient = cv2.magnitude(cv2.Sobel(gray,cv2.CV_32F,1,0),
                                 cv2.Sobel(gray,cv2.CV_32F,0,1))
        width = max(2,min(gray.shape)//25)
        border = np.concatenate([gradient[:width].ravel(),gradient[-width:].ravel(),
                                 gradient[:,:width].ravel(),gradient[:,-width:].ravel()])
        return float(np.mean(border))

    def observe(self, frame, screen, timestamp, *, raw=None, calibration=None):
        if timestamp is None or (self.last_timestamp is not None and timestamp <= self.last_timestamp):
            return None
        self.last_timestamp = timestamp
        # Share Active Vision's hysteresis and fresh-structure contract without
        # opening a camera, creating a worker, requesting motion or new controls.
        if raw is not None and getattr(calibration, 'corners', None) is not None and timestamp-self.geometry_checked_at >= 1:
            from .eyes.settle import locate, verify_supported_border
            self.geometry_checked_at=timestamp
            expected=screen.get('state') != 'gameplay'
            current=None
            if not expected:
                try:
                    verify_supported_border(raw, np.asarray(calibration.corners)*raw.size)
                    # The known edges/endpoints were independently supported on
                    # this exposure. This is verification, not a new neck pose.
                    current=np.asarray(calibration.corners)
                except ValueError:
                    try: current=locate(raw, require_uniform_border=False)/raw.size
                    except ValueError: pass
            decision=self.geometry.observe(calibration.corners, current, now=timestamp,
                expected_transition=expected, authorized=False)
            if decision in ('request_permission','suspend_and_request'):
                return dict(symptom='persistent structural viewpoint degradation',
                            inference='cause and physical movement unqualified',
                            active_vision_decision=decision, physical_authorization=False)
        # Recognized attract, terminal and ambiguous pages cannot prove failure.
        if screen.get('state') != 'gameplay':
            self.imaging.streak = self.blur_streak = 0
            return None
        current = self.border_detail(frame)
        self.blur_streak = self.blur_streak+1 if self.detail >= 10 and current < self.detail*.05 else 0
        drift = self.imaging.observe(frame)
        if drift:
            return dict(drift, symptom='persistent border loss or excessive clipping',
                        inference='cause and physical movement unqualified')
        if self.blur_streak >= 6:
            return dict(symptom='persistent severe loss of measured border detail',
                        reference_detail=self.detail,current_detail=current,fresh_support=self.blur_streak,
                        inference='blur, occlusion or viewpoint cause unqualified')
        return None

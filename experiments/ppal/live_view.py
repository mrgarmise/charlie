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

    @staticmethod
    def border_detail(frame):
        gray = cv2.cvtColor(np.asarray(frame.convert('RGB')), cv2.COLOR_RGB2GRAY)
        gradient = cv2.magnitude(cv2.Sobel(gray,cv2.CV_32F,1,0),
                                 cv2.Sobel(gray,cv2.CV_32F,0,1))
        width = max(2,min(gray.shape)//25)
        border = np.concatenate([gradient[:width].ravel(),gradient[-width:].ravel(),
                                 gradient[:,:width].ravel(),gradient[:,-width:].ravel()])
        return float(np.mean(border))

    def observe(self, frame, screen, timestamp):
        if timestamp is None or (self.last_timestamp is not None and timestamp <= self.last_timestamp):
            return None
        self.last_timestamp = timestamp
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

"""Observation-only sprite classifier trained from physical-camera examples.

Connected bright regions are compared by shape and color with labeled examples.
Low similarity, conflicting classes and oversized overlaps remain unknown.
Similarity is not a calibrated probability. This detector never authorizes play.
"""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from .detectors import Detection


def feature(rgb):
    # Normalize crop size, retaining color and silhouette; no full-frame search.
    resized = cv2.resize(rgb, (16, 24), interpolation=cv2.INTER_AREA).astype(np.float32)
    resized = np.maximum(resized - 75, 0)
    vector = resized.reshape(-1)
    return vector / max(float(np.linalg.norm(vector)), 1e-6)


def regions(frame):
    rgb = np.asarray(frame.convert('RGB'))
    mask = (rgb.max(axis=2) > 145).astype(np.uint8)
    mask[:5] = 0; mask[-5:] = 0; mask[:, :5] = 0; mask[:, -5:] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, connectivity=8)
    output = []
    for x, y, w, h, area in stats[1:]:
        if area < 8 or w < 3 or h < 3:
            continue
        output.append(((int(x), int(y), int(x+w), int(y+h)), int(area),
                       rgb[y:y+h, x:x+w]))
    return output


class SpriteDetector:
    observation_only = True

    def __init__(self, profile):
        if profile.get('type') != 'camera-sprites-v1':
            raise ValueError('Expected camera-sprites-v1 profile')
        self.examples = profile['examples']
        if not self.examples or any(e['kind'] not in ('player', 'human', 'threat') for e in self.examples):
            raise ValueError('Labeled player/human/threat examples required')
        self.vectors = np.array([feature(np.asarray(e['rgb'], dtype=np.uint8)) for e in self.examples])
        self.threshold = float(profile.get('threshold', .86))
        self.margin = float(profile.get('margin', .07))

    @classmethod
    def load(cls, path: Path):
        return cls(json.loads(path.read_text()))

    def detect(self, frame: Image.Image):
        found = []
        width, height = frame.size
        for box, area, patch in regions(frame):
            scores = self.vectors @ feature(patch)
            by_class = {kind: max((float(score) for score, e in zip(scores, self.examples)
                                  if e['kind'] == kind), default=-1)
                        for kind in ('player', 'human', 'threat')}
            ranked = sorted(by_class, key=by_class.get, reverse=True)
            best, second = ranked[:2]
            score = by_class[best]
            kind = best if (score >= self.threshold and score-by_class[second] >= self.margin
                            and box[2]-box[0] <= 45 and box[3]-box[1] <= 45) else 'unknown'
            found.append(Detection(kind, ((box[0]+box[2])/2/width*100,
                                          (box[1]+box[3])/2/height*100), box, area))
        return found

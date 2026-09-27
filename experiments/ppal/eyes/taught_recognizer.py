"""Human-grounded recognition from promoted Robotron sprite knowledge.

Similarity scores are evidence, not calibrated probabilities. Recognition never
implicitly authorizes controls; callers must apply their own safety gate.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .sprites import feature, regions
from .detectors import Detection


class TaughtRecognizer:
    def __init__(self, knowledge: dict, threshold: float = 0.82, margin: float = 0.04):
        if knowledge.get("schema") != "robotron-taught-sprites-v1":
            raise ValueError("Expected robotron-taught-sprites-v1 knowledge")
        references = defaultdict(list)
        for example in knowledge.get("examples", []):
            if not example.get("human_confirmed"):
                continue
            references[example["identity"]].append(example["feature"])
        if not references.get("player"):
            raise ValueError("Human-confirmed player examples are required")
        self.references = {
            identity: np.asarray(vectors, dtype=np.float32)
            for identity, vectors in references.items()
        }
        self.threshold = float(threshold)
        self.margin = float(margin)

    @classmethod
    def load(cls, path: Path, threshold: float = 0.82, margin: float = 0.04):
        return cls(json.loads(path.read_text(encoding="utf-8")), threshold, margin)

    def classify_patch(self, patch) -> tuple[str, float, float, dict[str, float]]:
        query = feature(patch)
        by_class = {}
        for identity, matrix in self.references.items():
            scores = matrix @ query
            top = np.sort(scores)[-3:]
            by_class[identity] = float(np.median(top))
        ranked = sorted(by_class.items(), key=lambda item: item[1], reverse=True)
        identity, score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else -1.0
        if score < self.threshold or score - runner_up < self.margin:
            identity = "unknown"
        return identity, score, runner_up, by_class

    def detect(self, frame: Image.Image):
        """Return (Detection, evidence) pairs in corrected playfield coordinates."""
        width, height = frame.size
        output = []
        for box, area, patch in regions(frame):
            identity, score, runner_up, by_class = self.classify_patch(patch)
            detection = Detection(
                identity,
                ((box[0] + box[2]) / 2 / width * 100,
                 (box[1] + box[3]) / 2 / height * 100),
                box,
                area,
            )
            output.append((detection, {
                "identity": identity,
                "score": score,
                "runner_up": runner_up,
                "class_scores": by_class,
            }))
        return output

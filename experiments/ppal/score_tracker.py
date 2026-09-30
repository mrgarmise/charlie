"""Temporal Robotron score tracking.

Visual recognition and temporal belief are deliberately separate. A HUD reader
proposes scores from pixels; ScoreTracker decides when a proposal is trustworthy
enough to become the episode score. SCORE is the primary external objective.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScoreObservation:
    sample: int
    observed_score: int | None
    score: int | None
    delta: int
    confidence: float
    changed: bool
    status: str


class ScoreTracker:
    """Conservative monotonic score belief over noisy visual observations.

    Robotron score is monotonic within an episode. A new value normally needs
    repeated visual support before it is committed. The first readable value can
    be accepted immediately at high confidence so a run can establish its
    baseline without inventing a zero score.
    """

    def __init__(
        self,
        *,
        confirm_samples: int = 2,
        min_confidence: float = 0.70,
        immediate_confidence: float = 0.97,
        max_jump: int | None = None,
    ) -> None:
        if confirm_samples < 1:
            raise ValueError("confirm_samples must be >= 1")
        self.confirm_samples = int(confirm_samples)
        self.min_confidence = float(min_confidence)
        self.immediate_confidence = float(immediate_confidence)
        self.max_jump = max_jump

        self.sample = 0
        self.score: int | None = None
        self._pending: int | None = None
        self._pending_count = 0
        self._pending_confidence = 0.0

    def reset(self) -> None:
        self.sample = 0
        self.score = None
        self._pending = None
        self._pending_count = 0
        self._pending_confidence = 0.0

    def _clear_pending(self) -> None:
        self._pending = None
        self._pending_count = 0
        self._pending_confidence = 0.0

    def observe(self, observed_score: Optional[int], confidence: float = 1.0) -> ScoreObservation:
        self.sample += 1
        confidence = max(0.0, min(1.0, float(confidence)))

        if observed_score is None:
            return self._result(None, 0, False, "unreadable", confidence)
        if isinstance(observed_score, bool) or not isinstance(observed_score, int) or observed_score < 0:
            raise ValueError("observed_score must be a nonnegative integer or None")
        if confidence < self.min_confidence:
            return self._result(observed_score, 0, False, "low_confidence", confidence)

        if self.score is None:
            if confidence >= self.immediate_confidence or self.confirm_samples == 1:
                self.score = observed_score
                self._clear_pending()
                return self._result(observed_score, 0, False, "baseline", confidence)
            return self._pending_result(observed_score, confidence, baseline=True)

        if observed_score == self.score:
            self._clear_pending()
            return self._result(observed_score, 0, False, "stable", confidence)

        if observed_score < self.score:
            self._clear_pending()
            return self._result(observed_score, 0, False, "rejected_decrease", confidence)

        jump = observed_score - self.score
        if self.max_jump is not None and jump > self.max_jump:
            self._clear_pending()
            return self._result(observed_score, 0, False, "rejected_jump", confidence)

        if confidence >= self.immediate_confidence:
            old = self.score
            self.score = observed_score
            self._clear_pending()
            return self._result(observed_score, self.score - old, True, "changed", confidence)

        return self._pending_result(observed_score, confidence, baseline=False)

    def _pending_result(self, observed_score: int, confidence: float, *, baseline: bool) -> ScoreObservation:
        if observed_score == self._pending:
            self._pending_count += 1
            self._pending_confidence = max(self._pending_confidence, confidence)
        else:
            self._pending = observed_score
            self._pending_count = 1
            self._pending_confidence = confidence

        if self._pending_count >= self.confirm_samples:
            if baseline:
                self.score = observed_score
                delta = 0
                changed = False
                status = "baseline"
            else:
                old = self.score
                self.score = observed_score
                delta = self.score - old
                changed = True
                status = "changed"
            committed_confidence = self._pending_confidence
            self._clear_pending()
            return self._result(observed_score, delta, changed, status, committed_confidence)

        return self._result(
            observed_score, 0, False,
            "pending_baseline" if baseline else "pending_change",
            confidence,
        )

    def _result(self, observed_score, delta, changed, status, confidence) -> ScoreObservation:
        return ScoreObservation(
            sample=self.sample,
            observed_score=observed_score,
            score=self.score,
            delta=int(delta),
            confidence=float(confidence),
            changed=bool(changed),
            status=status,
        )


class VisualScoreTracker:
    """Connect any HUDReader to temporal score belief.

    The reader owns pixel recognition. This class deliberately ignores lives for
    now; score is the performance objective and can be validated independently.
    """

    def __init__(self, reader, tracker: ScoreTracker | None = None) -> None:
        self.reader = reader
        self.tracker = tracker or ScoreTracker()

    def reset(self) -> None:
        self.tracker.reset()

    def observe(self, image) -> ScoreObservation:
        hud = self.reader.read(image)
        if hud is None:
            return self.tracker.observe(None, 0.0)
        return self.tracker.observe(hud.score, hud.confidence)

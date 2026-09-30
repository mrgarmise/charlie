"""Temporal Robotron score tracking for one- and two-player games.

Visual recognition and temporal belief are deliberately separate. A HUD reader
proposes score channels from pixels; independent ScoreTrackers decide when each
proposal is trustworthy. Which channel belongs to SELF is explicit state rather
than an assumption that Charlie must always be player one.
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


@dataclass(frozen=True)
class ScoreChannels:
    player1: ScoreObservation
    player2: ScoreObservation
    self_channel: int | None

    @property
    def self_score(self) -> int | None:
        return self.for_player(self.self_channel).score if self.self_channel else None

    @property
    def self_delta(self) -> int:
        return self.for_player(self.self_channel).delta if self.self_channel else 0

    def for_player(self, player: int | None) -> ScoreObservation:
        if player == 1:
            return self.player1
        if player == 2:
            return self.player2
        raise ValueError("player must be 1 or 2")


class ScoreTracker:
    """Conservative monotonic score belief over noisy visual observations."""

    def __init__(self, *, confirm_samples: int = 2, min_confidence: float = 0.70,
                 immediate_confidence: float = 0.97, max_jump: int | None = None) -> None:
        if confirm_samples < 1:
            raise ValueError("confirm_samples must be >= 1")
        self.confirm_samples = int(confirm_samples)
        self.min_confidence = float(min_confidence)
        self.immediate_confidence = float(immediate_confidence)
        self.max_jump = max_jump
        self.reset()

    def reset(self) -> None:
        self.sample = 0
        self.score: int | None = None
        self._pending: int | None = None
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
            return self._result(None, 0, False, "absent_or_unreadable", confidence)
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
                self.score, delta, changed, status = observed_score, 0, False, "baseline"
            else:
                old = self.score
                self.score = observed_score
                delta, changed, status = self.score - old, True, "changed"
            committed_confidence = self._pending_confidence
            self._clear_pending()
            return self._result(observed_score, delta, changed, status, committed_confidence)
        return self._result(observed_score, 0, False,
                            "pending_baseline" if baseline else "pending_change", confidence)

    def _result(self, observed_score, delta, changed, status, confidence) -> ScoreObservation:
        return ScoreObservation(self.sample, observed_score, self.score, int(delta),
                                float(confidence), bool(changed), status)


class DualScoreTracker:
    """Independent P1/P2 temporal score channels with explicit SELF ownership."""

    def __init__(self, *, self_channel: int | None = 1, **tracker_kwargs) -> None:
        self.player1 = ScoreTracker(**tracker_kwargs)
        self.player2 = ScoreTracker(**tracker_kwargs)
        self.set_self_channel(self_channel)

    def set_self_channel(self, player: int | None) -> None:
        if player not in (None, 1, 2):
            raise ValueError("self_channel must be None, 1, or 2")
        self.self_channel = player

    def reset(self) -> None:
        self.player1.reset()
        self.player2.reset()

    def observe(self, player1_score: int | None, player2_score: int | None,
                *, player1_confidence: float = 1.0,
                player2_confidence: float = 1.0) -> ScoreChannels:
        return ScoreChannels(
            self.player1.observe(player1_score, player1_confidence),
            self.player2.observe(player2_score, player2_confidence),
            self.self_channel,
        )


class VisualScoreTracker:
    """Connect a one- or two-channel HUD reader to temporal score belief.

    New readers should expose player1_score/player2_score. The legacy synthetic
    HUDObservation(score=...) is treated as P1 so existing simulator code keeps
    working while the real Robotron reader becomes explicitly two-channel.
    """

    def __init__(self, reader, tracker: DualScoreTracker | None = None,
                 *, self_channel: int | None = 1) -> None:
        self.reader = reader
        self.tracker = tracker or DualScoreTracker(self_channel=self_channel)

    def reset(self) -> None:
        self.tracker.reset()

    def set_self_channel(self, player: int | None) -> None:
        self.tracker.set_self_channel(player)

    def observe(self, image) -> ScoreChannels:
        hud = self.reader.read(image)
        if hud is None:
            return self.tracker.observe(None, None, player1_confidence=0.0,
                                        player2_confidence=0.0)
        p1 = getattr(hud, "player1_score", getattr(hud, "score", None))
        p2 = getattr(hud, "player2_score", None)
        p1c = getattr(hud, "player1_confidence", getattr(hud, "confidence", 0.0))
        p2c = getattr(hud, "player2_confidence", 0.0)
        return self.tracker.observe(p1, p2, player1_confidence=p1c,
                                    player2_confidence=p2c)

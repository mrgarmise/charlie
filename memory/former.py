"""Select significant experiences for Charlie's durable memory.

The former is independent of the store. Producers supply observations and
explicit outcomes; it never infers causation from adjacent frames.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass(frozen=True)
class Experience:
    kind: Literal["observation", "outcome", "fact", "decision"]
    summary: str
    source: str
    goal: str | None = None
    action: str | None = None
    outcome: str | None = None
    subject: str | None = None
    confidence: float = 1.0
    novelty: bool = False
    significant: bool = False
    tags: tuple[str, ...] = ()
    evidence: str | None = None


@dataclass(frozen=True)
class CandidateMemory:
    text: str
    kind: str
    source: str
    confidence: float
    importance: float
    reason: str
    tags: tuple[str, ...]
    subject: str | None
    evidence: str | None
    formed_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class MemoryFormer:
    """Rule-based first version; a future model can replace the selection policy."""

    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold
        self._seen: set[tuple[str, str, str]] = set()

    def consider(self, event: Experience) -> CandidateMemory | None:
        if not event.summary.strip() or not event.source.strip():
            raise ValueError("A memory needs a summary and source")
        if not 0 <= event.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        reasons = []
        score = 0.0
        if event.novelty:
            reasons.append("novel observation")
            score += 0.65
        if event.significant:
            reasons.append("significant event")
            score += 0.8
        if event.kind == "outcome" and event.outcome:
            reasons.append("reported outcome")
            score += 0.7
        if event.kind in ("fact", "decision") and event.subject:
            reasons.append("reusable " + event.kind)
            score += 0.7
        score = min(score, 1.0)
        if score < self.threshold:
            return None
        key = (event.source, event.kind, event.evidence or event.summary.strip())
        if key in self._seen:
            return None
        self._seen.add(key)
        details = [event.summary.strip()]
        if event.goal:
            details.append("Goal: " + event.goal)
        if event.action:
            details.append("Action: " + event.action)
        if event.outcome:
            details.append("Outcome: " + event.outcome)
        return CandidateMemory(
            text=". ".join(details).rstrip(".") + ".",
            kind=event.kind, source=event.source,
            confidence=event.confidence, importance=score,
            reason=", ".join(reasons), tags=event.tags,
            subject=event.subject, evidence=event.evidence,
            formed_at=datetime.now(timezone.utc).isoformat(),
        )

"""Derive reward from successive screen readings, with explicit unknowns."""

from dataclasses import dataclass

from .eyes.hud import HUDObservation


@dataclass(frozen=True)
class MeasuredOutcome:
    reward: int | None
    events: tuple[str, ...]


class RewardTracker:
    def __init__(self, death_penalty: int = 100, max_score_jump: int = 10000) -> None:
        self.death_penalty = death_penalty
        self.max_score_jump = max_score_jump

    def evaluate(self, before: HUDObservation | None,
                 after: HUDObservation | None) -> MeasuredOutcome:
        if before is None or after is None or before.score is None or after.score is None:
            return MeasuredOutcome(None, ("hud_unreadable",))
        if before.lives is None or after.lives is None:
            return MeasuredOutcome(None, ("lives_unreadable",))
        delta = after.score - before.score
        if delta < 0 or delta > self.max_score_jump or after.lives > before.lives:
            return MeasuredOutcome(None, ("hud_reset_or_implausible",))
        life_loss = before.lives - after.lives
        events = []
        if delta:
            events.append(f"score:+{delta}")
        if life_loss:
            events.append(f"lives_lost:{life_loss}")
        return MeasuredOutcome(delta - self.death_penalty * life_loss, tuple(events))

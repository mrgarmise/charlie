"""Translate PPAL observations into possible long-term memories.

PPAL-0's frames are scripted, not action-dependent. A disappearing object is
an observation, not evidence that a fire/move command succeeded.
"""

from experiments.ppal.models import Action, Goal, Intent, WorldState

from .former import Experience, MemoryFormer
from .store import MemoryStore


class PPALMemoryAdapter:
    def __init__(self, former: MemoryFormer, store: MemoryStore,
                 source: str = "ppal:scripted") -> None:
        self.former, self.store, self.source = former, store, source
        self._seen_threats: set[str] = set()

    def observe(self, before: WorldState, goal: Goal, intent: Intent,
                action: Action, after: WorldState) -> int:
        """Return number of memories saved; PPAL's dense logger stays separate."""
        events: list[Experience] = []
        new_threats = {t.id for t in after.threats} - {t.id for t in before.threats}
        for identifier in sorted(new_threats - self._seen_threats):
            events.append(Experience(
                kind="observation", summary=f"New threat {identifier} appeared at tick {after.tick}",
                source=self.source, goal=f"{goal.kind}:{goal.target_id or '-'}",
                action=f"{intent.kind}; move={action.move}; fire={action.fire}",
                subject=identifier, novelty=True, confidence=0.9,
                evidence=f"PPAL transition {before.tick}->{after.tick}", tags=("ppal", "threat"),
            ))
        self._seen_threats.update(new_threats)
        vanished = {t.id for t in before.targets} - {t.id for t in after.targets}
        for identifier in sorted(vanished):
            events.append(Experience(
                kind="observation", summary=f"Target {identifier} was no longer visible at tick {after.tick}",
                source=self.source, goal=f"{goal.kind}:{goal.target_id or '-'}",
                action=f"{intent.kind}; move={action.move}; fire={action.fire}",
                subject=identifier, significant=True, confidence=0.9,
                evidence=f"PPAL transition {before.tick}->{after.tick}", tags=("ppal", "target"),
            ))
        if before.alive and not after.alive:
            events.append(Experience(
                kind="observation", summary=f"Player death observed at tick {after.tick}",
                source=self.source, goal=f"{goal.kind}:{goal.target_id or '-'}",
                action=f"{intent.kind}; move={action.move}; fire={action.fire}",
                significant=True, confidence=0.95,
                evidence=f"PPAL transition {before.tick}->{after.tick}", tags=("ppal", "failure"),
            ))
        saved = 0
        for event in events:
            candidate = self.former.consider(event)
            if candidate is not None:
                self.store.save(candidate)
                saved += 1
        return saved

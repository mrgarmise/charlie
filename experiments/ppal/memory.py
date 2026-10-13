"""Readable experience log. Recording does not change the policy."""

from dataclasses import asdict
import json
from pathlib import Path

from .models import Action, Goal, Intent, WorldState


class Memory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, before: WorldState, goal: Goal, intent: Intent,
               action: Action, after: WorldState, *, reward: int | None = None,
               source: str = "scripted", events: tuple[str, ...] = ()) -> None:
        entry = {"before": asdict(before), "goal": asdict(goal), "intent": asdict(intent),
                 "action": asdict(action), "after": asdict(after),
                 "source": source, "reward": reward, "events": events}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry) + "\n")

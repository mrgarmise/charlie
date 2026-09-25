"""Small, game-neutral messages passed between PPAL components."""

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class Position:
    x: float
    y: float

    def distance(self, other: "Position") -> float:
        return hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class Object:
    id: str
    position: Position


@dataclass(frozen=True)
class WorldState:
    tick: int
    player: Position
    targets: tuple[Object, ...]
    threats: tuple[Object, ...]
    alive: bool = True


@dataclass(frozen=True)
class Goal:
    kind: str
    target_id: str | None = None


@dataclass(frozen=True)
class Intent:
    kind: str
    target_id: str | None = None
    destination: Position | None = None


@dataclass(frozen=True)
class Action:
    move: str = "STAY"
    fire: str = "NONE"
    reason: str = ""

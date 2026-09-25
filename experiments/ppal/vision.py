"""PPAL-0's synthetic observation source; a camera adapter can replace it."""

from .models import Object, Position, WorldState


def demo_frames() -> tuple[WorldState, ...]:
    human = Object("human_1", Position(90, 50))
    blocker = Object("grunt_1", Position(45, 50))
    distant = Object("grunt_2", Position(80, 90))
    sudden = Object("grunt_3", Position(21, 49))
    return (
        WorldState(0, Position(10, 50), (human,), (blocker, distant)),
        WorldState(1, Position(14, 50), (human,), (blocker, distant)),
        WorldState(2, Position(18, 50), (human,), (blocker, distant, sudden)),
        WorldState(3, Position(18, 55), (human,), (blocker, distant)),
        WorldState(4, Position(24, 50), (human,), (distant,)),
        WorldState(5, Position(72, 50), (human,), (distant,)),
        WorldState(6, Position(90, 50), (), (distant,)),
    )

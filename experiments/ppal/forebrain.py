"""Persistent objective selection. No joystick commands live here."""

from .models import Goal, WorldState


class Forebrain:
    def __init__(self) -> None:
        self.goal: Goal | None = None

    def update(self, world: WorldState) -> Goal:
        if not world.alive:
            self.goal = Goal("survive")
            return self.goal
        ids = {target.id for target in world.targets}
        if self.goal and self.goal.kind == "rescue" and self.goal.target_id in ids:
            return self.goal
        if world.targets:
            target = min(world.targets, key=lambda item: world.player.distance(item.position))
            self.goal = Goal("rescue", target.id)
        else:
            self.goal = Goal("survive")
        return self.goal

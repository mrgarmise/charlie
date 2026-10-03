"""Short-horizon tactics plus an immediate collision override."""

from math import hypot
from typing import TYPE_CHECKING

from .models import Action, Goal, Intent, Position, WorldState

if TYPE_CHECKING:
    from .shot_learning import ShotModel


MOVE_VECTORS = {"N": (0, -1), "NE": (1, -1), "E": (1, 0), "SE": (1, 1),
                "S": (0, 1), "SW": (-1, 1), "W": (-1, 0), "NW": (-1, -1)}


def direction(start: Position, end: Position, deadband: float = 3) -> str:
    dx, dy = end.x - start.x, end.y - start.y
    horizontal = "E" if dx > deadband else "W" if dx < -deadband else ""
    vertical = "S" if dy > deadband else "N" if dy < -deadband else ""
    return vertical + horizontal or "STAY"


def distance_to_segment(point: Position, start: Position, end: Position) -> float:
    dx, dy = end.x - start.x, end.y - start.y
    denominator = dx * dx + dy * dy
    if denominator == 0:
        return point.distance(start)
    fraction = max(0.0, min(1.0, ((point.x - start.x) * dx + (point.y - start.y) * dy) / denominator))
    return point.distance(Position(start.x + fraction * dx, start.y + fraction * dy))


class Hindbrain:
    def __init__(self, panic_radius: float = 9, route_width: float = 9,
                 shot_model: "ShotModel | None" = None) -> None:
        self.panic_radius = panic_radius
        self.route_width = route_width
        self.shot_model = shot_model
        self.last_clear_id: str | None = None
        self.last_clear_tick: int | None = None
        self.last_panic_hold_id: str | None = None
        self.last_panic_hold_tick: int | None = None

    def decide(self, world: WorldState, goal: Goal) -> tuple[Intent, Action]:
        nearby = [threat for threat in world.threats if world.player.distance(threat.position) < self.panic_radius]
        if nearby:
            threat = min(nearby, key=lambda item: world.player.distance(item.position))
            # At a short but non-contact distance, clear the threat without
            # abandoning the route. If that shot failed, dodge next tick.
            failed_hold = (self.last_panic_hold_id == threat.id
                           and self.last_panic_hold_tick is not None
                           and world.tick > self.last_panic_hold_tick)
            if world.player.distance(threat.position) > 6 and not failed_hold:
                self.last_panic_hold_id = threat.id
                self.last_panic_hold_tick = world.tick
                return (Intent("clear", threat.id, threat.position),
                        Action("STAY", direction(world.player, threat.position),
                               "clear close threat; preserve rescue route"))
            self.last_panic_hold_id = None
            self.last_panic_hold_tick = None
            escape = Position(2 * world.player.x - threat.position.x, 2 * world.player.y - threat.position.y)
            return (Intent("evade", threat.id, escape),
                    Action(direction(world.player, escape, 0), direction(world.player, threat.position, 0), "immediate threat"))

        self.last_panic_hold_id = None
        self.last_panic_hold_tick = None

        target = next((item for item in world.targets if item.id == goal.target_id), None)
        if target is None:
            return Intent("hold"), Action(reason="no current rescue target")

        blockers = [threat for threat in world.threats
                    if distance_to_segment(threat.position, world.player, target.position) < self.route_width
                    and threat.position.distance(world.player) < target.position.distance(world.player)]
        if blockers:
            blocker = min(blockers, key=lambda item: world.player.distance(item.position))
            # Keep the rescue as the destination. If the same blocker survived
            # last tick's shot, advance while firing to improve the angle.
            repeated = (self.last_clear_id == blocker.id and self.last_clear_tick is not None
                        and world.tick > self.last_clear_tick)
            self.last_clear_id = blocker.id
            self.last_clear_tick = world.tick
            fire = direction(world.player, blocker.position)
            predicted_miss = (self.shot_model is not None and not self.shot_model.likely_hit(
                world.player, blocker.position, fire))
            movement = direction(world.player, target.position) if repeated or predicted_miss else "STAY"
            if movement in MOVE_VECTORS:
                dx, dy = MOVE_VECTORS[movement]
                length = hypot(dx, dy)
                next_position = Position(max(0, min(100, world.player.x + 8 * dx / length)),
                                         max(0, min(100, world.player.y + 8 * dy / length)))
                if any(next_position.distance(item.position) <= 4 for item in world.threats):
                    movement = "STAY"
            return (Intent("clear", blocker.id, blocker.position),
                    Action(movement, fire,
                           "advance toward rescue after missed shot" if repeated else
                           "predicted miss; advance toward rescue" if movement != "STAY" else "clear route"))
        self.last_clear_id = None
        self.last_clear_tick = None
        movement = direction(world.player, target.position)
        if movement in MOVE_VECTORS:
            dx, dy = MOVE_VECTORS[movement]
            length = hypot(dx, dy)
            next_position = Position(max(0, min(100, world.player.x + 8 * dx / length)),
                                     max(0, min(100, world.player.y + 8 * dy / length)))
            collisions = [threat for threat in world.threats
                          if next_position.distance(threat.position) <= 4]
            if collisions:
                threat = min(collisions, key=lambda item: world.player.distance(item.position))
                return (Intent("clear", threat.id, threat.position),
                        Action("STAY", direction(world.player, threat.position),
                               "clear threat on next step toward rescue"))
        return (Intent("approach", target.id, target.position),
                Action(movement, "NONE", "approach target"))

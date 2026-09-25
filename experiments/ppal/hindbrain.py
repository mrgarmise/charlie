"""Short-horizon tactics plus an immediate collision override."""

from .models import Action, Goal, Intent, Position, WorldState


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
    def __init__(self, panic_radius: float = 9, route_width: float = 9) -> None:
        self.panic_radius = panic_radius
        self.route_width = route_width

    def decide(self, world: WorldState, goal: Goal) -> tuple[Intent, Action]:
        nearby = [threat for threat in world.threats if world.player.distance(threat.position) < self.panic_radius]
        if nearby:
            threat = min(nearby, key=lambda item: world.player.distance(item.position))
            escape = Position(2 * world.player.x - threat.position.x, 2 * world.player.y - threat.position.y)
            return (Intent("evade", threat.id, escape),
                    Action(direction(world.player, escape, 0), direction(world.player, threat.position, 0), "immediate threat"))

        target = next((item for item in world.targets if item.id == goal.target_id), None)
        if target is None:
            return Intent("hold"), Action(reason="no current rescue target")

        blockers = [threat for threat in world.threats
                    if distance_to_segment(threat.position, world.player, target.position) < self.route_width
                    and threat.position.distance(world.player) < target.position.distance(world.player)]
        if blockers:
            blocker = min(blockers, key=lambda item: world.player.distance(item.position))
            return (Intent("clear", blocker.id, blocker.position),
                    Action("STAY", direction(world.player, blocker.position), "clear route"))
        return (Intent("approach", target.id, target.position),
                Action(direction(world.player, target.position), "NONE", "approach target"))

"""Persistent objective selection. No joystick commands live here."""

from .models import Goal, WorldState


class Forebrain:
    def __init__(self, policy=None) -> None:
        self.goal: Goal | None = None
        self.policy = policy
        self.last_reason = {}

    def update(self, world: WorldState) -> Goal:
        values = self.policy.values('goal_preference') if self.policy and world.observation_safe else {}
        self.last_reason = dict(reason='existing nearest persistent rescue objective',
            policy=self.policy.trace(['goal_preference'] if values else [],
                disposition='eligible' if world.observation_safe else 'unsafe observation') if self.policy else None)
        if not world.alive:
            self.goal = Goal("survive")
            return self.goal
        if not world.observation_safe:
            self.goal = Goal('survive')
            self.last_reason['reason'] = 'unsafe observation; conservative goal'
            return self.goal
        if values and values.get('survive', 0) > values.get('rescue', 1):
            self.goal = Goal('survive')
            self.last_reason['reason'] = 'qualified goal preference'
            return self.goal
        ids = {target.id for target in world.targets}
        if self.goal and self.goal.kind == "rescue" and self.goal.target_id in ids:
            return self.goal
        if world.targets:
            weight = values.get('target_threat_weight', 0)
            def cost(item):
                clearance = min((item.position.distance(t.position) for t in world.threats), default=100)
                return world.player.distance(item.position) + weight * (100-clearance)
            target = min(world.targets, key=cost)
            self.goal = Goal("rescue", target.id)
        else:
            self.goal = Goal("survive")
        return self.goal

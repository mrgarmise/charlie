"""A small causal arena, deliberately simpler than Robotron.

Fire removes the nearest threat in an aimed lane. Move changes position.
Touching a threat ends the episode; reaching a target rescues it. A single
reinforcement appears after the first blocker is cleared to exercise the
emergency override. Nothing in this module is a learned policy.
"""

from dataclasses import dataclass
from math import hypot

from .models import Action, Object, Position, WorldState


VECTORS = {
    "N": (0, -1), "NE": (1, -1), "E": (1, 0), "SE": (1, 1),
    "S": (0, 1), "SW": (-1, 1), "W": (-1, 0), "NW": (-1, -1),
}


@dataclass(frozen=True)
class StepResult:
    world: WorldState
    reward: int
    events: tuple[str, ...]
    done: bool


class Simulator:
    def __init__(self, *, player: Position = Position(10, 50),
                 targets: tuple[Object, ...] | None = None,
                 threats: tuple[Object, ...] | None = None,
                 reinforcement: bool = True, shot_lane_scale: float = 1.0) -> None:
        if shot_lane_scale <= 0:
            raise ValueError("shot_lane_scale must be positive")
        self.shot_lane_scale = shot_lane_scale
        self.player = player
        self.targets = list(targets if targets is not None else (Object("human_1", Position(90, 50)),))
        self.threats = list(threats if threats is not None else (Object("grunt_1", Position(45, 50)),))
        self.tick = 0
        self.score = 0
        self.alive = True
        self.done = False
        self.reinforcement = reinforcement
        self.reinforcement_spawned = False

    def observe(self) -> WorldState:
        return WorldState(self.tick, self.player, tuple(self.targets), tuple(self.threats), self.alive)

    def step(self, action: Action) -> StepResult:
        if self.done:
            raise RuntimeError("episode finished; create a new Simulator")
        if action.move not in (*VECTORS, "STAY") or action.fire not in (*VECTORS, "NONE"):
            raise ValueError("unsupported move or fire direction")

        events: list[str] = []
        reward = 0
        if action.fire != "NONE":
            dx, dy = VECTORS[action.fire]
            length = hypot(dx, dy)
            ux, uy = dx / length, dy / length
            candidates = []
            for threat in self.threats:
                vx, vy = threat.position.x - self.player.x, threat.position.y - self.player.y
                forward = vx * ux + vy * uy
                sideways = abs(vx * uy - vy * ux)
                if 0 < forward <= 55 and sideways <= max(4, forward * 0.12) * self.shot_lane_scale:
                    candidates.append((forward, threat))
            if candidates:
                _, hit = min(candidates, key=lambda pair: pair[0])
                self.threats.remove(hit)
                reward += 10
                self.score += 10
                events.append(f"destroyed:{hit.id}")

        if action.move != "STAY":
            dx, dy = VECTORS[action.move]
            length = hypot(dx, dy)
            self.player = Position(max(0, min(100, self.player.x + 8 * dx / length)),
                                   max(0, min(100, self.player.y + 8 * dy / length)))

        if any(self.player.distance(threat.position) <= 4 for threat in self.threats):
            self.alive = False
            self.done = True
            reward -= 100
            events.append("died")
        else:
            rescued = [target for target in self.targets if self.player.distance(target.position) <= 8]
            for target in rescued:
                self.targets.remove(target)
                reward += 100
                self.score += 100
                events.append(f"rescued:{target.id}")
            if not self.targets:
                self.done = True

        # One deterministic environmental event, after the first successful shot.
        if (self.reinforcement and not self.done and not self.reinforcement_spawned
                and "destroyed:grunt_1" in events):
            self.threats.append(Object("grunt_2", Position(self.player.x + 3, self.player.y - 1)))
            self.reinforcement_spawned = True
            events.append("arrived:grunt_2")

        self.tick += 1
        return StepResult(self.observe(), reward, tuple(events), self.done)

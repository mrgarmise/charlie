"""Repeatable evaluation arenas for the current PPAL policy.

These are tests of behavior in a toy simulator, not Robotron benchmarks.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import random

from .forebrain import Forebrain
from .hindbrain import Hindbrain
from .models import Object, Position
from .simulator import Simulator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .shot_learning import ShotModel


@dataclass(frozen=True)
class Arena:
    name: str
    player: Position
    targets: tuple[Object, ...]
    threats: tuple[Object, ...]
    reinforcement: bool = False


def named_arenas() -> tuple[Arena, ...]:
    return (
        Arena("open_field", Position(10, 50),
              (Object("human_1", Position(90, 50)),), ()),
        Arena("straight_blocker", Position(10, 50),
              (Object("human_1", Position(90, 50)),), (Object("grunt_1", Position(45, 50)),)),
        Arena("surprise_threat", Position(10, 50),
              (Object("human_1", Position(90, 50)),), (Object("grunt_1", Position(45, 50)),), True),
        Arena("two_rescues", Position(10, 50),
              (Object("human_1", Position(32, 50)), Object("human_2", Position(85, 50))),
              (Object("grunt_1", Position(55, 50)),)),
        Arena("diagonal_route", Position(10, 10),
              (Object("human_1", Position(85, 80)),),
              (Object("grunt_1", Position(48, 44)),)),
        Arena("edge_escape", Position(2, 2),
              (Object("human_1", Position(80, 80)),),
              (Object("grunt_1", Position(5, 2)),)),
        Arena("crossfire", Position(25, 50),
              (Object("human_1", Position(85, 50)),),
              (Object("grunt_1", Position(32, 50)), Object("grunt_2", Position(25, 58)))),
    )


def generated_arenas(seed: int, count: int) -> tuple[Arena, ...]:
    rng = random.Random(seed)
    arenas = []
    for index in range(count):
        targets = tuple(Object(f"human_{n}", Position(rng.randint(60, 92), rng.randint(12, 88)))
                        for n in range(1, rng.randint(1, 3) + 1))
        threats = tuple(Object(f"grunt_{n}", Position(rng.randint(17, 92), rng.randint(8, 92)))
                        for n in range(1, rng.randint(3, 7) + 1))
        arenas.append(Arena(f"seed_{seed:04d}_{index:03d}", Position(10, 50), targets, threats))
    return tuple(arenas)


def evaluate(arena: Arena, max_steps: int = 80, trace: list[dict] | None = None,
             shot_model: "ShotModel | None" = None, shot_lane_scale: float = 1.0) -> dict:
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    env = Simulator(player=arena.player, targets=arena.targets, threats=arena.threats,
                    reinforcement=arena.reinforcement, shot_lane_scale=shot_lane_scale)
    forebrain, hindbrain = Forebrain(), Hindbrain(shot_model=shot_model)
    counts = {"shots": 0, "hits": 0, "evades": 0, "rescues": 0, "goal_changes": 0}
    previous_goal = None
    positions = []
    for _ in range(max_steps):
        world = env.observe()
        goal = forebrain.update(world)
        if previous_goal is not None and previous_goal != goal.target_id:
            counts["goal_changes"] += 1
        previous_goal = goal.target_id
        intent, action = hindbrain.decide(world, goal)
        counts["shots"] += action.fire != "NONE"
        counts["evades"] += intent.kind == "evade"
        result = env.step(action)
        if trace is not None:
            trace.append({"tick": world.tick, "player": (round(world.player.x, 1), round(world.player.y, 1)),
                          "goal": goal.target_id, "intent": intent.kind,
                          "intent_target": intent.target_id, "move": action.move,
                          "fire": action.fire, "events": result.events,
                          "after": (round(result.world.player.x, 1), round(result.world.player.y, 1))})
        counts["hits"] += sum(event.startswith("destroyed:") for event in result.events)
        counts["rescues"] += sum(event.startswith("rescued:") for event in result.events)
        positions.append(result.world.player)
        if result.done:
            break
    status = "success" if env.done and env.alive else "death" if not env.alive else "timeout"
    if status == "timeout" and len(positions) >= 8 and len(set(positions[-8:])) == 1:
        status = "stalled"
    return {"arena": arena.name, "status": status, "steps": env.tick,
            "score": env.score, "targets": len(arena.targets),
            "threats": len(arena.threats), **counts}


def report(arenas: tuple[Arena, ...], max_steps: int = 80) -> dict:
    results = [evaluate(arena, max_steps) for arena in arenas]
    return {"summary": {"total": len(results),
                         "successes": sum(row["status"] == "success" for row in results),
                         "deaths": sum(row["status"] == "death" for row in results),
                         "timeouts": sum(row["status"] in ("timeout", "stalled") for row in results)},
            "results": results}


def save_report(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

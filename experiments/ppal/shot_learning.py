"""PPAL-5: learn synthetic shot outcomes from perceived objects and visible HUD."""

from dataclasses import asdict, dataclass
import json
from math import exp, hypot
from pathlib import Path
import random

import numpy as np

from .closed_loop import ArenaRenderer
from .eyes.cli import SYNTHETIC_PROFILE
from .eyes.detectors import ColorBlobDetector
from .eyes.hud import BitmapHUDReader
from .eyes.pipeline import VisionPipeline
from .models import Action, Object, Position, WorldState
from .eyes.hud import HUDObservation
from .reward import MeasuredOutcome, RewardTracker
from .simulator import Simulator, VECTORS


FEATURES = ("bias", "sideways_over_lane", "forward_over_range")


def shot_features(player: Position, threat: Position, fire: str) -> tuple[float, ...]:
    if fire not in VECTORS:
        raise ValueError("shot direction must be one of the eight fire directions")
    dx, dy = VECTORS[fire]
    length = hypot(dx, dy)
    ux, uy = dx / length, dy / length
    vx, vy = threat.x - player.x, threat.y - player.y
    forward = vx * ux + vy * uy
    sideways = abs(vx * uy - vy * ux)
    return (1.0, sideways / max(4.0, forward * 0.12), forward / 55.0)


@dataclass(frozen=True)
class ShotExample:
    features: tuple[float, ...]
    hit: int
    observed_reward: int
    oracle_reward: int | None
    fire: str


def collect_shots(count: int, seed: int, shot_lane_scale: float = 1.0) -> list[ShotExample]:
    """Fire in one-threat rendered arenas; labels come only from HUD pixels."""
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    pipeline = VisionPipeline(ColorBlobDetector.load(SYNTHETIC_PROFILE))
    hud = BitmapHUDReader.load(Path(__file__).parent / "eyes/profiles/synthetic_hud.json")
    rewards = RewardTracker()
    examples = []
    directions = tuple(VECTORS)
    for index in range(count):
        fire = directions[index % len(directions)]
        dx, dy = VECTORS[fire]
        length = hypot(dx, dy)
        ux, uy = dx / length, dy / length
        forward = rng.uniform(11, 43)
        sideways = rng.uniform(-11, 11)
        threat = Position(50 + forward * ux - sideways * uy,
                          50 + forward * uy + sideways * ux)
        arena = Simulator(player=Position(50, 50),
                          targets=(Object("human_1", Position(95, 95)),),
                          threats=(Object("grunt_1", threat),), reinforcement=False,
                          shot_lane_scale=shot_lane_scale)
        renderer = ArenaRenderer(arena)
        before = pipeline.process(renderer.read(), 0)
        if before.world is None or len(before.world.threats) != 1:
            raise RuntimeError("training object was not uniquely visible")
        features = shot_features(before.world.player, before.world.threats[0].position, fire)
        before_hud = hud.read(before.playfield)
        result = arena.step(Action("STAY", fire))
        after = pipeline.process(renderer.read(), 1)
        measured = rewards.evaluate(before_hud, hud.read(after.playfield))
        if measured.reward is None:
            raise RuntimeError("training HUD was unreadable")
        examples.append(ShotExample(features, int(measured.reward > 0), measured.reward,
                                    result.reward, fire))
    return examples


def save_replay(examples: list[ShotExample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for row in examples:
            output.write(json.dumps(asdict(row)) + "\n")


def load_replay(path: Path) -> list[ShotExample]:
    rows = [ShotExample(tuple(row["features"]), row["hit"], row["observed_reward"],
                        row["oracle_reward"], row["fire"])
            for line in path.read_text(encoding="utf-8").splitlines()
            if (row := json.loads(line))]
    if not rows or any(len(row.features) != len(FEATURES) or row.hit not in (0, 1) for row in rows):
        raise ValueError("replay has no usable shot examples")
    return rows


@dataclass(frozen=True)
class ShotModel:
    weights: tuple[float, ...]
    threshold: float = 0.5

    def probability(self, player: Position, threat: Position, fire: str) -> float:
        return self.predict(shot_features(player, threat, fire))

    def predict(self, features: tuple[float, ...]) -> float:
        if len(features) != len(self.weights):
            raise ValueError("feature count does not match model")
        z = sum(a * b for a, b in zip(self.weights, features))
        return 1 / (1 + exp(-max(-40, min(40, z))))

    def likely_hit(self, player: Position, threat: Position, fire: str) -> bool:
        return self.probability(player, threat, fire) >= self.threshold

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, "domain": "synthetic-rendered-only",
                                    "features": FEATURES, "weights": self.weights,
                                    "threshold": self.threshold}, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ShotModel":
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("version") != 1 or data.get("domain") != "synthetic-rendered-only"
                or tuple(data.get("features", ())) != FEATURES
                or len(data.get("weights", ())) != len(FEATURES)):
            raise ValueError("incompatible synthetic shot model")
        return cls(tuple(float(w) for w in data["weights"]), float(data["threshold"]))


def train(examples: list[ShotExample], epochs: int = 1800,
          initial: ShotModel | None = None) -> ShotModel:
    if not examples or {row.hit for row in examples} != {0, 1}:
        raise ValueError("training needs both hits and misses")
    x = np.asarray([row.features for row in examples], dtype=float)
    y = np.asarray([row.hit for row in examples], dtype=float)
    weights = np.asarray(initial.weights, dtype=float).copy() if initial else np.zeros(len(FEATURES))
    for _ in range(epochs):
        logits = np.clip(x @ weights, -30, 30)
        probabilities = 1 / (1 + np.exp(-logits))
        gradient = x.T @ (probabilities - y) / len(y)
        weights -= 0.15 * gradient
    return ShotModel(tuple(map(float, weights)))


def brier(examples: list[ShotExample], model: ShotModel) -> float:
    return sum((model.predict(row.features) - row.hit) ** 2 for row in examples) / len(examples)


class ShotAdaptation:
    """Accept only unambiguous pixel-observed one-threat shot transitions."""

    def __init__(self, model: ShotModel, min_examples: int = 16) -> None:
        self.model = model
        self.min_examples = min_examples
        self.examples: list[ShotExample] = []
        self.skipped = 0
        self.updates = 0

    def observe(self, before: WorldState | None, action: Action, after: WorldState | None,
                before_hud: HUDObservation | None, after_hud: HUDObservation | None,
                outcome: MeasuredOutcome | None) -> bool:
        """Returns True when an update changed the currently deployed model."""
        if (before is None or after is None or before_hud is None or after_hud is None
                or outcome is None or outcome.reward is None or action.fire not in VECTORS
                or len(before.threats) != 1 or before_hud.score is None or after_hud.score is None
                or before_hud.lives is None or after_hud.lives is None
                or before_hud.lives != after_hud.lives
                or {item.id for item in before.targets} != {item.id for item in after.targets}):
            self.skipped += 1
            return False
        delta = after_hud.score - before_hud.score
        before_id = before.threats[0].id
        if outcome.reward != delta:
            self.skipped += 1
            return False
        if delta == 10 and len(after.threats) == 0:
            hit = 1
        elif delta == 0 and len(after.threats) == 1 and after.threats[0].id == before_id:
            hit = 0
        else:
            self.skipped += 1
            return False
        row = ShotExample(shot_features(before.player, before.threats[0].position, action.fire),
                          hit, outcome.reward, None, action.fire)
        return self.accept_example(row)

    def accept_example(self, row: ShotExample) -> bool:
        """Consume an already pixel-labeled row, including a replay row."""
        self.examples.append(row)
        if len(self.examples) >= self.min_examples and len(self.examples) % 8 == 0:
            return self.update()
        return False

    def update(self) -> bool:
        if len(self.examples) < self.min_examples or {row.hit for row in self.examples} != {0, 1}:
            return False
        self.model = train(self.examples, initial=self.model)
        self.updates += 1
        return True

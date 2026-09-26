"""Observe pixels -> plan -> act -> observe again; synthetic world is causal."""

from dataclasses import asdict
import json
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from .forebrain import Forebrain
from .hindbrain import Hindbrain
from .models import Action, Object, Position, WorldState
from .simulator import Simulator
from .vision_tracker import ObjectTracker
from .reward import RewardTracker
from .eyes.hud import HUDReader, draw_synthetic_hud
from .eyes.pipeline import VisionPipeline
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .shot_learning import ShotModel


class ArenaRenderer:
    """Render the simulator into pixels; the policy never receives its state."""

    def __init__(self, arena: Simulator, size: tuple[int, int] = (640, 480)) -> None:
        self.arena = arena
        self.size = size

    def read(self) -> Image.Image:
        world = self.arena.observe()
        width, height = self.size
        frame = Image.new("RGB", self.size, (15, 15, 24))
        draw = ImageDraw.Draw(frame)

        def dot(position: Position, color: tuple[int, int, int], radius: int) -> None:
            x, y = position.x / 100 * width, position.y / 100 * height
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)

        if world.alive:
            dot(world.player, (255, 0, 0), 7)
        for item in world.targets:
            dot(item.position, (0, 255, 0), 6)
        for item in world.threats:
            dot(item.position, (255, 0, 255), 6)
        draw_synthetic_hud(frame, self.arena.score, int(world.alive))
        return frame


class EpisodeRunner:
    def __init__(self, source, pipeline: VisionPipeline, sink, log_path: Path,
                 arena: Simulator | None = None, duration_ms: int = 100,
                 preview_dir: Path | None = None, hud_reader: HUDReader | None = None,
                 shot_model: "ShotModel | None" = None,
                 adaptation_path: Path | None = None,
                 adaptation_replay: Path | None = None,
                 memory_gateway=None) -> None:
        if adaptation_path and (shot_model is None or hud_reader is None):
            raise ValueError("adaptation needs an initial model and a visible HUD reader")
        from .shot_learning import ShotAdaptation
        self.memory_gateway = memory_gateway
        self.run_id = uuid.uuid4().hex
        self.source = source
        self.pipeline = pipeline
        self.sink = sink
        self.arena = arena
        self.duration_ms = duration_ms
        self.log_path = log_path
        self.preview_dir = preview_dir
        self.hud_reader = hud_reader
        self.reward_tracker = RewardTracker()
        self.forebrain = Forebrain()
        self.hindbrain = Hindbrain(shot_model=shot_model)
        self.tracker = ObjectTracker()
        self.adaptation = ShotAdaptation(shot_model) if adaptation_path else None
        self.adaptation_path = adaptation_path
        self.adaptation_replay = adaptation_replay

    def run(self, max_steps: int = 30) -> dict:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.preview_dir:
            self.preview_dir.mkdir(parents=True, exist_ok=True)
        total_reward = 0
        last_world = None
        with self.log_path.open("w", encoding="utf-8") as log:
            frame = self.source.read()
            initial = self.pipeline.process(frame, 0)
            before = self.tracker.update(initial.world)
            for tick in range(max_steps):
                perceived = initial
                if self.preview_dir:
                    perceived.annotated.save(self.preview_dir / f"view_{tick:03d}.jpg", quality=80)
                if before is None:
                    goal = intent = None
                    action = Action(reason="no unambiguous player; neutral")
                else:
                    goal = self.forebrain.update(before)
                    intent, action = self.hindbrain.decide(before, goal)
                self.sink.execute(action, self.duration_ms)
                result = self.arena.step(action) if self.arena else None
                after_frame = self.source.read()
                after_perceived = self.pipeline.process(after_frame, tick + 1)
                after = self.tracker.update(after_perceived.world)
                before_hud = self.hud_reader.read(perceived.playfield) if self.hud_reader else None
                after_hud = self.hud_reader.read(after_perceived.playfield) if self.hud_reader else None
                measured = self.reward_tracker.evaluate(before_hud, after_hud) if self.hud_reader else None
                reward = measured.reward if measured else result.reward if result else None
                shot_probability = (self.hindbrain.shot_model.probability(before.player,
                                    next(iter(before.threats)).position, action.fire)
                                    if before and len(before.threats) == 1 and action.fire != "NONE"
                                    and self.hindbrain.shot_model else None)
                accepted_before = len(self.adaptation.examples) if self.adaptation else 0
                updated = (self.adaptation.observe(before, action, after, before_hud, after_hud, measured)
                           if self.adaptation else False)
                if updated:
                    self.hindbrain.shot_model = self.adaptation.model
                if reward is not None:
                    total_reward += reward
                record = {"run_id": self.run_id, "tick": tick, "status": perceived.status,
                          "goal": asdict(goal) if goal else None,
                          "intent": asdict(intent) if intent else None,
                          "action": asdict(action),
                          "before": asdict(before) if before else None,
                          "after": asdict(after) if after else None,
                          "hud_before": asdict(before_hud) if before_hud else None,
                          "hud_after": asdict(after_hud) if after_hud else None,
                          "reward": reward,
                          "reward_origin": "pixels" if self.hud_reader else "simulator" if result else None,
                          "shot_probability": shot_probability,
                          "shot_adaptation_accepted": (len(self.adaptation.examples) > accepted_before
                                                        if self.adaptation else None),
                          "events": measured.events if measured else result.events if result else (),
                          "oracle_reward": result.reward if result else None,
                          "oracle_events": result.events if result else (),
                          "source": "rendered_simulator" if result else "camera"}
                log.write(json.dumps(record) + "\n")
                log.flush()
                last_world = after
                print(f"{tick:02d} {perceived.status} goal={goal.target_id if goal else '-'} "
                      f"move={action.move} fire={action.fire} "
                      f"reward={reward if reward is not None else '?'} "
                      f"events={','.join(measured.events) if measured and measured.events else '-'}")
                initial = after_perceived
                before = after
                if (result and result.done) or (after_hud and after_hud.lives == 0):
                    break
        if self.adaptation:
            if self.adaptation_replay:
                from .shot_learning import save_replay
                save_replay(self.adaptation.examples, self.adaptation_replay)
            if self.adaptation.updates:
                self.adaptation.model.save(self.adaptation_path)
        outcome = {"steps": tick + 1, "score": self.arena.score if self.arena else None,
                "reward": total_reward if (self.arena or self.hud_reader) else None,
                "done": self.arena.done if self.arena else None,
                "alive": self.arena.alive if self.arena else None,
                "last_state_available": last_world is not None,
                "adaptation_examples": len(self.adaptation.examples) if self.adaptation else None,
                "adaptation_skipped": self.adaptation.skipped if self.adaptation else None,
                "adaptation_updates": self.adaptation.updates if self.adaptation else None}
        if self.memory_gateway is not None:
            from memory.former import Experience
            import sqlite3
            try:
                self.memory_gateway.remember(Experience(
                    kind="observation", source="ppal:simulator" if self.arena else "robotron:camera",
                    summary=(f"Completed {tick + 1} PPAL steps. "
                             f"Measured reward: {outcome['reward']}. "
                             "This session alone does not establish policy improvement"),
                    significant=True, confidence=1.0,
                    tags=("ppal", "simulation" if self.arena else "robotron", "session"),
                    evidence=f"{self.log_path.resolve()} run={self.run_id}",
                ))
            except (OSError, sqlite3.Error) as exc:
                print(f"Memory queue unavailable ({type(exc).__name__}); session log retained")
        return outcome

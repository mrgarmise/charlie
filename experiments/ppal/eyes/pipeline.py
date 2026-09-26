"""Frame -> calibrated playfield -> candidates -> annotation and optional state."""

from dataclasses import dataclass

from PIL import Image, ImageDraw

from ..models import Object, Position, WorldState
from .calibration import Calibration
from .detectors import Detection, Detector


@dataclass
class FrameResult:
    playfield: Image.Image
    annotated: Image.Image
    detections: list[Detection]
    world: WorldState | None
    status: str


class VisionPipeline:
    def __init__(self, detector: Detector, calibration: Calibration | None = None) -> None:
        self.detector = detector
        self.calibration = calibration

    def process(self, frame: Image.Image, tick: int) -> FrameResult:
        playfield = self.calibration.apply(frame) if self.calibration else frame.convert("RGB")
        detections = self.detector.detect(playfield)
        players = [item for item in detections if item.kind == "player"]
        status = "CALIBRATED" if self.calibration else "UNCALIBRATED"
        world = None
        if len(players) == 1:
            others = {kind: [item for item in detections if item.kind == kind]
                      for kind in ("human", "threat")}
            def objects(kind: str) -> tuple[Object, ...]:
                return tuple(Object(f"{kind}_{index}", Position(*item.center))
                             for index, item in enumerate(others[kind], start=1))
            world = WorldState(tick, Position(*players[0].center), objects("human"), objects("threat"))
        else:
            status += f" | player candidates={len(players)}; no WorldState"
        annotated = playfield.copy()
        draw = ImageDraw.Draw(annotated)
        colors = {"player": "#00eaff", "human": "#7bff79", "threat": "#ff7070"}
        for item in detections:
            draw.rectangle(item.box, outline=colors.get(item.kind, "white"), width=2)
            draw.text((item.box[0], max(0, item.box[1] - 12)), item.kind.upper(),
                      fill=colors.get(item.kind, "white"))
        banner_y = max(0, annotated.height - 20)
        draw.rectangle((0, banner_y, min(annotated.width, 520), annotated.height), fill="black")
        draw.text((4, banner_y + 3), status, fill="white")
        return FrameResult(playfield, annotated, detections, world, status)

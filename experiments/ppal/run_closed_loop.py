"""PPAL-3: rendered-pixel simulation, or supervised Pi camera operation."""

import argparse
import json
from pathlib import Path

from .arcade_transport import ArcadeController
from .closed_loop import ArenaRenderer, EpisodeRunner
from .eyes.cli import SYNTHETIC_PROFILE
from .eyes.calibration import Calibration
from .eyes.detectors import ColorBlobDetector
from .eyes.hud import BitmapHUDReader
from .eyes.pipeline import VisionPipeline
from .eyes.sources import PiCameraSource
from .eyes.readiness import audit
from .hands import RecordingSink
from .simulator import Simulator
from .shot_learning import ShotModel


def validate_live_args(args: argparse.Namespace) -> None:
    if not args.arm:
        return
    if args.mode != "camera" or not args.host or not args.profile or not args.calibration:
        raise ValueError("--arm requires --mode camera, --host, --profile and --calibration")
    if args.profile.resolve() == SYNTHETIC_PROFILE.resolve():
        raise ValueError("the synthetic color profile cannot arm the arcade")
    if args.max_steps > 100:
        raise ValueError("armed runs are limited to 100 steps")
    if getattr(args, "shot_model", None):
        raise ValueError("synthetic shot models cannot arm the arcade")
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    synthetic = json.loads(SYNTHETIC_PROFILE.read_text(encoding="utf-8"))
    if profile.get("draft") or profile.get("rules") == synthetic.get("rules"):
        raise ValueError("review and tune a real-frame profile before arming")
    if not {"player", "human", "threat"}.issubset(
            {rule.get("kind") for rule in profile.get("rules", [])}):
        raise ValueError("armed profile needs player, human and threat rules")


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-3 closed loop")
    parser.add_argument("--remember", action="store_true",
                        help="queue session evidence through Charlie memory evaluator; works offline")
    parser.add_argument("--mode", choices=("synthetic", "camera"), default="synthetic")
    parser.add_argument("--arm", action="store_true", help="send camera-driven actions to Charlie Arcade")
    parser.add_argument("--host", help="Charlie Arcade host/IP when armed")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--controller-protocol", choices=("positions", "legacy"), default="positions")
    parser.add_argument("--profile", type=Path, help="measured Robotron HSV profile")
    parser.add_argument("--calibration", type=Path, help="measured playfield corners")
    parser.add_argument("--hud-profile", type=Path, help="bitmap score/lives templates; omit for unknown reward")
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--duration-ms", type=int, default=100)
    parser.add_argument("--log", type=Path, default=Path("ppal_closed_loop.jsonl"))
    parser.add_argument("--preview-dir", type=Path)
    parser.add_argument("--preflight-dir", type=Path, default=Path("ppal_live_preflight"))
    parser.add_argument("--shot-model", type=Path, help="optional PPAL-5 synthetic shot model")
    parser.add_argument("--adapt-shot-model", type=Path,
                        help="write updated model only after enough clear pixel-labeled shots")
    parser.add_argument("--adapt-replay", type=Path, default=Path("ppal6_adaptation.jsonl"))
    parser.add_argument("--synthetic-shot-scale", type=float, default=1.0,
                        help="toy firing-lane width multiplier for adaptation tests")
    args = parser.parse_args()
    try:
        validate_live_args(args)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    if args.max_steps < 1 or not 30 <= args.duration_ms <= 500:
        parser.error("max-steps must be positive and duration-ms must be 30..500")
    if args.shot_model and args.mode != "synthetic":
        parser.error("the synthetic shot model requires --mode synthetic")
    if args.adapt_shot_model and (not args.shot_model or args.mode != "synthetic"):
        parser.error("--adapt-shot-model requires --shot-model and --mode synthetic")
    if args.adapt_shot_model and args.adapt_shot_model.resolve() == args.shot_model.resolve():
        parser.error("--adapt-shot-model must be a different file from --shot-model")
    if args.synthetic_shot_scale <= 0 or (args.mode != "synthetic" and args.synthetic_shot_scale != 1.0):
        parser.error("--synthetic-shot-scale must be positive and requires synthetic mode")

    arena = Simulator(shot_lane_scale=args.synthetic_shot_scale) if args.mode == "synthetic" else None
    source = None
    try:
        profile = (args.profile or SYNTHETIC_PROFILE) if arena else args.profile
        detector = ColorBlobDetector.load(profile) if profile else ColorBlobDetector([])
        calibration = Calibration.load(args.calibration) if args.calibration else None
        pipeline = VisionPipeline(detector, calibration)
        synthetic_hud = Path(__file__).parent / "eyes" / "profiles" / "synthetic_hud.json"
        hud_profile = args.hud_profile or (synthetic_hud if arena else None)
        hud_reader = BitmapHUDReader.load(hud_profile) if hud_profile else None
        shot_model = ShotModel.load(args.shot_model) if args.shot_model else None
        source = ArenaRenderer(arena) if arena else PiCameraSource()
        if args.arm:
            summary = audit(source, pipeline, args.preflight_dir, frames=3,
                            interval_ms=100, hud_reader=hud_reader)
            if summary["player_frames"] != 3 or summary["human_frames"] < 2:
                raise RuntimeError(f"camera preflight found uncertain player/human candidates: {summary}; "
                                   f"inspect {args.preflight_dir} and keep controls neutral")
            print(f"Camera preflight: {summary}; previews={args.preflight_dir}")
        sink = ArcadeController(args.host, args.port,
                                protocol=args.controller_protocol) if args.arm else RecordingSink()
        with sink:
            gateway = None
            if args.remember:
                from memory.gateway import MemoryGateway
                gateway = MemoryGateway()
            outcome = EpisodeRunner(source, pipeline, sink, args.log, arena,
                                    args.duration_ms, args.preview_dir, hud_reader, shot_model,
                                    args.adapt_shot_model,
                                    args.adapt_replay if args.adapt_shot_model else None,
                                    memory_gateway=gateway).run(args.max_steps)
        print(f"OUTCOME {outcome} log={args.log} "
              f"controller={'ARCADE' if args.arm else 'DRY RUN'}")
    finally:
        if source is not None and hasattr(source, "close"):
            source.close()


if __name__ == "__main__":
    main()

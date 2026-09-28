"""Offline Robotron replay laboratory.

Replays saved corrected playfield frames (view_*.jpg) through Charlie's current
taught recognizer, persistent self tracker, gameplay object tracker, Forebrain,
and Hindbrain.  This module NEVER opens ArcadeController and cannot send input.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

from PIL import Image

from .forebrain import Forebrain
from .hindbrain import Hindbrain
from .models import Action, Object, Position, WorldState
from .robotron_session import PersistentSelfTracker
from .vision_tracker import ObjectTracker
from .eyes.taught_recognizer import TaughtRecognizer

HUMANS = {"dad", "mom", "kid"}
THREATS = {"grunt", "hulk", "red_circle_enemy", "mine"}


def _distance(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _objects(pairs, identities, prefix):
    accepted = []
    for detection, evidence in pairs:
        if detection.kind in identities:
            accepted.append((detection.kind, tuple(detection.center)))
    accepted.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
    return tuple(
        Object(f"{prefix}_{kind}_{i}", Position(*center))
        for i, (kind, center) in enumerate(accepted, 1)
    )


def _appearance_player(pairs, previous=None, min_score=0.78, max_distance=15.0):
    choices = []
    for detection, evidence in pairs:
        score = float(evidence.get("class_scores", {}).get("player", -1.0))
        if detection.kind != "player" and score < min_score:
            continue
        center = tuple(detection.center)
        distance = 0.0 if previous is None else _distance(center, previous)
        if previous is None or distance <= max_distance:
            choices.append((score, -distance, center))
    if not choices:
        return None
    choices.sort(reverse=True)
    if len(choices) > 1 and choices[0][0] - choices[1][0] < 0.02:
        return None
    return choices[0][2]


def _action_dict(action):
    fire = "NONE" if action.fire == "STAY" else action.fire
    return {"move": action.move, "fire": fire, "reason": action.reason}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--knowledge", type=Path,
                        default=Path("config/robotron/sprite-knowledge.json"))
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--margin", type=float, default=0.04)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-frames", type=int, default=0,
                        help="0 means replay every view_*.jpg frame")
    args = parser.parse_args()

    frames = sorted(args.recording.glob("view_*.jpg"))
    if not frames:
        parser.error(f"no view_*.jpg frames found in {args.recording}")
    if args.max_frames:
        frames = frames[:args.max_frames]

    if args.output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output = Path(f"robotron-runs/replay-{stamp}")
    args.output.mkdir(parents=True, exist_ok=False)

    recognizer = TaughtRecognizer.load(args.knowledge, args.threshold, args.margin)
    self_tracker = PersistentSelfTracker(max_distance=7.0, max_missed=3)
    object_tracker = ObjectTracker()
    forebrain = Forebrain()
    hindbrain = Hindbrain()

    player = None
    rows = []
    action_counts = Counter()
    acquisition_tick = None
    reacquisitions = 0

    print(f"ROBOTRON REPLAY: {len(frames)} corrected playfield frames")
    print("OFFLINE ONLY: no controller is opened")

    for tick, frame_path in enumerate(frames):
        with Image.open(frame_path) as image:
            pairs = recognizer.detect(image.convert("RGB"))
        detections = [d for d, _ in pairs]

        if player is None:
            candidate = _appearance_player(pairs)
            if candidate is not None:
                obs = self_tracker.seed(tick, detections, candidate, max_seed_distance=7.0)
                if obs.center is not None:
                    player = obs.center
                    acquisition_tick = tick
                    print(f"SELF ACQUIRED frame={tick} track={obs.track_id} "
                          f"x={player[0]:.2f} y={player[1]:.2f}")
        else:
            obs = self_tracker.update(tick, detections)
            if obs.center is not None:
                player = obs.center
            else:
                candidate = _appearance_player(
                    pairs, previous=player,
                    min_score=0.72,
                    max_distance=min(28.0, 12.0 + self_tracker.misses * 3.0),
                )
                if candidate is not None:
                    obs = self_tracker.reseed(
                        tick, detections, candidate, max_seed_distance=7.0)
                    if obs.center is not None:
                        player = obs.center
                        reacquisitions += 1

        targets = _objects(pairs, HUMANS, "human")
        threats = _objects(pairs, THREATS, "threat")

        row = {
            "tick": tick,
            "frame": frame_path.name,
            "detections": len(detections),
            "self_track_id": self_tracker.player_track_id,
            "player": list(player) if player is not None else None,
        }

        if player is None:
            row["status"] = "self_unknown"
            rows.append(row)
            continue

        world = WorldState(
            tick=tick,
            player=Position(*player),
            targets=targets,
            threats=threats,
            alive=True,
        )
        world = object_tracker.update(world)
        goal = forebrain.update(world)
        intent, action = hindbrain.decide(world, goal)
        action_data = _action_dict(action)
        action_counts[(action_data["move"], action_data["fire"])] += 1

        row.update({
            "status": "decision",
            "targets": [{"id": x.id, "x": x.position.x, "y": x.position.y}
                        for x in world.targets],
            "threats": [{"id": x.id, "x": x.position.x, "y": x.position.y}
                        for x in world.threats],
            "goal": {"kind": goal.kind, "target_id": goal.target_id},
            "intent": {"kind": intent.kind, "target_id": intent.target_id},
            "action": action_data,
        })
        rows.append(row)

    tracks = self_tracker.tracks()
    summary = {
        "recording": str(args.recording),
        "frames": len(frames),
        "decision_frames": sum(r["status"] == "decision" for r in rows),
        "self_unknown_frames": sum(r["status"] == "self_unknown" for r in rows),
        "self_acquisition_tick": acquisition_tick,
        "self_reacquisitions": reacquisitions,
        "self_tracks_seen": len(tracks),
        "actions": [
            {"move": move, "fire": fire, "count": count}
            for (move, fire), count in action_counts.most_common()
        ],
    }

    (args.output / "replay.json").write_text(json.dumps(rows, indent=2) + "\n")
    (args.output / "tracks.json").write_text(
        json.dumps({"tracks": tracks}, indent=2) + "\n")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(f"DECISIONS: {summary['decision_frames']}/{summary['frames']} frames")
    print(f"SELF UNKNOWN: {summary['self_unknown_frames']} frames")
    print(f"SELF REACQUISITIONS: {reacquisitions}")
    print(f"Evidence: {args.output}")


if __name__ == "__main__":
    main()

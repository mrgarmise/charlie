"""Small live Robotron runner using Charlie's taught eyes and PPAL brain.

This is deliberately bounded: gameplay time defaults to 20 seconds and the
controller is neutralized on every pulse, on vision loss, and on exit.
Normal play reuses the promoted playfield calibration for fast startup. Charlie
may start Robotron himself after the camera is ready, then waits for visual proof
of gameplay before acquiring self. Fresh calibration remains opt-in and occurs
only after START because the Robotron border exists only during gameplay. The
run clock starts only after player acquisition.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import time

from .arcade_transport import ArcadeController
from .forebrain import Forebrain
from .hindbrain import Hindbrain
from .models import Action, Object, Position, WorldState
from .eyes.sources import PiCameraSource
from .eyes.calibration import Calibration
from .eyes.settle import prepare
from .eyes.taught_recognizer import TaughtRecognizer

HUMANS = {"dad", "mom", "kid"}
THREATS = {"grunt", "hulk", "red_circle_enemy", "mine"}


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _center_bootstrap(pairs, radius=5.0):
    near = [d for d, _ in pairs if _distance(d.center, (50.0, 50.0)) <= radius]
    return tuple(near[0].center) if len(near) == 1 else None


def _player_fix(pairs, previous, max_distance=12.0, min_score=0.78):
    """Carry self identity locally; appearance is evidence, not sole authority."""
    choices = []
    for detection, evidence in pairs:
        score = float(evidence.get("class_scores", {}).get("player", -1.0))
        distance = _distance(detection.center, previous)
        if distance <= max_distance and (score >= min_score or detection.kind == "player"):
            choices.append((distance, -score, tuple(detection.center)))
    if not choices:
        return None
    choices.sort()
    if len(choices) > 1 and choices[1][0] - choices[0][0] < 1.0:
        return None
    return choices[0][2]


def _objects(pairs, identities, prefix):
    accepted = []
    for detection, evidence in pairs:
        if detection.kind in identities:
            accepted.append((detection.kind, tuple(detection.center)))
    accepted.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
    return tuple(Object(f"{prefix}_{kind}_{i}", Position(*center))
                 for i, (kind, center) in enumerate(accepted, 1))



def _quick_frames(source, calibration, recognizer, count=5, interval=0.035):
    frames = []
    for _ in range(count):
        playfield = calibration.apply(source.read())
        frames.append(recognizer.detect(playfield))
        if interval:
            time.sleep(interval)
    return frames


def _appearance_bootstrap(frames, min_score=0.82, max_spread=4.0):
    """Use repeated strong player appearance only when it forms one stable cluster."""
    points = []
    for pairs in frames:
        candidates = []
        for detection, evidence in pairs:
            score = float(evidence.get("class_scores", {}).get("player", -1.0))
            if detection.kind == "player" or score >= min_score:
                candidates.append((score, tuple(detection.center)))
        if len(candidates) == 1:
            points.append(candidates[0][1])
    if len(points) < 3:
        return None
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    if max(_distance(p, (cx, cy)) for p in points) > max_spread:
        return None
    return (cx, cy)


def _causal_bootstrap(before_frames, after_frames, direction="E", min_motion=0.20,
                      max_match=7.0, min_player_score=0.72):
    """Find the sprite whose observed displacement matches our tiny probe command."""
    if direction != "E":
        raise ValueError("initial causal bootstrap currently supports E only")
    before = before_frames[-1] if before_frames else []
    after = after_frames[-1] if after_frames else []
    candidates = []
    for bd, be in before:
        pscore = float(be.get("class_scores", {}).get("player", -1.0))
        mscore = float(be.get("class_scores", {}).get("mine", -1.0))
        if pscore < min_player_score or mscore > pscore + 0.02:
            continue
        for ad, ae in after:
            dist = _distance(bd.center, ad.center)
            dx = ad.center[0] - bd.center[0]
            dy = ad.center[1] - bd.center[1]
            if dist <= max_match and dx >= min_motion and abs(dy) <= max(2.5, abs(dx) * 1.5):
                ascore = float(ae.get("class_scores", {}).get("player", -1.0))
                score = pscore + ascore + dx * 0.05 - abs(dy) * 0.02
                candidates.append((score, tuple(ad.center), dx, dy))
    candidates.sort(reverse=True)
    if not candidates:
        return None
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.03:
        return None
    return candidates[0][1]

def _stable_center_bootstrap(frames, radius=5.0, min_support=3, max_spread=3.0):
    """Require the new-game center candidate to persist, not merely flash once."""
    points = []
    for pairs in frames:
        near = [tuple(d.center) for d, _ in pairs
                if _distance(d.center, (50.0, 50.0)) <= radius]
        if len(near) == 1:
            points.append(near[0])
    if len(points) < min_support:
        return None
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    if max(_distance(p, (cx, cy)) for p in points) > max_spread:
        return None
    return (cx, cy)


def _acquire_from_frames(frames):
    """Prefer a stable untouched center spawn, then repeated appearance evidence."""
    player = _stable_center_bootstrap(frames)
    if player is not None:
        return player, "new_game_center"
    player = _appearance_bootstrap(frames)
    if player is not None:
        return player, "appearance"
    return None, None


def _pair_evidence(pairs):
    rows = []
    for detection, evidence in pairs:
        scores = evidence.get("class_scores", {})
        rows.append({
            "kind": detection.kind,
            "center": [round(float(detection.center[0]), 3),
                       round(float(detection.center[1]), 3)],
            "player_score": round(float(scores.get("player", -1.0)), 4),
            "mine_score": round(float(scores.get("mine", -1.0)), 4),
            "best_score": round(float(evidence.get("score", -1.0)), 4),
            "runner_up": round(float(evidence.get("runner_up", -1.0)), 4),
        })
    return rows


def _wait_for_gameplay(source, calibration, recognizer, evidence_dir, timeout=4.0):
    """Observe quietly after START and preserve why acquisition passed or failed."""
    deadline = time.monotonic() + timeout
    collected = []
    watch = []
    frame_no = 0
    first_visual = None
    while time.monotonic() < deadline:
        playfield = calibration.apply(source.read())
        pairs = recognizer.detect(playfield)
        collected.append(pairs)
        collected = collected[-6:]
        center = _stable_center_bootstrap(collected)
        appearance = _appearance_bootstrap(collected)
        entry = {
            "frame": frame_no,
            "t": round(timeout - max(0.0, deadline - time.monotonic()), 4),
            "candidate_count": len(pairs),
            "stable_center": list(center) if center else None,
            "stable_appearance": list(appearance) if appearance else None,
            "candidates": _pair_evidence(pairs),
        }
        watch.append(entry)
        if pairs and first_visual is None:
            first_visual = frame_no
            print(f"GAMEPLAY VISUAL CANDIDATES detected at watch frame {frame_no}")
        # Save a small visual trail without turning every run into a frame dump.
        if frame_no < 4 or frame_no % 8 == 0 or center is not None:
            playfield.save(evidence_dir / f"startup-{frame_no:03d}.png")
        if center is not None:
            return center, "new_game_center", collected, watch, first_visual
        frame_no += 1
        time.sleep(0.025)

    # Only after the protected center-spawn watch expires do we allow appearance.
    player = _appearance_bootstrap(collected)
    if player is not None:
        return player, "appearance_after_center_window", collected, watch, first_visual
    return None, None, collected, watch, first_visual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--host", default="charlie-arcade.local")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--pulse-ms", type=int, default=80)
    parser.add_argument("--knowledge", type=Path,
                        default=Path("config/robotron/sprite-knowledge.json"))
    parser.add_argument("--calibration", type=Path,
                        default=Path("config/robotron/playfield-latest.json"),
                        help="promoted playfield calibration used for fast startup")
    parser.add_argument("--recalibrate", action="store_true",
                        help="after START, rediscover the live game border instead of loading --calibration")
    parser.add_argument("--no-start-game", action="store_true",
                        help="do not tap START; use when Robotron gameplay is already running")
    parser.add_argument("--start-wait", type=float, default=4.0,
                        help="seconds to wait after START for visual gameplay/self evidence")
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--margin", type=float, default=0.04)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--arm", action="store_true",
                        help="actually send movement/fire commands")
    args = parser.parse_args()

    if not 1 <= args.seconds <= 60:
        parser.error("--seconds must be 1..60")
    if not 30 <= args.pulse_ms <= 200:
        parser.error("--pulse-ms must be 30..200")
    if not 1.0 <= args.start_wait <= 10.0:
        parser.error("--start-wait must be 1..10 seconds")
    if args.output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output = Path(f"robotron-runs/play-{stamp}")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)

    recognizer = TaughtRecognizer.load(args.knowledge, args.threshold, args.margin)
    forebrain = Forebrain()
    hindbrain = Hindbrain()
    source = PiCameraSource()
    rows = []
    controller = None
    result = "not started"

    try:
        # Start the camera first. In normal operation this happens while Robotron
        # is still in attract/demo mode, giving exposure/AF time without costing
        # any gameplay. No demo-screen calibration is attempted.
        for _ in range(6):
            source.read()
            time.sleep(0.04)

        auto_start = args.arm and not args.no_start_game
        if auto_start:
            controller = ArcadeController(args.host, args.port, protocol="positions")
            print("CAMERA READY; tapping Robotron START")
            controller._command("START")  # Zero v2 protocol: momentary button tap
            print("START sent; waiting for visual gameplay evidence")

        if args.recalibrate:
            if not args.arm and not args.no_start_game:
                raise RuntimeError("--recalibrate needs live gameplay; start the game first and use --no-start-game")
            calibration = prepare(source, args.output)
            calibration_mode = "fresh"
        else:
            if not args.calibration.exists():
                raise RuntimeError(
                    f"saved calibration missing: {args.calibration}; run once with --recalibrate")
            calibration = Calibration.load(args.calibration)
            calibration_mode = "saved"
            print(f"Loaded calibration: {args.calibration}")

        if auto_start:
            player, acquisition, frames, startup_watch, gameplay_visual_frame = _wait_for_gameplay(
                source, calibration, recognizer, args.output, timeout=args.start_wait)
        else:
            frames = _quick_frames(source, calibration, recognizer, count=5)
            startup_watch = []
            gameplay_visual_frame = None
            player, acquisition = _acquire_from_frames(frames)

        # If appearance cannot settle the question, ask the game one tiny causal
        # question: move east briefly and watch which player-like sprite obeys.
        if player is None and args.arm:
            if controller is None:
                controller = ArcadeController(args.host, args.port, protocol="positions")
            print("CENTER WATCH EXPIRED; self-ID still ambiguous; trying one 60ms east probe")
            controller.execute(Action("E", "NONE", "causal self-identification"), 60)
            after_frames = _quick_frames(source, calibration, recognizer, count=4, interval=0.025)
            player = _causal_bootstrap(frames, after_frames)
            if player is not None:
                acquisition = "causal_east_probe"
                frames = after_frames

        if player is None:
            raise RuntimeError("could not identify the player; controls neutral")

        print(f"PLAYER ACQUIRED ({acquisition}) x={player[0]:.2f} y={player[1]:.2f}")
        if not args.arm:
            result = "PREFLIGHT PASS: player acquired; controls untouched"
            print(result)
            return

        if controller is None:
            controller = ArcadeController(args.host, args.port, protocol="positions")
        started = time.monotonic()
        deadline = started + args.seconds
        tick = 0
        lost = 0
        print(f"CHARLIE LOOSE: {args.seconds:.1f}s hard gameplay limit")

        while time.monotonic() < deadline:
            raw = source.read()
            playfield = calibration.apply(raw)
            pairs = recognizer.detect(playfield)
            new_player = _player_fix(pairs, player)
            if new_player is None:
                lost += 1
                rows.append({"tick": tick, "t": time.monotonic()-started,
                             "status": "player_lost", "lost": lost})
                # Do not act on a guessed self location.
                if lost >= 3:
                    result = "STOPPED: player lost for 3 consecutive frames"
                    print(result)
                    break
                tick += 1
                continue
            player = new_player
            lost = 0

            targets = _objects(pairs, HUMANS, "human")
            threats = _objects(pairs, THREATS, "threat")
            world = WorldState(tick=tick, player=Position(*player),
                               targets=targets, threats=threats, alive=True)
            goal = forebrain.update(world)
            intent, action = hindbrain.decide(world, goal)
            # Hindbrain direction() uses STAY for a zero/deadband vector.
            # That is valid for movement, but the arcade firing vocabulary uses
            # NONE for a centered right stick. Normalize at the transport edge.
            if action.fire == "STAY":
                action = Action(action.move, "NONE", action.reason)

            remaining_ms = int(max(0.0, deadline-time.monotonic()) * 1000)
            if remaining_ms < 30:
                result = "TIME LIMIT"
                break
            pulse_ms = min(args.pulse_ms, remaining_ms)
            if pulse_ms < 30:
                result = "TIME LIMIT"
                break
            controller.execute(action, pulse_ms)
            rows.append({
                "tick": tick, "t": time.monotonic()-started,
                "player": list(player),
                "targets": len(targets), "threats": len(threats),
                "goal": {"kind": goal.kind, "target_id": goal.target_id},
                "intent": {"kind": intent.kind, "target_id": intent.target_id},
                "action": {"move": action.move, "fire": action.fire,
                           "reason": action.reason},
            })
            tick += 1
        else:
            result = "TIME LIMIT"

        print(f"RUN COMPLETE: {result}; ticks={tick}")
    except KeyboardInterrupt:
        result = "INTERRUPTED"
        print("INTERRUPTED; neutralizing")
    finally:
        if controller is not None:
            try:
                controller.close()
            except (OSError, ConnectionError):
                pass
        source.close()
        report = {"result": result, "armed": args.arm, "seconds": args.seconds,
                  "pulse_ms": args.pulse_ms, "ticks": len(rows),
                  "auto_start": bool(args.arm and not args.no_start_game),
                  "calibration_mode": locals().get("calibration_mode"),
                  "acquisition": locals().get("acquisition"),
                  "gameplay_visual_frame": locals().get("gameplay_visual_frame"),
                  "startup_watch": locals().get("startup_watch", []),
                  "steps": rows}
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Evidence: {args.output}/report.json")


if __name__ == "__main__":
    main()

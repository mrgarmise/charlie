"""One bounded Robotron eye->hand->eye experiment.

The default is observation-only. --arm permits exactly one movement pulse, with
no firing, only after repeated player evidence. Controls are closed/neutralized
before post-action observation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time
from datetime import datetime

from .arcade_transport import ArcadeController
from .models import Action
from .eyes.sources import PiCameraSource
from .eyes.settle import prepare
from .eyes.taught_recognizer import TaughtRecognizer


@dataclass(frozen=True)
class PlayerFix:
    center: tuple[float, float]
    supporting_frames: int
    frames: int
    spread: float


def stable_player_fix(frame_players, min_support=4, max_spread=4.0):
    """Accept one spatially stable player candidate in enough frames.

    Frames with zero or multiple player candidates do not support the fix.
    This deliberately abstains rather than choosing among ambiguous candidates.
    """
    points = [players[0] for players in frame_players if len(players) == 1]
    if len(points) < min_support:
        return None
    x = float(np_median([p[0] for p in points]))
    y = float(np_median([p[1] for p in points]))
    spread = max(math.hypot(px - x, py - y) for px, py in points)
    if spread > max_spread:
        return None
    return PlayerFix((x, y), len(points), len(frame_players), spread)


def np_median(values):
    ordered = sorted(float(v) for v in values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def direction_verified(before, after, direction, minimum=0.25):
    dx = after[0] - before[0]
    dy = after[1] - before[1]
    checks = {
        "E": dx >= minimum,
        "W": dx <= -minimum,
        "S": dy >= minimum,
        "N": dy <= -minimum,
    }
    if direction not in checks:
        raise ValueError("probe direction must be N, E, S, or W")
    return checks[direction], dx, dy


def center_bootstrap_fix(frame_candidates, min_support=4, center=(50.0, 50.0),
                         radius=4.0, max_spread=4.0):
    """Bootstrap player identity from Robotron's untouched new-game spawn.

    At the start of a new game the player is known to spawn at playfield center.
    This rule is used only to acquire the initial identity; it is not a general
    "center means player" classifier.  Exactly one candidate must be near center
    in each supporting frame and that candidate must remain spatially stable.
    """
    points = []
    for candidates in frame_candidates:
        near = [c["center"] for c in candidates
                if math.hypot(c["center"][0] - center[0],
                              c["center"][1] - center[1]) <= radius]
        if len(near) == 1:
            points.append(tuple(near[0]))
    if len(points) < min_support:
        return None
    x = float(np_median([p[0] for p in points]))
    y = float(np_median([p[1] for p in points]))
    spread = max(math.hypot(px - x, py - y) for px, py in points)
    if spread > max_spread:
        return None
    return PlayerFix((x, y), len(points), len(frame_candidates), spread)


def anchored_player_fix(frame_candidates, anchor, min_support=4, max_distance=12.0,
                        min_player_score=0.82, max_spread=5.0):
    """Reacquire the bootstrapped player after one short movement pulse.

    Identity is carried forward from the known center spawn. Candidates must be
    near the prior player position and retain meaningful similarity to the
    human-taught player class, but need not win the appearance margin test.
    """
    points = []
    for candidates in frame_candidates:
        eligible = [c for c in candidates
                    if c.get("player_score", -1.0) >= min_player_score
                    and math.hypot(c["center"][0] - anchor[0],
                                   c["center"][1] - anchor[1]) <= max_distance]
        if not eligible:
            continue
        eligible.sort(key=lambda c: (
            math.hypot(c["center"][0] - anchor[0], c["center"][1] - anchor[1]),
            -c.get("player_score", -1.0),
        ))
        # Do not choose between two nearly equidistant plausible candidates.
        if len(eligible) > 1:
            d0 = math.hypot(eligible[0]["center"][0] - anchor[0], eligible[0]["center"][1] - anchor[1])
            d1 = math.hypot(eligible[1]["center"][0] - anchor[0], eligible[1]["center"][1] - anchor[1])
            if d1 - d0 < 1.5:
                continue
        points.append(tuple(eligible[0]["center"]))
    if len(points) < min_support:
        return None
    x = float(np_median([p[0] for p in points]))
    y = float(np_median([p[1] for p in points]))
    spread = max(math.hypot(px - x, py - y) for px, py in points)
    if spread > max_spread:
        return None
    return PlayerFix((x, y), len(points), len(frame_candidates), spread)



def stationary_anchor_fix(frame_candidates, anchor, min_support=4, max_distance=12.0,
                          max_spread=1.5, mine_margin=0.02):
    """Use neutral-control stillness as evidence for the player's identity.

    Candidates are clustered by continuity near the last player position. A
    cluster must remain nearly stationary while controls are neutral. Strongly
    mine-like candidates are excluded because mines are also stationary.
    """
    clusters = []
    for candidates in frame_candidates:
        eligible = []
        for c in candidates:
            center = tuple(c["center"])
            if math.hypot(center[0] - anchor[0], center[1] - anchor[1]) > max_distance:
                continue
            scores = c.get("class_scores", {})
            player_score = scores.get("player", c.get("player_score", -1.0))
            mine_score = scores.get("mine", -1.0)
            if mine_score >= player_score + mine_margin:
                continue
            eligible.append(c)
        used = set()
        for cluster in clusters:
            last = cluster[-1]["center"]
            choices = [(math.hypot(c["center"][0]-last[0], c["center"][1]-last[1]), i, c)
                       for i, c in enumerate(eligible) if i not in used]
            if choices:
                distance, i, c = min(choices)
                if distance <= 2.5:
                    cluster.append(c); used.add(i)
        for i, c in enumerate(eligible):
            if i not in used:
                clusters.append([c])
    viable = []
    for cluster in clusters:
        if len(cluster) < min_support:
            continue
        xs = [c["center"][0] for c in cluster]
        ys = [c["center"][1] for c in cluster]
        center = (float(np_median(xs)), float(np_median(ys)))
        spread = max(math.hypot(c["center"][0]-center[0], c["center"][1]-center[1]) for c in cluster)
        if spread <= max_spread:
            viable.append((math.hypot(center[0]-anchor[0], center[1]-anchor[1]), center, len(cluster), spread))
    if not viable:
        return None
    viable.sort()
    if len(viable) > 1 and viable[1][0] - viable[0][0] < 1.5:
        return None
    _, center, support, spread = viable[0]
    return PlayerFix(center, support, len(frame_candidates), spread)


def motion_probe_fix(neutral_fix, moved_candidates, direction, min_support=3,
                     minimum=0.20, max_distance=6.0):
    """Identify the controlled sprite by its response to a tiny commanded move."""
    if neutral_fix is None:
        return None
    points = []
    for candidates in moved_candidates:
        choices = []
        for c in candidates:
            center = tuple(c["center"])
            distance = math.hypot(center[0]-neutral_fix.center[0], center[1]-neutral_fix.center[1])
            if distance > max_distance:
                continue
            ok, _, _ = direction_verified(neutral_fix.center, center, direction, minimum=minimum)
            if ok:
                choices.append((distance, center))
        if choices:
            points.append(min(choices)[1])
    if len(points) < min_support:
        return None
    x = float(np_median([p[0] for p in points])); y = float(np_median([p[1] for p in points]))
    spread = max(math.hypot(px-x, py-y) for px, py in points)
    if spread > 4.0:
        return None
    return PlayerFix((x, y), len(points), len(moved_candidates), spread)

def observe(source, calibration, recognizer, frames, interval_ms, evidence_dir, phase):
    frame_players = []
    frame_candidates = []
    rows = []
    for tick in range(frames):
        raw = source.read()
        playfield = calibration.apply(raw)
        pairs = recognizer.detect(playfield)
        players = [d.center for d, ev in pairs if d.kind == "player"]
        frame_players.append(players)
        candidates = [
            {"kind": d.kind, "center": list(d.center), "box": list(d.box),
             "score": ev["score"], "runner_up": ev["runner_up"],
             "player_score": ev["class_scores"].get("player", -1.0),
             "class_scores": ev["class_scores"]}
            for d, ev in pairs
        ]
        frame_candidates.append(candidates)
        rows.append({
            "frame": tick,
            "players": [list(p) for p in players],
            "candidates": candidates,
        })
        playfield.save(evidence_dir / f"{phase}-{tick:02d}.png")
        if interval_ms and tick + 1 < frames:
            time.sleep(interval_ms / 1000)
    return stable_player_fix(frame_players), frame_candidates, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge", type=Path,
                        default=Path("config/robotron/sprite-knowledge.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument("--interval-ms", type=int, default=80)
    parser.add_argument("--move", choices=("N", "E", "S", "W"), default="E")
    parser.add_argument("--duration-ms", type=int, default=100)
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--margin", type=float, default=0.04)
    parser.add_argument("--arm", action="store_true")
    parser.add_argument("--active-recovery", action="store_true",
                        help="if normal reacquisition fails, permit one extra tiny motion probe")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--protocol", choices=("positions", "legacy"), default="positions")
    args = parser.parse_args()

    if not 4 <= args.frames <= 20:
        parser.error("--frames must be 4..20")
    if not 30 <= args.duration_ms <= 200:
        parser.error("visual probe --duration-ms must be 30..200")
    if args.arm and not args.host:
        parser.error("--arm requires --host")
    if args.active_recovery and not args.arm:
        parser.error("--active-recovery requires --arm")
    if args.output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output = Path(f"robotron-runs/visual-control-probe-{stamp}")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}; choose a new directory")
    args.output.mkdir(parents=True)

    recognizer = TaughtRecognizer.load(args.knowledge, args.threshold, args.margin)
    source = PiCameraSource()
    report = {"armed": args.arm, "move": args.move, "duration_ms": args.duration_ms}
    try:
        calibration = prepare(source, args.output)
        appearance_before, before_candidates, before_rows = observe(
            source, calibration, recognizer, args.frames, args.interval_ms, args.output, "before")
        before = appearance_before or center_bootstrap_fix(before_candidates)
        acquisition = "appearance" if appearance_before else ("new_game_center" if before else None)
        report["before_frames"] = before_rows
        report["before_fix"] = vars(before) if before else None
        report["acquisition"] = acquisition
        if before is None:
            report["result"] = "ABORTED: no stable player fix (appearance or new-game center); controls never connected"
            print(report["result"])
            return
        print(f"Player fix BEFORE ({acquisition}): x={before.center[0]:.2f} y={before.center[1]:.2f} "
              f"support={before.supporting_frames}/{before.frames} spread={before.spread:.2f}")
        if not args.arm:
            report["result"] = "PREFLIGHT PASS: unarmed; no controller connection made"
            print(report["result"])
            return

        # Exactly one bounded movement pulse. Context manager guarantees neutral/close.
        with ArcadeController(args.host, args.port, protocol=args.protocol) as controller:
            controller.execute(Action(move=args.move, fire="NONE",
                                      reason="one-step visual control probe"), args.duration_ms)
        report["pulse_sent"] = True
        time.sleep(0.12)

        appearance_after, after_candidates, after_rows = observe(
            source, calibration, recognizer, args.frames, args.interval_ms, args.output, "after")
        anchored_after = anchored_player_fix(after_candidates, before.center,
                                             min_player_score=args.threshold)
        stationary_after = None if (appearance_after or anchored_after) else stationary_anchor_fix(
            after_candidates, before.center)
        after = appearance_after or anchored_after or stationary_after
        report["after_frames"] = after_rows
        report["after_fix"] = vars(after) if after else None
        report["reacquisition"] = ("appearance" if appearance_after else
                                   ("anchored" if anchored_after else
                                    ("neutral_stationary" if stationary_after else None)))
        if after is None and args.active_recovery:
            # Controls are neutral here. First find a stationary, non-mine-like local
            # candidate, then make one tiny causal probe and watch what responds.
            neutral_fix = stationary_anchor_fix(after_candidates, before.center, min_support=3)
            report["recovery_neutral_fix"] = vars(neutral_fix) if neutral_fix else None
            if neutral_fix is not None:
                recovery_ms = min(60, args.duration_ms)
                with ArcadeController(args.host, args.port, protocol=args.protocol) as controller:
                    controller.execute(Action(move=args.move, fire="NONE",
                                              reason="active self-identification probe"), recovery_ms)
                report["active_recovery_pulse"] = {"move": args.move, "duration_ms": recovery_ms}
                time.sleep(0.08)
                _, recovery_candidates, recovery_rows = observe(
                    source, calibration, recognizer, args.frames, args.interval_ms,
                    args.output, "recovery")
                report["recovery_frames"] = recovery_rows
                after = motion_probe_fix(neutral_fix, recovery_candidates, args.move)
                report["after_fix"] = vars(after) if after else None
                report["reacquisition"] = "active_motion" if after else None
        if after is None:
            report["result"] = "PULSE SENT; VERIFY UNKNOWN: player not reacquired unambiguously"
            print(report["result"])
            return
        ok, dx, dy = direction_verified(before.center, after.center, args.move)
        report["displacement"] = {"dx": dx, "dy": dy}
        report["verified"] = ok
        report["result"] = "VERIFIED" if ok else "NOT VERIFIED"
        print(f"Player fix AFTER:  x={after.center[0]:.2f} y={after.center[1]:.2f} "
              f"support={after.supporting_frames}/{after.frames} spread={after.spread:.2f}")
        print(f"Displacement: dx={dx:+.2f} dy={dy:+.2f}; commanded={args.move}; {report['result']}")
    finally:
        source.close()
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Evidence: {args.output}/report.json")


if __name__ == "__main__":
    main()

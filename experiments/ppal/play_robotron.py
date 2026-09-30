"""Small live Robotron runner using Charlie's taught eyes and PPAL brain.

This is deliberately bounded: gameplay time defaults to 20 seconds and the
controller is neutralized on every pulse, during vision uncertainty, and on exit.
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
import hashlib
import subprocess

from .arcade_transport import ArcadeController
from .forebrain import Forebrain
from .hindbrain import Hindbrain
from .vision_tracker import ObjectTracker
from .robotron_session import PersistentSelfTracker
from .shadow_predictor import ShadowPredictor, action_dict
from .models import Action, Object, Position, WorldState
from .eyes.sources import PiCameraSource
from .eyes.calibration import Calibration
from .eyes.settle import prepare
from .eyes.taught_recognizer import TaughtRecognizer
from .robotron_screen_state import classify_screen_state
from .episode_end import EpisodeEndObserver
from .robotron_agency import VisualAgency
from PIL import ImageDraw

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


def _causal_bootstrap(before_frames, after_frames, direction="E",
                      min_motion=0.20, max_match=7.0,
                      min_player_score=0.72, anchor=None):
    """Find a player-looking sprite whose displacement obeys our probe."""
    vectors = {
        "E": (1.0, 0.0),
        "S": (0.0, 1.0),
        "W": (-1.0, 0.0),
        "N": (0.0, -1.0),
    }
    if direction not in vectors:
        raise ValueError(f"unsupported causal direction: {direction}")

    vx, vy = vectors[direction]
    before = before_frames[-1] if before_frames else []
    after = after_frames[-1] if after_frames else []
    candidates = []

    for bd, be in before:
        pscore = float(be.get("class_scores", {}).get("player", -1.0))
        mscore = float(be.get("class_scores", {}).get("mine", -1.0))

        if pscore < min_player_score or mscore > pscore + 0.02:
            continue

        if anchor is not None and _distance(bd.center, anchor) > max_match:
            continue

        for ad, ae in after:
            dist = _distance(bd.center, ad.center)
            dx = ad.center[0] - bd.center[0]
            dy = ad.center[1] - bd.center[1]

            along = dx * vx + dy * vy
            sideways = abs(dx * vy - dy * vx)

            if (dist <= max_match
                    and along >= min_motion
                    and sideways <= max(2.5, abs(along) * 1.5)):
                ascore = float(
                    ae.get("class_scores", {}).get("player", -1.0))
                if ascore < min_player_score:
                    continue
                score = (
                    pscore + ascore
                    + along * 0.05
                    - sideways * 0.02
                )
                candidates.append(
                    (score, tuple(ad.center), dx, dy))

    candidates.sort(reverse=True)

    if not candidates:
        return None

    if (len(candidates) > 1
            and candidates[0][0] - candidates[1][0] < 0.03):
        return None

    return candidates[0][1]


def _control_challenge(source, calibration, recognizer, controller,
                       initial_frames=None, pulse_ms=60):
    """Test a suspected SELF causally.

    Three successful directional probes confirm SELF.
    Two independently eligible failed probes reject SELF.
    Anything weaker is inconclusive.
    """
    frames = initial_frames or _quick_frames(
        source, calibration, recognizer, count=4, interval=0.025)

    evidence = []
    hits = 0
    failures = 0
    anchor = None

    for direction in ("E", "S", "W"):
        # Every leg must begin with its own stable player-like candidate.
        # After a failed leg we therefore do not blindly carry the old anchor
        # into another causal claim.
        candidate = _appearance_bootstrap(frames)
        if candidate is None:
            break

        anchor = candidate

        controller.execute(
            Action(direction, "NONE", "control challenge"),
            pulse_ms)

        after = _quick_frames(
            source, calibration, recognizer,
            count=4, interval=0.025)

        observed = _causal_bootstrap(
            frames, after,
            direction=direction,
            anchor=anchor)

        obeyed = observed is not None
        evidence.append({
            "direction": direction,
            "obeyed": obeyed,
            "observed": list(observed) if observed is not None else None,
        })

        if obeyed:
            hits += 1
            anchor = observed
        else:
            failures += 1

        frames = after

    attempts = len(evidence)
    eligible = attempts > 0
    confirmed = attempts == 3 and hits == 3
    rejected = failures >= 2

    return {
        "confirmed": confirmed,
        "rejected": rejected,
        "eligible": eligible,
        "hits": hits,
        "failures": failures,
        "attempts": attempts,
        "player": anchor if confirmed else None,
        "evidence": evidence,
        "frames": frames,
    }

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
    parser.add_argument("--focus", type=float, default=None,
                        help="lock camera to this manual lens position after warm-up and before START")
    parser.add_argument("--start-wait", type=float, default=4.0,
                        help="seconds to wait after START for visual gameplay/self evidence")
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--margin", type=float, default=0.04)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--arm", action="store_true",
                        help="actually send movement/fire commands")
    args = parser.parse_args()

    if not 1 <= args.seconds <= 3600:
        parser.error("--seconds must be 1..3600")
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
    shadow_forebrain = Forebrain()
    shadow_hindbrain = Hindbrain()
    shadow_predictor = ShadowPredictor(horizon_seconds=.15, max_speed=100.)
    object_tracker = ObjectTracker()
    self_tracker = PersistentSelfTracker(max_distance=7.0, max_missed=3)
    visual_agency = VisualAgency()
    source = PiCameraSource()
    rows = []
    review_frames = []
    agency_rows = []
    agency_frames = []
    latest_agency_frame = None
    def record_agency(snapshot):
        row = {"sample": visual_agency.tick, **snapshot}
        if latest_agency_frame is not None and len(agency_frames) < 24:
            frame = latest_agency_frame.copy()
            draw = ImageDraw.Draw(frame)
            for track_id in visual_agency.positions:
                track = visual_agency.tracker.active[track_id]
                belief = visual_agency.agency.beliefs[track_id]
                color = "lime" if track_id == snapshot["self_track_id"] else "yellow"
                draw.rectangle(track.box, outline=color)
                draw.text((track.box[0], track.box[1]), f"{track_id} {belief.confidence:.2f}", fill=color)
            name = f"agency-{len(agency_frames):03d}.png"
            frame.save(args.output / name)
            row["frame"] = name
            agency_frames.append({"sample": visual_agency.tick, "path": name,
                                  "candidates": _pair_evidence(visual_agency.pairs)})
        agency_rows.append(row)
        with (args.output / "agency.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        if snapshot["event"]:
            print(f"AGENCY {snapshot['event'].upper()}: self={snapshot['self_track_id']} "
                  f"candidate={snapshot['candidate_track_id']} confidence={snapshot['confidence']:.2f} "
                  f"runner={snapshot['runner_up_confidence']:.2f}")
    def read_agency_pairs():
        nonlocal latest_agency_frame
        latest_agency_frame = calibration.apply(source.read())
        return recognizer.detect(latest_agency_frame)
    def save_review(raw, tick, reason):
        if len(review_frames) >= (40 if reason == 'final-view' else 39):
            return
        name = f'review-{len(review_frames):03d}-{tick}-{reason}.jpg'
        raw.save(args.output/name, quality=85)
        review_frames.append({'tick':tick,'reason':reason,'path':name})
    try:
        revision = subprocess.check_output(['git','rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git','status','--porcelain'],text=True,stderr=subprocess.DEVNULL))
    except (OSError,subprocess.CalledProcessError):
        revision,dirty = None,None
    provenance = {'git_commit':revision,'dirty_worktree':dirty,
                  'knowledge_sha256':hashlib.sha256(args.knowledge.read_bytes()).hexdigest()}
    controller = None
    result = "not started"
    episode_end = {"state": "unknown", "confirmed": False, "evidence": None}

    try:
        # Start the camera first. In normal operation this happens while Robotron
        # is still in attract/demo mode, giving exposure/AF time without costing
        # any gameplay. No demo-screen calibration is attempted.
        for _ in range(6):
            source.read()
            time.sleep(0.04)

        if args.focus is not None:
            if not 0.0 <= args.focus <= 32.0:
                raise ValueError("--focus must be between 0.0 and 32.0")
            source.set_manual_focus(args.focus)
            # Discard a few frames after the lens move before gameplay begins.
            for _ in range(4):
                source.read()
                time.sleep(0.04)
            actual_focus = source.lens_position()
            print(f"FOCUS LOCKED: requested={args.focus:.3f} actual={actual_focus}")

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

        # Appearance/center are proposals. Armed play requires direct agency.
        if args.arm:
            if controller is None:
                controller = ArcadeController(args.host, args.port, protocol="positions")
            print("DISCOVERING SELF: short movement/neutral probes over all visual candidates")
            player = visual_agency.discover(read_agency_pairs, controller, record=record_agency)
            frames = [visual_agency.pairs]
            acquisition = "generic_visual_agency" if player is not None else None

        if player is None:
            raise RuntimeError("could not identify the player; controls neutral")

        print(f"PLAYER ACQUIRED ({acquisition}) x={player[0]:.2f} y={player[1]:.2f}")

        # Bind trusted startup acquisition to an identity-independent visual track.
        seed_pairs = frames[-1] if frames else []
        seed_detections = [d for d, _ in seed_pairs]
        self_obs = self_tracker.seed(0, seed_detections, player, max_seed_distance=7.0)
        if self_obs.center is not None:
            player = self_obs.center
            print(f"SELF TRACK SEEDED: track={self_obs.track_id}")
        else:
            print("SELF TRACK: startup seed deferred to live frame")

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
        pending_move = None
        pending_at = None
        episode_observer = EpisodeEndObserver(required_not_gameplay=8)
        print(f"CHARLIE LOOSE: {args.seconds:.1f}s hard gameplay limit")

        while time.monotonic() < deadline:
            raw = source.read()
            observed_at = time.monotonic()-started
            playfield = calibration.apply(raw)
            pairs = recognizer.detect(playfield)
            detections = [d for d, _ in pairs]

            # Normal movement is another causal experiment; right-stick firing
            # never enters the BODY evidence model. Track continuity supplies WHERE.
            agency_snapshot = visual_agency.observe(
                pairs, pending_move,
                time.monotonic()-pending_at if pending_at is not None else None)
            latest_agency_frame = playfield
            record_agency(agency_snapshot)
            pending_move = None
            pending_at = None
            self_obs = self_tracker.update(tick + 1, detections)
            agency_player = visual_agency.player
            new_player = None
            if agency_player is not None:
                if self_obs.center is not None and _distance(self_obs.center, agency_player) <= .5:
                    new_player = self_obs.center
                else:
                    # Conservative track lineage changes require new causal identity.
                    self_obs = self_tracker.reseed(tick + 1, detections, agency_player)
                    new_player = self_obs.center

            if new_player is None:
                lost += 1
                if lost in (1,3):
                    save_review(raw,tick,'identity-loss')

                # Uncertainty stops ACTION, not EFFORT.  Never drive from a
                # guessed self location; neutralize and spend the remaining
                # gameplay window trying to reacquire Charlie.
                try:
                    controller._command("NEUTRAL")
                except (OSError, ConnectionError):
                    raise

                recovery_frames = _quick_frames(
                    source, calibration, recognizer, count=4, interval=0.025)
                recovered = None  # Global resemblance is not proof of a new SELF.

                recovery = "generic_visual_agency"
                if lost == 1 or lost % 12 == 0:
                    recovered = visual_agency.discover(
                        read_agency_pairs, controller, deadline=deadline, record=record_agency)
                    recovery_frames = [visual_agency.pairs]
                    detections = [d for d, _ in visual_agency.pairs]

                # SELF loss never ends an episode.  It only changes what Charlie
                # does: remain neutral, keep looking, and gather independent
                # evidence about whether Robotron itself has left gameplay.
                screen = classify_screen_state(playfield)
                episode_observer.observe_screen(screen["state"])

                # A causal challenge is corroborating evidence, not a termination
                # rule.  Do it occasionally after sustained loss; failure means
                # "no controllable SELF demonstrated", never "the game is over".
                challenge = None
                if recovered is None and lost >= 3 and (lost == 3 or lost % 12 == 0):
                    print(
                        f"REACQUIRING: {lost} misses; "
                        "checking for controllable SELF")
                    challenge = _control_challenge(
                        source, calibration, recognizer, controller,
                        initial_frames=recovery_frames)

                    rows.append({
                        "tick": tick,
                        "t": time.monotonic() - started,
                        "status": "control_challenge",
                        "lost": lost,
                        "confirmed": challenge["confirmed"],
                        "eligible": challenge["eligible"],
                        "hits": challenge["hits"],
                        "attempts": challenge["attempts"],
                        "evidence": challenge["evidence"],
                        "screen_state": screen,
                    })

                    if challenge["confirmed"]:
                        # Legacy appearance challenge can corroborate gameplay,
                        # but cannot authorize a different SELF without generic agency.
                        episode_observer.observe_agency(True)

                        final_pairs = challenge["frames"][-1]
                        detections = [d for d, _ in final_pairs]
                        print(
                            "CONTROL CONFIRMED: "
                            f"{challenge['hits']}/"
                            f"{challenge['attempts']}")
                    elif challenge["rejected"]:
                        # Established gameplay was followed by genuine SELF loss,
                        # and independently eligible causal probes rejected the
                        # stable SELF-like candidates. Appearance must not
                        # overrule this stronger negative agency evidence.
                        episode_observer.observe_agency(False)
                        recovered = None
                        result = "GAME OVER"
                        episode_end = {
                            "state": "game_over",
                            "confirmed": True,
                            "evidence": episode_observer.evidence(
                                screen=screen,
                                self_lost_frames=lost,
                            ),
                        }
                        episode_end["evidence"]["rule"] = (
                            "established_gameplay_plus_eligible_failed_agency"
                        )
                        episode_end["evidence"]["control_challenge"] = challenge
                        save_review(raw, tick, "game-over-failed-agency")
                        print(
                            "GAME OVER CONFIRMED: stable SELF candidates "
                            "failed robust causal control challenge")
                        break
                    elif challenge["eligible"]:
                        recovered = None
                        print(
                            "SELF CHALLENGE INCONCLUSIVE; remaining neutral "
                            "and continuing observation")
                    else:
                        print(
                            "NO PLAUSIBLE SELF TO CHALLENGE; "
                            "remaining neutral and continuing observation")

                # Episode termination requires a transition out of established
                # gameplay, not merely loss of SELF.  The striped/multicolour
                # attract border supplies positive visual evidence; failed agency
                # is independent corroboration.  Eight consecutive observations
                # deliberately makes a one-frame transition/glitch insufficient.
                if recovered is None and episode_observer.confirmed:
                    result = "GAME OVER"
                    episode_end = {
                        "state": "game_over",
                        "confirmed": True,
                        "evidence": episode_observer.evidence(
                            screen=screen,
                            self_lost_frames=lost,
                        ),
                    }
                    save_review(raw, tick, "game-over")
                    print(
                        "GAME OVER CONFIRMED: persistent non-gameplay "
                        "appearance + no controllable SELF")
                    break

                if recovered is None:
                    rows.append({
                        "tick": tick,
                        "t": time.monotonic() - started,
                        "status": "reacquiring",
                        "lost": lost,
                        "last_player": list(player),
                        "screen_state": screen,
                        "not_gameplay_streak": episode_observer.not_gameplay_streak,
                    })
                    if lost == 1:
                        print("PLAYER LOST: controls neutral; REACQUIRING")
                    tick += 1
                    continue

                # Recovery used NEW frames. Do not seed against the stale pre-recovery view.
                if recovery != 'causal_control_challenge':
                    detections = [d for d, _ in recovery_frames[-1]]
                object_tracker = ObjectTracker()
                shadow_predictor = ShadowPredictor(horizon_seconds=.15, max_speed=100.)
                forebrain = Forebrain(); shadow_forebrain = Forebrain()
                player = recovered
                reseed = self_tracker.reseed(
                    tick + 1, detections, player, max_seed_distance=7.0)
                if reseed.center is not None:
                    player = reseed.center
                rows.append({
                    "tick": tick,
                    "t": time.monotonic() - started,
                    "status": "player_reacquired",
                    "self_track_id": reseed.track_id,
                    "lost": lost,
                    "method": recovery,
                    "player": list(player),
                })
                print(
                    f"PLAYER REACQUIRED ({recovery}) after {lost} misses "
                    f"x={player[0]:.2f} y={player[1]:.2f}")
                episode_observer.self_reacquired()
                lost = 0
                tick += 1
                continue

            if tick % 50 == 0:
                save_review(raw,tick,'gameplay')
            player = new_player
            if self_obs.center is None:
                reseed = self_tracker.reseed(
                    tick + 1, detections, player, max_seed_distance=7.0)
                if reseed.center is not None:
                    player = reseed.center
            if lost:
                print(f"PLAYER REACQUIRED (local track) after {lost} misses")
                episode_observer.self_reacquired()
            lost = 0

            targets = _objects(pairs, HUMANS, "human")
            threats = _objects(pairs, THREATS, "threat")
            world = WorldState(tick=tick, player=Position(*player),
                               targets=targets, threats=threats, alive=True)

            # Semantic gameplay IDs persist even as raw detector IDs change.
            world = object_tracker.update(world)
            goal = forebrain.update(world)
            intent, action = hindbrain.decide(world, goal)

            # SHADOW ONLY: anticipate the next visual state and ask a separate
            # PPAL brain what it would do.  The real controller below still
            # receives `action`, never `shadow_action`.
            shadow_predictor.observe(world, observed_at)
            projected_world = shadow_predictor.project(world)
            shadow_goal = shadow_forebrain.update(projected_world)
            shadow_intent, shadow_action = shadow_hindbrain.decide(
                projected_world, shadow_goal)

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
            pending_at = time.monotonic()
            controller.execute(action, pulse_ms)
            pending_move = action.move
            rows.append({
                "tick": tick, "observed_at": observed_at, "t": time.monotonic()-started,
                "player": list(player),
                "self_track_id": self_tracker.player_track_id,
                "agency": agency_snapshot,
                "targets": len(targets), "threats": len(threats),
                "goal": {"kind": goal.kind, "target_id": goal.target_id},
                "intent": {"kind": intent.kind, "target_id": intent.target_id},
                "action": {"move": action.move, "fire": action.fire,
                           "reason": action.reason},
                "shadow": {
                    "prediction": shadow_predictor.snapshot(
                        world, projected_world),
                    "goal": {"kind": shadow_goal.kind,
                             "target_id": shadow_goal.target_id},
                    "intent": {"kind": shadow_intent.kind,
                               "target_id": shadow_intent.target_id},
                    "action": action_dict(shadow_action),
                    "differs": (
                        shadow_action.move != action.move
                        or ("NONE" if shadow_action.fire == "STAY"
                            else shadow_action.fire) != action.fire
                    ),
                },
            })
            tick += 1
        else:
            result = "TIME LIMIT"

        print(f"RUN COMPLETE: {result}; ticks={tick}")
    except KeyboardInterrupt:
        result = "INTERRUPTED"
        print("INTERRUPTED; neutralizing")
    except Exception as exc:
        result = f'ERROR: {type(exc).__name__}: {exc}'
        raise
    finally:
        if controller is not None:
            try:
                controller.close()
            except (OSError, ConnectionError):
                pass
        source.close()
        if 'raw' in locals():
            save_review(raw,locals().get('tick',0),'final-view')
        report = {"provenance": provenance, "review_frames": review_frames, "result": result, "armed": args.arm, "seconds": args.seconds,
                  "pulse_ms": args.pulse_ms, "ticks": len(rows),
                  "episode_end": episode_end,
                  "score": None, "score_status": "unmeasured",
                  "learning_mode": "fixed_policy_with_shadow_diagnostics",
                  "auto_start": bool(args.arm and not args.no_start_game),
                  "calibration_mode": locals().get("calibration_mode"),
                  "acquisition": locals().get("acquisition"),
                  "gameplay_visual_frame": locals().get("gameplay_visual_frame"),
                  "startup_watch": locals().get("startup_watch", []),
                  "agency_frames": agency_frames,
                  "agency_samples": len(agency_rows),
                  "agency_log": "agency.jsonl",
                  "steps": rows}
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Evidence: {args.output}/report.json")


if __name__ == "__main__":
    main()

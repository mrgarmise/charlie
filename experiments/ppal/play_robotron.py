"""Small live Robotron runner using Charlie's taught eyes and PPAL brain.

Healthy gameplay continues to a confirmed terminal state. Diagnostic duration
limits are opt-in, and the
controller is neutralized on every pulse, during vision uncertainty, and on exit.
Normal play reuses the promoted playfield calibration for fast startup. Charlie
may start Robotron himself after the camera is ready, then waits for visual proof
of gameplay before acquiring self. Fresh geometric calibration is completed
before START using either an attract or gameplay border. The
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
from .robotron_session import PersistentSelfTracker, RobotronSessionManager, SessionState, GameDiary
from .shadow_predictor import ShadowPredictor, action_dict
from .models import Action, Object, Position, WorldState
from .eyes.sources import PiCameraSource
from .eyes.calibration import Calibration
from .eyes.settle import prepare
from .eyes.exposure import optimize_screen_exposure
from .eyes.taught_recognizer import TaughtRecognizer
from .robotron_screen_state import classify_screen_state
from .episode_end import EpisodeEndObserver
from .robotron_agency import VisualAgency
from .score_observer import ScoreObserver
from .observation_camera import ObservedCamera
from .preflight import sensory_preflight, ImagingMonitor
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


def _objects(pairs, identities, prefix, assignments=None, exclude_track_id=None):
    if assignments is not None:
        return tuple(Object(f"sprite_{assignments[index]}", Position(*detection.center))
                     for index, (detection, _) in enumerate(pairs)
                     if detection.kind in identities and index in assignments
                     and assignments[index] != exclude_track_id)
    accepted = []
    for detection, evidence in pairs:
        if detection.kind in identities:
            accepted.append((detection.kind, tuple(detection.center)))
    accepted.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
    return tuple(Object(f"{prefix}_{kind}_{i}", Position(*center))
                 for i, (kind, center) in enumerate(accepted, 1))



def _quick_frames(source, calibration, recognizer, count=5, interval=0.035, on_observation=None, deadline=None):
    frames = []
    for _ in range(count):
        if deadline is not None and time.monotonic() >= deadline:
            break
        playfield = calibration.apply(source.read())
        pairs = recognizer.detect(playfield)
        frames.append(pairs)
        if on_observation:
            on_observation(pairs, playfield)
        if interval:
            time.sleep(interval if deadline is None else max(0., min(interval, deadline-time.monotonic())))
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
                       initial_frames=None, pulse_ms=60, on_observation=None, deadline=None):
    """Test a suspected SELF causally.

    Three successful directional probes confirm SELF.
    Two independently eligible failed probes reject SELF.
    Anything weaker is inconclusive.
    """
    frames = initial_frames or _quick_frames(
        source, calibration, recognizer, count=4, interval=0.025, on_observation=on_observation, deadline=deadline)

    evidence = []
    hits = 0
    failures = 0
    anchor = None

    for direction in ("E", "S", "W"):
        if deadline is not None and time.monotonic()+pulse_ms/1000 >= deadline:
            break
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
            count=4, interval=0.025, on_observation=on_observation, deadline=deadline)
        if deadline is not None and time.monotonic() >= deadline:
            break  # An incomplete observation window is not failed agency.

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


def _initial_start_decision(source, calibration, *, timeout=4., required=3,classifier=classify_screen_state):
    """Positive stable pregame authorizes one START; gameplay attaches, else stop."""
    deadline=time.monotonic()+timeout
    history=[]; frames=[]; previous=None; streak=0
    while time.monotonic()<deadline:
        raw=source.read()
        screen=classifier(calibration.apply(raw))
        phase=screen.get('phase','unknown')
        streak=streak+1 if phase==previous else 1
        previous=phase
        history.append(dict(at=time.monotonic(),capture_timestamp=source.timestamp,
                            capture=source.capture,screen=screen,consecutive=streak))
        if len(frames)<6:frames.append((f'start-decision-{len(frames):03d}.png',raw.copy()))
        if streak>=required and phase in ('startable','gameplay'):
            return dict(action='start' if phase=='startable' else 'attach',
                        reason='stable positive '+phase,observations=history),frames
        time.sleep(.025)
    return dict(action='stop',reason='no stable positive pregame or gameplay evidence',observations=history),frames


def _explore_startup(source,calibration,controller,forebrain,recorder,*,timeout=30.,max_actions=32,classifier=classify_screen_state,on_control=None):
    """Bounded permitted interactions; visual commencement is a separate gate."""
    deadline=time.monotonic()+timeout;history=[];streak=0;last_at=None
    for attempt in range(max_actions+3):
        if time.monotonic()>=deadline:break
        raw=source.read();frame=calibration.apply(raw);screen=classifier(frame)
        fresh=last_at is None or source.timestamp>last_at;last_at=source.timestamp
        streak=streak+1 if fresh and screen.get('phase')=='gameplay' else 0
        if streak>=3:
            return dict(action='attach',reason='three fresh gameplay observations after exploration',observations=history,
                        gameplay_verified=True,exploratory_actions=len(history))
        if screen.get('phase')=='gameplay':continue # observe commencement quietly
        if len(history)>=max_actions:break
        # Coarse measured scene signature is context, not a semantic label.
        context=hashlib.sha256(frame.convert('RGB').resize((16,12)).tobytes()).hexdigest()
        action=forebrain.exploratory_action(dict(screen,context=context))
        prediction=dict(question=forebrain.last_reason['question'],action=action_dict(action),
                        controls=list(action.controls),origin_at=source.timestamp,screen=screen,
                        expectation='an observable response may occur; identity and game meaning unestablished')
        prediction_id=recorder.event('exploratory_prediction',prediction,at=time.monotonic())
        if action.controls:
            for button in action.controls:
                if on_control:on_control(button,'requested')
                controller._command(button)
                if on_control:on_control(button,'acknowledged')
        else:controller.execute(action,80)
        execution=getattr(controller,'last_execution',None)
        recorder.event('exploratory_execution',dict(prediction_id=prediction_id,action=action_dict(action),
            controls=list(action.controls),transport=getattr(controller,'last_command',None),execution=execution),at=time.monotonic())
        after=calibration.apply(source.read());following=classifier(after)
        after_context=hashlib.sha256(after.convert('RGB').resize((16,12)).tobytes()).hexdigest()
        outcome=dict(prediction_id=prediction_id,origin_at=prediction['origin_at'],observed_at=source.timestamp,
            controls=list(action.controls),scene_changed=after_context!=context,screen=following,
            interpretation='visual change is association, not independently established control causation',
            result='provisional_response' if after_context!=context else 'inconclusive',
            proposed_sequence=[r['controls'] for r in history[-3:]]+[list(action.controls)])
        recorder.event('exploratory_outcome',outcome,at=time.monotonic())
        forebrain.exploratory_outcome(outcome);history.append(outcome)
    return dict(action='wait',reason='bounded exploration ended without independently verified gameplay',
                observations=history,gameplay_verified=False,request='additional readable observations or operator assistance')


def _wait_for_gameplay(source, calibration, recognizer, evidence_dir, timeout=4.0, on_observation=None, generic_ready=False,classifier=classify_screen_state):
    """Observe quietly after START and preserve why acquisition passed or failed."""
    deadline = time.monotonic() + timeout
    collected = []
    watch = []
    frame_no = 0
    first_visual = None
    while time.monotonic() < deadline:
        playfield = calibration.apply(source.read())
        pairs = recognizer.detect(playfield)
        if on_observation:
            on_observation(pairs, playfield)
        collected.append(pairs)
        collected = collected[-6:]
        center = _stable_center_bootstrap(collected)
        appearance = _appearance_bootstrap(collected)
        entry = {
            "frame": frame_no,
            "t": round(timeout - max(0.0, deadline - time.monotonic()), 4),
            "candidate_count": len(pairs),
            "capture_timestamp": getattr(source, 'timestamp', None),
            "observed_at_monotonic": time.monotonic(),
            "screen_state": classifier(playfield),
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
        gameplay_confirmed = len(watch)>=3 and all(r['screen_state'].get('phase')=='gameplay' for r in watch[-3:])
        if generic_ready and gameplay_confirmed and len(collected) >= 3:
            recent = collected[-3:]
            stable = all(old and new and .5 <= len(new)/len(old) <= 2.
                         and sum(min(_distance(d.center, before.center) for before, _ in old) <= 3.
                                 for d, _ in new) / len(new) >= .8
                         for old, new in zip(recent, recent[1:]))
            if stable:
                return None, "generic_visual_ready", collected, watch, first_visual
        if gameplay_confirmed and center is not None:
            return center, "new_game_center", collected, watch, first_visual
        frame_no += 1
        time.sleep(0.025)

    # Only after the protected center-spawn watch expires do we allow appearance.
    player = _appearance_bootstrap(collected) if len(watch)>=3 and all(
        r['screen_state'].get('phase')=='gameplay' for r in watch[-3:]) else None
    if player is not None:
        return player, "appearance_after_center_window", collected, watch, first_visual
    return None, None, collected, watch, first_visual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", "--diagnostic-seconds", dest="seconds", type=float, default=None,
                        help="opt-in diagnostic duration limit; not normal game completion")
    parser.add_argument("--uncertainty-seconds", type=float, default=60.,
                        help="stop after sustained inability to demonstrate controlled SELF; never authorize START")
    parser.add_argument("--supervised-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--host", default="charlie-arcade.local")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--pulse-ms", type=int, default=80)
    parser.add_argument("--knowledge", type=Path,
                        default=Path("config/robotron/sprite-knowledge.json"))
    parser.add_argument("--calibration", type=Path,
                        default=Path("config/robotron/playfield-latest.json"),
                        help="promoted playfield calibration used for fast startup")
    parser.add_argument("--recalibrate", action="store_true",
                        help="before START, rediscover screen geometry instead of loading --calibration")
    parser.add_argument("--no-start-game", action="store_true",
                        help="do not tap START; use when Robotron gameplay is already running")
    parser.add_argument("--focus", type=float, default=None,
                        help="lock camera to this manual lens position after warm-up and before START")
    parser.add_argument("--start-wait", type=float, default=4.0,
                        help="seconds to wait after START for visual gameplay/self evidence")
    parser.add_argument('--exploration-seconds',type=float,default=30.)
    parser.add_argument('--exploration-actions',type=int,default=32)
    parser.add_argument('--title-reference',type=Path,help='operator-verified hashed title marker declaration; no text recognition')
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--margin", type=float, default=0.04)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--arm", action="store_true",
                        help="actually send movement/fire commands")
    parser.add_argument("--bootstrap-body-fire", action="store_true",
                        help="experimental provisional BODY identity with independent and simultaneous FIRE exploration")
    parser.add_argument('--experiment-plan', type=Path,
                        help='one precommitted developmental actuator experiment')
    parser.add_argument('--observer-context', type=Path, help='optional display-only project context; never policy input')
    parser.add_argument('--learned-semantics',type=Path,help='separately authorized, independently validated candidate-crop activation manifest')
    parser.add_argument('--learned-policy',type=Path,help='qualified local PPAL decision policy; current acceptance is offline only')
    parser.add_argument('--rolling-seconds',type=float,default=0.,help='opt-in bounded original incident memory; native RAM tradeoff unmeasured')
    parser.add_argument('--rolling-frames',type=int,default=60)
    parser.add_argument('--rolling-memory-mib',type=int,default=32)
    parser.add_argument('--visual-retention-hz',type=float,help='opt-in sampled-visual-v1; strict originals remain default')
    parser.add_argument('--evidence-frame-capacity',type=int,default=16)
    parser.add_argument('--evidence-record-capacity',type=int,default=512)
    parser.add_argument('--evidence-memory-mib',type=int,default=128)
    args = parser.parse_args()
    screen_classifier=classify_screen_state
    if args.title_reference:
        from .robotron_screen_state import TaughtTitleReference
        screen_classifier=TaughtTitleReference(args.title_reference).classify
    if not 1<=args.exploration_actions<=128 or not 1<=args.exploration_seconds<=120:
        parser.error('bounded exploration requires 1..128 actions and 1..120 seconds')

    if args.seconds is not None and (not math.isfinite(args.seconds) or not 1 <= args.seconds <= 3600):
        parser.error("--seconds must be 1..3600")
    if not math.isfinite(args.rolling_seconds) or not 0<=args.rolling_seconds<=10 or not 1<=args.rolling_frames<=300 or not 1<=args.rolling_memory_mib<=128:
        parser.error('rolling budgets require 0..10 seconds, 1..300 frames, 1..128 MiB')
    if args.visual_retention_hz is not None and (not math.isfinite(args.visual_retention_hz) or not 0<args.visual_retention_hz<=30):
        parser.error('visual retention Hz must be positive and <=30')
    if not (1<=args.evidence_frame_capacity<=64 and args.evidence_frame_capacity<=args.evidence_record_capacity<=4096
            and 16<=args.evidence_memory_mib<=512):
        parser.error('evidence budgets require frames 1..64, records frames..4096, memory 16..512 MiB')
    if not math.isfinite(args.uncertainty_seconds) or not 10 <= args.uncertainty_seconds <= 300:
        parser.error("--uncertainty-seconds must be 10..300")
    if not 30 <= args.pulse_ms <= 200:
        parser.error("--pulse-ms must be 30..200")
    if not 1.0 <= args.start_wait <= 10.0:
        parser.error("--start-wait must be 1..10 seconds")
    if args.output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        args.output = Path(f"robotron-runs/play-{stamp}")
    if args.arm and not args.supervised_child:
        import sys
        from .progress_supervision import supervise
        # Parent remains independent of camera/perception/controller operations.
        command = [sys.executable, "-m", "experiments.ppal.play_robotron", *sys.argv[1:]]
        if "--output" not in sys.argv[1:]:
            command.extend(["--output", str(args.output)])
        command.append("--supervised-child")
        rc = supervise(command, args.output.parent/(args.output.name+"-progress.json"), processing=90.)
        raise SystemExit(rc)
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)

    experiment_plan = None
    experiment_status = {'status':'not_requested','attempted':False,'reason':None}
    if args.experiment_plan:
        try:
            from .experiment_return import validate_plan
            experiment_plan = validate_plan(json.loads(args.experiment_plan.read_text()),args.output)
            experiment_status = {'status':'pending','attempted':False,'reason':None,
                                 'prediction_id':experiment_plan['prediction_id']}
        except (OSError,ValueError,TypeError) as exc:
            experiment_status = {'status':'rejected','attempted':False,'reason':str(exc)}
            print(f'EXPERIMENT REJECTED: {exc}; existing policy retained')

    recognizer = TaughtRecognizer.load(args.knowledge, args.threshold, args.margin)
    semantic_observer=None;semantic_error=None
    if args.learned_semantics:
        try:
            from learning.operational import load_manifest
            from .semantic_observer import SemanticObserver
            activation,model=load_manifest(args.learned_semantics,physical=args.arm)
            semantic_observer=SemanticObserver(model,activation)
        except (OSError,ValueError,KeyError,ImportError,RuntimeError) as exc:
            semantic_error=f'{type(exc).__name__}: {exc}'
            print('LEARNED SEMANTICS UNAVAILABLE: '+semantic_error+'; baseline retained')
    from .policy_loading import load_startup_policy
    policy,policy_error=load_startup_policy(args.learned_policy,physical=args.arm)
    forebrain = Forebrain(policy=policy)
    hindbrain = Hindbrain(explore_fire=args.bootstrap_body_fire,policy=policy,tactical_learning=True)
    shadow_forebrain = Forebrain()
    shadow_hindbrain = Hindbrain(explore_fire=args.bootstrap_body_fire)
    shadow_predictor = ShadowPredictor(horizon_seconds=.15, max_speed=100.)
    visual_agency = VisualAgency(bootstrap_body_fire=args.bootstrap_body_fire)
    self_tracker = PersistentSelfTracker(max_distance=7.0, max_missed=3,
                                         tracker=visual_agency.tracker if args.arm else None)
    session = RobotronSessionManager(clock=time.monotonic)
    diary = GameDiary(args.output, clock=time.monotonic)
    timing = {'clock':'monotonic', 'gameplay_timer_boundary':'after SELF discovery; includes reacquisition',
              'first_life_lost_at':None, 'life_tracking':'unmeasured; SELF loss is not a life boundary'}
    def mark(kind, **data):
        at = time.monotonic()
        timing[kind] = at
        diary.event(kind, at=at, **data)
        return at
    def phase(state, reason):
        if session.state != state:
            diary.transition(session.transition(state, reason))
            if progress:
                progress.update(mode=state.value, mode_started_at=time.monotonic())
    from .progress_supervision import Progress, SupervisedController, ObservationFailure, UncertaintyWindow
    progress = Progress(args.output.parent/(args.output.name+"-progress.json")) if args.arm else None
    if progress: progress.enter("camera")
    mark('camera_initialization_started')
    source = ObservedCamera(PiCameraSource(), require_fresh=args.arm, progress=progress)
    publisher = None
    try:
        from .eyes.passive import PassivePublisher
        observer_context = {'episode':str(args.output.resolve()), 'project':None}
        if args.observer_context:
            try:
                supplied=json.loads(args.observer_context.read_text())
                if supplied.get('episode')==observer_context['episode']:
                    observer_context['project']=supplied.get('project')
            except (OSError,ValueError,TypeError):pass
        elif experiment_plan and experiment_plan.get('project_id'):
            observer_context['project']={'id':experiment_plan['project_id'],'goal':experiment_plan.get('project_objective')}
        publisher = PassivePublisher(context=observer_context)
        source.publisher = publisher
    except Exception:
        pass  # Optional visual observation must not gate camera or gameplay.
    score_observer = None
    preceding_action = None
    from .progress_evidence import DurableRows
    rows = DurableRows(args.output/"steps.jsonl")
    review_frames = []
    agency_samples = 0
    agency_frames = []
    latest_agency_frame = None
    buffered_frames = []
    raw_frames = []
    recorder=None
    recent_observation_ids=[]
    def record_agency(snapshot):
        if recorder is not None and recorder.latest_observation is not None:
            recorder.event('perception_trace',dict(schema='first-person-trace-v1',
                agency=snapshot,interpretation='Charlie-authored provisional beliefs; not independent visual truth'),
                at=source.timestamp,sources=list(recent_observation_ids))
            recent_observation_ids.append(source.observation_id)
            if len(recent_observation_ids)>8:recent_observation_ids.pop(0)
        nonlocal agency_samples
        execution = getattr(controller, 'last_execution', None) or {}
        if session.state == SessionState.ACQUIRING and execution.get('move') not in (None,'STAY') and 'first_body_probe_at' not in timing:
            timing['first_body_probe_at'] = execution.get('started_at')
            diary.event('first_body_probe', at=execution.get('started_at'), control_execution=execution)
        status = snapshot.get('identity_status')
        if status in ('provisional', 'confirmed') and f'first_{status}_self_at' not in timing:
            timing[f'first_{status}_self_at'] = source.timestamp
            mark(f'first_{status}_self_recorded', capture_timestamp=source.timestamp,
                 track_id=snapshot.get('controlled_track_id'), identity_status=status)
        row = {"sample": visual_agency.tick, "capture_timestamp": source.timestamp, "capture": source.capture,
               "viewer_state":source.viewer_state,
               "control_execution": getattr(controller, "last_execution", None), "session_phase":session.state.value, **snapshot}
        if publisher is not None and source.raw is not None:
            publisher.submit(source.raw, timestamp=source.timestamp, playfield=latest_agency_frame,
                metadata={'phase':session.state.value, 'agency':snapshot,
                          'control_execution':getattr(controller,'last_execution',None),
                          'preceding_action':preceding_action, 'experiment':experiment_plan})
        # Encoding PNGs between pulses lengthened unseen intervals substantially.
        # Buffer a bounded set of originals; write images only after controls close.
        if args.visual_retention_hz is None and latest_agency_frame is not None and len(raw_frames) < 96:
            raw_name = f"raw-{visual_agency.tick:04d}.png"
            buffered_frames.append((raw_name, latest_agency_frame.copy()))
            row["raw_frame"] = raw_name
            raw_frames.append({"sample":visual_agency.tick, "path":raw_name})
        if args.visual_retention_hz is None and latest_agency_frame is not None and len(agency_frames) < 24:
            frame = latest_agency_frame.copy()
            draw = ImageDraw.Draw(frame)
            for track_id in visual_agency.positions:
                track = visual_agency.tracker.active[track_id]
                belief = visual_agency.agency.beliefs[track_id]
                color = "lime" if track_id == snapshot["self_track_id"] else "yellow"
                draw.rectangle(track.box, outline=color)
                draw.text((track.box[0], track.box[1]), f"{track_id} {belief.confidence:.2f}", fill=color)
            name = f"agency-{len(agency_frames):03d}.png"
            buffered_frames.append((name, frame))
            row["frame"] = name
            agency_frames.append({"sample": visual_agency.tick, "path": name,
                                  "candidates": _pair_evidence(visual_agency.pairs)})
        if progress: progress.perception()
        agency_samples += 1
        recorder.append_line(args.output/'agency.jsonl',row)
        if snapshot["event"]:
            print(f"AGENCY {snapshot['event'].upper()}: self={snapshot['self_track_id']} "
                  f"candidate={snapshot['candidate_track_id']} confidence={snapshot['confidence']:.2f} "
                  f"runner={snapshot['runner_up_confidence']:.2f}")
        if score_observer is not None and source.raw is not None:
            score_observer.submit(source.raw, timestamp=source.timestamp,observation_id=source.observation_id,
                                  sample=visual_agency.tick, preceding_action={
                                      "action":preceding_action, "agency_command":snapshot.get("command"),
                                      "self_track_id":snapshot.get("self_track_id"),
                                      "control_execution":getattr(controller, "last_execution", None),
                                      "phase":snapshot.get("phase"),
                                      "response_window":snapshot.get("response_window"),
                                      "identity_status":snapshot.get("identity_status"),
                                      "actuators":snapshot.get("actuators")} if preceding_action or snapshot.get("command") is not None or getattr(controller, "last_execution", None) is not None else None)
    def observe_unmeasured(pairs, frame):
        nonlocal latest_agency_frame
        latest_agency_frame = frame
        record_agency(visual_agency.observe(pairs, observed_at=source.timestamp))
    def read_agency_pairs():
        nonlocal latest_agency_frame
        latest_agency_frame = calibration.apply(source.read())
        return recognizer.detect(latest_agency_frame)
    def save_review(raw, tick, reason):
        if len(review_frames) >= (40 if reason == 'final-view' else 39):
            return
        name = f'review-{len(review_frames):03d}-{tick}-{reason}.jpg'
        buffered_frames.append((name, raw.copy()))
        review_frames.append({'tick':tick,'reason':reason,'path':name})
    try:
        revision = subprocess.check_output(['git','rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git','status','--porcelain'],text=True,stderr=subprocess.DEVNULL))
    except (OSError,subprocess.CalledProcessError):
        revision,dirty = None,None
    provenance = {'git_commit':revision,'dirty_worktree':dirty,
                  'knowledge_sha256':hashlib.sha256(args.knowledge.read_bytes()).hexdigest()}
    from .progress_evidence import CaptureEvidence
    try:
        recorder=CaptureEvidence(args.output,diary.capture_origin['capture_id'],provenance,
            capacity=args.evidence_frame_capacity,record_capacity=args.evidence_record_capacity,
            byte_capacity=args.evidence_memory_mib*1024*1024,visual_hz=args.visual_retention_hz,rolling_seconds=args.rolling_seconds,
            rolling_frames=args.rolling_frames,rolling_bytes=args.rolling_memory_mib*1024*1024)
    except BaseException:
        source.close()
        raise
    source.recorder=recorder
    rows.recorder=recorder
    mark('evidence_recording_started',journal='session-evidence.sqlite3',scope='recording session, not verified game')
    def new_controller():
        if progress: progress.enter('controller')
        instance = ArcadeController(args.host, args.port, protocol="positions")
        if progress:
            progress.enter('perception')
            return SupervisedController(instance, progress)
        return instance
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

        # Task-aware optics preflight runs before START, with neutral controls,
        # and never inside the time-critical tracking/score observation loop.
        mark('calibration_started')
        calibration,sensory_report=sensory_preflight(source,args.output,seed_position=args.focus)
        original_detect=recognizer.detect
        def trace_detect(frame):
            pairs=original_detect(frame)
            recorder.event('detector_trace',dict(schema='first-person-trace-v1',
                detections=[dict(kind=d.kind,center=list(d.center),box=list(d.box),pixels=d.pixels,
                                 detector_output=e) for d,e in pairs],
                geometry=dict(corners=getattr(calibration,'corners',None),output_size=getattr(calibration,'output_size',None)),
                interpretation='Charlie detector outputs; no independent identity/semantic truth'),at=source.timestamp)
            return pairs
        recognizer.detect=trace_detect
        exposure_preflight=sensory_report.get('exposure')
        calibration_mode='fresh_session'
        mark('calibration_finished', mode=calibration_mode)
        recorder.ready()
        mark('evidence_ready',raw_frames=recorder.count)
        phase(SessionState.CAMERA_READY, 'optics and geometric calibration complete')
        mark('camera_ready')

        auto_start = args.arm and not args.no_start_game
        if auto_start:
            decision, decision_frames = _initial_start_decision(source, calibration, timeout=args.start_wait,classifier=screen_classifier)
            buffered_frames.extend(decision_frames)
            mark('start_decision', decision=decision)
            auto_start = decision['action']!='attach'
            if auto_start:
                decision=dict(decision,classifier_recommendation=decision['action'],action='explore',
                    reason='usable recorded view and explicit session authority; explore permitted inputs')
            if not auto_start:
                print('GAMEPLAY ALREADY VISIBLE: attaching without START')
        else:
            decision = {'action':'attach' if args.arm else 'observe', 'reason':'explicit --no-start-game or unarmed observation'}
            mark('start_decision', decision=decision)
        if auto_start:
            controller = new_controller()
            phase(SessionState.STARTING, 'explicit session authority and usable recorded view; screen semantics may be unknown')
            mark('exploration_started')
            def exploratory_control(button,state):
                if button=='START':
                    mark('start_'+state)
                    if state=='acknowledged':timing['start_transport']=getattr(controller,'last_command',None)
            exploration=_explore_startup(source,calibration,controller,forebrain,recorder,
                timeout=args.exploration_seconds,max_actions=args.exploration_actions,on_control=exploratory_control,classifier=screen_classifier)
            recorder.event('startup_summary',exploration,at=time.monotonic())
            mark('exploration_finished',verified=exploration['gameplay_verified'])
            if not exploration['gameplay_verified']:
                raise RuntimeError('exploratory startup waiting: '+exploration['reason'])
            phase(SessionState.WAITING_FOR_GAMEPLAY, 'fresh visual commencement; controls alone never establish an episode')

        # Fresh temporal state belongs to this run/new START, never unreadable frames.
        try:
            score_observer = ScoreObserver(calibration, args.output / "score.jsonl")
        except Exception as exc:
            print(f"SCORE UNKNOWN: {type(exc).__name__}: {exc}")

        if args.arm:
            player, acquisition, frames, startup_watch, gameplay_visual_frame = _wait_for_gameplay(
                source, calibration, recognizer, args.output, timeout=args.start_wait,
                on_observation=observe_unmeasured, generic_ready=True,classifier=screen_classifier)
            if acquisition is None:
                raise RuntimeError('gameplay entry unconfirmed; controls neutral')
        else:
            frames = _quick_frames(source, calibration, recognizer, count=5,
                                   on_observation=observe_unmeasured if args.arm else None)
            startup_watch = []
            gameplay_visual_frame = None
            player, acquisition = _acquire_from_frames(frames)

        mark('candidate_watch_finished')
        timing['first_visual_candidates_at'] = next((r['capture_timestamp'] for r in startup_watch if r['candidate_count']), None)
        timing['first_classified_gameplay_at'] = next((r['capture_timestamp'] for r in startup_watch
            if r['screen_state']['state']=='gameplay'), None)
        timing['gameplay_confirmed_at'] = next((startup_watch[i]['capture_timestamp'] for i in range(2,len(startup_watch))
            if all(r['screen_state'].get('phase')=='gameplay' for r in startup_watch[i-2:i+1])), None)
        phase(SessionState.ACQUIRING, 'candidate watch complete; direct actuator evidence follows')

        # Appearance/center are proposals. Armed play requires direct agency.
        if args.arm:
            if controller is None:
                controller = new_controller()
            print("DISCOVERING SELF: short movement/neutral probes over all visual candidates")
            mark('self_discovery_started')
            player = visual_agency.discover(read_agency_pairs, controller, record=record_agency,
                                           observation_time=lambda: source.timestamp)
            mark('self_discovery_finished', identity_status='confirmed' if visual_agency.agency.self_id is not None else 'provisional' if player is not None else 'unknown')
            frames = [visual_agency.pairs]
            acquisition = ("generic_visual_agency" if visual_agency.agency.self_id is not None else
                           "provisional_body_agency" if player is not None else None)
            if acquisition == "provisional_body_agency":
                print(f"SELF PROVISIONAL: hypothesis={visual_agency.controlled_track_id}; FIRE outcomes unconfirmed")

        if player is None:
            raise RuntimeError("could not identify the player; controls neutral")

        identity_word = "HYPOTHESIS" if acquisition == "provisional_body_agency" else "ACQUIRED"
        print(f"PLAYER {identity_word} ({acquisition}) x={player[0]:.2f} y={player[1]:.2f}")

        # Bind trusted startup acquisition to an identity-independent visual track.
        seed_pairs = frames[-1] if frames else []
        seed_detections = [d for d, _ in seed_pairs]
        self_obs = (self_tracker.bind_track(0, visual_agency.controlled_track_id, visual_agency.positions)
                    if args.arm else self_tracker.seed(0, seed_detections, player, max_seed_distance=7.0))
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
            controller = new_controller()
        started = time.monotonic()
        deadline = started + args.seconds if args.seconds is not None else float("inf")
        timing.update(gameplay_timer_started_at=started, gameplay_deadline=deadline if args.seconds else None,
                      duration_limit_kind="diagnostic" if args.seconds else "none")
        uncertainty = UncertaintyWindow(args.uncertainty_seconds)
        phase(SessionState.PLAYING, 'ordinary policy enabled with acquired or provisional SELF')
        diary.event('gameplay_timer_started', at=started, deadline=deadline if args.seconds else None, identity=acquisition)
        tick = 0
        lost = 0
        pending_move = None
        pending_at = None
        pending_origin = None
        pending_origin_at = None
        episode_observer = EpisodeEndObserver(required_not_gameplay=8)
        imaging_monitor=ImagingMonitor(calibration.apply(source.raw))
        for watched in startup_watch:
            episode_observer.observe_phase(dict(watched['screen_state'],capture_timestamp=watched.get('capture_timestamp')))
        print(f"CHARLIE LOOSE: diagnostic limit {args.seconds:.1f}s" if args.seconds else "CHARLIE LOOSE: progress supervised; waiting for confirmed Robotron terminal state")

        while time.monotonic() < deadline:
            raw = source.read()
            observed_at = time.monotonic()-started
            playfield = calibration.apply(raw)
            pairs = recognizer.detect(playfield)
            detections = [d for d, _ in pairs]

            # Normal movement is another causal experiment; right-stick firing
            # never enters the BODY evidence model. Track continuity supplies WHERE.
            response_window = pending_move not in (None, 'STAY')
            if response_window:
                early = visual_agency.observe(pairs, observed_at=source.timestamp)
                early['phase'] = 'response_window_early_unmeasured'
                early['response_window'] = {'origin_at': pending_origin_at, 'move': pending_move,
                                            'endpoint': 1, 'endpoints': 2}
                latest_agency_frame = playfield
                record_agency(early)
                if time.monotonic() >= deadline:
                    result = "DIAGNOSTIC LIMIT"
                    break
                raw = source.read()
                observed_at = time.monotonic()-started
                playfield = calibration.apply(raw)
                pairs = recognizer.detect(playfield)
                detections = [d for d, _ in pairs]
            agency_snapshot = visual_agency.observe(
                pairs, pending_move,
                time.monotonic()-pending_at if pending_at is not None else None,
                observed_at=source.timestamp,
                reference_positions=pending_origin if response_window else None)
            if response_window:
                agency_snapshot['phase'] = 'action_response_window'
                agency_snapshot['response_window'] = {
                    'origin_at': pending_origin_at, 'endpoint_at': source.timestamp,
                    'move': pending_move, 'endpoint': 2, 'endpoints': 2,
                    'duration_seconds': source.timestamp-pending_origin_at}

            latest_agency_frame = playfield
            record_agency(agency_snapshot)
            pending_move = None
            pending_at = None
            # Observe terminal transitions independently of a lingering SELF belief.
            screen=screen_classifier(playfield)
            screen['capture_timestamp']=source.timestamp
            episode_observer.observe_phase(screen)
            if episode_observer.visual_boundary:
                result='GAME OVER'
                episode_end=dict(state='game_over',confirmed=True,evidence=episode_observer.evidence(screen=screen,self_lost_frames=lost))
                save_review(raw,tick,'game-over')
                diary.event('episode_boundary_confirmed',evidence=episode_end['evidence'])
                print('GAME OVER CONFIRMED: gameplay → rankings → attract evidence')
                break
            drift=imaging_monitor.observe(playfield)
            if drift and screen.get('phase') not in ('title','terminal','startable'):
                controller._command('NEUTRAL')
                diary.event('sensory_reacquisition_requested',evidence=drift)
                if not drift['allowed']:
                    raise ObservationFailure('bounded sensory reacquisition exhausted; assistance required')
                recorder.preparing=True
                calibration,reacquired_optics=sensory_preflight(source,args.output,seed_position=args.focus)
                recorder.ready();imaging_monitor.reacquired(calibration.apply(source.raw))
                recorder.event('sensory_reacquired',reacquired_optics,at=time.monotonic())
                interrupted=hindbrain.interrupt_tactic('new imaging coordinates; previous response window interrupted')
                if interrupted:recorder.event('tactical_outcome',interrupted,at=time.monotonic())
                retired=visual_agency.reframe()
                diary.event('coordinate_epoch_changed',retired_track_ids=retired,reason='fresh independently observed geometry')
                if score_observer is not None:score_observer.reframe(calibration)
                if policy:policy.reset_predictions()
                pending_move=None;pending_origin_at=None
                self_tracker.player_track_id=None
                shadow_predictor=ShadowPredictor(horizon_seconds=.15,max_speed=100.)
                continue # fresh geometry requires ordinary agency recovery
            self_obs = self_tracker.observe_tracks(tick + 1, visual_agency.positions)
            agency_player = visual_agency.player
            new_player = None
            if agency_player is not None:
                if self_obs.center is not None and _distance(self_obs.center, agency_player) <= .5:
                    new_player = self_obs.center
                else:
                    # Conservative track lineage changes require new causal identity.
                    self_obs = self_tracker.bind_track(tick + 1, visual_agency.controlled_track_id, visual_agency.positions)
                    new_player = self_obs.center

            if new_player is None:
                lost += 1
                phase(SessionState.REACQUIRING, 'SELF unavailable; life boundary UNKNOWN')
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
                    source, calibration, recognizer, count=4, interval=0.025,
                    on_observation=observe_unmeasured, deadline=deadline)
                if time.monotonic() >= deadline:
                    result = 'DIAGNOSTIC LIMIT'
                    break
                recovered = None  # Global resemblance is not proof of a new SELF.

                recovery = "generic_visual_agency"
                if lost == 1 or lost % 12 == 0:
                    recovered = visual_agency.discover(
                        read_agency_pairs, controller, deadline=deadline, record=record_agency,
                        observation_time=lambda: source.timestamp)
                    if recovered is not None and visual_agency.agency.self_id is None:
                        recovery = "provisional_body_agency"
                    recovery_frames = [visual_agency.pairs]
                    detections = [d for d, _ in visual_agency.pairs]

                # SELF loss never ends an episode.  It only changes what Charlie
                # does: remain neutral, keep looking, and gather independent
                # evidence about whether Robotron itself has left gameplay.
                screen = classify_screen_state(latest_agency_frame if latest_agency_frame is not None else playfield)
                screen['capture_timestamp'] = source.timestamp

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
                        initial_frames=recovery_frames, on_observation=observe_unmeasured, deadline=deadline)

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
                        # Failed probes cannot distinguish death, respawn, bad
                        # identity or delay from the end of a whole game.
                        episode_observer.observe_agency(False)
                        recovered = None
                        print('SELF CHALLENGE REJECTED; episode boundary remains unconfirmed')
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
                # Recovery/challenge may have taken seconds: use its newest
                # already-calibrated evidence, not the frame preceding it.
                screen = classify_screen_state(latest_agency_frame if latest_agency_frame is not None else playfield)
                screen['capture_timestamp'] = source.timestamp
                episode_observer.observe_phase(screen)
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
                    if uncertainty.observe(False, time.monotonic()):
                        result = 'OBSERVATION UNCERTAIN'
                        diary.event('observation_uncertainty_stop', screen=screen, boundary='unverified',
                                    duration=time.monotonic()-uncertainty.since)
                        break
                    if progress: progress.cycle()  # completed neutral observation/recovery, not ordinary play
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
                shadow_predictor = ShadowPredictor(horizon_seconds=.15, max_speed=100.)
                forebrain = Forebrain(policy=policy); shadow_forebrain = Forebrain()
                if policy:policy.reset_predictions()
                player = recovered
                reseed = self_tracker.bind_track(
                    tick + 1, visual_agency.controlled_track_id, visual_agency.positions)
                if reseed.center is not None:
                    player = reseed.center
                rows.append({
                    "tick": tick,
                    "t": time.monotonic() - started,
                    "status": "player_reacquired",
                    "self_track_id": reseed.track_id,
                    "lost": lost,
                    "method": recovery,
                    "identity_status": "confirmed" if visual_agency.agency.self_id is not None else "provisional",
                    "capture_timestamp": source.timestamp,
                    "capture": source.capture,
                    "action_timestamp": pending_at,
                    "player": list(player),
                })
                print(
                    f"PLAYER REACQUIRED ({recovery}) after {lost} misses "
                    f"x={player[0]:.2f} y={player[1]:.2f}")
                episode_observer.self_reacquired()
                phase(SessionState.PLAYING, 'SELF reacquired; no new-game inference')
                lost = 0
                tick += 1
                continue

            if tick % 50 == 0:
                save_review(raw,tick,'gameplay')
            player = new_player
            if self_obs.center is None:
                reseed = self_tracker.bind_track(
                    tick + 1, visual_agency.controlled_track_id, visual_agency.positions)
                if reseed.center is not None:
                    player = reseed.center
            if lost:
                print(f"PLAYER REACQUIRED (local track) after {lost} misses")
                episode_observer.self_reacquired()
            lost = 0

            planning_pairs=pairs;semantic_evidence=[]
            if semantic_observer is not None:
                # The generic association and agency observation are already done.
                # Only soft metadata can change; no inference on this thread.
                planning_pairs,semantic_evidence=semantic_observer.apply(pairs,visual_agency.assignments,
                    visual_agency.tracker.active,self_id=visual_agency.controlled_track_id,timestamp=source.timestamp)
                semantic_observer.submit(playfield,pairs,visual_agency.assignments,visual_agency.tracker.active,
                    self_id=visual_agency.controlled_track_id,timestamp=source.timestamp)
            targets = _objects(planning_pairs, HUMANS|{'human'}, "human", visual_agency.assignments,
                               visual_agency.controlled_track_id)
            threats = _objects(planning_pairs, THREATS|{'threat'}, "threat", visual_agency.assignments,
                               visual_agency.controlled_track_id)
            unresolved = _objects(planning_pairs, {d.kind for d, _ in planning_pairs}-HUMANS-THREATS-{'human','threat'},
                                  "unresolved", visual_agency.assignments,
                                  visual_agency.controlled_track_id)
            world = WorldState(tick=tick, player=Position(*player),
                               targets=targets, threats=threats, alive=True, unresolved=unresolved,
                               observation_safe=policy is None or agency_snapshot.get('identity_status')=='confirmed')

            # Physical IDs come directly from generic tracks. A semantic label
            # change does not rename the object or run a second association pass.
            decision_started=time.perf_counter_ns()
            tactical_outcome=hindbrain.tactical_feedback(world,timestamp=source.timestamp,
                track_id=visual_agency.controlled_track_id,identity_status=agency_snapshot.get('identity_status'),
                response_window=agency_snapshot.get('response_window'))
            goal = forebrain.update(world)
            intent, action = hindbrain.decide(world, goal, timestamp=source.timestamp)
            decision_ns=time.perf_counter_ns()-decision_started
            feedback_persistence_ns=0
            if tactical_outcome is not None:
                began=time.perf_counter_ns()
                outcome_id=recorder.event('tactical_outcome',tactical_outcome,at=time.monotonic())
                if args.rolling_seconds and tactical_outcome.get('resolved_result')=='contradicted':
                    recorder.request_incident('Charlie tactical prediction contradicted',prediction_id=tactical_outcome.get('prediction_id'))
                feedback_persistence_ns=time.perf_counter_ns()-began
            experiment_context = None
            if experiment_plan and not experiment_status['attempted']:
                from .experiment_return import experimental_action
                baseline_action = action
                proposed, skip_reason = experimental_action(
                    experiment_plan, world, intent, baseline_action, agency_snapshot, now=time.monotonic())
                experiment_status['reason'] = skip_reason
                if proposed is not None:
                    action = proposed
                    experiment_context = {'prediction_id':experiment_plan['prediction_id'],
                        'memory_id':experiment_plan['memory_id'],
                        'track_id':visual_agency.controlled_track_id,
                        'identity_status':agency_snapshot.get('identity_status'),
                        'origin_at':source.timestamp,'baseline_action':action_dict(baseline_action),
                        'action':action_dict(action)}

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

            remaining_ms = int(max(0.0, deadline-time.monotonic()) * 1000) if args.seconds else args.pulse_ms
            if remaining_ms < 30:
                result = "DIAGNOSTIC LIMIT"
                break
            pulse_ms = min(args.pulse_ms, remaining_ms)
            if pulse_ms < 30:
                result = "DIAGNOSTIC LIMIT"
                break
            uncertainty.observe(True, time.monotonic())
            pending_origin = dict(visual_agency.positions)
            pending_origin_at = source.timestamp
            pending_at = time.monotonic()
            if 'first_ordinary_action_requested' not in timing:
                mark('first_ordinary_action_requested', action=action_dict(action), identity_status=agency_snapshot.get('identity_status'))
            preceding_action = {"tick":tick, "timestamp":pending_at, **action_dict(action)}
            began=time.perf_counter_ns()
            hindbrain.align_tactical_action(action)
            tactical_prediction_id=recorder.event('tactical_prediction',dict(
                **hindbrain.tactical_plan,actual_action=action_dict(action),
                observed_world=dict(tick=world.tick,player=[world.player.x,world.player.y],
                    targets=[dict(id=o.id,position=[o.position.x,o.position.y]) for o in world.targets],
                    threats=[dict(id=o.id,position=[o.position.x,o.position.y]) for o in world.threats],
                    unresolved=[dict(id=o.id,position=[o.position.x,o.position.y]) for o in world.unresolved]),
                self_track_id=visual_agency.controlled_track_id,identity_status=agency_snapshot.get('identity_status'),
                policy=hindbrain.last_decision.get('policy'),goal=vars(goal),
                intent=dict(kind=intent.kind,target_id=intent.target_id)),at=time.monotonic(),sources=recent_observation_ids)
            prediction_persistence_ns=time.perf_counter_ns()-began
            controller.execute(action, pulse_ms)
            hindbrain.executed_tactic(world,action,timestamp=source.timestamp,
                track_id=visual_agency.controlled_track_id,prediction_id=tactical_prediction_id)
            recorder.event('tactical_execution',dict(prediction_id=tactical_prediction_id,
                action=action_dict(action),control_execution=getattr(controller,'last_execution',None)),at=time.monotonic())
            if 'first_ordinary_execution' not in timing:
                execution = getattr(controller, 'last_execution', None)
                timing['first_ordinary_execution'] = dict(execution) if execution else None
                diary.event('first_ordinary_execution', at=execution.get('started_at') if execution else None,
                            control_execution=execution, identity_status=agency_snapshot.get('identity_status'))
            if experiment_context is not None:
                experiment_status.update(status='executed',attempted=True,reason=experiment_plan['reason'])
                print(f"EXPERIMENT: BODY={action.move} FIRE={action.fire}; prediction={experiment_plan['prediction_id'][:12]}")
            if publisher is not None:
                publisher.submit(source.raw, timestamp=source.timestamp, playfield=latest_agency_frame,
                    metadata={'phase':'ordinary_action_completed', 'agency':agency_snapshot,
                              'action':action_dict(action), 'intent':{'kind':intent.kind,'target_id':intent.target_id},
                              'control_execution':getattr(controller,'last_execution',None), 'experiment':experiment_plan})
            pending_move = action.move
            rows.append({
                "tick": tick, "observed_at": observed_at, "t": time.monotonic()-started,
                "capture_timestamp": source.timestamp,
                "capture": source.capture,
                "action_timestamp": pending_at,
                "control_execution":getattr(controller,'last_execution',None),
                "viewer_state":source.viewer_state,
                "player": list(player),
                "self_track_id": self_tracker.player_track_id,
                "identity_status": agency_snapshot.get("identity_status"),
                "experiment": experiment_context,
                "recording_pipeline":recorder.telemetry(),
                "tactical_learning":dict(plan=hindbrain.tactical_plan,outcome=tactical_outcome,
                    prediction_id=tactical_prediction_id,decision_ns=decision_ns,
                    feedback_persistence_ns=feedback_persistence_ns,prediction_persistence_ns=prediction_persistence_ns),
                "learned_semantics": semantic_evidence,
                "qualified_policy": {'forebrain':forebrain.last_reason,'hindbrain':hindbrain.last_decision,
                                     'error':policy_error,'decision_ns':decision_ns},
                "agency": agency_snapshot,
                "targets": len(targets), "threats": len(threats),
                "unresolved": len(unresolved),
                "world_objects": {role:[{"id":o.id, "position":[o.position.x,o.position.y]}
                                        for o in getattr(world,role)]
                                  for role in ("targets","threats","unresolved")},
                "intent": {"kind":intent.kind, "target_id":intent.target_id},
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
            if progress: progress.cycle()
            tick += 1
        else:
            result = "DIAGNOSTIC LIMIT"

        print(f"RUN COMPLETE: {result}; ticks={tick}")
    except KeyboardInterrupt:
        result = "INTERRUPTED"
        print("INTERRUPTED; neutralizing")
    except Exception as exc:
        result = f'ERROR: {type(exc).__name__}: {exc}'
        if isinstance(exc, ObservationFailure) or (progress and progress.data['phase'] == 'camera'):
            failure_kind = 'observation_failure'
        elif progress:
            failure_kind = progress.data.get('failure_kind',
                'controller_failure' if progress.data['phase'] == 'controller' else 'player_failure')
        else:
            failure_kind = 'player_failure'
        raise
    finally:
        # Release controls/camera before disk-backed diaries or writer drains.
        recording_error=None
        if controller is not None:
            try:controller.close()
            except (OSError,ConnectionError):pass
        try:source.close()
        except Exception as exc:recording_error=f'camera close: {type(exc).__name__}: {exc}'
        if progress:
            try:progress.enter('finalizing')
            except OSError as exc:recording_error=f'progress finalization: {exc}'
        timing['stopped_at'] = time.monotonic()
        start_transport = timing.get('start_transport') or {}
        ordinary = timing.get('first_ordinary_execution') or {}
        if ordinary.get('started_at') is not None and start_transport.get('write_completed_at') is not None:
            timing['start_to_first_ordinary_action_seconds'] = ordinary['started_at']-start_transport['write_completed_at']
            timing['start_to_first_ordinary_action_basis'] = 'controller action start minus START local write completion; not remote execution/display onset'
        try:
            diary.transition(session.stop(result));diary.close()
        except OSError as exc:recording_error=f'diary finalization: {exc}'
        try:recorder.close()
        except Exception as exc:
            recording_error=f'{type(exc).__name__}: {exc}'
            result='ERROR: evidence finalization failed; original partial records retained'
        if recording_error:result='ERROR: evidence finalization failed; original partial records retained'
        if progress:
            try:progress.enter('finalizing')
            except OSError:pass
        if publisher is not None:
            publisher.close()
        if semantic_observer is not None:
            semantic_observer.close()
        if score_observer is not None:
            score_observer.close()
        if score_observer is not None and not score_observer.thread.is_alive():
            buffered_frames.extend(score_observer.frames)
        if score_observer is not None and score_observer.thread.is_alive():
            recording_error='score instrumentation writer unfinished; next-game handoff blocked'
            result='ERROR: incomplete score recording'
        score_summary = score_observer.report() if score_observer is not None else {"status":"unmeasured", "self_score":None}
        if 'raw' in locals():
            save_review(raw,locals().get('tick',0),'final-view')
        # Controllers are already neutral/closed before any image encoding.
        for name, frame in buffered_frames:
            frame.save(args.output / name)
        tracks = self_tracker.tracks() if args.arm else []
        (args.output / "tracks.json").write_text(json.dumps({"tracks":tracks}, indent=2)+"\n")
        report = {"session_timing":timing, "session_transitions":[vars(r) for r in session.transitions], "session_events":"events.jsonl", "provenance": provenance, "review_frames": review_frames, "result": result, "armed": args.arm, "seconds": args.seconds,
                  "failure_kind": locals().get("failure_kind"),
                  "progress": dict(progress.data, publication_seconds=progress.cost_seconds) if progress else None,
                  "partial_action_evidence":"steps.jsonl",
                  "pulse_ms": args.pulse_ms, "ticks": len(rows),
                  "episode_end": episode_end,
                  "score": score_summary["self_score"], "score_status": score_summary["status"],
                  "score_summary": score_summary,
                  "learning_mode": "session_tactical_feedback_with_guarded_persistent_policy",
                  "auto_start": locals().get('auto_start', False),
                  "start_decision": locals().get('decision'),
                  "exploratory_startup":locals().get('exploration'),
                  "sensory_preflight":locals().get('sensory_report'),
                  "session_evidence":"session-evidence.sqlite3",
                  "recording_error":recording_error,
                  "recording_pipeline":recorder.telemetry(),
                  "prediction_commitment_mode":"buffered_live_prospective",
                  "calibration_mode": locals().get("calibration_mode"),
                  "exposure_preflight": locals().get("exposure_preflight"),
                  "calibration": {"corners":getattr(locals().get("calibration"), "corners", None),
                                  "output_size":getattr(locals().get("calibration"), "output_size", None)},
                  "acquisition": locals().get("acquisition"),
                  "gameplay_visual_frame": locals().get("gameplay_visual_frame"),
                  "startup_watch": locals().get("startup_watch", []),
                  "diagnostic_buffer_bytes":sum(f.width*f.height*len(f.getbands()) for _,f in buffered_frames),
                  "agency_frames": agency_frames,
                  "raw_frames": raw_frames,
                  "tracking_log": "agency.jsonl",
                  "tracking_schema": "sprite-tracking-v3",
                  "capture_mode": "fresh_exposure" if args.arm else "read_completion",
                  "passive_observer": publisher.report() if publisher is not None else {'status':'unavailable'},
                  "camera_lease_handoff_seconds": getattr(getattr(getattr(source,'camera',None),'lease',None),'handoff_seconds',None),
                  "agency_acquisition_protocol": "two_fresh_endpoints_then_independent_neutral",
                  "planning_mode": "rescue_with_open_space_fallback",
                  "learned_semantics": semantic_observer.report() if semantic_observer is not None else {'status':'baseline','error':semantic_error},
                  "bootstrap_body_fire": args.bootstrap_body_fire,
                  "fire_agency_status": "exploratory evidence only; projectile/origin interpretation unvalidated",
                  "experiment_status": experiment_status,
                  "tracks": "tracks.json",
                  "agency_samples": agency_samples,
                  "agency_log": "agency.jsonl",
                  "steps": rows}
        from learning.foundry import atomic_json
        report['policy_identity']=dict(policy.identity) if policy else dict(kind='baseline',code_revision=revision,
            knowledge_sha256=provenance['knowledge_sha256'],bootstrap_body_fire=args.bootstrap_body_fire)
        atomic_json(args.output / "report.json", report)
        # Existing diary gains deferred score evidence before immutable sealing.
        # Operator reviews go to a consolidated notebook, never into this sealed source.
        from memory.evidence import EvidenceJournal
        score_diary=EvidenceJournal(args.output/'session-evidence.sqlite3')
        try:ScoreObserver.queue_game(score_diary,args.output,session=args.output.parent,number=args.output.name)
        finally:score_diary.close()
        from memory.episode_identity import finalize_capture
        if recording_error is None:finalize_capture(args.output)
        print(f"Evidence: {args.output}/report.json")
        if recording_error:
            import sys
            if sys.exc_info()[0] is None:raise ObservationFailure(recording_error)


if __name__ == "__main__":
    main()

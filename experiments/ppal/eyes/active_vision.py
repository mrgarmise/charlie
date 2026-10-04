"""Finite, evidence-driven physical viewpoint preparation. No background worker.

Own a source only for run(); primary tasks pass degradation observations separately.
RP2040Controller and PiCameraSource remain the sole hardware/ownership interfaces.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
import json
import math
import os
from pathlib import Path
import time
import numpy as np
import cv2
from .calibration import Calibration
from .passive import atomic_json
from ..preflight import PreflightConfig, optimize_screen_focus, screen_sharpness


class State(str, Enum):
    ACQUIRE = 'ACQUIRE'
    OPTIMIZE = 'OPTIMIZE'
    VALIDATE = 'VALIDATE'
    LOCKED = 'LOCKED'
    STOPPED = 'STOPPED'
    FAILED = 'FAILED'
    YIELDED = 'YIELDED'


class PrimaryOwnership(InterruptedError):
    pass


class ReacquisitionPermit:
    """One-use evidence ticket issued only by a DegradationGate."""
    def __init__(self, gate, at):
        self.gate, self.at, self.used = gate, at, False
        self.created_at = time.monotonic()

    def consume(self):
        if self.used or self.gate._permit is not self or time.monotonic()-self.created_at > 5:
            raise PermissionError('fresh degradation transition required')
        self.used = True
        self.gate._permit = None
        return 'DEGRADATION'


@dataclass(frozen=True)
class Config:
    pan_min: float = 0
    pan_max: float = 180
    tilt_min: float = 20
    tilt_max: float = 160
    step: float = 6
    rate: float = 15  # commanded degrees per second, both axes combined
    settle: float = .25
    experiments: int = 24
    acquisition_moves: int = 36
    validation_views: int = 4
    jitter: float = .012  # normalized corner displacement, independent of pixels
    min_sharpness: float = 8
    min_confidence: float = .7
    min_area: float = .08
    improvement: float = .005

    def __post_init__(self):
        if not (0 <= self.pan_min < self.pan_max <= 180 and
                0 <= self.tilt_min < self.tilt_max <= 180):
            raise ValueError('travel bounds exceed firmware limits')
        if not (0 < self.step <= 12 and 0 < self.rate <= 30 and self.settle >= .1
                and self.experiments > 0 and self.acquisition_moves > 0
                and self.validation_views >= 3 and self.jitter > 0):
            raise ValueError('invalid motion/validation limits')
        if not (0 < self.min_confidence <= 1 and 0 < self.min_area < 1
                and self.min_sharpness > 0 and self.improvement > 0):
            raise ValueError('invalid quality thresholds')


@dataclass(frozen=True)
class Target:
    calibration: Calibration
    confidence: float
    area: float
    margin: float
    rotation: float
    perspective: float
    sharpness: float

    @property
    def quality(self):
        # Complete target support dominates residual correction. Moving closer
        # to a clipped view can never win merely by reducing rotation.
        return (2*self.confidence + min(self.area, .5) + min(self.margin, .08)*3
                - abs(self.rotation)/90 - self.perspective*.4)


def discover(frame):
    """Discover rectangular targets in full FOV, including rotated screens.

    This generic fallback identifies geometry, not semantic identity. Tasks may
    inject their existing target detector (e.g. Robotron's supported border).
    """
    gray = np.asarray(frame.convert('L'))
    edges = cv2.Canny(gray, 45, 130)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    w, h = frame.size
    for contour in contours:
        quad = cv2.approxPolyDP(contour, .025*cv2.arcLength(contour, True), True)
        if len(quad) != 4 or not cv2.isContourConvex(quad):
            continue
        p = quad.reshape(4, 2).astype(float)
        if cv2.contourArea(p.astype(np.float32)) < .08*w*h:
            continue
        # Cyclic order, then top-left in the current image (no remembered crop).
        p = p[np.argsort(np.arctan2(p[:, 1]-p[:, 1].mean(), p[:, 0]-p[:, 0].mean()))]
        p = np.roll(p, -np.argmin(p.sum(axis=1)), axis=0)
        support = []
        for start, end in zip(p, np.roll(p, -1, axis=0)):
            hits = []
            for x,y in np.linspace(start, end, 64).astype(int):
                hits.append(bool(edges[max(0,y-3):min(h,y+4), max(0,x-3):min(w,x+4)].any()))
            support.append(sum(hits)/len(hits))
        t = measure(frame, p, min(support))
        if t.margin > .005:
            candidates.append(t)
    if not candidates:
        raise ValueError('no complete rectangular target')
    return max(candidates, key=lambda t: t.quality)


def robotron_target(frame):
    from .settle import locate
    return measure(frame, locate(frame), .9)


def measure(frame, pixels, confidence):
    p = np.asarray(pixels, dtype=float)
    if p.shape != (4, 2) or not np.isfinite(p).all():
        raise ValueError('invalid target geometry')
    w, h = frame.size
    n = p / (w, h)
    if np.any(n <= 0) or np.any(n >= 1):
        raise ValueError('clipped target')
    calibration = Calibration.from_pixels(p.tolist(), frame.size)
    lengths = np.linalg.norm(p-np.roll(p, -1, axis=0), axis=1)
    perspective = abs(math.log(lengths[0]/lengths[2])) + abs(math.log(lengths[1]/lengths[3]))
    rotation = math.degrees(math.atan2(*(p[1]-p[0])[::-1]))
    return Target(calibration, confidence, cv2.contourArea(p.astype(np.float32))/(w*h),
                  float(min(n.min(), (1-n).min())), rotation, perspective,
                  screen_sharpness(calibration.apply(frame), .08))


class ActiveVision:
    """Synchronous finite optimizer. Factories are called only inside run().

    Initial pose must come from the current hardware session, never a cached
    successful viewpoint. Hardware motion requires explicit authorization.
    STOP and camera closure run on every exit, including KeyboardInterrupt.
    """
    def __init__(self, source_factory, controller, output, *, initial_pose,
                 authorized=False, simulated=False, detector=discover,
                 config=None, publisher_factory=None, journal=None, reacquisition=None, neck_health=None,
                 calibration_service=None, wait=time.sleep):
        self.source_factory = source_factory
        self.controller = controller
        self.output = Path(output)
        self.pose = tuple(initial_pose)
        self.authorized = authorized
        self.simulated = simulated
        self.detector = detector
        self.cfg = config or Config()
        self._config_supplied = config is not None
        self.reacquisition = reacquisition
        self._control_claimed = self._motion_released = False
        self.publisher_factory = publisher_factory
        self.wait = wait
        self.journal = journal
        self.neck_health = neck_health
        self.calibration_service = calibration_service
        self._last_corners = None
        self._health_observation_size = None
        self.state = State.ACQUIRE
        self.cancelled = False
        self.source = self.publisher = None
        self.events = []
        self.samples = 0
        self.confidence = None
        self._bounds(self.pose)

    def _bounds(self, pose):
        pan, tilt = pose
        if not (math.isfinite(pan) and math.isfinite(tilt) and
                self.cfg.pan_min <= pan <= self.cfg.pan_max and
                self.cfg.tilt_min <= tilt <= self.cfg.tilt_max):
            raise ValueError('pose outside safe travel')

    def interrupt(self):
        self.cancelled = True
        self.controller.stop()

    def event(self, decision, **data):
        record = dict(index=len(self.events), state=self.state.value,
                      decision=decision, pose=self.pose, simulated=self.simulated,
                      at=time.monotonic(), **data)
        self.events.append(record)
        if self.publisher and hasattr(self.publisher, 'directory'):
            atomic_json(self.publisher.directory/'active-vision.json', dict(
                producer_pid=os.getpid(), run=str(self.output.resolve()),
                state=self.state.value, confidence=self.confidence, pose=self.pose,
                decision=decision, at=record['at']))
        with (self.output/'decisions.jsonl').open('a') as f:
            f.write(json.dumps(record, allow_nan=False)+'\n')
        if self.journal:
            self.journal.append('event', dict(category='active_vision', **record),
                episode=str(self.output.resolve()), producer='ActiveVision', version='1')

    def check(self):
        if self.neck_health is not None and self.neck_health.quarantined:
            raise PermissionError('neck safety uncertain; supervised recalibration required')
        if self.cancelled:
            raise InterruptedError('Active Vision interrupted')
        if not self.controller.connected:
            raise ConnectionError('RP2040 disconnected')
        camera = getattr(self.source, 'camera', None)
        lease = getattr(camera, 'lease', None)
        if lease is not None and lease.should_yield():
            raise PrimaryOwnership('primary task requested camera ownership')
        if not self.simulated and self._control_claimed and not self._motion_released:
            status = self.controller.motion_status()
            if status and status.get('task') == 'PRIMARY':
                raise PrimaryOwnership('primary task acquired RP2040 ownership')
            if (not status or not status.get('armed') or status.get('owner') != 'ACTIVE_VISION'
                    or status.get('epoch') != self.controller.motion_epoch):
                raise ConnectionError('RP2040 control grant expired or revoked')

    def move(self, pose):
        if not self.simulated and (not self.authorized or not self._control_claimed):
            raise PermissionError('scoped Active Vision control required')
        self.check()
        self._bounds(pose)
        distance = sum(abs(a-b) for a,b in zip(pose, self.pose))
        if distance > self.cfg.step+1e-6:
            raise ValueError('unbounded movement')
        if self.neck_health is not None:
            self.neck_health.prepare(self.pose,pose,self._last_corners)
        if not self.controller.look(*pose, rate=self.cfg.rate):
            raise ConnectionError('RP2040 rejected movement')
        self.pose = tuple(pose)
        if self.simulated:
            self.wait(distance/self.cfg.rate+self.cfg.settle)
            self.check()
        else:
            # Firmware acceleration makes requested rate an unreliable
            # estimate of actual completion time. Poll the existing
            # controller's reported state, with a finite deadline.
            deadline = time.monotonic() + max(
                3.0, distance/max(.001, self.cfg.rate)*5 + self.cfg.settle
            )
            settled = False
            while time.monotonic() < deadline:
                self.check()
                status = self.controller.viewpoint_status(timeout=1.0)
                if status is None:
                    raise ConnectionError('RP2040 viewpoint response unavailable')
                if (not status['moving'] and
                        abs(status['pan']-pose[0]) <= 1 and
                        abs(status['tilt']-pose[1]) <= 1):
                    settled = True
                    break
                self.wait(.1)
            if not settled:
                raise ConnectionError('physical pose did not settle before deadline')
        self.event('bounded physical experiment', distance=distance)

    def observe(self):
        self.check()
        # Fresh post-command exposure for Pi; replay sources may provide read().
        frame = getattr(self.source, 'read_fresh', self.source.read)()
        self.check()  # Preemption after capture prevents any further inference.
        self.samples += 1
        stem = f'{self.samples:05d}'
        frame.save(self.output/f'raw_{stem}.png')
        try:
            target = self.detector(frame)
        except ValueError as exc:
            self.event('target unavailable', reason=str(exc), raw=f'raw_{stem}.png')
            if self.neck_health is not None:
                self.neck_health.observe(None,telemetry=self.controller.motion_status())
                self.check()
            return None
        # Existing calibration corners are normalized; CAL-1 response evidence
        # is in raw-image pixels. Never compare those units directly.
        width,height=self._health_observation_size or frame.size
        self._last_corners = [[x*width,y*height] for x,y in target.calibration.corners]
        if self.neck_health is not None:
            self.neck_health.observe(self._last_corners,telemetry=self.controller.motion_status())
            self.check()
        self.confidence = target.confidence
        corrected = target.calibration.apply(frame)
        corrected.save(self.output/f'corrected_{stem}.png')
        self.event('observe target', target=asdict(target), quality=target.quality,
                   raw=f'raw_{stem}.png', corrected=f'corrected_{stem}.png')
        if self.publisher:
            self.publisher.submit(frame, timestamp=time.monotonic(), playfield=corrected,
                metadata={'active_vision': dict(state=self.state.value,
                    confidence=target.confidence, decision=self.events[-1], pose=self.pose)})
        return target

    def stable_observation(self):
        views = [self.observe() for _ in range(3)]
        if not all(self.usable(t) for t in views):
            return None
        points = np.array([t.calibration.corners for t in views])
        jitter = float(np.max(np.linalg.norm(points-np.median(points, axis=0), axis=2)))
        self.event('measure experiment stability', jitter=jitter)
        return views[-1] if jitter <= self.cfg.jitter else None

    def usable(self, t):
        return t is not None and t.confidence >= self.cfg.min_confidence and t.area >= self.cfg.min_area

    def run(self):
        if self.state != State.ACQUIRE:
            raise RuntimeError('one finite run per optimizer; reacquire with a new instance')
        if not self.simulated and not self.authorized:
            raise PermissionError('explicit physical movement authorization required')
        self.output.mkdir(parents=True, exist_ok=False)
        result = None
        try:
            self.check()
            if self.simulated:
                if not self.controller.stop():raise ConnectionError('could not stop existing scan')
            else:
                status = getattr(self.controller, 'motion_status', lambda:None)()
                if (not status or not status.get('armed') or not status.get('envelope')
                        or not status.get('electrical_gate_cleared')):
                    raise ConnectionError('RP2040 local physical arm and assembled calibration required')
                envelope = status['envelope']
                self._health_observation_size=envelope.get('observation_size')
                if self.calibration_service is not None:
                    profile=self.calibration_service.refresh()
                    if profile is None or profile['calibration_id']!=envelope['calibration_id']:
                        raise PermissionError('durable Pi/RP2040 qualified profile agreement required')
                    self.neck_health=self.calibration_service.health
                if status.get('neck_health_required') and self.neck_health is None:
                    from hardware.neck_health import NeckHealth
                    self.neck_health = NeckHealth(self.controller,envelope['calibration_id'],
                        lambda record:self.event('neck health evidence',record=record),
                        response_model=envelope.get('visual_response'))
                if not self._config_supplied:
                    self.cfg = Config(pan_min=envelope['pan']['min'],pan_max=envelope['pan']['max'],
                        tilt_min=envelope['tilt']['min'],tilt_max=envelope['tilt']['max'],
                        step=min(2,envelope['max_step']),rate=min(5,envelope['max_rate']))
                if (self.cfg.pan_min < envelope['pan']['min'] or self.cfg.pan_max > envelope['pan']['max']
                        or self.cfg.tilt_min < envelope['tilt']['min'] or self.cfg.tilt_max > envelope['tilt']['max']
                        or self.cfg.step > envelope['max_step'] or self.cfg.rate > envelope['max_rate']):
                    raise ValueError('Pi configuration exceeds RP2040 calibration')
                self.pose = (status['pan'],status['tilt'])
                self._bounds(self.pose)
            self.source = self.source_factory()
            if not self.simulated:
                camera = getattr(self.source, 'camera', None)
                if camera is None or camera.lease is None or camera.lease.role != 'active_vision':
                    raise RuntimeError('Active Vision requires the existing active_vision camera lease')
                transition = 'INITIAL' if self.reacquisition is None else self.reacquisition.consume()
                if not self.controller.request_active_vision(transition):
                    raise ConnectionError('RP2040 refused scoped Active Vision control')
                self._control_claimed = True
            if self.publisher_factory:
                self.publisher = self.publisher_factory()
            self.event('discover from current full field of view')
            target = self.observe()
            # Finite serpentine exploration, independent of successful angles.
            direction = 1
            for _ in range(self.cfg.acquisition_moves):
                if self.usable(target):
                    break
                pan, tilt = self.pose
                next_pan = pan+direction*self.cfg.step
                if not self.cfg.pan_min <= next_pan <= self.cfg.pan_max:
                    if not self.simulated:
                        self.event('physical acquisition boundary reached')
                        break
                    direction *= -1
                    next_tilt = tilt+self.cfg.step
                    if next_tilt > self.cfg.tilt_max:
                        next_tilt = self.cfg.tilt_min
                    # wrap via bounded travel over successive turns
                    next_tilt = tilt+max(-self.cfg.step, min(self.cfg.step, next_tilt-tilt))
                    self.move((pan, next_tilt))
                else:
                    self.move((next_pan, tilt))
                target = self.observe()
            if not self.usable(target):
                raise ValueError('target acquisition budget exhausted')
            self.state = State.OPTIMIZE
            attempts = 0
            while attempts < self.cfg.experiments:
                origin = self.pose
                best = target
                improved = False
                for axis, sign in ((0,1),(0,-1),(1,1),(1,-1)):
                    if attempts >= self.cfg.experiments:
                        break
                    candidate = list(origin)
                    candidate[axis] += sign*self.cfg.step
                    try:self._bounds(candidate)
                    except ValueError:continue
                    self.move(candidate)
                    trial = self.stable_observation()
                    attempts += 1
                    same_target = self.usable(trial) and .7 <= trial.area/best.area <= 1.4
                    gain = trial.quality-best.quality if same_target else -100
                    if gain > self.cfg.improvement + .001*self.cfg.step:
                        target = trial
                        improved = True
                        self.event('retain measured improvement', gain=gain)
                        break
                    self.event('reject experiment', gain=gain)
                    self.move(origin)
                    restored = self.observe()
                    if not self.usable(restored):
                        raise ValueError('target lost after restoring prior pose')
                    target = restored
                if not improved:
                    break
            # Existing task-local focus mechanism; discover seed from current
            # metadata, not a supplied successful focus. Record every trial.
            seed = self.source.lens_position()
            if seed is None or not math.isfinite(seed):
                raise ValueError('camera did not report current lens position')
            owner = self
            class FocusEvidence:
                def set_manual_focus(self, position):
                    owner.check()
                    owner.source.set_manual_focus(position)
                    owner.event('manual focus experiment', lens_position=position)
                def read(self):
                    owner.check()
                    frame = getattr(owner.source, 'read_fresh', owner.source.read)()
                    owner.samples += 1
                    frame.save(owner.output/f'focus_raw_{owner.samples:05d}.png')
                    corrected = target.calibration.apply(frame)
                    corrected.save(owner.output/f'focus_corrected_{owner.samples:05d}.png')
                    owner.event('focus observation', sharpness=screen_sharpness(
                        corrected, .08), raw=f'focus_raw_{owner.samples:05d}.png',
                        corrected=f'focus_corrected_{owner.samples:05d}.png',
                        calibration=asdict(target.calibration))
                    return frame
            focus = optimize_screen_focus(FocusEvidence(), target.calibration,
                seed_position=seed, config=PreflightConfig(focus_samples=3))
            self.state = State.VALIDATE
            views = [self.observe() for _ in range(self.cfg.validation_views)]
            if not all(self.usable(t) and t.sharpness >= self.cfg.min_sharpness for t in views):
                raise ValueError('view/focus validation failed')
            corners = np.array([t.calibration.corners for t in views])
            jitter = float(np.max(np.linalg.norm(corners-np.median(corners, axis=0), axis=2)))
            if jitter > self.cfg.jitter:
                raise ValueError('unstable viewpoint')
            self.check()
            if not self.controller.stop():
                raise ConnectionError('STOP failed before lock')
            if not self.simulated:
                status = self.controller.motion_status()
                if not status or status.get('armed') or status.get('pwm_active') or status.get('moving'):
                    raise ConnectionError('PWM-off STOP not confirmed')
                self._motion_released = True
                # A de-energized assembled head may settle or sag. Never label
                # the held-PWM viewpoint as validated after releasing torque.
                views = [self.observe() for _ in range(self.cfg.validation_views)]
                if not all(self.usable(t) and t.sharpness >= self.cfg.min_sharpness for t in views):
                    raise ValueError('released-head viewpoint validation failed')
                points = np.array([t.calibration.corners for t in views])
                jitter = float(np.max(np.linalg.norm(points-np.median(points,axis=0),axis=2)))
                if jitter > self.cfg.jitter:raise ValueError('released-head view unstable')
            self.state = State.LOCKED
            result = dict(schema='charlie-active-vision-v1', state=self.state.value,
                simulated=self.simulated, resources_released=False, pose=self.pose, focus=asdict(focus),
                calibration=asdict(views[-1].calibration), target=asdict(views[-1]),
                jitter=jitter, samples=self.samples)
            self.event('validated lock; optimization terminates', configuration=result)
            atomic_json(self.output/'view.json', result)
            return result
        except BaseException as exc:
            self.state = (State.YIELDED if isinstance(exc, PrimaryOwnership) else
                State.STOPPED if isinstance(exc, (InterruptedError, KeyboardInterrupt)) else State.FAILED)
            self.event('terminate without validated view', reason=str(exc))
            raise
        finally:
            try:
                try:
                    if self.state == State.YIELDED and not self.simulated:
                        self.controller.primary_ownership()
                    self.controller.stop()
                finally:
                    try:
                        if self.publisher:
                            self.publisher.close()
                            thread = getattr(self.publisher, 'thread', None)
                            if thread is not None and thread.is_alive():
                                raise RuntimeError('passive publication worker did not terminate')
                    finally:
                        if self.source:self.source.close()
                if result is not None:
                    result['resources_released'] = True
                    atomic_json(self.output/'view.json', result)
            except BaseException:
                self.state = State.FAILED
                (self.output/'view.json').unlink(missing_ok=True)
                raise
            finally:
                self.source = self.publisher = None


class DegradationGate:
    """Cheap evidence consumer only. Never captures, detects, or moves hardware.

    Primary task supplies structural border geometry, not sprite/global motion.
    Missing observations are unknown; severe persistent loss requests suspension.
    """
    def __init__(self, *, persistence=5, severe=15, cooldown=30, displacement=.04):
        if not (0 < persistence <= severe and cooldown >= 0 and displacement > 0):
            raise ValueError('invalid hysteresis')
        self.persistence, self.severe = persistence, severe
        self.cooldown, self.displacement = cooldown, displacement
        self.bad = self.missing = 0
        self.last = -math.inf
        self.observed_at = -math.inf
        self._permit = None

    def observe(self, reference, current, *, now, expected_transition=False,
                authorized=False, requested=False):
        if not math.isfinite(now) or now <= self.observed_at:
            return 'continue'
        self.observed_at = now
        if current is not None:
            points = np.asarray(current)
            if points.shape != (4,2) or not np.isfinite(points).all():
                current = None
        if expected_transition and not requested:
            self._permit = None
            self.bad = self.missing = 0
            return 'continue'
        if current is None:
            self.missing += 1
            self.bad = max(0, self.bad-1)
        else:
            delta = float(np.max(np.linalg.norm(np.asarray(current)-np.asarray(reference), axis=1)))
            if delta <= self.displacement:self._permit = None
            self.bad = self.bad+1 if delta > self.displacement else max(0, self.bad-1)
            self.missing = 0
        severe = self.missing >= self.severe
        needed = requested or self.bad >= self.persistence or severe
        if needed and (requested or now-self.last >= self.cooldown):
            if authorized:
                self.last = now
                if self.bad >= self.persistence or severe:
                    self._permit = ReacquisitionPermit(self, now)
                self.bad = self.missing = 0
                return 'reacquire'
            return 'suspend_and_request' if severe else 'request_permission'
        return 'suspend_and_request' if severe else 'continue'

    def reacquisition_permit(self):
        if self._permit is None:
            raise PermissionError('persistent viewpoint degradation has not authorized a transition')
        return self._permit


def apply_validated_view(source, record):
    """Primary task calls after acquiring its own existing camera lease.

    No servo movement, discovery, or optimization. A fresh geometry check remains
    the primary task's responsibility following camera restart.
    """
    if record.get('schema') != 'charlie-active-vision-v1' or record.get('state') != 'LOCKED' or not record.get('resources_released'):
        raise ValueError('validated Active Vision configuration required')
    if record.get('simulated'):
        raise ValueError('simulation cannot authorize a physical task')
    source.set_manual_focus(record['focus']['lens_position'])
    c = record['calibration']
    return Calibration(tuple(tuple(p) for p in c['corners']), tuple(c['output_size']))

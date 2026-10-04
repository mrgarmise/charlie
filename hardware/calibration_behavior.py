"""Normal-brain CAL-1 capability, driven by existing perception ticks.

No camera, thread, learning scheduler, PWM, qualification or deployment owner.
The installed RP2040 independently decides which paths require GP10.
"""
import math
import uuid
import hashlib
import json
import subprocess
from pathlib import Path
from .scene_response import SceneResponse
from .neck_calibration import encode, durable_write, timestamp


class CalibrationBehavior:
    def __init__(self, service, *, authorized=False, supervised=False, simulated=False,
                 operator='operator_local', maximum_steps=24, estimator=None):
        self.service, self.body = service, service.controller
        self.authorized, self.supervised, self.simulated = authorized, supervised, simulated
        self.operator, self.maximum_steps = operator, maximum_steps
        self.estimator = estimator or SceneResponse()
        self.session = None
        self.run = None
        self.before = None
        self.pending = None
        self.start_pose = None
        self.path = []
        self.boundaries = []
        self.responses = []
        self.direction = 0
        self.step = 0
        self.requested = False
        self.confirmed_start = False
        self.last_tick = -math.inf
        self.last_message = None
        self.last_state = None
        self.tracking_pending = None
        self.digital = None
        self.blocked = False
        self.observation_version = 0
        self.stationary_anchor = None
        self.stationary_pose = None
        self.unobserved = 0
        self.startup_waiting = False
        self.search_remaining = 0
        self.search_sign = 1
        self.last_target_at = None
        self.phase = 'axes'
        self.grid = []
        self.commissioning = None
        self.project_id = None
        self.generated_candidate = None
        self.return_to_home = False
        self.automatic_attempted = False

    def request_search(self):
        self.search_remaining = 12

    def corrected_frame(self, frame):
        """Digital perception output; physical evidence always uses raw frames."""
        if not self.digital or not hasattr(frame, 'shape'):
            return frame
        import cv2
        import numpy as np
        dx, dy = self.digital['correction']
        transform = np.float32([[1, 0, -dx], [0, 1, -dy]])
        return cv2.warpAffine(frame, transform, (frame.shape[1], frame.shape[0]))

    def preserve_frame(self, snapshot):
        import cv2
        directory = self.service.repository.directory.parent / 'frames'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory/(snapshot['sha256']+'.png')
        success, buffer = cv2.imencode('.png', snapshot['gray'])
        if not success:
            raise OSError('frame encoding failed')
        raw = buffer.tobytes()
        if not path.exists():
            durable_write(path, raw)
        elif path.read_bytes() != raw:
            raise ValueError('preserved frame content mismatch')
        return dict(path=str(path), artifact_sha256=hashlib.sha256(raw).hexdigest(),
            gray_pixels_sha256=snapshot['sha256'], capture_rgb_sha256=snapshot['capture_sha256'])

    def provenance(self):
        root = Path(__file__).resolve().parents[1]
        revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True)
        files = ('hardware/calibration_behavior.py', 'hardware/scene_response.py',
                 'hardware/calibration_service.py', 'rp2040/calibration.py', 'rp2040/servos.py')
        return dict(code_revision=revision.stdout.strip() if revision.returncode == 0 else 'unavailable',
            source_sha256={name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files})

    def message(self, text):
        if text != self.last_message:
            self.body.message(text)
            self.last_message = text

    def request(self):
        self.requested = True
        self.blocked = False

    def confirm_start(self):
        # Keyboard confirmation is live and consumed once; never reconstructed
        # from a reboot, an old journal, or a commanded-position estimate.
        if self.startup_waiting or self.session and self.last_state == 'VERIFY_INITIAL':
            self.confirmed_start = True

    def record(self, op, **data):
        return self.service.event(op, brain_capability='CAL-1', simulated=self.simulated,
            execution_authorized=self.authorized, run_id=self.run, **data)

    def fail(self, reason):
        self.blocked = True
        try:
            row = self.record('brain_fault', reason=reason, mechanical_fault_confirmed=False,
                alternatives=['scene motion or occlusion', 'camera focus change', 'mount movement',
                              'servo or power discrepancy'])
            if self.project_id and self.service.executive:
                self.service.executive.transition(self.project_id, 'paused', reason,
                    self.service.journal, [row.id])
            if self.session:
                self.service.close_session()
        finally:
            self.session = None
            self.tracking_pending = None
            self.body.stop()
            self.message('CAL FAULT')

    def update(self, frame, target=None):
        now = self.service.clock()
        if self.blocked or now-self.last_tick < .1:
            return
        self.last_tick = now
        try:
            snapshot = self.estimator.snapshot(frame, target)
            if snapshot is None:
                if self.session or self.tracking_pending:
                    self.fail('camera frame unavailable')
                elif self.authorized:
                    self.fail('normal neck camera frame unavailable; fault unconfirmed')
                return
            if self.session:
                self.calibrate(snapshot)
            elif self.requested or self.supervised and not self.automatic_attempted and self.service.requests():
                self.begin(snapshot)
            elif self.authorized:
                self.track(snapshot, target)
        except Exception:
            self.fail('calibration/vision transport or evidence failure')
            raise

    def begin(self, snapshot):
        if not self.authorized or not self.supervised:
            self.message('CAL READY')
            return
        status = self.body.motion_status()
        cal = (status or {}).get('calibration', {})
        if not status or cal.get('state') == 'DISABLED':
            self.message('CAL CONFIG REQUIRED')
            return
        if self.tracking_pending or status.get('moving'):
            return
        if status.get('task') == 'PRIMARY':
            self.message('CAL WAIT PRIMARY')
            return
        if status.get('armed'):
            profile = self.service.refresh()
            if profile is None or profile['calibration_id'] != (status.get('envelope') or {}).get('calibration_id'):
                self.fail('Pi/Pico qualified profile mismatch before calibration')
                return
        rid = self.service.request('uncertain', dict(reason='brain requested supervised neck observations'))
        if self.service.executive is not None:
            selected = self.service.executive.select(methods=['supervised_neck_recalibration'],
                resources=['physical_authorization', 'supervision', 'electrical_clearance']
                    if status.get('electrical_gate_cleared') else ['physical_authorization', 'supervision'],
                authorized_methods=['supervised_neck_recalibration'])
            project = selected['project']
            if project is None or project['scope'].get('request_id') not in self.service.requests():
                self.message('CAL WAIT EXECUTIVE')
                return
            self.project_id = project['id']
            rid = project['scope']['request_id']
        self.run = 'brain_' + uuid.uuid4().hex[:20]
        directory = self.service.repository.directory.parent / 'sessions'
        self.session = self.service.supervised_session(rid, directory/(self.run+'.jsonl'),
                                                       simulated=self.simulated)
        self.session.evidence.append(dict(kind='brain_provenance', **self.provenance(),
            reused_commissioning=cal.get('constraints'), prior_profile=status.get('envelope'),
            authorization_scope='supervised calibration', operator=self.operator))
        self.session.request(dict(op='begin', mode='brain', run_id=self.run,
            supervised=True, operator=self.operator, evidence=self.run))
        self.requested = False
        self.automatic_attempted = True
        self.path, self.responses, self.boundaries = [], [], []
        self.direction = self.step = 0
        self.phase = 'axes'
        self.grid = []
        self.return_to_home = False
        self.commissioning = cal['constraints']
        self.generated_candidate = None
        self.confirmed_start = False
        self.before = snapshot
        self.start_pose = [status['pan'], status['tilt']] if status.get('armed') else None
        self.record('brain_session_started', prior_profile_id=(status.get('envelope') or {}).get('calibration_id'),
                    source_frame_sha256=snapshot['sha256'])
        observations = self.service.repository.directory.parent/'observations'
        if observations.exists():
            for path in sorted(observations.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
                previous = json.loads(path.read_text())
                if (previous.get('commissioning') == self.commissioning
                        and previous.get('simulated') == self.simulated):
                    self.record('brain_resume_bookmark', previous_run=previous['run_id'],
                        source=str(path), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        prior_progress=previous.get('bookmark'), pending_permission_restored=False)
                    if previous.get('bookmark', {}).get('phase') in ('grid', 'boundary'):
                        # A repeated capability call advances from initial
                        # combined-axis coverage to bounded ray exploration.
                        # Old observations never become a motion grant.
                        self.phase = 'boundary'
                        self.direction = min(3, previous.get('bookmark', {}).get('direction', 0)) if previous['bookmark']['phase'] == 'boundary' else 0
                    break
        self.calibrate(snapshot)

    def calibrate(self, snapshot):
        status = self.session.poll()
        state = status['state']
        self.last_state = state
        if state in ('ABORTED', 'DISABLED'):
            self.fail('RP2040 calibration ' + state)
            return
        if state == 'VERIFY_INITIAL':
            review = status['constraints'].get('powered_start_review') or {}
            self.message('START ' + str(review.get('pose', '?')) + ' CONFIRM V')
            if self.confirmed_start:
                pose = review.get('pose')
                if pose is None:
                    self.message('START POSE UNVERIFIED')
                    self.confirmed_start = False
                    return
                self.session.request(dict(op='verify', run_id=self.run, pose=pose,
                    operator=self.operator, evidence=self.run, pose_verified=True, supervised=True))
                self.start_pose = list(pose)
                self.confirmed_start = False
            return
        if state == 'PREPARED':
            self.message('WAIT GP10 ' + str(status.get('direction', '')))
            self.before = snapshot  # Fresh frame immediately before movement.
            return
        if state == 'MOVING':
            self.message('MOVING')
            return
        if state == 'AWAIT_CONFIRMATION':
            self.message('OBSERVING')
            result = self.estimator.compare(self.before, snapshot)
            result['frames'] = [self.preserve_frame(self.before), self.preserve_frame(snapshot)]
            # Keep raw flow evidence, but report displacement in the reviewed
            # profile's reference pixels, just as normal health monitoring does.
            raw_delta = result.get('displacement', [0, 0])
            size = snapshot['size']
            reference = status['constraints']['observation_size']
            result['raw_displacement'] = list(raw_delta)
            result['reference_size'] = list(reference)
            result['displacement'] = [v*r/s for v, r, s in zip(raw_delta, reference, size)]
            delta = result.get('displacement', [0, 0])
            if not result.get('reliable') or not .0025 <= sum(v*v for v in delta) <= 40000:
                self.fail('uncertain or unsuccessful camera response; no automatic retry')
                return
            if self.start_pose is None or self.pending is None:
                self.fail('movement has no brain proposal')
                return
            previous, target, returning = self.pending
            axis = 0 if abs(target[0]-previous[0]) > 1e-8 else 1
            angular = target[axis]-previous[axis]
            samples = [r['per_degree'] for r in self.responses if r['axis'] == axis]
            vector = [v/angular for v in delta]
            if samples:
                import numpy as np
                predicted = np.median(samples, axis=0)
                if np.linalg.norm(np.asarray(vector)-predicted) > max(1, np.linalg.norm(predicted)*.75):
                    self.fail('contradictory camera response; no obstruction retry')
                    return
            self.session.request(dict(op='confirm', run_id=self.run,
                step_id=status['prepared_step'], visual_displacement=delta, camera_evidence=result))
            self.responses.append(dict(axis=axis, per_degree=vector, previous_pose=previous,
                                       commanded_pose=target, evidence=result))
            if returning:
                self.path.pop()
            else:
                self.path.append((previous, target))
                if self.phase == 'axes':
                    self.direction += 1
                elif self.grid:
                    self.grid.pop(0)
            self.pending = None
            self.before = snapshot
            self.persist()
            return
        if state == 'READY':
            if self.pending is not None:
                # RP2040 returned READY without confirmation: GP10 was withheld.
                previous, target, _ = self.pending
                self.boundaries.append(dict(direction=self.direction, pose=target,
                    status='PROVISIONAL_OPERATOR_BOUNDARY', mechanical_hard_stop=False,
                    permission_observation=status.get('last_boundary')))
                self.record('brain_boundary', boundary=self.boundaries[-1])
                self.pending = None
                if self.phase == 'grid':
                    self.grid = []
                self.persist()
                self.message('LIMIT SET')
                self.direction += 1
                self.return_to_home = True
            if not status.get('jumper_released'):
                # Withheld permission resets the debouncer. Wait for actual
                # scheduler ticks rather than relying on UART latency.
                return
            if self.path and (self.phase == 'axes' or self.return_to_home or self.step >= self.maximum_steps or
                              self.boundaries and self.boundaries[-1]['direction'] == self.direction-1):
                previous, target = self.path[-1]
                self.prepare(snapshot, target, previous, returning=True, constraints=status['constraints'])
                return
            if not self.path:
                self.return_to_home = False
            if self.step >= self.maximum_steps:
                self.finish()
                return
            telemetry = self.body.motion_status()
            if not telemetry:
                self.fail('neck telemetry unavailable')
                return
            pose = [telemetry['pan'], telemetry['tilt']] if telemetry.get('armed') else list(self.start_pose)
            if self.direction >= 4:
                if self.phase == 'boundary':
                    self.finish()
                    return
                if self.phase == 'axes':
                    self.phase = 'grid'
                    d = min(.5, status['constraints']['max_step'])
                    p, t = self.start_pose
                    self.grid = [[p+d, t], [p+d, t-d], [p, t-d], [p-d, t-d],
                        [p-d, t], [p-d, t+d], [p, t+d], [p+d, t+d], [p+d, t], [p, t]]
                    if self.boundaries:
                        self.grid = []  # Withheld boundary never becomes a safe corner.
                if not self.grid:
                    self.finish()
                    return
                target = self.grid[0]
                from rp2040.motion_geometry import contains
                constraints = status['constraints']
                if not contains(constraints['clearance_polygon'], target, constraints['commissioning_margin']):
                    self.record('combined_grid_blocked', requested_pose=target, reason='hard safety constraint')
                    self.grid = []
                    self.finish()
                    return
                self.prepare(snapshot, pose, target, returning=False, constraints=constraints)
                return
            axis, sign = ((0, 1), (0, -1), (1, 1), (1, -1))[self.direction]
            target = list(pose)
            target[axis] += sign*min(.5, status['constraints']['max_step'])
            from rp2040.motion_geometry import contains
            constraints = status['constraints']
            if (not constraints[('pan','tilt')[axis]]['min'] <= target[axis] <= constraints[('pan','tilt')[axis]]['max']
                    or not contains(constraints['clearance_polygon'], target, constraints['commissioning_margin'])):
                self.boundaries.append(dict(direction=self.direction, pose=target,
                    status='HARD_CONSTRAINT', mechanical_hard_stop=False))
                self.direction += 1
                self.return_to_home = True
                self.persist()
                return
            if self.phase == 'boundary' and self.step+len(self.path)+2 > self.maximum_steps:
                # Reserve the whole supported retreat before extending a ray.
                self.return_to_home = True
                self.maximum_steps = self.step+len(self.path)
                return
            self.prepare(snapshot, pose, target, returning=False, constraints=constraints)

    def prepare(self, snapshot, previous, target, *, returning, constraints):
        self.step += 1
        self.before = snapshot
        self.pending = (list(previous), list(target), returning)
        self.session.request(dict(op='prepare', run_id=self.run,
            step_id='step_%04d' % self.step, pose=target, rate=min(1, constraints['max_rate'])))
        self.record('brain_experiment_selected', previous_pose=previous, requested_pose=target,
            objective='verify return response' if returning else 'reduce axis response and boundary uncertainty',
            source_frame_sha256=snapshot['sha256'])

    def persist(self):
        self.observation_version += 1
        document = dict(schema='charlie-neck-observations-v1', run_id=self.run,
            created_at=timestamp(), validation_status='PROVISIONAL', simulated=self.simulated,
            measured_position=None, boundaries=self.boundaries, responses=self.responses,
            commissioning=self.commissioning,
            bookmark=dict(phase=self.phase, direction=self.direction, step=self.step,
                next_goal='continue boundary and combined-axis observations after fresh startup authority'),
            evidence=str(self.session.evidence.path), supersedes=[],
            evidence_prefix_bytes=self.session.evidence.path.stat().st_size,
            evidence_prefix_sha256=hashlib.sha256(self.session.evidence.path.read_bytes()).hexdigest(),
            limitations=['visual response is not mechanical clearance', 'no interpolated region is qualified'])
        directory = self.service.repository.directory.parent / 'observations'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (self.run+'_%04d.json' % self.observation_version)
        if not path.exists():
            durable_write(path, encode(document))

    def finish(self):
        self.persist()
        self.session.request(dict(op='finish', run_id=self.run, resume_normal=True))
        evidence_path = self.session.evidence.path
        self.service.close_session(retain_qualified=True)
        self.session = None
        if self.phase == 'grid' and not self.grid and not self.boundaries:
            from .neck_calibration import derive_candidate
            try:
                candidate = derive_candidate(evidence_path, self.commissioning,
                    name=self.run+'_candidate', margin=.1)
            except ValueError as exc:
                self.record('candidate_inconclusive', reason=str(exc))
            else:
                self.service.repository.save(candidate)
                self.generated_candidate = candidate['calibration_id']
                self.record('candidate_generated', candidate_id=candidate['calibration_id'],
                    qualification_granted=False, evidence_sha256=candidate['evidence_sha256'])
        self.stationary_anchor = None
        self.stationary_pose = None
        # Prevent an unresolved qualification request from starting infinite
        # identical sessions. The Executive/user may request another session.
        self.message('CAL SAVED')
        row = self.record('brain_session_finished', qualification_granted=False,
                          candidate_id=self.generated_candidate)
        if self.project_id and self.service.executive:
            self.service.executive.transition(self.project_id,
                'candidate' if self.generated_candidate else 'paused',
                'independent physical qualification remains required', self.service.journal, [row.id])

    def track(self, snapshot, target):
        status = self.body.motion_status()
        if not status:
            self.fail('normal neck telemetry unavailable; fault unconfirmed')
            self.message('BRAIN LINK LOST')
            return
        profile = self.service.refresh()
        if not status.get('armed'):
            review = (profile or {}).get('powered_start_review') or {}
            if (not profile or not review or not status.get('neck_health_required')
                    or status.get('profile_invalid') or not status.get('electrical_gate_cleared')):
                self.message('START POSE UNVERIFIED' if profile else 'CAL PROFILE REQUIRED')
                return
            self.startup_waiting = True
            self.message('START ' + str(review.get('pose', '?')) + ' CONFIRM V')
            if self.confirmed_start:
                self.confirmed_start = self.startup_waiting = False
                evidence = 'startup_' + uuid.uuid4().hex[:20]
                self.record('powered_start_confirmation', operator=self.operator,
                    evidence=evidence, commanded_pose=review['pose'], measured_position=None)
                if not self.body.start_reviewed_powered_pose(review['pose'], operator=self.operator, evidence=evidence):
                    self.fail('reviewed normal startup rejected')
            return
        envelope = status.get('envelope') or {}
        if profile is None or envelope.get('calibration_id') != profile['calibration_id']:
            self.body.stop()
            self.message('CAL PROFILE REQUIRED')
            return
        if status.get('profile_invalid') or any(type(status.get(k)) not in (int, float)
                or not math.isfinite(status[k]) for k in ('pan', 'tilt')):
            self.service.health.unsafe('invalid normal neck telemetry')
            self.blocked = True
            return
        if self.tracking_pending:
            if status.get('moving'):
                return
            before, previous, requested = self.tracking_pending
            result = self.estimator.compare(before, snapshot)
            result['frames'] = [self.preserve_frame(before), self.preserve_frame(snapshot)]
            if not result.get('reliable'):
                self.service.health.unsafe('normal movement camera evidence unavailable')
                self.blocked = True
                return
            w, h = snapshot['size']
            corners = [[0, 0], [w, 0], [w, h], [0, h]]
            # Response model is recorded in profile pixel coordinates.
            pw, ph = profile['observation_size']
            dx, dy = result['displacement']
            old = [[x*pw/w, y*ph/h] for x, y in corners]
            moved = [[x+dx*pw/w, y+dy*ph/h] for x, y in old]
            self.service.health.prepare(previous, requested, old)
            self.service.health.observe(moved, telemetry=status)
            self.record('normal_camera_response', camera_evidence=result,
                        requested_pose=requested, physical_position_measured=False)
            self.tracking_pending = None
            self.stationary_anchor = snapshot
            self.stationary_pose = [status['pan'], status['tilt']]
            if self.service.health.quarantined:
                self.blocked = True
            return
        if status.get('moving') or status.get('owner') not in (None, 'ACTIVE_VISION'):
            self.service.health.unsafe('unexpected motion or owner in normal brain')
            self.blocked = True
            return
        pose = [status['pan'], status['tilt']]
        if self.stationary_pose is not None and any(abs(a-b) > .05 for a,b in zip(pose, self.stationary_pose)):
            self.service.health.unsafe('unexpected commanded pose change')
            self.blocked = True
            return
        if self.stationary_anchor is not None:
            result = self.estimator.compare(self.stationary_anchor, snapshot)
            self.unobserved = 0 if result.get('reliable') else self.unobserved+1
            if self.unobserved >= self.service.health.persistence:
                self.service.health.unsafe('background neck observation unavailable; fault unconfirmed')
                self.blocked = True
                return
            if result.get('reliable'):
                dx, dy = result['displacement']
                w, h = snapshot['size']; pw, ph = profile['observation_size']
                corners = [[dx*pw/w, dy*ph/h], [pw+dx*pw/w, dy*ph/h],
                           [pw+dx*pw/w, ph+dy*ph/h], [dx*pw/w, ph+dy*ph/h]]
                self.service.health.observe(corners, telemetry=status)
                if self.service.health.quarantined:
                    self.blocked = True
                    return
        else:
            self.stationary_anchor = snapshot
            self.stationary_pose = pose
            w, h = profile['observation_size']
            self.service.health.previous = [[0, 0], [w, 0], [w, h], [0, h]]
        w, h = snapshot['size']
        searching = target is None
        if target is not None:
            self.last_target_at = self.service.clock()
            self.search_remaining = 0
        elif self.last_target_at is not None and self.service.clock()-self.last_target_at > .5:
            self.last_target_at = None
            self.request_search()
        if searching and not self.search_remaining:
            return
        error = [float(target['x'])-w/2, float(target['y'])-h/2] if target is not None else [0, 0]
        # Digital framing can translate at most 15% of either frame dimension.
        correction = [max(-limit, min(limit, v)) for limit, v in zip((w*.15, h*.15), error)]
        residual = [v-c for v, c in zip(error, correction)]
        self.digital = dict(correction=correction, residual=residual)
        if not searching and max(abs(residual[0])/w, abs(residual[1])/h) < .03:
            return
        import numpy as np
        model = profile['visual_response']
        matrix = np.column_stack((model['pan'], model['tilt'])).astype(float)
        if abs(np.linalg.det(matrix)) < .0025:
            self.service.health.unsafe('ambiguous calibrated pan/tilt response')
            self.blocked = True
            return
        pw, ph = profile['observation_size']
        angular = np.linalg.solve(matrix, -np.asarray(residual)*[pw/w, ph/h])
        if searching:
            angular = np.asarray([self.search_sign*.5, 0])
        # Single bounded increment, followed by observation before any next one.
        axis = int(np.argmax(abs(angular)))
        delta = max(-min(.5, envelope['max_step']), min(min(.5, envelope['max_step']), angular[axis]))
        previous = [status['pan'], status['tilt']]
        requested = list(previous); requested[axis] += float(delta)
        from rp2040.motion_geometry import contains
        if (not profile[('pan','tilt')[axis]]['min'] <= requested[axis] <= profile[('pan','tilt')[axis]]['max']
                or not contains(profile['clearance_polygon'], requested, profile['clearance_margin'])):
            # Plan a shorter feasible increment; the RP2040 still independently
            # rejects an out-of-envelope request. Never clamp a firmware target.
            lo, hi = 0., 1.
            for _ in range(16):
                fraction = (lo+hi)/2
                proposal = list(previous); proposal[axis] += float(delta)*fraction
                if (profile[('pan','tilt')[axis]]['min'] <= proposal[axis] <= profile[('pan','tilt')[axis]]['max']
                        and contains(profile['clearance_polygon'], proposal, profile['clearance_margin'])):
                    lo = fraction
                else:
                    hi = fraction
            if abs(delta*lo) < .05:
                self.message('VIEW LIMIT')
                if searching:
                    self.search_sign *= -1
                    self.search_remaining -= 1
                return
            requested[axis] = previous[axis] + float(delta)*lo*.9
        transition = 'DEGRADATION' if status.get('task') == 'PRIMARY' else 'INITIAL'
        if not self.body.request_active_vision(transition):
            return
        self.record('bounded_viewfinding' if searching else 'offscale_camera_correction', digital=self.digital,
                    source_frame_sha256=snapshot['sha256'], requested_pose=requested)
        if not self.body.look(*requested, rate=min(1, envelope['max_rate'])):
            self.fail('physical correction rejected')
            return
        self.tracking_pending = (snapshot, previous, requested)
        if searching:
            self.search_remaining -= 1
        self.message('VIEWFINDING' if searching else 'TRACKING')

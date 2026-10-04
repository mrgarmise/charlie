"""CAL-1 intent/state/evidence. All PWM remains owned by ServoController.

Shipped commissioning profile is absent. GPIO is not an emergency stop.
"""
from servos import MotionError, Envelope, number, token
from motion_geometry import polygon, contains


class JumperEvents:
    """Stable HIGH -> stable LOW -> stable HIGH produces one event on release."""
    def __init__(self, clock, diff, debounce=60):
        self.clock, self.diff, self.debounce = clock, diff, debounce
        self.reset()

    def reset(self):
        self.raw = self.stable = None
        self.since = self.clock()
        self.ready = self.pressed = False

    def update(self, contact):
        contact = bool(contact)
        now = self.clock()
        if contact != self.raw:
            self.raw, self.since = contact, now
        if self.diff(now, self.since) < self.debounce or contact == self.stable:
            return False
        self.stable = contact
        if not contact:
            event = self.ready and self.pressed
            self.ready, self.pressed = True, False
            return event
        if self.ready: self.pressed = True
        return False

    def released(self):
        return self.stable is False and self.raw is False and not self.pressed


class CommissioningEnvelope(Envelope):
    """Reviewed provisional commissioning constraints, not a calibrated profile."""
    def __init__(self, profile):
        self.powered_start_review = profile.get('powered_start_review') if isinstance(profile, dict) else None
        if not isinstance(profile, dict) or profile.get('commissioning_reviewed') is not True:
            raise MotionError('COMMISSIONING_REVIEW_REQUIRED')
        adjusted = dict(profile)
        adjusted['assembled_head_verified'] = True  # Reuse numeric validator only.
        self.region = None
        self.margin = number(profile.get('commissioning_margin'))
        super().__init__(adjusted)
        try: self.region = polygon(profile.get('clearance_polygon'))
        except (ValueError, TypeError, OverflowError) as exc: raise MotionError(str(exc))
        self.margin = number(profile.get('commissioning_margin'))
        if not 0 < self.margin <= 2 or self.step > 1 or self.rate > 2:
            raise MotionError('COMMISSIONING_LIMITS_REQUIRED')
        self.pose(self.arm_pose); self.pose(self.home_pose)
        if (not isinstance(self.observation_size,list) or len(self.observation_size)!=2
                or any(type(v) is not int or not 16<=v<=10000 for v in self.observation_size)):
            raise MotionError('VISUAL_REFERENCE_SIZE_REQUIRED')

    def pose(self, values):
        result = super().pose(values)
        if self.region is not None and not contains(self.region, result, self.margin):
            raise MotionError('UNSAFE_AXIS_COMBINATION')
        return result

    def describe(self):
        result = super().describe()
        result.update(clearance_polygon=self.region, commissioning_margin=self.margin,
                      provisional=True, powered_start_review=self.powered_start_review)
        for axis, name in enumerate(('pan', 'tilt')):
            result[name].update(min_us=self.axes[axis][2], max_us=self.axes[axis][3])
        return result


class Calibration:
    DISABLED='DISABLED'; READY='READY'; VERIFY='VERIFY_INITIAL'; PREPARED='PREPARED'
    MOVING='MOVING'; CONFIRM='AWAIT_CONFIRMATION'; CLOSED='CLOSED'; ABORTED='ABORTED'

    def __init__(self, authority, profile, contact_input, sink=None):
        self.a, self.input, self.sink = authority, contact_input, sink
        self.envelope = CommissioningEnvelope(profile) if profile is not None else None
        self.jumper = JumperEvents(authority._clock, authority._diff)
        self.state = self.DISABLED if self.envelope is None or contact_input is None else self.READY
        self.events = []; self.run_id = None; self.pending = None; self.deadline = None
        self.initial = None; self.expected_epoch = None
        self.used_steps = set()
        self._contact_permit = self._movement_permit = False
        self.automated = False
        self.supervisor = None
        self.permission_wait_ms = 10000
        self.return_path = []
        self.last_boundary = None

    def qualified_path(self, start, target):
        """Independent convex envelope and identical pulse mapping, never a belief."""
        envelope = self.a.envelope
        if envelope is None or not envelope.qualified or self.a._profile_invalid:
            return False
        try:
            envelope.pose(start); envelope.pose(target)
            for axis in (0, 1):
                for pose in (start, target):
                    if abs(envelope.pulse(axis, pose[axis]) - self.envelope.pulse(axis, pose[axis])) > .01:
                        return False
            return True
        except MotionError:
            return False

    def powered_start(self, data):
        # A live pose confirmation does not prove that a powered initial pulse
        # is safe. That prerequisite belongs to the reviewed deployment profile.
        review = self.envelope.powered_start_review
        pose = self.envelope.pose(data.get('pose'))
        if (not review or review.get('powered_initialization_verified') is not True
                or review.get('reviewer') == data.get('operator')
                or not review.get('reviewer') or not review.get('evidence')
                or list(pose) != review.get('pose')):
            raise MotionError('POWERED_START_REVIEW_REQUIRED')
        proof = self.attest(data, ('pose_verified', 'supervised'))
        self.initial = pose
        return proof

    def event(self, kind, **details):
        if len(self.events) >= 192:
            self.state = self.ABORTED
            self.a.stop('CAL_EVIDENCE_FULL')
            raise MotionError('CAL_EVIDENCE_FULL')
        record = dict(seq=len(self.events)+1, kind=kind, run_id=self.run_id,
                      state=self.state, at_ms=self.a._clock(), session=self.a._session,
                      epoch=self.a._epoch, commanded_pose=list(self.a._positions),
                      pose_source='commanded_estimate', measured_position=None, **details)
        self.events.append(record)
        if self.sink is not None:
            try: self.sink(record)
            except Exception:
                self.state = self.ABORTED
                self.a.stop('CAL_EVIDENCE_FAILURE')
                raise MotionError('CAL_EVIDENCE_FAILURE')
        return record

    def interrupted(self, reason):
        if self.state in (self.VERIFY,self.READY,self.PREPARED,self.MOVING,self.CONFIRM) and self.run_id:
            self.state = self.ABORTED
            self.pending = self.initial = self.deadline = None
            self._contact_permit = self._movement_permit = False
            self.jumper.reset()
            self.event('interruption', reason=reason)

    def check(self, session, epoch, current_run=True):
        self.a.expire()
        if (session != self.a._session or type(epoch) is not int or epoch != self.a._epoch
                or current_run and self.run_id and epoch != self.expected_epoch):
            raise MotionError('STALE_SESSION_OR_EPOCH')
        if self.envelope is None or self.input is None or not self.a._electrical:
            raise MotionError('CALIBRATION_PREREQUISITES_REQUIRED')
        if self.a._diff(self.a._clock(),self.a._last_contact) >= 10000:
            raise MotionError('LIVE_SESSION_REQUIRED')

    def attest(self, value, flags):
        if not isinstance(value, dict) or any(value.get(k) is not True for k in flags):
            raise MotionError('OPERATOR_CONFIRMATION_REQUIRED')
        return dict(operator=token(value.get('operator')), evidence=token(value.get('evidence')),
                    **{k:True for k in flags})

    def request(self, session, epoch, data):
        if not isinstance(data, dict): raise MotionError('INVALID_CAL_REQUEST')
        op = data.get('op')
        if op == 'begin':
            self.check(session,epoch,current_run=False)
            automated = data.get('mode') == 'brain'
            supervision = self.attest(data, ('supervised',)) if automated else None
            reuse = (automated and self.a._armed and self.a._owner in (None, 'ACTIVE_VISION')
                     and not self.a.moving() and self.qualified_path(self.a._positions, self.a._positions))
            if self.state not in (self.READY,self.CLOSED,self.ABORTED) or self.a._armed and not reuse or self.a._task=='PRIMARY':
                raise MotionError('CALIBRATION_OWNER_CONFLICT')
            next_run = token(data.get('run_id'))
            if self.run_id == next_run:
                raise MotionError('FRESH_CAL_RUN_REQUIRED')
            # Host acknowledges a durably archived terminal run. Keep each
            # installed session bounded without requiring a firmware reinstall
            # or throwing away evidence that has not been acknowledged.
            if (self.state in (self.CLOSED,self.ABORTED) and self.events
                    and data.get('archived_run_id') == self.run_id and self.sink is not None):
                self.events = []
            if len(self.events) > 160: raise MotionError('ARCHIVE_PREVIOUS_RUN_REQUIRED')
            self.run_id = next_run
            self.automated = automated
            self.supervisor = supervision
            self.initial = self.pending = None
            self.used_steps = set()
            self.return_path = []
            self.last_boundary = None
            self.expected_epoch = epoch
            self.state = self.VERIFY
            self.deadline = self.a._clock()
            self.jumper.reset()
            self.event('begin', constraints=self.envelope.describe())
            if reuse:
                self.initial = tuple(self.a._positions)
                self.a._owner = self.a._task = 'CALIBRATION'
                self.state = self.READY
                self.event('qualified_start', verified_pose=list(self.initial),
                    physical_position_measured=False, source='existing_live_qualified_authority')
        else:
            self.check(session,epoch)
            if data.get('run_id') != self.run_id: raise MotionError('STALE_CAL_RUN')
            if op == 'verify':
                if self.state != self.VERIFY: raise MotionError('VERIFY_INITIAL_REQUIRED')
                if self.automated:
                    proof = self.powered_start(data)
                    pose = self.initial
                else:
                    proof = self.attest(data, ('pose_verified','pulse_mapping_verified','clearance_verified',
                                              'cutoff_verified','external_power_off'))
                    pose = self.envelope.pose(data.get('pose'))
                # The mapping at this pose must be independently checked while
                # disconnected/unpowered, not inferred from VIEWPOINT estimates.
                self.initial = pose
                self.state = self.READY
                self.deadline = self.a._clock()
                self.event('initial_verified', verified_pose=list(pose), operator_confirmation=proof)
            elif op == 'prepare':
                if self.state != self.READY or self.initial is None or not self.jumper.released() or self.read_input():
                    raise MotionError('VERIFIED_POSE_AND_RELEASED_JUMPER_REQUIRED')
                if self.a._diff(self.a._clock(), self.deadline) > 30000:
                    self.a.stop('CAL_CONFIRMATION_EXPIRED'); raise MotionError('CAL_CONFIRMATION_EXPIRED')
                proof = self.supervisor if self.automated else self.attest(data, ('clearance_verified','cutoff_verified','supervised'))
                target = self.envelope.pose(data.get('pose'))
                current = self.initial if not self.a._armed else tuple(self.a._positions)
                delta = [b-a for a,b in zip(current,target)]
                if sum(abs(v)>1e-8 for v in delta) != 1 or sum(abs(v) for v in delta)>self.envelope.step+1e-8:
                    raise MotionError('SINGLE_INCREMENT_REQUIRED')
                rate = number(data.get('rate'))
                if not 0 < rate <= self.envelope.rate: raise MotionError('RATE_OUTSIDE_CALIBRATION')
                step_id = token(data.get('step_id'))
                if step_id in self.used_steps: raise MotionError('REPEATED_STEP')
                self.used_steps.add(step_id)
                self.pending = dict(step_id=step_id, pose=target, rate=rate,
                                    direction=('pan' if abs(delta[0])>1e-8 else 'tilt')+('+' if sum(delta)>0 else '-'))
                self.pending['permission_required'] = not (self.automated and self.a._armed and self.qualified_path(current, target))
                returning = (self.automated and self.a._armed and self.return_path
                             and all(abs(a-b) <= 1e-5 for a,b in zip(current, self.return_path[-1][1]))
                             and all(abs(a-b) <= 1e-5 for a,b in zip(target, self.return_path[-1][0])))
                self.pending['returning'] = bool(returning)
                self.pending['previous_pose'] = tuple(current)
                if returning:
                    self.pending['permission_required'] = False
                self.state = self.PREPARED
                self.deadline = self.a._clock()
                self.event('prepared', requested_pose=list(target), direction=self.pending['direction'],
                           step_id=self.pending['step_id'], operator_confirmation=proof)
                if not self.pending['permission_required']:
                    self.start_movement('supervised_return_path' if returning else 'qualified_path')
            elif op == 'withhold':
                if not self.automated or self.state != self.PREPARED:
                    raise MotionError('PREPARED_BOUNDARY_REQUIRED')
                self.withhold('declined_command')
            elif op == 'confirm':
                if self.state != self.CONFIRM or data.get('step_id') != self.pending['step_id']:
                    raise MotionError('COMPLETED_STEP_CONFIRMATION_REQUIRED')
                proof = None if self.automated else self.attest(data, ('clearance_verified','no_binding','settled','supervised'))
                displacement = data.get('visual_displacement')
                if not isinstance(displacement,(list,tuple)) or len(displacement)!=2:
                    raise MotionError('VISUAL_DISPLACEMENT_REQUIRED')
                displacement = [number(v) for v in displacement]
                if self.automated:
                    camera = data.get('camera_evidence')
                    if (not isinstance(camera, dict) or camera.get('reliable') is not True
                            or not isinstance(camera.get('before_sha256'), str)
                            or len(camera['before_sha256']) != 64
                            or not isinstance(camera.get('after_sha256'), str)
                            or len(camera['after_sha256']) != 64
                            or not .0025 <= sum(v*v for v in displacement) <= 40000):
                        raise MotionError('RELIABLE_CAMERA_RESPONSE_REQUIRED')
                    self.event('camera_confirmed', step_id=self.pending['step_id'],
                        requested_pose=list(self.pending['pose']), direction=self.pending['direction'],
                        visual_displacement=displacement, camera_evidence=camera,
                        boundary_supervision=self.supervisor, validation_status='PROVISIONAL')
                    if self.pending['returning']:
                        self.return_path.pop()
                    else:
                        self.return_path.append((self.pending['previous_pose'], tuple(self.pending['pose'])))
                else:
                    self.event('confirmed', step_id=self.pending['step_id'], requested_pose=list(self.pending['pose']),
                               direction=self.pending['direction'], visual_displacement=displacement,
                               operator_confirmation=proof)
                self.pending = None; self.state = self.READY; self.deadline = self.a._clock()
            elif op == 'finish':
                if self.state != self.READY or self.initial is None: raise MotionError('UNCONFIRMED_STEP')
                retain = (self.automated and data.get('resume_normal') is True and self.a._armed
                          and self.qualified_path(self.a._positions, self.a._positions))
                self.event('finished')
                self.state = self.CLOSED
                if retain:
                    self.a._owner = self.a._task = None
                    self.event('normal_resumed', qualified_profile=self.a.envelope.identifier)
                else:
                    self.a.stop('CAL_FINISHED')
            else: raise MotionError('UNKNOWN_CAL_OPERATION')
        self.a.contact()
        return self.status()

    def status(self):
        return dict(schema='charlie-cal-1', state=self.state, run_id=self.run_id,
                    epoch=self.a._epoch, jumper_released=self.jumper.released(),
                    prepared_step=self.pending['step_id'] if self.pending else None,
                    event_count=len(self.events), physical_position_measured=False,
                    automated=self.automated,
                    last_boundary=self.last_boundary,
                    permission_required=bool(self.pending and self.pending.get('permission_required', True)),
                    direction=self.pending['direction'] if self.pending else None,
                    constraints=self.envelope.describe() if self.envelope else None)

    def withhold(self, reason='permission_timeout'):
        self.last_boundary = dict(reason=reason, permission_received=False,
            operator_intent='unconfirmed' if reason == 'permission_timeout' else 'declined',
            mechanical_hard_stop=False)
        self.event('permission_withheld', step_id=self.pending['step_id'],
            requested_pose=list(self.pending['pose']), direction=self.pending['direction'],
            validation_status='PROVISIONAL_OPERATOR_BOUNDARY', **self.last_boundary)
        self.pending = None
        self._contact_permit = self._movement_permit = False
        self.state = self.READY
        self.deadline = self.a._clock()
        self.jumper.reset()

    def start_movement(self, source):
        self.event('movement_authority', step_id=self.pending['step_id'], source=source)
        self._contact_permit = True
        self.a._calibration_activate(self.initial, self.envelope)
        self.expected_epoch = self.a._epoch
        self.state = self.MOVING
        self._movement_permit = True
        self.a._calibration_move(self.pending['pose'], self.pending['rate'])
        self.event('movement_started', step_id=self.pending['step_id'],
                   requested_pose=list(self.pending['pose']), direction=self.pending['direction'])

    def update(self):
        if self.input is None: return
        event = self.jumper.update(self.read_input())
        self._update_event(event)

    def read_input(self):
        try: return self.input()
        except Exception:
            self.a.stop('CAL_INPUT_FAILED'); raise MotionError('CAL_INPUT_FAILED')

    def _update_event(self,event):
        if (self.automated and self.state == self.PREPARED and self.pending['permission_required']
                and self.a._diff(self.a._clock(), self.deadline) > self.permission_wait_ms):
            self.withhold()
            return
        if self.state in (self.VERIFY,self.READY,self.PREPARED,self.MOVING,self.CONFIRM) and self.run_id and self.deadline is not None:
            if self.a._diff(self.a._clock(),self.deadline) > 30000:
                self.a.stop('CAL_STAGE_TIMEOUT'); return
        if event:
            if self.state != self.PREPARED:
                if self.run_id: self.event('ignored_contact', reason='NO_PREPARED_STEP')
                return
            if self.expected_epoch != self.a._epoch or self.a.expire():
                self.a.stop('CAL_STALE_CONTACT'); return
            self.event('jumper_permit', step_id=self.pending['step_id'])
            self.start_movement('gp10')
        if self.state == self.MOVING and not self.a.moving():
            self.state = self.CONFIRM; self.deadline = self.a._clock()
            self.event('movement_completed', step_id=self.pending['step_id'],
                       requested_pose=list(self.pending['pose']), direction=self.pending['direction'])

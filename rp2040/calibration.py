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
                      provisional=True)
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
            if self.state not in (self.READY,self.CLOSED,self.ABORTED) or self.a._armed or self.a._task=='PRIMARY':
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
            self.initial = self.pending = None
            self.used_steps = set()
            self.expected_epoch = epoch
            self.state = self.VERIFY
            self.deadline = self.a._clock()
            self.jumper.reset()
            self.event('begin', constraints=self.envelope.describe())
        else:
            self.check(session,epoch)
            if data.get('run_id') != self.run_id: raise MotionError('STALE_CAL_RUN')
            if op == 'verify':
                if self.state != self.VERIFY: raise MotionError('VERIFY_INITIAL_REQUIRED')
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
                proof = self.attest(data, ('clearance_verified','cutoff_verified','supervised'))
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
                self.state = self.PREPARED
                self.deadline = self.a._clock()
                self.event('prepared', requested_pose=list(target), direction=self.pending['direction'],
                           step_id=self.pending['step_id'], operator_confirmation=proof)
            elif op == 'confirm':
                if self.state != self.CONFIRM or data.get('step_id') != self.pending['step_id']:
                    raise MotionError('COMPLETED_STEP_CONFIRMATION_REQUIRED')
                proof = self.attest(data, ('clearance_verified','no_binding','settled','supervised'))
                displacement = data.get('visual_displacement')
                if not isinstance(displacement,(list,tuple)) or len(displacement)!=2:
                    raise MotionError('VISUAL_DISPLACEMENT_REQUIRED')
                displacement = [number(v) for v in displacement]
                self.event('confirmed', step_id=self.pending['step_id'], requested_pose=list(self.pending['pose']),
                           direction=self.pending['direction'], visual_displacement=displacement,
                           operator_confirmation=proof)
                self.pending = None; self.state = self.READY; self.deadline = self.a._clock()
            elif op == 'finish':
                if self.state != self.READY or self.initial is None: raise MotionError('UNCONFIRMED_STEP')
                self.event('finished')
                self.state = self.CLOSED
                self.a.stop('CAL_FINISHED')
            else: raise MotionError('UNKNOWN_CAL_OPERATION')
        self.a.contact()
        return self.status()

    def status(self):
        return dict(schema='charlie-cal-1', state=self.state, run_id=self.run_id,
                    epoch=self.a._epoch, jumper_released=self.jumper.released(),
                    prepared_step=self.pending['step_id'] if self.pending else None,
                    event_count=len(self.events), physical_position_measured=False)

    def update(self):
        if self.input is None: return
        event = self.jumper.update(self.read_input())
        self._update_event(event)

    def read_input(self):
        try: return self.input()
        except Exception:
            self.a.stop('CAL_INPUT_FAILED'); raise MotionError('CAL_INPUT_FAILED')

    def _update_event(self,event):
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
            self._contact_permit = True
            self.a._calibration_activate(self.initial, self.envelope)
            self.expected_epoch = self.a._epoch
            self.state = self.MOVING
            self._movement_permit = True
            self.a._calibration_move(self.pending['pose'], self.pending['rate'])
            self.event('movement_started', step_id=self.pending['step_id'],
                       requested_pose=list(self.pending['pose']), direction=self.pending['direction'])
        if self.state == self.MOVING and not self.a.moving():
            self.state = self.CONFIRM; self.deadline = self.a._clock()
            self.event('movement_completed', step_id=self.pending['step_id'],
                       requested_pose=list(self.pending['pose']), direction=self.pending['direction'])

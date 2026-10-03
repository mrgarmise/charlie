"""Single RP2040 motion authority. Startup creates neither Pin nor PWM.

Only Head A (GP4/GP5) can be activated. Profiles and local interlock are firmware
inputs, never serial commands. Public Servo facades cannot write PWM directly.
Positions are commanded estimates; there are no physical position sensors.
"""
import math
import time
from config import HEARTBEAT_TIMEOUT, PWM_FREQUENCY
from motion_profile import CALIBRATED_ENVELOPE, ELECTRICAL_GATE_CLEARED
from motion_geometry import polygon, contains


class MotionError(RuntimeError):
    pass


def number(value):
    if isinstance(value, bool):
        raise MotionError('INVALID_NUMBER')
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        raise MotionError('INVALID_NUMBER')
    if not math.isfinite(value):
        raise MotionError('INVALID_NUMBER')
    return value


def token(value):
    if (not isinstance(value, str) or not 8 <= len(value) <= 64 or
            any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in value)):
        raise MotionError('INVALID_SESSION')
    return value


class Envelope:
    """Copied, validated calibration; no runtime profile replacement API."""
    def __init__(self, profile):
        if (not isinstance(profile, dict) or profile.get('assembled_head_verified') is not True
                or profile.get('pins') != [4, 5] or not profile.get('calibration_id')):
            raise MotionError('ASSEMBLED_CALIBRATION_REQUIRED')
        self.identifier = token(profile['calibration_id'])
        self.axes = []
        for name in ('pan', 'tilt'):
            axis = profile.get(name, {})
            try:
                low, high, pulse_low, pulse_high = [number(axis[k]) for k in
                    ('min', 'max', 'min_us', 'max_us')]
            except KeyError:
                raise MotionError('INCOMPLETE_CALIBRATION')
            if not (0 <= low < high <= 180 and 0 < pulse_low < pulse_high < 1000000/PWM_FREQUENCY):
                raise MotionError('INVALID_CALIBRATION')
            self.axes.append((low, high, pulse_low, pulse_high))
        try:
            self.rate = number(profile['max_rate'])
            self.step = number(profile['max_step'])
            self.arm_pose = self.pose(profile['confirmed_arm_pose'])
            self.home_pose = self.pose(profile['home_pose'])
        except KeyError:
            raise MotionError('INCOMPLETE_CALIBRATION')
        if not (0 < self.rate <= 30 and 0 < self.step <= 12):
            raise MotionError('INVALID_CALIBRATION')
        try:
            self.region = polygon(profile['clearance_polygon']) if 'clearance_polygon' in profile else None
        except (ValueError, TypeError, OverflowError) as exc:
            raise MotionError(str(exc))
        self.qualified = profile.get('validation_status') == 'QUALIFIED'
        self.visual_response = profile.get('visual_response')
        self.observation_size = profile.get('observation_size')
        if self.qualified:
            from neck_profile_schema import validate
            try: validate(profile)
            except (ValueError,TypeError,KeyError,OverflowError) as exc: raise MotionError(str(exc))
        self.pose(self.arm_pose); self.pose(self.home_pose)

    def pose(self, values):
        if not isinstance(values, (list, tuple)) or len(values) != 2:
            raise MotionError('INVALID_POSE')
        pose = tuple(number(v) for v in values)
        if any(not self.axes[i][0] <= v <= self.axes[i][1] for i, v in enumerate(pose)):
            raise MotionError('OUTSIDE_CALIBRATED_ENVELOPE')
        if getattr(self, 'region', None) is not None and not contains(self.region, pose):
            raise MotionError('UNSAFE_AXIS_COMBINATION')
        return pose

    def pulse(self, axis, angle):
        low, high, pulse_low, pulse_high = self.axes[axis]
        if not low <= number(angle) <= high:
            raise MotionError('OUTSIDE_CALIBRATED_ENVELOPE')
        return pulse_low + (angle-low)*(pulse_high-pulse_low)/(high-low)

    def describe(self):
        return dict(calibration_id=self.identifier, pins=[4,5],
            pan=dict(min=self.axes[0][0], max=self.axes[0][1]),
            tilt=dict(min=self.axes[1][0], max=self.axes[1][1]),
            max_rate=self.rate, max_step=self.step,
            clearance_polygon=self.region, independently_qualified=self.qualified,
            visual_response=self.visual_response,observation_size=self.observation_size)


class Servo:
    """Read-only compatibility facade; all mutation goes through authority."""
    def __init__(self, pin, authority=None, axis=None):
        if authority is None:
            raise MotionError('DIRECT_SERVO_CONSTRUCTION_FORBIDDEN')
        self._authority, self._axis = authority, axis
        self.pin = pin

    @property
    def pwm(self):
        # Do not expose a raw hardware object as a backdoor to duty_u16().
        return None if self._axis > 1 or not self._authority._pwms else 'AUTHORITY_OWNED'

    @property
    def position(self):
        return 90.0 if self._axis > 1 else self._authority._positions[self._axis]

    @property
    def target(self):
        return 90.0 if self._axis > 1 else self._authority._targets[self._axis]

    @property
    def velocity(self):
        return 0.0 if self._axis > 1 else self._authority._velocities[self._axis]

    def write(self, angle, **authorization):
        return self.move_to(angle, **authorization)

    def move_to(self, angle, rate=None, **authorization):
        if self._axis > 1:
            raise MotionError('HEAD_B_DISABLED')
        values = list(self._authority._positions)
        values[self._axis] = angle
        return self._authority.look(*values, rate=rate, **authorization)

    def update(self):
        raise MotionError('DIRECT_SERVO_UPDATE_FORBIDDEN')

    def stop(self):
        self._authority.stop()


class ServoController:
    """The sole actuator owner, with local physical arming and scoped control.

    There is deliberately no remote/public arm method. A debounced local input
    must be released then pressed after a live session is established. Static
    approval flags, configured envelope, and a real input are all required.
    Defaults are the shipped DISARMED profile. Factories are for hardware-free
    tests; main supplies no replacement policy or alternate controller.
    """
    def __init__(self, profile=None, *, electrical_gate=None, arm_input=None,
                 clock=None, pwm_factory=None, pin_factory=None, calibration_profile=None,
                 calibration_input=None, calibration_sink=None, autonomous_enabled=False,
                 profile_quarantine=None, profile_operation=None, force_empty_profile=False):
        selected = None if force_empty_profile else CALIBRATED_ENVELOPE if profile is None else profile
        self.envelope = Envelope(selected) if selected is not None else None
        self._electrical = ELECTRICAL_GATE_CLEARED if electrical_gate is None else electrical_gate is True
        self._input = arm_input
        self._clock = clock or getattr(time, 'ticks_ms', lambda:int(time.monotonic()*1000))
        self._diff = getattr(time, 'ticks_diff', lambda a,b:a-b)
        self._pwm_factory, self._pin_factory = pwm_factory, pin_factory
        self._positions = [90.0,90.0]
        self._targets = list(self._positions)
        self._velocities = [0.0,0.0]
        self._pwms = []
        self._armed = False
        self._session = None
        self._owner = None
        self._task = None
        self._epoch = 0
        self._released = False
        self._low_samples = self._high_samples = 0
        self._last_contact = self._last_update = self._clock()
        self._rate = 0.0
        self.last_reason = 'BOOT_DISARMED'
        self._start_confirmation = None
        self._autonomous_enabled = autonomous_enabled is True
        self._quarantine = profile_quarantine
        self._profile_operation = profile_operation
        self._normal_operation = False
        self._activation_permit = self._target_permit = False
        self._profile_invalid = False
        self.a_pan, self.a_tilt = Servo(4,self,0), Servo(5,self,1)
        self.b_pan, self.b_tilt = Servo(14,self,2), Servo(15,self,3)
        from calibration import Calibration
        self.calibration = Calibration(self, calibration_profile, calibration_input, calibration_sink)

    def status(self):
        self.expire()
        return dict(schema='charlie-motion-authority-v1', state='ARMED' if self._armed else 'DISARMED',
            armed=self._armed, owner=self._owner, task=self._task, epoch=self._epoch,
            session=self._session, pose_source='commanded_estimate', measured_position=None,
            pose_verified=False, pan=self._positions[0], tilt=self._positions[1],
            moving=self.moving(), pwm_active=bool(self._pwms), eligible_pins=[4,5],
            inactive_pins=[14,15], envelope=self.envelope.describe() if self.envelope else None,
            electrical_gate_cleared=self._electrical,
            local_arm_available=self._input is not None or self._autonomous_enabled and bool(self.envelope and self.envelope.qualified),
            profile_invalid=self._profile_invalid, calibration=self.calibration.status(),
            neck_health_required=self._autonomous_enabled,
            reason=self.last_reason)

    def moving(self):
        return self._armed and any(abs(a-b) > 1e-6 for a,b in zip(self._positions,self._targets))

    def stop(self, reason='STOP'):
        if self._normal_operation and reason not in ('STOP','IDLE','SLEEP','PRIMARY_ACQUIRED'):
            self._profile_invalid = True
        self._armed = False
        self._owner = None
        self._epoch += 1
        self._targets = list(self._positions)
        self._velocities = [0.0,0.0]
        self._released = False
        self._low_samples = self._high_samples = 0
        self._start_confirmation = None
        self._activation_permit = self._target_permit = False
        pwms, self._pwms = self._pwms, []
        self.last_reason = reason
        # Attempt to disable BOTH outputs even if one hardware operation fails.
        error = None
        for pwm in pwms:
            try:
                try:pwm.duty_u16(0)
                finally:pwm.deinit()
            except Exception as exc:error = exc
        if hasattr(self, 'calibration'): self.calibration.interrupted(reason)
        if self._normal_operation and not self._profile_invalid and reason in ('STOP','IDLE','SLEEP','PRIMARY_ACQUIRED'):
            self._profile_operation(False)
            self._normal_operation = False
        if error is not None:
            raise MotionError('PWM_DISABLE_FAILED')

    def expire(self):
        if self._diff(self._clock(), self._last_contact) >= HEARTBEAT_TIMEOUT*1000:
            if self._armed or self._owner is not None or (hasattr(self,'calibration') and
                    self.calibration.state in ('VERIFY_INITIAL','PREPARED','AWAIT_CONFIRMATION')):
                self.stop('WATCHDOG_EXPIRED')
            return True
        return False

    def contact(self):
        self.expire()  # An arriving PING cannot rescue an expired authorization.
        self._last_contact = self._clock()

    def establish_session(self, session):
        session = token(session)
        self.stop('NEW_SESSION')
        self._session, self._task = session, None
        self.contact()

    def poll_local_arm(self):
        if self._input is None:
            return
        if not self._input():
            self._low_samples += 1
            self._high_samples = 0
            if self._low_samples >= 3:self._released = True
            return
        self._low_samples = 0
        self._high_samples += 1
        if self._released and self._high_samples >= 3:
            self._released = False
            if (self._armed or self.expire() or self._session is None or
                    self.envelope is None or not self.envelope.qualified or not self._electrical or self._profile_invalid
                    or not self._valid_start_confirmation() or self.calibration.run_id is not None):
                self.last_reason = 'LOCAL_ARM_REFUSED'
                return
            # Profile records an operator-confirmed start pose, not a sensor
            # reading. Pressing the local input confirms that prerequisite.
            self._activation_permit = True
            self._activate(self._start_confirmation['pose'], self.envelope)

    def confirm_start_pose(self, session, epoch, pose, evidence):
        self.expire()
        if self._armed or self.envelope is None or self._profile_invalid:
            raise MotionError('START_VERIFICATION_REFUSED')
        if session != self._session or session is None or type(epoch) is not int or epoch != self._epoch:
            raise MotionError('STALE_SESSION_OR_EPOCH')
        proof = self.calibration.attest(evidence, ('pose_verified','pulse_mapping_verified',
                     'clearance_verified','cutoff_verified','external_power_off'))
        verified = self.envelope.pose(pose)
        self._start_confirmation = dict(pose=verified, evidence=proof, epoch=epoch,
                                         at=self._clock())
        self.contact()

    def _valid_start_confirmation(self):
        c = self._start_confirmation
        return c is not None and c['epoch']==self._epoch and self._diff(self._clock(),c['at'])<=30000

    def activate_autonomous(self, session, epoch):
        self.validate_start_scope(session,epoch)
        if not self._autonomous_enabled or not self.envelope.qualified or self._quarantine is None or self._profile_operation is None:
            raise MotionError('INDEPENDENT_QUALIFICATION_REQUIRED')
        self._profile_operation(True)
        self._normal_operation = True
        self._activation_permit = True
        self._activate(self._start_confirmation['pose'], self.envelope)

    def validate_start_scope(self, session, epoch):
        self.expire()
        if (session!=self._session or session is None or type(epoch) is not int or epoch!=self._epoch
                or self._armed or not self._electrical or self._profile_invalid
                or self.envelope is None or not self._valid_start_confirmation()
                or self.calibration.state in ('VERIFY_INITIAL','PREPARED','MOVING','AWAIT_CONFIRMATION')):
            raise MotionError('VERIFIED_START_REQUIRED')

    def _activate(self, pose, envelope):
        # Sole PWM creation site. Exact live operator-verified pose, never HOME.
        if not self._activation_permit: raise MotionError('ACTIVATION_AUTHORITY_REQUIRED')
        self._activation_permit = False
        self._positions = list(envelope.pose(pose)); self._targets = list(self._positions)
        try:
            if self._pwm_factory is None:
                from machine import Pin, PWM
                pwm_factory, pin_factory = PWM, Pin
            else: pwm_factory, pin_factory = self._pwm_factory, self._pin_factory
            for axis,pin in enumerate((4,5)):
                pwm = pwm_factory(pin_factory(pin)); self._pwms.append(pwm)
                pwm.freq(PWM_FREQUENCY)
                pwm.duty_u16(int(envelope.pulse(axis,self._positions[axis])*65535/(1000000/PWM_FREQUENCY)))
            self._armed = True; self._epoch += 1; self._last_update = self._clock()
            self._start_confirmation = None
            self.last_reason = 'VERIFIED_POSE_ACTIVATION'
        except Exception:
            self.stop('ARM_HARDWARE_FAILED'); raise MotionError('ARM_HARDWARE_FAILED')

    def _calibration_activate(self, pose, envelope):
        c = self.calibration
        if c.state!='PREPARED' or not c._contact_permit or c.initial is None or not self._electrical or self._owner not in (None,'CALIBRATION'):
            raise MotionError('CALIBRATION_PERMIT_REQUIRED')
        c._contact_permit = False
        if not self._armed:
            self._activation_permit = True
            self._activate(pose,envelope)
        self._owner = self._task = 'CALIBRATION'

    def _calibration_move(self, pose, rate):
        c = self.calibration
        if c.state!='MOVING' or not c._movement_permit or self._owner!='CALIBRATION' or tuple(pose)!=tuple(c.pending['pose']) or rate!=c.pending['rate']:
            raise MotionError('CALIBRATION_PERMIT_REQUIRED')
        c._movement_permit = False
        self._target_permit = True
        self._set_target(pose,rate,self.calibration.envelope)

    def invalidate_profile(self, reason):
        self._profile_invalid = True
        self.stop('NECK_HEALTH_UNCERTAIN')
        if self._quarantine is not None: self._quarantine(reason)

    def validate_control(self, session=None, epoch=None):
        self.expire()
        if not self._armed:
            raise MotionError('HEAD_MOTION_DISARMED')
        if (session != self._session or type(epoch) is not int or epoch != self._epoch
                or self._owner not in ('ACTIVE_VISION','LEGACY') or self._profile_invalid):
            raise MotionError('CONTROL_AUTHORIZATION_REQUIRED')

    def authorize(self, owner, session, epoch, transition):
        self.expire()
        if not self._armed:
            raise MotionError('HEAD_MOTION_DISARMED')
        if session != self._session or type(epoch) is not int or epoch != self._epoch:
            raise MotionError('STALE_SESSION_OR_EPOCH')
        if owner not in ('ACTIVE_VISION','LEGACY') or self._owner not in (None,owner) or self._profile_invalid:
            raise MotionError('OWNER_CONFLICT')
        if self._task == 'PRIMARY':
            if owner != 'ACTIVE_VISION' or transition != 'DEGRADATION':
                raise MotionError('EXPLICIT_DEGRADATION_TRANSITION_REQUIRED')
        elif transition != 'INITIAL':
            raise MotionError('INVALID_OWNERSHIP_TRANSITION')
        self._owner = self._task = owner
        self.contact()

    def primary_acquire(self, session, epoch):
        if session != self._session or type(epoch) is not int or epoch != self._epoch:
            raise MotionError('STALE_SESSION_OR_EPOCH')
        self.stop('PRIMARY_ACQUIRED')
        self._task = 'PRIMARY'
        self.contact()

    def look(self, pan, tilt, rate=None, *, session=None, epoch=None):
        self.validate_control(session,epoch)
        self._target_permit = True
        self._set_target((pan,tilt),rate,self.envelope)

    def _set_target(self, values, rate, envelope):
        if not self._target_permit: raise MotionError('TARGET_AUTHORITY_REQUIRED')
        self._target_permit = False
        target = envelope.pose(values)
        rate = envelope.rate if rate is None else number(rate)
        if not 0 < rate <= envelope.rate:
            raise MotionError('RATE_OUTSIDE_CALIBRATION')
        if sum(abs(a-b) for a,b in zip(target,self._positions)) > envelope.step+1e-6:
            raise MotionError('STEP_OUTSIDE_CALIBRATION')
        self._targets, self._rate = list(target), rate
        self.contact()

    def home(self, **authorization):
        self.validate_control(**authorization)
        self.look(*self.envelope.home_pose, **authorization)

    def head_a(self, pan, tilt, rate=None, **authorization):
        self.look(pan,tilt,rate,**authorization)

    def head_b(self, *args, **kwargs):
        raise MotionError('HEAD_B_DISABLED')

    def update(self):
        self.expire()
        self.calibration.update()
        self.poll_local_arm()
        now = self._clock()
        elapsed = min(.05,max(0,self._diff(now,self._last_update)/1000))
        self._last_update = now
        if not self._armed or self._owner is None or not self.moving():
            return
        try:
            envelope = self.calibration.envelope if self._owner=='CALIBRATION' else self.envelope
            envelope.pose(self._targets)  # Check again before any PWM write.
            error = [b-a for a,b in zip(self._positions,self._targets)]
            total = sum(abs(v) for v in error)
            factor = min(1,self._rate*elapsed/total)
            next_pose = [p+e*factor for p,e in zip(self._positions,error)]
            envelope.pose(next_pose)
            for axis,pwm in enumerate(self._pwms):
                pwm.duty_u16(int(envelope.pulse(axis,next_pose[axis])*65535/(1000000/PWM_FREQUENCY)))
            self._velocities = [e*factor/elapsed if elapsed else 0 for e in error]
            self._positions = next_pose
            if not self.moving():self._velocities = [0.0,0.0]
        except Exception:
            self.stop('ACTUATION_FAILED')
            raise MotionError('ACTUATION_FAILED')

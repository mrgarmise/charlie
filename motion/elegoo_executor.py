"""Application-owned request boundary above the existing ELEGOO controller.

An authority is an independently installed admission service, not a behavior or
registry flag. Without it no transport is opened. Command receipts are not pose.
"""
from copy import deepcopy
from dataclasses import dataclass
import threading
import os
from pathlib import Path
import time
from uuid import uuid4

from experiments.ppal.mobile_navigation import QualifiedMobileExecutor, finite, age


@dataclass(frozen=True)
class ActuatorRequest:
    id: str
    requester: str
    group: str
    action: str
    at: float
    source: str
    observation_id: str
    parameters: dict


class QualifiedElegooExecutor(QualifiedMobileExecutor):
    def __init__(self, base, *, bus, authority=None, clock=time.monotonic, fault_path=None):
        super().__init__(base, None, clock=clock)
        self.fault_path = Path(fault_path) if fault_path is not None else None
        if self.fault_path is not None and self.fault_path.exists():
            self.stop_uncertain = True
        self.bus, self.authority = bus, authority
        self.boot_id = uuid4().hex
        self._connected = False
        self._safety_stopped = False
        self._receipts = 0
        self._receipt_lock = threading.Lock()
        self._generation = uuid4().hex
        self._manual_owner = None
        self._manual_until = 0.
        bus.claim_observations('elegoo-actuator-state', self, metadata={
            'body': 'ELEGOO', 'modality': 'command-state',
            'clock': 'host-monotonic', 'physical_pose': 'unknown',
            'acquisition': 'executor receipts; not independently observed movement'})

    def _reserve_wire_attempt(self, request_id):
        # A crash after this durable marker cannot silently rearm a new process.
        # A leftover marker has no automatic clear path; independent recovery is
        # outside the executor and must preserve the original incident evidence.
        if self.fault_path is None:
            return
        self.fault_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.fault_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write(str(request_id)[:128]+'\n')
                stream.flush()
                os.fsync(stream.fileno())
            directory = os.open(self.fault_path.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        except BaseException:
            self.stop_uncertain = True
            raise

    def _complete_wire_attempt(self):
        if self.fault_path is None:
            return
        try:
            self.fault_path.unlink()
            directory = os.open(self.fault_path.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        except BaseException:
            self.stop_uncertain = True
            raise

    def attach_pet_context(self, context):
        if self.context is not None and self.context is not context:
            raise ValueError('pet safety context already attached')
        self.context = context

    def _execute_exclusive(self, proposal, *, lease, local_cancel):
        self._check_manual(None)
        if self._safety_stopped:
            raise PermissionError('emergency STOP latched')
        if self.context is None:
            raise PermissionError('pet context unavailable')
        self.context.activation()
        if not self.context.safe(proposal) or not lease.valid(self.clock(), self.context.boot_id):
            raise PermissionError('pet safety veto')
        if not self._connected:
            self.base.connect()
            self._connected = True
        result = super()._execute_exclusive(proposal, lease=lease, local_cancel=local_cancel)
        request = ActuatorRequest(proposal['id'], 'pet-follow', 'chassis', proposal['action'],
                                  proposal['at'], 'elegoo-v4', proposal['frame_id'], {})
        self._publish(request, result)
        return result

    def _publish(self, request, result):
        from stimulus.bus import Observation
        with self._receipt_lock:
            self._receipts += 1
            self.bus.publish_observation('elegoo-actuator-state', self, Observation(
                'elegoo-actuator-state', self._receipts, self.clock(),
                dict(request_id=request.id, requester=request.requester,
                     group=request.group, action=request.action, source=request.source,
                     observation_id=request.observation_id, requested_at=request.at,
                     parameters=deepcopy(request.parameters), **result),
                {'physical_outcome': 'unknown', 'boot_id': self.boot_id}, self._generation))

    def _source(self, request):
        frame = self.bus.latest_frame(request.source, max_age=.25, clock=self.clock)
        if frame is not None:
            identifier = getattr(frame, 'frame_id', getattr(frame, 'id', None))
            if identifier == request.observation_id:
                return frame
        observation = self.bus.latest_observation(request.source, max_age=.25, clock=self.clock)
        if observation is not None and request.observation_id == f'{observation.generation}:{observation.sequence}':
            return observation
        raise ValueError('fresh source-bound observation required')

    def _check_manual(self, owner):
        # Expired browser authority never silently resumes autonomous movement.
        # Release/watchdog must first finish STOP and explicitly clear ownership.
        with self._state_lock:
            if self._manual_owner is not None:
                if owner is not self._manual_owner or self.clock() >= self._manual_until:
                    raise PermissionError('manual control owns chassis')
            elif owner is not None:
                raise PermissionError('manual authority revoked')

    def claim_manual(self, owner, until):
        if owner is None or not 0 < until-self.clock() <= .5:
            raise ValueError('bounded manual owner required')
        with self._state_lock:
            if self._manual_owner is not None or self._safety_stopped or self.stop_uncertain or self._closed:
                raise PermissionError('manual control unavailable')
            self._manual_owner, self._manual_until = owner, until
        # Block autonomy before preempting any existing in-flight pulse.
        try:
            self.stop()
            if self.stop_uncertain:raise PermissionError('STOP uncertain')
        except BaseException:
            self.emergency_stop()
            raise

    def renew_manual(self, owner, until):
        with self._state_lock:
            if owner is not self._manual_owner or not self.clock() < self._manual_until or not 0 < until-self.clock() <= .5:
                raise PermissionError('manual lease expired or foreign')
            self._manual_until = until

    def release_manual(self, owner):
        with self._state_lock:
            if owner is not self._manual_owner:raise PermissionError('foreign manual owner')
            self._manual_until = 0.
        try:return self.stop()
        finally:
            with self._state_lock:self._manual_owner = None

    def request_manual(self, owner, request):
        if request.group != 'chassis' or request.requester != 'mobile-operator':
            raise PermissionError('manual chassis request required')
        return self.request(request, _manual_owner=owner)

    def request(self, request, *, _manual_owner=None):
        if not isinstance(request, ActuatorRequest):
            raise ValueError('typed actuator request required')
        # Isolate nested input from caller mutation during admission/dispatch.
        request = deepcopy(request)
        if request.action == 'stop':
            return self.stop()
        if request.group == 'chassis':self._check_manual(_manual_owner)
        if not self._request_lock.acquire(blocking=False):
            raise ValueError('another actuator request is active')
        cancel = threading.Event()
        attempted = False
        try:
            with self._state_lock:
                if (self._closed or self._safety_stopped or self.stop_uncertain or self._stop_inflight
                        or (self._stop_at is not None and request.at <= self._stop_at)):
                    raise ValueError('stopped, closed or uncertain executor')
                self._active_cancel = cancel
            if request.group == 'chassis':self._check_manual(_manual_owner)
            if (not isinstance(request.id,str) or not 1 <= len(request.id) <= 128
                    or not isinstance(request.requester,str) or not 1 <= len(request.requester) <= 128 or request.id in self.used
                    or len(self.used) >= 256 or not 0 <= age(self.clock(), request.at) <= .1):
                raise ValueError('invalid, stale or replayed actuator request')
            if (request.group, request.action) not in (('chassis', 'pulse'), ('camera-pan', 'pan')):
                raise ValueError('unsupported actuator request')
            evidence = self._source(request)
            if self.authority is None:
                raise PermissionError('independent actuator qualification unavailable')
            # Authority must independently bind device, boot, source, environment,
            # firmware and separately measured group limits on every dispatch.
            grant = self.authority.admit(request, evidence, boot_id=self.boot_id)
            lease, envelope = grant['lease'], deepcopy(grant['envelope'])
            if (grant.get('group') != request.group or not lease.valid(self.clock(), self.boot_id)
                    or grant.get('request_id') != request.id):
                raise PermissionError('unbound actuator grant')
            params = request.parameters
            if request.group == 'chassis':
                duration, pwm, direction = params.get('seconds'), params.get('pwm'), params.get('direction')
                if (not finite(duration) or not 0 < duration <= min(.2, envelope['max_duration'])
                        or type(pwm) is not int or not 0 < pwm <= min(35, envelope['max_pwm'])
                        or direction not in envelope['directions']
                        or self.clock()+duration > lease.expires_at):
                    raise ValueError('chassis envelope exceeded')
            else:
                degrees = params.get('degrees')
                if (not finite(degrees) or not max(20, envelope['min_degrees']) <= degrees <= min(160, envelope['max_degrees'])
                        or envelope.get('position_command_verified') is not True
                        or self.clock()+.05 > lease.expires_at):
                    raise ValueError('pan envelope unqualified or exceeded')
            def safe():
                try:
                    if request.group == 'chassis':self._check_manual(_manual_owner)
                except PermissionError:return False
                return (not cancel.is_set() and not self.stop_uncertain and
                        lease.valid(self.clock(), self.boot_id) and
                        self.authority.safe(request, grant) is True)
            if not safe():
                raise PermissionError('independent safety veto')
            self.used.add(request.id)
            if not self._connected:
                self.base.connect()
                self._connected = True
            if not safe():
                raise PermissionError('admission changed during connection')
            self._reserve_wire_attempt(request.id)
            attempted = True
            if request.group == 'chassis':
                result = self.base.pulse(direction, pwm=pwm, seconds=duration,
                    lease=lease, boot_id=self.boot_id, envelope=envelope, _executor=self,
                    safety_check=safe, cancel=cancel)
                if result.get('stop', {}).get('acknowledged') is not True:
                    self.stop_uncertain = True
            else:
                # Existing servo protocol and rounding; never start legacy pivot.
                angle = self.base.car.pan_qualified(degrees, safety_check=safe,
                    wire_guard=lambda:not cancel.is_set() and not self.stop_uncertain
                        and lease.valid(self.clock(),self.boot_id), _executor=self)
                result = dict(acknowledged=True, commanded_degrees=angle)
                if not safe():
                    self.stop_uncertain = True
                    raise InterruptedError('pan admission changed during execution')
            if not self.stop_uncertain:
                self._complete_wire_attempt()
            result = dict(result, executed=None, physically_observed=None)
            self._publish(request, result)
            return result
        except BaseException as exc:
            if attempted:
                self.stop_uncertain = True
                self.stop()
            self._publish(request, dict(acknowledged=False, error=type(exc).__name__,
                                       uncertain=self.stop_uncertain, physically_observed=None,
                                       wire_attempt=deepcopy(getattr(getattr(self.base,'car',None),'last_pulse',None))
                                       if isinstance(getattr(getattr(self.base,'car',None),'last_pulse',None),dict) else None))
            raise
        finally:
            with self._state_lock:
                if self._active_cancel is cancel:
                    self._active_cancel = None
            self._request_lock.release()

    def emergency_stop(self):
        # Independent safety stops revoke all requesters for this lifetime.
        with self._state_lock:
            self._safety_stopped = True
        return self.stop()

    def stop(self):
        try:
            if self._connected:
                result = super().stop()
            else:
                with self._state_lock:
                    self._stop_at = self.clock()
                    if self._active_cancel is not None:
                        self._active_cancel.set()
                result = dict(sent=False, acknowledged=False, physically_stopped=None,
                              reason='transport not opened; no physical claim')
            return result
        finally:
            # Publishing must never prevent or delay attempting STOP.
            try:
                receipt = ActuatorRequest(uuid4().hex,'stop','chassis','stop',self.clock(),'', '', {})
                self._publish(receipt,dict(acknowledged=locals().get('result',{}).get('acknowledged'),
                                           uncertain=self.stop_uncertain,physically_observed=None))
            except Exception:
                pass

    def close(self):
        try:
            super().close()
        finally:
            self.bus.release_observations('elegoo-actuator-state', self)


_application_executor = None
_application_lock = threading.Lock()


def install_application_executor(executor):
    global _application_executor
    with _application_lock:
        if _application_executor is not None:
            raise RuntimeError('application already owns an ELEGOO executor')
        _application_executor = executor


def remove_application_executor(executor):
    global _application_executor
    with _application_lock:
        if _application_executor is executor:
            _application_executor = None


def application_executor():
    if _application_executor is None:
        raise RuntimeError('application-owned ELEGOO executor unavailable')
    return _application_executor

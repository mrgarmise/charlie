"""Application-owned request boundary above the existing ELEGOO controller.

An authority is an independently installed admission service, not a behavior or
registry flag. Without it no transport is opened. Command receipts are not pose.
"""
from copy import deepcopy
from dataclasses import dataclass
import threading
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
    def __init__(self, base, *, bus, authority=None, clock=time.monotonic):
        super().__init__(base, None, clock=clock)
        self.bus, self.authority = bus, authority
        self.boot_id = uuid4().hex
        self._connected = False
        self._receipts = 0
        self._generation = uuid4().hex
        bus.claim_observations('elegoo-actuator-state', self, metadata={
            'body': 'ELEGOO', 'modality': 'command-state',
            'clock': 'host-monotonic', 'physical_pose': 'unknown',
            'acquisition': 'executor receipts; not independently observed movement'})

    def attach_pet_context(self, context):
        if self.context is not None and self.context is not context:
            raise ValueError('pet safety context already attached')
        self.context = context

    def _execute_exclusive(self, proposal, *, lease, local_cancel):
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
        self._receipts += 1
        self.bus.publish_observation('elegoo-actuator-state', self, Observation(
            'elegoo-actuator-state', self._receipts, self.clock(),
            dict(request_id=request.id, requester=request.requester,
                 group=request.group, action=request.action, **result),
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

    def request(self, request):
        if not isinstance(request, ActuatorRequest):
            raise ValueError('typed actuator request required')
        # Isolate nested input from caller mutation during admission/dispatch.
        request = deepcopy(request)
        if request.action == 'stop':
            return self.stop()
        if not self._request_lock.acquire(blocking=False):
            raise ValueError('another actuator request is active')
        cancel = threading.Event()
        attempted = False
        try:
            with self._state_lock:
                if (self._closed or self.stop_uncertain or self._stop_inflight
                        or (self._stop_at is not None and request.at <= self._stop_at)):
                    raise ValueError('stopped, closed or uncertain executor')
                self._active_cancel = cancel
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
            attempted = True
            if request.group == 'chassis':
                result = self.base.pulse(direction, pwm=pwm, seconds=duration,
                    lease=lease, boot_id=self.boot_id, envelope=envelope,
                    safety_check=safe, cancel=cancel)
                if result.get('stop', {}).get('acknowledged') is not True:
                    self.stop_uncertain = True
            else:
                # Existing servo protocol and rounding; never start legacy pivot.
                angle = self.base.car.pan_qualified(degrees, safety_check=safe)
                result = dict(acknowledged=True, commanded_degrees=angle)
                if not safe():
                    self.stop_uncertain = True
                    raise InterruptedError('pan admission changed during execution')
            result = dict(result, executed=None, physically_observed=None)
            self._publish(request, result)
            return result
        except BaseException as exc:
            if attempted:
                self.stop_uncertain = True
                self.stop()
            self._publish(request, dict(acknowledged=False, error=type(exc).__name__,
                                       uncertain=self.stop_uncertain, physically_observed=None))
            raise
        finally:
            with self._state_lock:
                if self._active_cancel is cancel:
                    self._active_cancel = None
            self._request_lock.release()

    def stop(self):
        if self._connected:
            return super().stop()
        with self._state_lock:
            self._stop_at = self.clock()
            if self._active_cancel is not None:
                self._active_cancel.set()
        return dict(sent=False, acknowledged=False, physically_stopped=None,
                    reason='transport not opened; no physical claim')

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

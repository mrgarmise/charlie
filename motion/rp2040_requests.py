"""Request adapter over the existing CAL-1 brain and serial owner.

No PWM, firmware activation, profile mutation, second serial port or substitute
controller. Native firmware retains envelope, electrical and watchdog authority.
"""
import threading
import time
import os
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
from contextlib import nullcontext
from motion.elegoo_executor import ActuatorRequest
from experiments.ppal.mobile_navigation import age


class RP2040Requests:
    _owner_lock = threading.Lock()
    def __init__(self, controller, calibration, bus, *, clock=time.monotonic, fault_path=None):
        with self._owner_lock:
            if controller.__dict__.get('_charlie_rp2040_gateway') is not None:
                raise ValueError('RP2040 controller already has an actuator gateway')
            controller.__dict__['_charlie_rp2040_gateway'] = self
        self.controller, self.calibration, self.bus, self.clock = controller, calibration, bus, clock
        self.lock = threading.Lock()
        self.used = set()
        self.fault_path = Path(fault_path) if fault_path is not None else None
        self.uncertain = self.fault_path is not None and self.fault_path.exists()
        self.stopped_at = None
        self.generation, self.sequence = uuid4().hex, 0
        self.bus.claim_observations('rp2040-motion-state',self,metadata={
            'body':'RP2040','modality':'controller-state','clock':'host-monotonic receipt',
            'acquisition':'existing RP2040 controller MOTION_STATUS',
            'physical_pose':'not measured; firmware reports commanded estimates'})

    def poll(self):
        from stimulus.bus import Observation
        if not self.lock.acquire(blocking=False):
            return False
        try:
            started = self.clock()
            status = self.controller.motion_status()
            if (not isinstance(status,dict) or status.get('schema') != 'charlie-motion-authority-v1'
                    or not getattr(self.controller,'link_session',None)
                    or status.get('session') != self.controller.link_session):
                raise ValueError('current controller status unavailable')
            self.sequence += 1
            self.bus.publish_observation('rp2040-motion-state',self,Observation(
                'rp2040-motion-state',self.sequence,self.clock(),status,
                {'query_started_at':started,'physical_pose':'unknown',
                 'position_provenance':'firmware commanded estimate'},self.generation))
            return True
        except Exception as exc:
            self.bus.observation_fault('rp2040-motion-state',self,str(exc))
            return False
        finally:
            self.lock.release()

    def close(self):
        self.bus.release_observations('rp2040-motion-state',self)

    def _reserve(self):
        if self.fault_path is None:
            return
        self.fault_path.parent.mkdir(parents=True,exist_ok=True)
        try:
            fd = os.open(self.fault_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as stream:
                stream.write('RP2040 request in progress; physical outcome unknown\n')
                stream.flush();os.fsync(stream.fileno())
            directory = os.open(self.fault_path.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        except BaseException:
            self.uncertain = True
            raise

    def _complete(self):
        if self.fault_path is None:
            return
        try:
            self.fault_path.unlink()
            directory = os.open(self.fault_path.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        except BaseException:
            self.uncertain = True
            raise

    def _latch(self):
        self.uncertain = True
        if self.fault_path is not None and not self.fault_path.exists():
            try:self._reserve()
            except OSError:pass  # Existing in-memory latch still fails closed.

    def _completed_safely(self):
        valid = getattr(self.controller, 'motion_scope_valid', None)
        return (getattr(self.controller, 'connected', True)
                and not getattr(self.calibration.brain, 'blocked', False)
                and (not callable(valid) or valid()))

    def stop(self):
        self.stopped_at = self.clock()
        brain = self.calibration.brain
        try:
            sent = self.controller.stop()
            if sent is not True:
                self._latch()
            return dict(sent=sent, acknowledged=None, physically_stopped=None)
        except BaseException:
            self._latch()
            raise
        finally:
            if brain is not None:
                brain.search_remaining = 0

    def _scope(self):
        scope = getattr(self.controller, 'motion_scope', None)
        return scope() if callable(scope) else nullcontext()

    def observe_frame(self, frame, target=None):
        if self.uncertain:
            return None
        with self._scope():
            if not self.lock.acquire(blocking=False):
                return None
            try:
                self._reserve()
                result = self.calibration.observe_frame(frame,target)
                if not self._completed_safely():
                    self._latch()
                else:
                    self._complete()
                return result
            except BaseException:
                self._latch()
                self.stop()
                raise
            finally:
                self.lock.release()

    def _schedule_search(self):
        intent = getattr(self.controller, 'apply_motion_intent', None)
        if callable(intent):
            return intent(self.calibration.brain.request_search)
        self.calibration.brain.request_search()
        return True

    def request_search(self):
        if self.uncertain or self.calibration.brain is None:
            return False
        with self._scope():
            return self._schedule_search()

    def request(self, request):
        if not isinstance(request, ActuatorRequest):
            raise ValueError('typed actuator request required')
        if request.action == 'stop':
            return self.stop()
        with self._scope():
            return self._request_scoped(request)

    def _request_scoped(self, request):
        if not self.lock.acquire(blocking=False):
            raise ValueError('RP2040 request already active')
        try:
            request = deepcopy(request)
            if (self.uncertain or request.group != 'rp2040-head' or request.action not in ('track-target','search')
                    or not request.id or request.id in self.used or len(self.used) >= 256
                    or not 0 <= age(self.clock(),request.at) <= .1
                    or (self.stopped_at is not None and request.at <= self.stopped_at)):
                raise ValueError('stale, replayed, stopped or unsupported RP2040 request')
            frame = self.bus.latest_frame(request.source,max_age=.25,clock=self.clock)
            if frame is None or frame.id != request.observation_id or frame.source != 'pi-primary':
                raise ValueError('fresh primary-camera observation required')
            brain = self.calibration.brain
            if brain is None or not brain.authorized or brain.blocked or self.calibration.health.quarantined:
                raise PermissionError('existing CAL-1 authority unavailable')
            # CAL-1 performs profile, owner, status and observed-response checks.
            # Never substitute a host-side "armed" flag for those checks.
            self.used.add(request.id)
            if request.action == 'search':
                if not self._schedule_search():
                    raise InterruptedError('search invalidated by STOP')
                result = None
            else:
                target = request.parameters.get('target')
                if not isinstance(target, dict):
                    raise ValueError('existing detector target required')
                self._reserve()
                result = self.calibration.observe_frame(frame.image, target)
                if not self._completed_safely():
                    self._latch()
                else:
                    self._complete()
            return dict(accepted=True, dispatched=None, acknowledged=None,
                        physically_observed=None, owner='existing CAL-1', result=result)
        except (PermissionError,ValueError):
            raise
        except BaseException:
            self._latch()
            self.stop()
            raise
        finally:
            self.lock.release()

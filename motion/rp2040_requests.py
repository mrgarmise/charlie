"""Request adapter over the existing CAL-1 brain and serial owner.

No PWM, firmware activation, profile mutation, second serial port or substitute
controller. Native firmware retains envelope, electrical and watchdog authority.
"""
import threading
import time
from copy import deepcopy
from motion.elegoo_executor import ActuatorRequest
from experiments.ppal.mobile_navigation import age


class RP2040Requests:
    def __init__(self, controller, calibration, bus, *, clock=time.monotonic):
        self.controller, self.calibration, self.bus, self.clock = controller, calibration, bus, clock
        self.lock = threading.Lock()
        self.used = set()
        self.uncertain = False
        self.stopped_at = None

    def stop(self):
        self.stopped_at = self.clock()
        brain = self.calibration.brain
        if brain is not None:
            brain.search_remaining = 0
        try:
            sent = self.controller.stop()
            if sent is not True:
                self.uncertain = True
            return dict(sent=sent, acknowledged=None, physically_stopped=None)
        except BaseException:
            self.uncertain = True
            raise

    def request(self, request):
        if not isinstance(request, ActuatorRequest):
            raise ValueError('typed actuator request required')
        if request.action == 'stop':
            return self.stop()
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
                brain.request_search()
                result = None
            else:
                target = request.parameters.get('target')
                if not isinstance(target, dict):
                    raise ValueError('existing detector target required')
                result = self.calibration.observe_frame(frame.image, target)
            return dict(accepted=True, dispatched=None, acknowledged=None,
                        physically_observed=None, owner='existing CAL-1', result=result)
        except (PermissionError,ValueError):
            raise
        except BaseException:
            self.uncertain = True
            self.stop()
            raise
        finally:
            self.lock.release()

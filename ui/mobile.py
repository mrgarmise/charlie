"""Mobile Body view of application-owned senses and qualified actuator requests.

Browser leases are additional arbitration only; independent physical admission is
still required for every pulse. No device opens, inferred safety, or firmware I/O.
"""
from collections import deque
from copy import deepcopy
import io
import math
import secrets
import threading
import time
from uuid import uuid4

from motion.elegoo_executor import ActuatorRequest


class MobileConsole:
    freshness = .5
    lease_seconds = .4

    def __init__(self, bus, executor=None, *, clock=time.monotonic):
        self.bus, self.executor, self.clock = bus, executor, clock
        self.boot = uuid4().hex
        self.lock = threading.RLock()
        self.camera_lock = threading.RLock()
        self.operation = threading.Lock()
        self.owner = None
        self.lease = None
        self.expires = 0.
        self.sequence = -1
        self.closed = False
        self.command = {'state': 'idle', 'physical_outcome': 'unobserved'}
        self.subscription = bus.subscribe_frames('elegoo-v4', max_age=self.freshness, clock=clock)
        self.frame = None
        self.frame_error = 'waiting for shared ELEGOO producer'
        self.receipts = deque(maxlen=120)
        self.png = None
        self.png_id = None
        self.encode_seconds = None
        self.shutdown = threading.Event()
        self.watchdog = None

    def start(self):
        if self.watchdog is not None:return
        def watch():
            while not self.shutdown.wait(.025):
                self.expire()
        self.watchdog = threading.Thread(target=watch, name='mobile-console-watchdog', daemon=True)
        self.watchdog.start()

    def expire(self):
        with self.lock:
            expired = self.lease is not None and self.clock() >= self.expires
            if expired:
                # Revoke before potentially blocking on STOP. No command can renew.
                self.lease = None
                owner, self.owner = self.owner, None
                self.command = {'state': 'watchdog STOP', 'physical_outcome': 'unobserved'}
        if expired and self.executor:
            try:self.executor.release_manual(owner)
            except Exception as exc:
                self.command = {'state': 'STOP error', 'error': str(exc)[:256], 'physical_outcome': 'unknown'}
                self.executor.emergency_stop()
        return expired

    def acquire(self):
        if not self.operation.acquire(blocking=False):raise PermissionError('control operation active')
        try:
            with self.lock:
                if self.closed or self.lease is not None:raise PermissionError('operator already owns control or service closed')
                if self.executor is None:raise PermissionError('monitoring only; executor unavailable')
                # Browser permission cannot establish physical qualification.
                if self.executor.authority is None:raise PermissionError('independent actuator authority absent')
                self.executor.authority.active('chassis', self.executor.boot_id)
                owner = object()
                until = self.clock()+self.lease_seconds
                self.executor.claim_manual(owner, until)
                self.owner, self.lease, self.expires = owner, secrets.token_urlsafe(32), until
                self.sequence = -1
                return {'boot': self.boot, 'lease': self.lease, 'expires_in': max(0,until-self.clock())}
        finally:self.operation.release()

    def _authorize(self, body):
        if (self.closed or body.get('boot') != self.boot or not isinstance(body.get('lease'), str)
                or self.lease is None or not secrets.compare_digest(body['lease'], self.lease)
                or self.clock() >= self.expires):
            raise PermissionError('current boot-bound operator lease required')
        seq = body.get('sequence')
        if type(seq) is not int or seq <= self.sequence or seq > 2**53:
            raise ValueError('strictly increasing command sequence required')
        self.sequence = seq
        return self.owner

    def control(self, body):
        action = body.get('action')
        if action == 'emergency':
            # A drive credential may always STOP, even without a current lease.
            with self.lock:
                self.lease = None
                self.command = {'state': 'emergency STOP latched', 'physical_outcome': 'unobserved'}
            return self.executor.emergency_stop() if self.executor else dict(sent=False, reason='no executor')
        if action in ('release','stop'):
            with self.lock:
                owner = self._authorize(body)
                if action == 'release':
                    self.lease = None
                    self.owner = None
            result = self.executor.release_manual(owner) if action == 'release' else self.executor.stop()
            with self.lock:self.command = {'state': action, 'receipt': deepcopy(result), 'physical_outcome': 'unobserved'}
            return result
        if not self.operation.acquire(blocking=False):raise PermissionError('command active; no queued motor commands')
        try:
            with self.lock:
                owner = self._authorize(body)
                if action == 'release':
                    self.lease = None
                    self.owner = None
                elif action in ('heartbeat', 'drive', 'stop'):
                    self.expires = self.clock()+self.lease_seconds
                    self.executor.renew_manual(owner, self.expires)
                else:raise ValueError('unsupported control action')
            if action == 'release':
                result = self.executor.release_manual(owner)
            elif action == 'stop':
                result = self.executor.stop()
            elif action == 'heartbeat':
                return {'expires_in': self.lease_seconds}
            else:
                direction, pwm = body.get('direction'), body.get('pwm')
                if direction not in ('FORWARD', 'REVERSE', 'LEFT', 'RIGHT') or type(pwm) is not int or not 1 <= pwm <= 35:
                    raise ValueError('bounded direction and PWM required')
                frame = self.bus.latest_frame('elegoo-v4', max_age=.25, clock=self.clock)
                if frame is None:raise PermissionError('fresh source-bound frame unavailable')
                # Pan is an independent measurement, never the last commanded angle.
                feed = self.bus.latest_observation('elegoo-pose', max_age=.25, clock=self.clock)
                pan = feed.values.get('pan_degrees') if feed else None
                if type(pan) not in (int,float) or not math.isfinite(pan):
                    raise PermissionError('independently measured camera pan unavailable')
                request = ActuatorRequest(uuid4().hex, 'mobile-operator', 'chassis', 'pulse', self.clock(),
                    'elegoo-v4', frame.id, dict(direction=direction,pwm=pwm,seconds=.1,expected_pan_degrees=pan))
                result = self.executor.request_manual(owner, request)
            with self.lock:
                self.command = {'state': action, 'receipt': deepcopy(result), 'physical_outcome': 'unobserved'}
            return result
        except Exception as exc:
            with self.lock:self.command = {'state': 'rejected or failed', 'error': str(exc)[:256], 'physical_outcome': 'unknown'}
            raise
        finally:self.operation.release()

    def _camera(self):
        try:
            frame = self.subscription.read()
            if frame is not None:
                if self.frame and frame.stream_generation != self.frame.stream_generation:self.receipts.clear()
                self.frame = frame
                self.receipts.append(frame.received_at)
                self.frame_error = None
        except (OSError,TimeoutError) as exc:
            self.frame, self.png, self.png_id = None, None, None
            self.receipts.clear()
            self.frame_error = str(exc)
        f = self.frame
        age = self.clock()-f.received_at if f else None
        fresh = age is not None and 0 <= age <= self.freshness
        rate = (len(self.receipts)-1)/(self.receipts[-1]-self.receipts[0]) if len(self.receipts)>1 and self.receipts[-1]>self.receipts[0] else None
        return dict(available=fresh, reason=self.frame_error if not fresh else None, age_seconds=age,
            source='elegoo-v4', frame_id=f.id if f else None, generation=f.stream_generation if f else None,
            geometry=[f.image.shape[1],f.image.shape[0]] if f else None,
            subscriber_fps=rate if fresh else None, dropped=self.subscription.dropped,
            exposure_latency_seconds=None, latency_note='receipt age only; exposure clock unknown',
            encoding='lossless PNG baseline', encode_seconds=self.encode_seconds)

    def image(self):
        with self.camera_lock:
            camera = self._camera()
            if not camera['available']:raise TimeoutError('camera frame unavailable or stale')
            if self.png_id != self.frame.id:
                from PIL import Image
                start = time.perf_counter()
                buffer = io.BytesIO()
                Image.fromarray(self.frame.image[:,:,::-1]).save(buffer, format='PNG')
                self.png, self.png_id = buffer.getvalue(), self.frame.id
                self.encode_seconds = time.perf_counter()-start
            return self.png, camera

    def status(self):
        with self.camera_lock:
            camera = self._camera()
            sensors = {}
            for source, metadata in self.bus.describe_observations().items():
                if not source.startswith('elegoo-'):continue
                entry = dict(metadata, available=False, age_seconds=None, hz=None, values=None)
                try:
                    history = self.bus.recent_observations(source,max_age=5,clock=self.clock)
                    if history:
                        last = history[-1]
                        age = self.clock()-last.received_at
                        span = history[-1].received_at-history[0].received_at
                        valid = last.values.get('valid',True) is True
                        entry.update(age_seconds=age, available=0<=age<=.5 and valid,
                            values=deepcopy(last.values), provenance=deepcopy(last.provenance),
                            hz=(len(history)-1)/span if span>0 else None)
                        if not entry['available']:entry['values']=None;entry['hz']=None
                        if entry['available'] and source=='elegoo-ultrasonic':
                            meters=last.values.get('meters')
                            entry['centimeters']=meters*100 if type(meters) in (int,float) and math.isfinite(meters) else None
                except OSError as exc:entry['error']=str(exc)
                sensors[source]=entry
            detections = None
            try:
                o = self.bus.latest_observation('object-detections:elegoo-v4',max_age=.5,clock=self.clock)
                if o and camera['available']:
                    p=o.values
                    if (p.get('frame_id')==camera['frame_id'] and p.get('stream_generation')==camera['generation']
                            and p.get('geometry')==camera['geometry']):detections=deepcopy(p)
            except OSError:pass
            e=self.executor
            ready=False;reason='qualified executor unavailable'
            if e:
                try:
                    if e.stop_uncertain or e._safety_stopped:raise PermissionError('STOP latch or uncertain physical state')
                    if e.authority is None:raise PermissionError('independent actuator authority absent')
                    e.authority.active('chassis',e.boot_id)
                    ready=True;reason='per-command source and safety admission still required'
                except Exception as exc:reason=str(exc)[:256]
            return dict(boot=self.boot,camera=camera,sensors=sensors,detections=detections,
                control=dict(available=ready,reason=reason,owned=self.lease is not None,
                    expires_in=max(0,self.expires-self.clock()) if self.lease else 0,
                    max_pwm=35, pulse_seconds=.1, command=deepcopy(self.command)),
                deferred_sensors=['battery voltage','line tracking','raw IMU: installed driver/protocol unqualified'])

    def close(self):
        with self.lock:
            if self.closed:return
            self.closed=True
            owner,self.owner=self.owner,None
            self.lease=None
        self.shutdown.set()
        try:
            if owner and self.executor:self.executor.release_manual(owner)
        finally:
            self.subscription.close()
            if self.watchdog:self.watchdog.join(timeout=1)

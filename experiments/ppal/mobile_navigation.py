"""Proposal-only local mobile decision boundary. No firmware commands invented."""
from dataclasses import dataclass, asdict
import math
import time
import threading
from uuid import uuid4


def finite(x):return type(x) in (int,float) and math.isfinite(x)

def age(now, then):return now-then if finite(now) and finite(then) else float('inf')


@dataclass(frozen=True)
class MobileLimits:
    max_receipt_age: float = .5
    max_sensor_age: float = .25
    stand_off_m: float = 1.
    stop_distance_m: float = .6
    max_speed: float = .15
    max_duration: float = .2
    # Engineering proposal limits only, not hardware-qualified units/thresholds.

    def __post_init__(self):
        if (any(not finite(v) or v<=0 for v in asdict(self).values())
                or self.stop_distance_m>=self.stand_off_m or self.max_speed>1 or self.max_duration>1):
            raise ValueError('invalid conservative proposal limits')


@dataclass(frozen=True)
class MotionLease:
    mode: str = 'disarmed'
    expires_at: float = 0
    authority: str | None = None
    boot_id: str | None = None

    def valid(self, now, boot_id):
        return (self.mode in ('supervised_trial','qualified_autonomous') and bool(self.authority)
                and self.boot_id==boot_id and finite(self.expires_at) and now<self.expires_at)


class MobileNavigator:
    def __init__(self, limits=None, *, clock=time.monotonic):
        self.limits,self.clock=limits or MobileLimits(),clock

    def propose(self, observation, tracking, telemetry):
        """Fail closed; booleans must come from independently qualified sensors.

        Relative depth is an anomaly signal only. Real ultrasonic is necessary
        but insufficient: mapped hazards, floor and blind spots require evidence.
        """
        now=self.clock(); l=self.limits; reasons=[]
        frame=observation['frame']; depth=observation.get('depth',{})
        frame_age=age(now,frame.get('received_at'))
        if not finite(frame_age) or not 0<=frame_age<=l.max_receipt_age:reasons.append('stale_frame')
        if frame.get('source_age_known') is not True:reasons.append('unknown_capture_age')
        if not frame.get('authentic'):reasons.append('offline_fixture')
        if observation.get('qualification')!='native-qualified':reasons.append('unqualified_perception')
        if depth.get('kind')!='relative' or depth.get('valid') is not True:reasons.append('uncertain_depth')
        if depth.get('zones') and (depth.get('frame_id')!=frame['id'] or depth.get('received_at')!=frame.get('received_at')):reasons.append('depth_frame_mismatch')
        if depth.get('anomaly') is not False:reasons.append('depth_anomaly_or_unknown')
        pan=frame.get('pan_deg')
        if not finite(pan) or abs(pan-90)>5:reasons.append('off_axis_or_unknown_camera')
        target=tracking.get('target')
        if target is None or not target.get('observed') or target.get('ambiguous'):reasons.append('target_lost_or_ambiguous')
        for name in ('ultrasonic','target_range','yaw','heartbeat','floor_clearance','hazard_map','blind_spot','lateral_clearance'):
            sensor=telemetry.get(name,{})
            sensor_age=age(now,sensor.get('at'))
            if (not finite(sensor_age) or not 0<=sensor_age<=l.max_sensor_age
                    or sensor.get('valid') is not True or sensor.get('source')!='car-qualified'):
                reasons.append(f'{name}_unverified')
        distance=telemetry.get('ultrasonic',{}).get('meters')
        if not finite(distance) or not 0<distance<=10:reasons.append('invalid_range')
        elif distance<=l.stand_off_m:reasons.append('stand_off')
        target_range=telemetry.get('target_range',{})
        if (not finite(target_range.get('meters')) or target_range['meters']<=l.stand_off_m
                or target is None or target_range.get('track_id')!=target.get('id')):reasons.append('target_distance_unverified_or_near')
        for name in ('target_range','ultrasonic'):
            sensor=telemetry.get(name,{})
            if sensor.get('frame_id')!=frame['id'] or sensor.get('field_of_view_verified') is not True:reasons.append(name+'_field_of_view_unknown')
        if not finite(telemetry.get('yaw',{}).get('degrees')):reasons.append('invalid_yaw')
        for name in ('floor_clearance','hazard_map','blind_spot','lateral_clearance'):
            if telemetry.get(name,{}).get('clear') is not True:reasons.append(f'{name}_uncertain')
        if telemetry.get('pet_distress') is not False:reasons.append('humane_condition_unverified')
        for name in ('pet_willing','human_clear','zone_inspected','power_ok'):
            if name in telemetry and telemetry[name] is not True:reasons.append(name+'_veto')
        action='stop'
        if not reasons:
            w=frame['geometry'][0]; x,_,r,_=target['box']; offset=((x+r)/2)/w-.5
            action='turn' if abs(offset)>.15 else 'advance'
        return dict(schema='charlie.mobile.proposal.v1', id=uuid4().hex, frame_id=frame['id'],
                    at=now, action=action, direction=('LEFT' if target and sum(target['box'][::2])/2<frame['geometry'][0]/2 else 'RIGHT') if action=='turn' else None,
                    speed=l.max_speed if action!='stop' else 0, duration=l.max_duration if action!='stop' else 0,
                    reasons=reasons, limits=asdict(l), physical_authorization=False,
                    handoff=dict(owner='existing ELEGOO body',camera_pan_deg=pan,
                        yaw_deg=telemetry.get('yaw',{}).get('degrees'),camera_limits_deg=[20,160],
                        status='centered camera required before chassis steering; no blind alignment' if not finite(pan) or abs(pan-90)>5 else 'chassis steering owns centered view'))


class MobileExecutionGate:
    """Independent gate with no built-in physical backend.

    Only a future, verified car-local bounded-motion adapter may be injected.
    Disarmed mode doesn't even connect/send STOP. Queued != executed != observed.
    """
    def __init__(self, *, backend=None, clock=time.monotonic, boot_id=None, safety_check=None):
        self.backend,self.clock=backend,clock
        self.safety_check=safety_check
        self.boot_id=boot_id or uuid4().hex
        self.lease=MotionLease()

    def execute(self, proposal):
        now=self.clock(); errors=[]
        if not self.lease.valid(now,self.boot_id):errors.append('disarmed_or_expired_authority')
        if self.backend is None:errors.append('no_qualified_car_local_adapter')
        if self.safety_check is None:errors.append('independent_safety_check_unavailable')
        else:
            try:
                if self.safety_check(proposal) is not True:errors.append('independent_safety_veto')
            except Exception:errors.append('independent_safety_error')
        if proposal.get('action') not in ('stop','turn','advance'):errors.append('invalid_action')
        if proposal.get('reasons'):errors.append('safety_veto')
        proposal_age=age(now,proposal.get('at'))
        if not finite(proposal_age) or not 0<=proposal_age<=.1:errors.append('stale_proposal')
        if not finite(proposal.get('speed')) or not 0<=proposal['speed']<=.15:errors.append('speed_limit')
        if not finite(proposal.get('duration')) or not 0<=proposal['duration']<=.2:errors.append('duration_limit')
        if finite(proposal.get('duration')) and (not finite(self.lease.expires_at) or now+proposal['duration']>self.lease.expires_at):errors.append('lease_horizon')
        if proposal.get('action')=='turn' and proposal.get('direction') not in ('LEFT','RIGHT'):errors.append('invalid_turn')
        if self.backend is not None and getattr(self.backend,'car_local_qualified',False) is not True:errors.append('unqualified_backend')
        result=dict(proposal_id=proposal.get('id'), requested=proposal.get('action'), approved=not errors,
                    rejected=errors, dispatched=False, acknowledged=False, executed=None, observed_consequence=None)
        if errors:
            # If a previously active adapter exists, stop on any veto/lease expiry.
            if getattr(self,'active',False):
                try:self.backend.stop()
                finally:self.active=False
            return result
        try:
            self.active=True
            ack=self.backend.execute_bounded(proposal,lease=self.lease)
            result.update(dispatched=True, acknowledged=ack.get('acknowledged') is True,
                          executed=ack.get('executed') if type(ack.get('executed')) is bool else None)
            if 'stop' in ack:result['stop']=ack['stop']
            if 'wire' in ack:result['wire']=ack['wire']
            if ack.get('bounded_complete'):
                confirmed=ack.get('stop',{}).get('acknowledged') is True
                self.active=not confirmed
                if not confirmed:result.update(approved=False,physical_uncertainty=True,rejected=['stop_unconfirmed'])
            if not result['acknowledged']:self.backend.stop(); self.active=False
        except Exception as exc:
            result.update(approved=False,rejected=['controller_error'],error=type(exc).__name__)
            attempt=getattr(self.backend,'last_attempt',None)
            if isinstance(attempt,dict) and attempt:
                result.update(dispatched=None,wire_attempt=attempt,physical_uncertainty=True)
            try:self.backend.stop()
            finally:self.active=False
        return result

    def close(self):
        if getattr(self,'active',False):
            try:self.backend.stop()
            finally:self.active=False
        self.lease=MotionLease()


class QualifiedMobileExecutor:
    """Adapter behind the existing gate, using the existing MobileBase only.

    No direct detector motor calls. No device opens until deployment validates.
    """
    _owner_lock=threading.Lock()

    def __init__(self,base,context,*,clock=time.monotonic,cancel=None):
        # The same live transport facade must not acquire two independent
        # arbiters. A faulted owner remains attached for this facade lifetime.
        with self._owner_lock:
            if base.__dict__.get('_charlie_qualified_executor') is not None:
                raise ValueError('transport already has a qualified executor')
            base.__dict__['_charlie_qualified_executor']=self
        self.base,self.context,self.clock,self.cancel=base,context,clock,cancel
        self.last_attempt=None
        self.car_local_qualified=True;self.used=set();self.last_stop=None
        self.stop_uncertain=False
        self._request_lock=threading.Lock()
        self._state_lock=threading.Lock()
        self._active_cancel=None
        self._stop_at=None
        self._stop_inflight=0
        self._closed=False

    def execute_bounded(self,proposal,*,lease):
        # A second caller must never queue an old motion command behind another.
        if not self._request_lock.acquire(blocking=False):
            raise ValueError('another actuator request is active')
        local_cancel=threading.Event()
        try:
            with self._state_lock:
                at=proposal.get('at')
                if self._closed or self._stop_inflight or (self._stop_at is not None and
                        (not finite(at) or at<=self._stop_at)):
                    raise ValueError('request predates STOP or STOP is pending')
                self._active_cancel=local_cancel
            return self._execute_exclusive(proposal,lease=lease,local_cancel=local_cancel)
        finally:
            with self._state_lock:
                if self._active_cancel is local_cancel:self._active_cancel=None
            self._request_lock.release()

    def _execute_exclusive(self,proposal,*,lease,local_cancel):
        now=self.clock()
        proposal_age=age(now,proposal.get('at'))
        if (not finite(proposal_age) or not 0<=proposal_age<=.1
                or proposal.get('action') not in ('stop','turn','advance')
                or proposal.get('reasons') or not finite(proposal.get('duration'))
                or not 0<=proposal['duration']<=.2 or not finite(proposal.get('speed'))
                or not 0<=proposal['speed']<=.15
                or not isinstance(proposal.get('id'),str) or not proposal['id']
                or (proposal.get('action')!='stop' and (proposal['speed']<=0 or proposal['duration']<=0))
                or (proposal.get('action')=='turn' and proposal.get('direction') not in ('LEFT','RIGHT'))):
            raise ValueError('invalid, stale or vetoed actuator request')
        if local_cancel.is_set() or (self.cancel is not None and self.cancel.is_set()):
            raise InterruptedError('actuator request cancelled')
        active,report=self.context.activation()
        if self.stop_uncertain or (self.last_stop is not None and self.last_stop.get('acknowledged') is not True):
            raise ValueError('uncertain previous STOP; revoke/requalify before further movement')
        c=self.context.current
        if (c is None or proposal['id'] in self.used or not self.context.safe(proposal)
                or not lease.valid(self.clock(),self.context.boot_id)
                or proposal.get('binding')!=self.binding(c)):
            raise ValueError('expired/replayed/unbound mobile dispatch')
        self.used.add(proposal['id'])
        if len(self.used)>256:raise ValueError('bounded executor session exhausted; renew episode')
        if proposal['action']=='stop':return self.stop()
        direction=proposal['direction'] if proposal['action']=='turn' else 'FORWARD'
        envelope=report['direction_envelopes'][direction]
        pwm=max(1,int(envelope['max_pwm']*proposal['speed']/.15))
        reserve = getattr(self, '_reserve_wire_attempt', None)
        if reserve is not None:reserve(proposal['id'])
        self.last_attempt=dict(wire_delivery='unknown until independent response',proposal_id=proposal['id'])
        class CombinedCancel:
            def is_set(inner):
                return local_cancel.is_set() or (self.cancel is not None and self.cancel.is_set())
        try:
            result=self.base.pulse(direction,pwm=pwm,seconds=min(proposal['duration'],envelope['max_duration']),
                lease=lease,boot_id=self.context.boot_id,envelope=envelope,_executor=self,
                safety_check=lambda:self.context.safe(proposal),cancel=CombinedCancel())
        except BaseException:
            # A raised start/STOP exchange can leave physical delivery unknown.
            # A subsequent ACK must not silently clear this session fault.
            self.stop_uncertain=True
            attempt=getattr(getattr(self.base,'car',None),'last_pulse',None)
            if isinstance(attempt,dict):
                from copy import deepcopy
                self.last_attempt['wire_result']=deepcopy(attempt)
            raise
        with self._state_lock:
            self.last_stop=result.get('stop')
            if not isinstance(self.last_stop,dict) or self.last_stop.get('acknowledged') is not True:
                self.stop_uncertain=True
        if not self.stop_uncertain:
            complete = getattr(self, '_complete_wire_attempt', None)
            if complete is not None:complete()
        return dict(acknowledged=result['acknowledged'],executed=None,bounded_complete=True,
                    wire=result.get('command'),stop=result.get('stop'),physically_observed=None)

    @staticmethod
    def binding(context):
        from memory.evidence import digest
        return digest(dict(frame=context['observation']['frame'],sensors=context['observation']['sensors'],
            target=context['tracking']['target'],activation=context['activation']['activation_key']))

    def stop(self):
        # Never wait for the motion request lock. STOP preempts the pulse and
        # invalidates proposals issued before it; physical delivery is separate.
        with self._state_lock:
            self._stop_at=self.clock()
            self._stop_inflight+=1
            if self._active_cancel is not None:self._active_cancel.set()
        try:
            result=self.base.stop_verified()
            with self._state_lock:
                self.last_stop=result
                if not isinstance(result,dict) or result.get('acknowledged') is not True:
                    self.stop_uncertain=True
            return result
        except BaseException:
            with self._state_lock:self.stop_uncertain=True
            raise
        finally:
            with self._state_lock:self._stop_inflight-=1

    def close(self):
        with self._state_lock:self._closed=True
        stopped=False
        try:
            result=self.stop()
            stopped=isinstance(result,dict) and result.get('acknowledged') is True
        finally:
            self.base.close()
        # An outstanding request or ambiguous stop retains the owner: creating
        # another executor on this facade cannot erase the uncertainty.
        if stopped and not self.stop_uncertain and self._request_lock.acquire(blocking=False):
            try:
                with self._owner_lock:
                    if self.base.__dict__.get('_charlie_qualified_executor') is self:
                        del self.base.__dict__['_charlie_qualified_executor']
            finally:self._request_lock.release()

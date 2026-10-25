"""Proposal-only local mobile decision boundary. No firmware commands invented."""
from dataclasses import dataclass, asdict
import math
import time
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
        action='stop'
        if not reasons:
            w=frame['geometry'][0]; x,_,r,_=target['box']; offset=((x+r)/2)/w-.5
            action='turn' if abs(offset)>.15 else 'advance'
        return dict(schema='charlie.mobile.proposal.v1', id=uuid4().hex, frame_id=frame['id'],
                    at=now, action=action, direction=('LEFT' if target and sum(target['box'][::2])/2<frame['geometry'][0]/2 else 'RIGHT') if action=='turn' else None,
                    speed=l.max_speed if action!='stop' else 0, duration=l.max_duration if action!='stop' else 0,
                    reasons=reasons, limits=asdict(l), physical_authorization=False)


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
            if not result['acknowledged']:self.backend.stop(); self.active=False
        except Exception as exc:
            result.update(approved=False,rejected=['controller_error'],error=type(exc).__name__)
            try:self.backend.stop()
            finally:self.active=False
        return result

    def close(self):
        if getattr(self,'active',False):
            try:self.backend.stop()
            finally:self.active=False
        self.lease=MotionLease()

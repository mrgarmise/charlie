"""Behavior-side compatibility API. Owns requests/alignment state, no device."""
import time
from uuid import uuid4
from hardware.elegoo_mobile import AttentionAlignState
from motion.elegoo_executor import ActuatorRequest, application_executor


class MobileRequests:
    def __init__(self, *, executor=None, requester='face-tracking', clock=time.monotonic):
        self.executor = executor if executor is not None else application_executor()
        self.requester, self.clock = requester, clock
        self.source = self.observation_id = None
        self.align = AttentionAlignState()
        self.pan_assumed = 90

    def bind_frame(self, frame):
        self.source = frame.source
        self.observation_id = getattr(frame, 'frame_id', getattr(frame, 'id', None))

    def _request(self, group, action, **parameters):
        return self.executor.request(ActuatorRequest(uuid4().hex, self.requester,
            group, action, self.clock(), self.source, self.observation_id, parameters))

    def pan(self, degrees):
        result = self._request('camera-pan', 'pan', degrees=degrees, expected_pan_degrees=self.pan_assumed)
        if result.get('acknowledged') is not True:
            raise RuntimeError('pan not acknowledged')
        self.pan_assumed = result['commanded_degrees']
        return self.pan_assumed

    def pivot(self, direction, speed=None):
        # This engineering cap is not qualification. Independent admission may
        # only reduce it and must certify local expiration before dispatch.
        return self._request('chassis', 'pulse', direction=direction,
                             pwm=20 if speed is None else speed, seconds=.1, expected_pan_degrees=self.pan_assumed)

    def yaw(self):
        value = self.executor.bus.latest_observation('elegoo-pose', max_age=.25, clock=self.clock)
        if value is None or value.values.get('yaw_valid') is not True:
            raise TimeoutError('fresh independently verified yaw unavailable')
        return value.values['yaw_degrees']

    def stop(self):
        self.align.active = False
        return self.executor.stop()

    def cancel_attention_align(self, reason='cancelled'):
        self.align.reason = reason
        self.align.active = False
        return self.stop()

    def begin_attention_align(self, current_pan, max_rotation=None):
        current_pan = int(round(current_pan))
        if 80 <= current_pan <= 100:
            return False
        sign = 1 if current_pan < 90 else -1
        target = abs(90-current_pan)
        if max_rotation is not None:
            target = min(target, float(max_rotation))
        self.align = AttentionAlignState(active=True, direction='RIGHT' if sign == 1 else 'LEFT',
            start_pan=current_pan, last_pan=current_pan, start_yaw=self.yaw(),
            target_rotation=target, target_pan=int(round(current_pan+sign*target)),
            yaw_sign=sign, started_at=self.clock())
        try:
            self.pivot(self.align.direction)
        except BaseException:
            self.align.active = False
            self.stop()
            raise
        return True

    def update_attention_align(self, face_visible=True):
        state = self.align
        if not state.active:
            return dict(active=False, done=True, reason=state.reason)
        reason = 'face_lost' if not face_visible else 'timeout' if self.clock()-state.started_at > 3 else None
        try:
            yaw_delta = self.yaw()-state.start_yaw if reason is None else 0
        except Exception:
            reason, yaw_delta = 'yaw_error', 0
        progress = yaw_delta*state.yaw_sign
        if reason is None and progress < -5:
            reason = 'wrong_way_yaw'
        if reason is not None:
            self.cancel_attention_align(reason)
            return dict(active=False, done=True, reason=reason, yaw_delta=yaw_delta)
        desired = max(20, min(160, int(round(state.start_pan+yaw_delta))))
        desired = min(desired, 90) if state.start_pan < 90 else max(desired, 90)
        try:
            if abs(desired-state.last_pan) >= 2:
                state.last_pan = self.pan(desired)
            if progress >= state.target_rotation:
                state.last_pan = self.pan(state.target_pan)
                self.cancel_attention_align('aligned')
                return dict(active=False, done=True, reason='aligned', yaw_delta=yaw_delta, pan=state.last_pan)
            # Renewal follows a new source-bound admission and fresh yaw. There
            # is no continuous motor command waiting for the next camera frame.
            self.pivot(state.direction)
        except BaseException:
            self.cancel_attention_align('actuator_error')
            raise
        return dict(active=True, done=False, reason=None, yaw_delta=yaw_delta,
                    progress=progress, target=state.target_rotation, pan=state.last_pan)

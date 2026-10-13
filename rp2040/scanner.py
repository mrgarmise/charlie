"""Propose bounded calibrated targets; never own or actuate servos."""
from servos import MotionError


class Scanner:
    def __init__(self, servos=None):
        self.servos = servos
        self.direction = 1

    def update(self):
        if self.servos is None or self.servos.envelope is None:
            raise MotionError('ASSEMBLED_CALIBRATION_REQUIRED')
        pan,tilt = self.servos.a_pan.position,self.servos.a_tilt.position
        low,high,_,_ = self.servos.envelope.axes[0]
        step = min(.5,self.servos.envelope.step)
        candidate = pan+self.direction*step
        if not low <= candidate <= high:
            self.direction *= -1
            candidate = pan+self.direction*step
        # Narrow profiles may have no full step left. Remain stationary rather
        # than introducing an uncalibrated alternate target or clipping input.
        if not low <= candidate <= high:candidate = pan
        return candidate,tilt

"""
servos.py

Dual head servo controller.

Head A
    GP4 Pan
    GP5 Tilt

Head B
    GP14 Pan
    GP15 Tilt

Both heads normally move together.
"""

from machine import Pin, PWM
import time

from config import *


class Servo:

    def __init__(self, pin):

        # SAFE STARTUP: do not energize a servo at an assumed angle.
        # PWM activation requires a separate calibrated implementation.
        self.pwm = None
        self.pin = pin

        self.position = 90.0
        self.target = 90.0
        self.velocity = 0.0
        self.speed_limit = MAX_SPEED

        # No startup position command.

    # ---------------------------------

    def angle_to_us(self, angle):

        angle = max(0, min(180, angle))

        span = SERVO_MAX_US - SERVO_MIN_US

        return SERVO_MIN_US + (span * angle / 180)

    # ---------------------------------

    def write(self, angle):

        self.position = angle

        us = self.angle_to_us(angle)

        duty = int(us * 65535 / 20000)

        if self.pwm is not None:
            self.pwm.duty_u16(duty)

    # ---------------------------------

    def move_to(self, angle, rate=None):

        self.speed_limit = (MAX_SPEED if rate is None else
                            min(MAX_SPEED, max(1.0, rate) / UPDATE_RATE_HZ))
        self.target = max(0, min(180, angle))

    # ---------------------------------

    def stop(self):
        self.target = self.position
        self.velocity = 0.0

    def update(self):

        error = self.target - self.position

        self.velocity += error * MAX_ACCEL

        self.velocity *= 0.82

        if self.velocity > self.speed_limit:
            self.velocity = self.speed_limit

        if self.velocity < -self.speed_limit:
            self.velocity = -self.speed_limit

        next_position = self.position + self.velocity
        if (self.target - self.position) * (self.target - next_position) <= 0:
            next_position = self.target
            self.velocity = 0.0
        self.write(max(0, min(180, next_position)))


class ServoController:

    def __init__(self):

        self.a_pan = Servo(HEAD_A_PAN_PIN)
        self.a_tilt = Servo(HEAD_A_TILT_PIN)

        self.b_pan = Servo(HEAD_B_PAN_PIN)
        self.b_tilt = Servo(HEAD_B_TILT_PIN)

    # -----------------------------

    def home(self):

        raise RuntimeError("HEAD_MOTION_DISARMED")
        self.look(HOME_PAN, HOME_TILT)

    # -----------------------------

    def look(self, pan, tilt, rate=None):
        raise RuntimeError("HEAD_MOTION_DISARMED")

        pan = max(PAN_MIN, min(PAN_MAX, pan))
        tilt = max(TILT_MIN, min(TILT_MAX, tilt))

        self.a_pan.move_to(pan, rate)
        self.a_tilt.move_to(tilt, rate)

        self.b_pan.move_to(pan, rate)
        self.b_tilt.move_to(tilt, rate)

    # -----------------------------

        raise RuntimeError("HEAD_MOTION_DISARMED")
    def head_a(self, pan, tilt, rate=None):

        self.a_pan.move_to(pan, rate)
        self.a_tilt.move_to(tilt, rate)

    # -----------------------------
        raise RuntimeError("HEAD_MOTION_DISARMED")

    def head_b(self, pan, tilt, rate=None):

        self.b_pan.move_to(pan, rate)
        self.b_tilt.move_to(tilt, rate)

    # -----------------------------

    def stop(self):
        for servo in (self.a_pan, self.a_tilt, self.b_pan, self.b_tilt):
            servo.stop()

        for servo in (self.a_pan, self.a_tilt, self.b_pan, self.b_tilt):
            if servo.pwm is not None:
                servo.pwm.deinit()
                servo.pwm = None

    def update(self):

        # Motion remains locked until calibrated arming is implemented.
        return

        self.a_pan.update()
        self.a_tilt.update()

        self.b_pan.update()
        self.b_tilt.update()

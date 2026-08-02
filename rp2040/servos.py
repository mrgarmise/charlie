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

        self.pwm = PWM(Pin(pin))
        self.pwm.freq(PWM_FREQUENCY)

        self.position = 90.0
        self.target = 90.0
        self.velocity = 0.0

        self.write(self.position)

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

        self.pwm.duty_u16(duty)

    # ---------------------------------

    def move_to(self, angle):

        self.target = max(0, min(180, angle))

    # ---------------------------------

    def update(self):

        error = self.target - self.position

        self.velocity += error * MAX_ACCEL

        self.velocity *= 0.82

        if self.velocity > MAX_SPEED:
            self.velocity = MAX_SPEED

        if self.velocity < -MAX_SPEED:
            self.velocity = -MAX_SPEED

        self.position += self.velocity

        self.write(self.position)


class ServoController:

    def __init__(self):

        self.a_pan = Servo(HEAD_A_PAN_PIN)
        self.a_tilt = Servo(HEAD_A_TILT_PIN)

        self.b_pan = Servo(HEAD_B_PAN_PIN)
        self.b_tilt = Servo(HEAD_B_TILT_PIN)

    # -----------------------------

    def home(self):

        self.look(HOME_PAN, HOME_TILT)

    # -----------------------------

    def look(self, pan, tilt):

        pan = max(PAN_MIN, min(PAN_MAX, pan))
        tilt = max(TILT_MIN, min(TILT_MAX, tilt))

        self.a_pan.move_to(pan)
        self.a_tilt.move_to(tilt)

        self.b_pan.move_to(pan)
        self.b_tilt.move_to(tilt)

    # -----------------------------

    def head_a(self, pan, tilt):

        self.a_pan.move_to(pan)
        self.a_tilt.move_to(tilt)

    # -----------------------------

    def head_b(self, pan, tilt):

        self.b_pan.move_to(pan)
        self.b_tilt.move_to(tilt)

    # -----------------------------

    def update(self):

        self.a_pan.update()
        self.a_tilt.update()

        self.b_pan.update()
        self.b_tilt.update()

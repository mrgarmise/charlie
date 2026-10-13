"""Behavior intent; every actuator request crosses ServoController authority."""
import time
from servos import MotionError


class BehaviorManager:
    IDLE='IDLE'; SCAN='SCAN'; TRACK='TRACK'; HOME='HOME'; SLEEP='SLEEP'; ERROR='ERROR'

    def __init__(self, display=None, servos=None, scanner=None):
        self.display,self.servos,self.scanner=display,servos,scanner
        self.mode=self.IDLE
        self._scan_authorization=None
        self.last_action=time.ticks_ms()

    def set_mode(self, mode):
        if mode==self.SCAN:
            if self._scan_authorization is None:
                raise MotionError('CONTROL_AUTHORIZATION_REQUIRED')
            self.servos.validate_control(**self._scan_authorization)
        self.mode=mode
        if mode!=self.SCAN:self._scan_authorization=None
        self.last_action=time.ticks_ms()
        if self.display:self.display.status(mode)

    def look(self, pan, tilt, rate=None, **authorization):
        self.servos.look(pan,tilt,rate,**authorization)
        self.set_mode(self.TRACK)

    def gaze(self, pan, tilt, rate=None, **authorization):
        self.servos.look(pan,tilt,rate,**authorization)

    def home(self, **authorization):
        self.servos.home(**authorization)
        self.set_mode(self.HOME)

    def scan(self, **authorization):
        self.servos.validate_control(**authorization)
        if self.scanner is None:raise MotionError('SCANNER_UNAVAILABLE')
        self._scan_authorization=authorization
        self.set_mode(self.SCAN)

    def stop(self):
        self.servos.stop()
        self.set_mode(self.IDLE)

    def sleep(self):
        self.stop()
        self.set_mode(self.SLEEP)
        if self.display:self.display.show_text('SLEEP')

    def error(self, message):
        self.stop()
        self.set_mode(self.ERROR)
        if self.display:self.display.error(message)

    def update(self):
        if self.mode==self.SCAN:
            try:
                self.servos.validate_control(**(self._scan_authorization or {}))
                if not self.servos.moving():
                    self.servos.look(*self.scanner.update(),**self._scan_authorization)
            except MotionError:
                self.stop()

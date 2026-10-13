"""Hardware-free checks for the temporary Pico recovery lockout."""
import subprocess
import sys
from pathlib import Path


def test_recovery_lockout_without_hardware():
    root = Path(__file__).resolve().parents[1]
    script = r'''
import sys
import types

machine = types.ModuleType("machine")

class Pin:
    def __init__(self, number):
        self.number = number

class PWM:
    def __init__(self, pin):
        raise AssertionError("PWM must not initialize during recovery lockout")

machine.Pin = Pin
machine.PWM = PWM
sys.modules["machine"] = machine

sys.path.insert(0, "rp2040")

from servos import ServoController

controller = ServoController()

assert controller.a_pan.pwm is None
assert controller.a_tilt.pwm is None
assert controller.b_pan.pwm is None
assert controller.b_tilt.pwm is None

# Direct callers must be rejected independently of the command handler.
try:
    controller.look(138, 90)
except RuntimeError as exc:
    assert str(exc) == "HEAD_MOTION_DISARMED"
else:
    raise AssertionError("Direct movement was not rejected")

controller.update()

assert controller.a_pan.pwm is None
assert controller.a_pan.position == 90.0
assert controller.a_pan.target == 90.0

from commands import CommandHandler

class Behavior:
    mode = "IDLE"
    servos = controller
    def gaze(self, *args, **kwargs):
        raise AssertionError("Movement command reached behavior layer")

class Heartbeat:
    def beat(self):
        pass

class Command:
    name = "LOOK"
    def arg_float(self, index, default):
        return default

CommandHandler(Behavior(), None, Heartbeat()).handle(Command())
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ERR HEAD_MOTION_DISARMED" in result.stdout

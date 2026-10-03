"""
Cyberdeck Pico Agent

Main scheduler.

This file ties all modules together.

"""

import sys
import select
import time
import gc


from config import *

import protocol


from servos import ServoController
from scanner import Scanner
from heartbeat import Heartbeat

from display import Display
from behaviors import BehaviorManager

from commands import CommandHandler
from servos import MotionError
from motion_profile import LOCAL_ARM_PIN, LOCAL_ARM_ACTIVE_LEVEL, ELECTRICAL_GATE_CLEARED, CALIBRATED_ENVELOPE



# ==================================================
# HARDWARE INITIALIZATION
# ==================================================

print()
print("==============================")
print(" Cyberdeck Agent Starting")
print("==============================")
print()


display = Display()

# No default GPIO/PWM construction. A future reviewed deployment may provide
# a separate local arming input; actuator pins and Head B pins are forbidden.
arm_input = None
if LOCAL_ARM_PIN is not None and ELECTRICAL_GATE_CLEARED and CALIBRATED_ENVELOPE is not None:
    if LOCAL_ARM_PIN in (4,5,14,15):
        raise RuntimeError('ARM_INPUT_CONFLICT')
    from machine import Pin
    arm_pin = Pin(LOCAL_ARM_PIN, Pin.IN, Pin.PULL_UP)
    arm_input = lambda: arm_pin.value() == LOCAL_ARM_ACTIVE_LEVEL
servos = ServoController(arm_input=arm_input)

scanner = Scanner(servos)

heartbeat = Heartbeat()



behaviors = BehaviorManager(
    display=display,
    servos=servos,
    scanner=scanner
)



commands = CommandHandler(
    behaviors,
    display,
    heartbeat
)



# ==================================================
# SERIAL INPUT
# ==================================================

poll = select.poll()

poll.register(
    sys.stdin,
    select.POLLIN
)



print(
    "READY"
)



# ==================================================
# MAIN LOOP
# ==================================================

link_lost = False
while True:
    # Check expiry BEFORE processing an arriving command or running behaviors.
    # PING/reconnection may renew communications, never old motion authority.
    expired = servos.expire() or not heartbeat.alive()
    if expired:
        if not link_lost:
            link_lost = True
            servos.stop('WATCHDOG_EXPIRED')
            behaviors.set_mode(behaviors.IDLE)
            display.status(display.NO_BRAIN)
    elif link_lost:
        link_lost = False
        display.status(behaviors.mode)

    if poll.poll(0):
        line = sys.stdin.readline()
        commands.handle(protocol.parse(line))

    try:
        behaviors.update()
        servos.update()
    except MotionError:
        servos.stop('SCHEDULER_SAFETY_FAILURE')
        behaviors.set_mode(behaviors.IDLE)
    display.update()
    gc.collect()
    time.sleep_ms(20)

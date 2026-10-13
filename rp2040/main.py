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
from motion_profile import CALIBRATION_PROFILE, CALIBRATION_INPUT_ENABLED, AUTONOMOUS_MOTION_ENABLED, PERSISTENT_PROFILE_DIRECTORY



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
if LOCAL_ARM_PIN == 10:
    raise RuntimeError('GP10_CALIBRATION_ONLY_NOT_ARM')
if LOCAL_ARM_PIN is not None and ELECTRICAL_GATE_CLEARED and CALIBRATED_ENVELOPE is not None:
    if LOCAL_ARM_PIN in (4,5,14,15):
        raise RuntimeError('ARM_INPUT_CONFLICT')
    from machine import Pin
    arm_pin = Pin(LOCAL_ARM_PIN, Pin.IN, Pin.PULL_UP)
    arm_input = lambda: arm_pin.value() == LOCAL_ARM_ACTIVE_LEVEL
cal_input = None
if CALIBRATION_INPUT_ENABLED:
    from machine import Pin
    cal_pin = Pin(10, Pin.IN, Pin.PULL_UP)
    cal_input = lambda: cal_pin.value() == 0
selected_profile = CALIBRATED_ENVELOPE
quarantine_profile = None
profile_operation = None
force_empty_profile = False
if PERSISTENT_PROFILE_DIRECTORY is not None:
    from profile_store import load, quarantine, operation
    try:
        selected_profile = load(PERSISTENT_PROFILE_DIRECTORY)
        quarantine_profile = lambda reason: quarantine(PERSISTENT_PROFILE_DIRECTORY, selected_profile['calibration_id'], reason)
        profile_operation = lambda active: operation(PERSISTENT_PROFILE_DIRECTORY, selected_profile['calibration_id'], active)
    except MotionError as exc:
        # No fallback to an older static profile after persistent validation fails.
        print('PROFILE_BLOCKED',str(exc))
        selected_profile = None
        force_empty_profile = True
        AUTONOMOUS_MOTION_ENABLED = False
        arm_input = None
servos = ServoController(profile=selected_profile, electrical_gate=ELECTRICAL_GATE_CLEARED,
    arm_input=arm_input, calibration_profile=CALIBRATION_PROFILE, calibration_input=cal_input,
    calibration_sink=lambda record: print('CAL_EVENT',__import__('commands').json.dumps(record)),
    autonomous_enabled=AUTONOMOUS_MOTION_ENABLED, profile_quarantine=quarantine_profile,
    profile_operation=profile_operation, force_empty_profile=force_empty_profile)

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
    cal_status = servos.calibration.status()
    cal_state = cal_status['state']
    notice = None
    if not link_lost and cal_status.get('automated'):
        if cal_state == 'VERIFY_INITIAL':
            review = (cal_status.get('constraints') or {}).get('powered_start_review') or {}
            notice = 'START ' + str(review['pose']) + ' CONFIRM V' if review.get('pose') else 'START POSE UNVERIFIED'
        elif cal_state == 'PREPARED':
            notice = 'WAIT GP10 ' + str(cal_status.get('direction', ''))
        elif cal_state == 'MOVING': notice = 'MOVING'
        elif cal_state == 'AWAIT_CONFIRMATION': notice = 'OBSERVING'
        elif cal_state == 'READY': notice = 'CAL READY'
        elif cal_state == 'ABORTED': notice = 'CAL FAULT'
        elif cal_state == 'CLOSED': notice = 'TRACKING' if servos.status()['armed'] else 'CAL SAVED'
    if hasattr(display, 'capability_status'):
        display.capability_status(notice)
    display.update()
    gc.collect()
    time.sleep_ms(20)

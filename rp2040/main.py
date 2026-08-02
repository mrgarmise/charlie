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



# ==================================================
# HARDWARE INITIALIZATION
# ==================================================

print()
print("==============================")
print(" Cyberdeck Agent Starting")
print("==============================")
print()


display = Display()

servos = ServoController()

scanner = Scanner()

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

while True:


    # --------------------------
    # Check serial commands
    # --------------------------

    if poll.poll(0):

        line = sys.stdin.readline()


        cmd = protocol.parse(
            line
        )


        commands.handle(
            cmd
        )


    # --------------------------
    # Update systems
    # --------------------------

    behaviors.update()


    servos.update()


    display.update()


    # --------------------------
    # Communication watchdog
    # --------------------------

    if not heartbeat.alive():

        if behaviors.mode != behaviors.IDLE:

            behaviors.set_mode(
                behaviors.IDLE
            )



    gc.collect()


    time.sleep_ms(20)

    time.sleep_ms(20)

"""
Serial command protocol.

Every command is one line terminated by newline.

Examples:

PING
LOOK <pan> <tilt> [rate] <session> <epoch>
TRACK <pan> <tilt> [rate] <session> <epoch>
SCAN <session> <epoch>
HOME <session> <epoch>
SLEEP
THINK
HAPPY
ERROR
PROGRESS 50
PROGRESS_CLEAR
MESSAGE HELLO
RX
TX
STOP
"""

from config import *


class Command:

    def __init__(self, line=""):

        self.raw = line.strip()
        self.name = ""
        self.args = []

        if self.raw:

            pieces = self.raw.split()

            self.name = pieces[0].upper()
            self.args = pieces[1:]

    def arg_int(self, index, default=0):

        try:
            return int(self.args[index])
        except:
            return default

    def arg_float(self, index, default=0.0):

        try:
            return float(self.args[index])
        except:
            return default

    def arg_text(self, start=0, default=""):

        try:
            return " ".join(
                self.args[start:]
            )
        except:
            return default

    def __repr__(self):

        return (
            "<Command "
            + self.name
            + " "
            + str(self.args)
            + ">"
        )


VALID_COMMANDS = {

    "PING",
    "IDLE",
    "LOOK",
    "TRACK",
    "SCAN",
    "STOP",
    "HOME",
    "SLEEP",
    "WAKE",

    "THINK",
    "HAPPY",
    "ERROR",

    "PROGRESS",
    "PROGRESS_CLEAR",

    "MESSAGE",

    "RX",
    "TX",

    "STATUS",
    "VIEWPOINT",
    "MOTION_STATUS",
    "SESSION",
    "AUTHORIZE",
    "PRIMARY",
    "MOVE",
    "ARM",
    "CAL",
    "CAL_STATUS",
    "START_VERIFY",
    "AUTOSTART",
    "NECK_UNCERTAIN",
}


def parse(line):

    if not isinstance(line, str) or not line.strip():
        return None
    limit = 2048 if line.startswith(('CAL ', 'START_VERIFY ')) else COMMAND_BUFFER
    if len(line) > limit:
        return None
    cmd = Command(line)

    if cmd.name not in VALID_COMMANDS:
        return None

    return cmd


def ok(msg="OK"):
    return "OK " + msg + "\n"


def error(msg="ERROR"):
    return "ERR " + msg + "\n"


def heartbeat():
    return "ALIVE\n"

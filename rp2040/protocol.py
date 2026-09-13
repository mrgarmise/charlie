"""
Serial command protocol.

Every command is one line terminated by newline.

Examples:

PING
LOOK 90 40
TRACK 103 37
SCAN
HOME
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
}


def parse(line):

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

"""
Serial command protocol.

Every command is one line terminated by \n

Examples

PING
LOOK 90 40
TRACK 103 37
SCAN
HOME
SLEEP
WAKE
THINK
HAPPY
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

    def arg_int(self,index,default=0):

        try:
            return int(self.args[index])
        except:
            return default

    def arg_float(self,index,default=0.0):

        try:
            return float(self.args[index])
        except:
            return default

    def __repr__(self):

        return f"<Command {self.name} {self.args}>"

# -------------------------------------------------------------

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

    "LOCK",

    "ERROR",

    "STATUS"

}

# -------------------------------------------------------------

def parse(line):

    cmd = Command(line)

    if cmd.name not in VALID_COMMANDS:

        return None

    return cmd

# -------------------------------------------------------------

def ok(msg="OK"):

    return f"OK {msg}\n"

def error(msg="ERROR"):

    return f"ERR {msg}\n"

def heartbeat():

    return "ALIVE\n"

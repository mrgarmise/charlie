import serial
import time
import threading


class RP2040Controller:
    """
    Communication layer between Raspberry Pi and RP2040.

    The Pi sends high-level semantic commands.
    The RP2040 handles physical execution and display rendering.
    """

    def __init__(
        self,
        port="/dev/ttyACM0",
        baud=115200
    ):

        self.port = port
        self.baud = baud

        self.serial = None
        self.lock = threading.Lock()

        self.connected = False

        self.connect()

    def connect(self):

        try:

            self.serial = serial.Serial(
                self.port,
                self.baud,
                timeout=1
            )

            time.sleep(2)

            self.connected = True

            print(
                "RP2040 connected"
            )

        except Exception as e:

            print(
                f"RP2040 connection failed: {e}"
            )

            self.connected = False

    def send(self, command):

        if not self.connected:
            return False

        try:

            with self.lock:

                self.serial.write(
                    (
                        command
                        + "\n"
                    ).encode()
                )

            return True

        except Exception as e:

            print(
                f"RP2040 send error: {e}"
            )

            return False

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    def ping(self):

        return self.send(
            "PING"
        )

    # --------------------------------------------------
    # MOTION / ATTENTION
    # --------------------------------------------------

    def home(self):

        return self.send(
            "HOME"
        )

    def scan(self):

        return self.send(
            "SCAN"
        )

    def stop(self):

        return self.send(
            "STOP"
        )

    def look(
        self,
        pan,
        tilt
    ):

        return self.send(
            f"LOOK {pan} {tilt}"
        )

    def track(
        self,
        pan,
        tilt
    ):

        return self.send(
            f"TRACK {pan} {tilt}"
        )

    # --------------------------------------------------
    # PERSISTENT DISPLAY STATE
    # --------------------------------------------------

    def display(self, state):

        return self.send(
            str(state).upper()
        )

    # --------------------------------------------------
    # TRANSIENT FEEDBACK
    # --------------------------------------------------

    def think(self):

        return self.send(
            "THINK"
        )

    def happy(self):

        return self.send(
            "HAPPY"
        )

    def error_feedback(self):

        return self.send(
            "ERROR"
        )

    # --------------------------------------------------
    # PROCESS DISPLAY
    # --------------------------------------------------

    def progress(self, value):

        value = max(
            0,
            min(
                100,
                int(value)
            )
        )

        return self.send(
            f"PROGRESS {value}"
        )

    def progress_clear(self):

        return self.send(
            "PROGRESS_CLEAR"
        )

    # --------------------------------------------------
    # MESSAGE / COMM ACTIVITY
    # --------------------------------------------------

    def message(self, text):

        text = str(text).strip()

        if not text:
            return False

        return self.send(
            "MESSAGE "
            + text
        )

    def rx_activity(self):

        return self.send(
            "RX"
        )

    def tx_activity(self):

        return self.send(
            "TX"
        )
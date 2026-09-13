import serial
import time
import threading


class RP2040Controller:
    """
    Communication layer between Raspberry Pi and RP2040.

    The Pi sends high-level semantic commands.
    The RP2040 handles physical execution and display rendering.

    A background heartbeat keeps the RP2040 informed that the
    Pi-side Charlie process is alive.

    Any real outgoing command resets the heartbeat timer, so
    PING is only transmitted after a quiet period.
    """

    HEARTBEAT_INTERVAL = 3.0
    RECONNECT_INTERVAL = 3.0

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

        self.last_tx = 0.0
        self.running = True

        self.connect()

        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )

        self.heartbeat_thread.start()

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    def connect(self):

        try:

            with self.lock:

                if self.serial:

                    try:
                        self.serial.close()
                    except Exception:
                        pass

                self.serial = serial.Serial(
                    self.port,
                    self.baud,
                    timeout=1
                )

            # Opening the Pico serial device can reset
            # MicroPython. Give it time to come online.
            time.sleep(2)

            self.connected = True
            self.last_tx = time.monotonic()

            print(
                "RP2040 connected"
            )

            return True

        except Exception as e:

            self.connected = False

            print(
                f"RP2040 connection failed: {e}"
            )

            return False

    def _mark_disconnected(self):

        self.connected = False

        try:

            if self.serial:
                self.serial.close()

        except Exception:
            pass

        self.serial = None

    # --------------------------------------------------
    # SEND
    # --------------------------------------------------

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

            # Every real transmission proves the Pi is alive.
            #
            # This also means ordinary commands postpone
            # the next heartbeat automatically.
            self.last_tx = time.monotonic()

            return True

        except Exception as e:

            print(
                f"RP2040 send error: {e}"
            )

            self._mark_disconnected()

            return False

    # --------------------------------------------------
    # BACKGROUND HEARTBEAT / RECONNECT
    # --------------------------------------------------

    def _heartbeat_loop(self):

        while self.running:

            if not self.connected:

                self.connect()

                time.sleep(
                    self.RECONNECT_INTERVAL
                )

                continue

            quiet_for = (
                time.monotonic()
                - self.last_tx
            )

            if quiet_for >= self.HEARTBEAT_INTERVAL:

                self.send(
                    "PING"
                )

            time.sleep(
                0.25
            )

    # --------------------------------------------------
    # CONNECTION COMMANDS
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
    # DISPLAY
    # --------------------------------------------------

    def display(self, state):

        return self.send(
            str(state).upper()
        )

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
    # MESSAGE / ACTIVITY
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

    # --------------------------------------------------
    # CLEAN SHUTDOWN
    # --------------------------------------------------

    def close(self):

        self.running = False

        with self.lock:

            try:

                if self.serial:
                    self.serial.close()

            except Exception:
                pass

        self.connected = False
import serial
import time
import threading
import json
import uuid


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

        self.motion_epoch = None
        self.motion_owner = None
        self.link_session = None
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
            self.motion_epoch = self.motion_owner = None
            self.link_session = uuid.uuid4().hex
            # Reconnection never preserves queued motion or control grants.
            if not self.send("STOP") or not self.send("SESSION " + self.link_session):
                self._mark_disconnected()
                return False
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
        self.motion_epoch = self.motion_owner = None
        self.link_session = None

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
        self.motion_epoch = self.motion_owner = None
        return self.send("STOP")

    def look(self, pan, tilt, *, rate=None):
        # Optional slew rate is executed by the existing RP2040 servos.
        suffix = "" if rate is None else f" {float(rate)}"
        if getattr(self, 'motion_owner', None) == 'ACTIVE_VISION':
            if rate is None:return False
            return self._accepted(f"MOVE {self.link_session} {self.motion_epoch} {pan} {tilt} {rate}", "MOVE")
        return self.send(f"LOOK {pan} {tilt}{suffix}")

    def track(
        self,
        pan,
        tilt
    ):

        return self.send(
            f"TRACK {pan} {tilt}"
        )

    def viewpoint_status(self, timeout=1.0):
        """Query commanded firmware pose estimates, never measured positions.

        The same transport lock excludes heartbeat writes. Legacy STOP_HOLD
        replies are recognized for telemetry compatibility, not authority.
        """
        if not self.connected:
            return None
        try:
            with self.lock:
                self.serial.write(b"VIEWPOINT\n")
                self.last_tx = time.monotonic()
                deadline = self.last_tx + timeout
                old_timeout = self.serial.timeout
                try:
                    self.serial.timeout = min(.1, timeout)
                    while time.monotonic() < deadline:
                        parts = self.serial.readline().decode(errors="replace").split()
                        if len(parts) == 8 and parts[0] == "VIEWPOINT":
                            return dict(pan=float(parts[1]), tilt=float(parts[2]),
                                        b_pan=float(parts[3]), b_tilt=float(parts[4]),
                                        moving=bool(int(parts[5])),
                                        mode=parts[6],
                                        stop_hold=parts[7] == "STOP_HOLD",
                                        disarmed=parts[7] == "DISARMED",
                                        armed=parts[7] == "ARMED", pose_source="commanded_estimate",
                                        measured_position=None,
                                        pose_verified=False)
                finally:
                    self.serial.timeout = old_timeout
            return None
        except Exception:
            self._mark_disconnected()
            return None

    def _exchange(self, command, prefix, timeout=1.0):
        if not self.connected:return None
        try:
            with self.lock:
                self.serial.write((command + "\n").encode())
                self.last_tx = time.monotonic()
                deadline = self.last_tx + timeout
                old_timeout = self.serial.timeout
                try:
                    self.serial.timeout = min(.1, timeout)
                    while time.monotonic() < deadline:
                        line = self.serial.readline().decode(errors="replace").strip()
                        if line.startswith(prefix):return line
                        if prefix.startswith("OK ") and line.startswith("ERR "):
                            return line
                finally:self.serial.timeout = old_timeout
        except Exception:
            self._mark_disconnected()
        return None

    def _accepted(self, command, name):
        answer = self._exchange(command, "OK " + name)
        accepted = answer == "OK " + name
        if not accepted:
            self.motion_epoch = self.motion_owner = None
        return accepted

    def motion_status(self):
        answer = self._exchange("MOTION_STATUS", "MOTION_STATUS ")
        if not answer:return None
        try:
            status = json.loads(answer.split(" ",1)[1])
            if status.get("schema") != "charlie-motion-authority-v1":return None
            return status
        except (ValueError,TypeError):return None

    def request_active_vision(self, transition="INITIAL"):
        # Requests control only. There is intentionally no host physical-arm API.
        status = self.motion_status()
        if (not status or not status.get("armed") or not status.get("envelope")
                or not status.get("electrical_gate_cleared")
                or not status.get("local_arm_available")
                or status.get("session") != self.link_session):
            return False
        revision = status["epoch"]
        if not self._accepted(f"AUTHORIZE ACTIVE_VISION {self.link_session} {revision} {transition}","AUTHORIZE"):
            return False
        self.motion_epoch, self.motion_owner = revision, "ACTIVE_VISION"
        return True

    def primary_ownership(self):
        status = self.motion_status()
        if not status or status.get("session") != self.link_session:return False
        accepted = self._accepted(f"PRIMARY {self.link_session} {status['epoch']}","PRIMARY")
        self.motion_epoch = self.motion_owner = None
        return accepted

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
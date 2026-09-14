import json
import socket
import threading
import time
import itertools
from dataclasses import dataclass


@dataclass
class AttentionAlignState:
    active: bool = False
    direction: str | None = None
    start_pan: int = 90
    last_pan: int = 90
    start_yaw: float = 0.0
    target_rotation: float = 0.0
    yaw_sign: int = 0
    started_at: float = 0.0
    reason: str | None = None


class ElegooMobileBase:
    """
    Charlie's independent ELEGOO-car interface.

    Transport:
      - dedicated background RX thread
      - immediate heartbeat echo
      - pending-command events
      - send locking

    High-level capabilities:
      - camera pan
      - yaw telemetry
      - continuous pivot
      - explicit stop
      - yaw-guided coordinated attention alignment
    """

    HOST = "192.168.4.1"
    PORT = 100

    PAN_CENTER = 90
    PAN_MIN = 20
    PAN_MAX = 160

    def __init__(
        self,
        host=HOST,
        port=PORT,
        timeout=2.0,
        turn_speed=75,
        max_align_seconds=3.0,
        min_pan_step=2,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout

        self.turn_speed = turn_speed
        self.max_align_seconds = max_align_seconds
        self.min_pan_step = min_pan_step

        self.sock = None
        self._rx_buffer = ""
        self._counter = itertools.count(1)

        self._running = False
        self._rx_thread = None

        self._send_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending = {}

        self.align = AttentionAlignState()

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    def connect(self):
        if (
            self.sock is not None
            and self._running
        ):
            return

        self.close()

        self.sock = socket.create_connection(
            (self.host, self.port),
            timeout=5,
        )
        self.sock.settimeout(0.25)

        self._running = True

        self._rx_thread = threading.Thread(
            target=self._receive_loop,
            name="ElegooRX",
            daemon=True,
        )
        self._rx_thread.start()

    def close(self):
        self._running = False

        sock = self.sock
        self.sock = None

        if sock is not None:
            try:
                sock.shutdown(
                    socket.SHUT_RDWR
                )
            except OSError:
                pass

            try:
                sock.close()
            except OSError:
                pass

        if self._rx_thread is not None:
            self._rx_thread.join(
                timeout=1
            )
            self._rx_thread = None

        with self._pending_lock:
            for item in self._pending.values():
                item["event"].set()

            self._pending.clear()

        self._rx_buffer = ""

    def __enter__(self):
        self.connect()
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        self.close()

    # --------------------------------------------------
    # BACKGROUND RECEIVE / HEARTBEAT
    # --------------------------------------------------

    def _receive_loop(self):
        while (
            self._running
            and self.sock is not None
        ):
            try:
                data = self.sock.recv(4096)

                if not data:
                    break

                self._rx_buffer += (
                    data.decode(
                        errors="replace"
                    )
                )

                self._process_buffer()

            except socket.timeout:
                continue

            except OSError:
                break

        self._running = False

    def _process_buffer(self):
        while True:
            start = self._rx_buffer.find(
                "{"
            )

            if start == -1:
                self._rx_buffer = ""
                return

            end = self._rx_buffer.find(
                "}",
                start,
            )

            if end == -1:
                if start > 0:
                    self._rx_buffer = (
                        self._rx_buffer[start:]
                    )

                return

            frame = self._rx_buffer[
                start:end + 1
            ]

            self._rx_buffer = (
                self._rx_buffer[
                    end + 1:
                ]
            )

            self._handle_frame(frame)

    def _handle_frame(self, frame):
        if frame == "{Heartbeat}":
            try:
                self._send_raw(
                    b"{Heartbeat}"
                )
            except Exception:
                pass

            return

        if frame == "{ok}":
            with self._pending_lock:
                if len(self._pending) == 1:
                    ident = next(
                        iter(
                            self._pending
                        )
                    )

                    item = (
                        self._pending[ident]
                    )

                    item["response"] = (
                        frame
                    )

                    item["event"].set()

            return

        inside = frame.strip("{}")

        if "_" not in inside:
            return

        ident, value = inside.split(
            "_",
            1,
        )

        with self._pending_lock:
            item = self._pending.get(
                ident
            )

            if item is not None:
                item["response"] = (
                    frame
                )
                item["value"] = value
                item["event"].set()

    # --------------------------------------------------
    # COMMAND TRANSPORT
    # --------------------------------------------------

    def _send_raw(self, raw):
        sock = self.sock

        if (
            sock is None
            or not self._running
        ):
            raise ConnectionError(
                "Elegoo is not connected"
            )

        with self._send_lock:
            sock.sendall(raw)

    def _next_id(self, prefix="cmd"):
        return (
            f"{prefix}"
            f"{next(self._counter)}"
        )

    def _send(
        self,
        payload,
        expected_id=None,
        timeout=None,
    ):
        self.connect()

        pending = None

        if expected_id is not None:
            pending = {
                "event": threading.Event(),
                "response": None,
                "value": None,
            }

            with self._pending_lock:
                self._pending[
                    expected_id
                ] = pending

        try:
            raw = json.dumps(
                payload,
                separators=(",", ":"),
            ).encode()

            try:
                self._send_raw(raw)

            except (
                OSError,
                ConnectionError,
            ):
                # One reconnect/retry is useful because the
                # ESP32 may close an idle TCP connection.
                self.close()
                self.connect()
                self._send_raw(raw)

            if pending is None:
                return {
                    "ok": True,
                    "response": None,
                    "value": None,
                }

            wait_time = (
                timeout
                if timeout is not None
                else self.timeout
            )

            if not pending[
                "event"
            ].wait(wait_time):
                raise TimeoutError(
                    f"timeout waiting for "
                    f"{expected_id}"
                )

            return {
                "ok": (
                    pending["response"]
                    is not None
                ),
                "response": (
                    pending["response"]
                ),
                "value": (
                    pending["value"]
                ),
            }

        finally:
            if expected_id is not None:
                with self._pending_lock:
                    self._pending.pop(
                        expected_id,
                        None,
                    )

    # --------------------------------------------------
    # SENSORS / HEAD
    # --------------------------------------------------

    def yaw(self):
        ident = self._next_id(
            "yaw"
        )

        result = self._send(
            {
                "N": 24,
                "H": ident,
            },
            expected_id=ident,
            timeout=0.8,
        )

        value = result["value"]

        if value is None:
            raise TimeoutError(
                "ELEGOO yaw timeout"
            )

        try:
            return float(value)

        except ValueError as exc:
            raise ValueError(
                f"invalid yaw response: "
                f"{result['response']}"
            ) from exc

    def pan(self, degrees):
        degrees = max(
            self.PAN_MIN,
            min(
                self.PAN_MAX,
                int(round(degrees)),
            ),
        )

        ident = self._next_id(
            "pan"
        )

        result = self._send(
            {
                "N": 5,
                "H": ident,
                "D1": 1,
                "D2": degrees,
            },
            expected_id=ident,
            timeout=1.2,
        )

        if not result["ok"]:
            raise TimeoutError(
                "ELEGOO pan ACK timeout"
            )

        return degrees

    # --------------------------------------------------
    # CHASSIS
    # --------------------------------------------------

    def start_pivot(
        self,
        direction,
        speed=None,
    ):
        speed = (
            speed
            if speed is not None
            else self.turn_speed
        )

        if direction == "LEFT":
            d1 = 1
        elif direction == "RIGHT":
            d1 = 2
        else:
            raise ValueError(
                "direction must be "
                "LEFT or RIGHT"
            )

        ident = self._next_id(
            "pivot"
        )

        result = self._send(
            {
                "N": 3,
                "H": ident,
                "D1": d1,
                "D2": int(speed),
            },
            expected_id=ident,
            timeout=1.0,
        )

        if not result["ok"]:
            raise TimeoutError(
                "ELEGOO pivot ACK timeout"
            )

    def stop(self):
        if self.sock is None:
            self.align.active = False
            return

        ident = self._next_id(
            "stop"
        )

        try:
            self._send(
                {
                    "N": 1,
                    "H": ident,
                    "D1": 0,
                    "D2": 0,
                    "D3": 0,
                },
                expected_id=ident,
                timeout=0.5,
            )

        except Exception:
            # Best-effort stop fallback using the stock stop
            # command which does not need an H-tagged reply.
            try:
                self._send(
                    {
                        "N": 102,
                        "H": self._next_id(
                            "stopstock"
                        ),
                        "D1": 9,
                    },
                    expected_id=None,
                )
            except Exception:
                pass

        self.align.active = False

    # --------------------------------------------------
    # COORDINATED ATTENTION ALIGNMENT
    # --------------------------------------------------

    def begin_attention_align(
        self,
        current_pan,
    ):
        current_pan = int(
            round(current_pan)
        )

        if (
            80
            <= current_pan
            <= 100
        ):
            return False

        if current_pan < 90:
            direction = "RIGHT"
            target_rotation = (
                90 - current_pan
            )
            yaw_sign = +1

        else:
            direction = "LEFT"
            target_rotation = (
                current_pan - 90
            )
            yaw_sign = -1

        start_yaw = self.yaw()

        self.align = (
            AttentionAlignState(
                active=True,
                direction=direction,
                start_pan=current_pan,
                last_pan=current_pan,
                start_yaw=start_yaw,
                target_rotation=(
                    target_rotation
                ),
                yaw_sign=yaw_sign,
                started_at=(
                    time.monotonic()
                ),
            )
        )

        try:
            self.start_pivot(
                direction
            )

        except Exception:
            self.align.active = False
            raise

        return True

    def update_attention_align(
        self,
        face_visible=True,
    ):
        state = self.align

        if not state.active:
            return {
                "active": False,
                "done": True,
                "reason": state.reason,
            }

        if not face_visible:
            state.reason = (
                "face_lost"
            )
            self.stop()

            return {
                "active": False,
                "done": True,
                "reason": state.reason,
            }

        elapsed = (
            time.monotonic()
            - state.started_at
        )

        if (
            elapsed
            > self.max_align_seconds
        ):
            state.reason = "timeout"
            self.stop()

            return {
                "active": False,
                "done": True,
                "reason": state.reason,
            }

        try:
            yaw_now = self.yaw()

        except Exception:
            state.reason = "yaw_error"
            self.stop()

            return {
                "active": False,
                "done": True,
                "reason": state.reason,
            }

        yaw_delta = (
            yaw_now
            - state.start_yaw
        )

        progress = (
            yaw_delta
            * state.yaw_sign
        )

        if progress < -5.0:
            state.reason = (
                "wrong_way_yaw"
            )
            self.stop()

            return {
                "active": False,
                "done": True,
                "reason": state.reason,
                "yaw_delta": yaw_delta,
            }

        desired_pan = int(
            round(
                state.start_pan
                + yaw_delta
            )
        )

        desired_pan = max(
            self.PAN_MIN,
            min(
                self.PAN_MAX,
                desired_pan,
            ),
        )

        if state.start_pan < 90:
            desired_pan = min(
                desired_pan,
                90,
            )
        else:
            desired_pan = max(
                desired_pan,
                90,
            )

        if (
            abs(
                desired_pan
                - state.last_pan
            )
            >= self.min_pan_step
        ):
            try:
                state.last_pan = self.pan(
                    desired_pan
                )

            except Exception:
                state.reason = (
                    "pan_error"
                )
                self.stop()

                return {
                    "active": False,
                    "done": True,
                    "reason": state.reason,
                }

        if (
            progress
            >= state.target_rotation
        ):
            state.reason = "aligned"
            self.stop()

            try:
                state.last_pan = (
                    self.pan(90)
                )
            except Exception:
                pass

            return {
                "active": False,
                "done": True,
                "reason": "aligned",
                "yaw_delta": yaw_delta,
                "pan": state.last_pan,
            }

        return {
            "active": True,
            "done": False,
            "reason": None,
            "yaw_delta": yaw_delta,
            "progress": progress,
            "target": (
                state.target_rotation
            ),
            "pan": state.last_pan,
        }

    def cancel_attention_align(
        self,
        reason="cancelled",
    ):
        if self.align.active:
            self.align.reason = reason
            self.stop()

    # --------------------------------------------------
    # STATUS
    # --------------------------------------------------

    @property
    def connected(self):
        return (
            self.sock is not None
            and self._running
        )

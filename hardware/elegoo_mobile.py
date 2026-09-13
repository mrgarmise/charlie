import json
import re
import socket
import time
from dataclasses import dataclass

FRAME_RE = re.compile(rb"\{[^{}]*\}")
YAW_RE = re.compile(r"^\{([^_{}]+)_(-?\d+(?:\.\d+)?)\}$")


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
    def __init__(
        self,
        host="192.168.4.1",
        port=100,
        turn_speed=75,
        max_align_seconds=3.0,
        min_pan_step=2,
    ):
        self.host = host
        self.port = port
        self.turn_speed = turn_speed
        self.max_align_seconds = max_align_seconds
        self.min_pan_step = min_pan_step

        self.sock = None
        self.buffer = bytearray()
        self.seq = 0

        self.align = AttentionAlignState()

    def connect(self):
        if self.sock is not None:
            return

        self.sock = socket.create_connection(
            (self.host, self.port),
            timeout=3.0,
        )
        self.sock.settimeout(0.04)
        self._frames(0.15)

    def close(self):
        try:
            self.stop()
        except Exception:
            pass

        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass

        self.sock = None

    def _ensure_connected(self):
        if self.sock is None:
            self.connect()

    def _send(self, obj):
        self._ensure_connected()
        payload = json.dumps(
            obj,
            separators=(",", ":"),
        ).encode()
        self.sock.sendall(payload)

    def _frames(self, duration=0.04):
        if self.sock is None:
            return []

        end = time.monotonic() + duration
        out = []

        while time.monotonic() < end:
            try:
                data = self.sock.recv(4096)

                if not data:
                    raise ConnectionError(
                        "ELEGOO peer closed connection"
                    )

                self.buffer.extend(data)

            except socket.timeout:
                pass

            while True:
                match = FRAME_RE.search(self.buffer)

                if not match:
                    break

                frame = bytes(match.group())
                del self.buffer[:match.end()]

                if frame == b"{Heartbeat}":
                    self.sock.sendall(b"{Heartbeat}")
                else:
                    out.append(
                        frame.decode(errors="replace")
                    )

            time.sleep(0.001)

        return out

    def _next_id(self, prefix):
        self.seq += 1
        return f"{prefix}{self.seq}"

    def _wait_ack(self, command_id, timeout=0.8):
        expected = "{" + command_id + "_ok}"
        end = time.monotonic() + timeout

        while time.monotonic() < end:
            for frame in self._frames(0.035):
                if frame == expected:
                    return True

        return False

    def yaw(self, timeout=0.5):
        command_id = self._next_id("yaw")

        self._send({
            "N": 24,
            "H": command_id,
        })

        end = time.monotonic() + timeout

        while time.monotonic() < end:
            for frame in self._frames(0.035):
                match = YAW_RE.match(frame)

                if (
                    match
                    and match.group(1) == command_id
                ):
                    return float(match.group(2))

        raise TimeoutError("ELEGOO yaw timeout")

    def pan(self, degrees):
        degrees = max(
            20,
            min(160, int(round(degrees))),
        )

        command_id = self._next_id("pan")

        self._send({
            "N": 5,
            "H": command_id,
            "D1": 1,
            "D2": degrees,
        })

        if not self._wait_ack(command_id):
            raise TimeoutError(
                "ELEGOO pan ACK timeout"
            )

        return degrees

    def start_pivot(self, direction, speed=None):
        speed = speed or self.turn_speed

        if direction == "LEFT":
            d1 = 1
        elif direction == "RIGHT":
            d1 = 2
        else:
            raise ValueError(direction)

        command_id = self._next_id("pivot")

        self._send({
            "N": 3,
            "H": command_id,
            "D1": d1,
            "D2": int(speed),
        })

        if not self._wait_ack(command_id):
            raise TimeoutError(
                "ELEGOO pivot ACK timeout"
            )

    def stop(self):
        if self.sock is None:
            return

        command_id = self._next_id("stop")

        self._send({
            "N": 1,
            "H": command_id,
            "D1": 0,
            "D2": 0,
            "D3": 0,
        })

        self._wait_ack(
            command_id,
            timeout=0.35,
        )

        self.align.active = False

    def begin_attention_align(self, current_pan):
        current_pan = int(round(current_pan))

        if 80 <= current_pan <= 100:
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

        self.align = AttentionAlignState(
            active=True,
            direction=direction,
            start_pan=current_pan,
            last_pan=current_pan,
            start_yaw=start_yaw,
            target_rotation=target_rotation,
            yaw_sign=yaw_sign,
            started_at=time.monotonic(),
        )

        try:
            self.start_pivot(direction)
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
            state.reason = "face_lost"
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

        if elapsed > self.max_align_seconds:
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
            state.reason = "wrong_way_yaw"
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
            20,
            min(160, desired_pan),
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
                state.reason = "pan_error"
                self.stop()

                return {
                    "active": False,
                    "done": True,
                    "reason": state.reason,
                }

        if progress >= state.target_rotation:
            state.reason = "aligned"
            self.stop()

            try:
                state.last_pan = self.pan(90)
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
            "target": state.target_rotation,
            "pan": state.last_pan,
        }

    def cancel_attention_align(
        self,
        reason="cancelled",
    ):
        if self.align.active:
            self.align.reason = reason
            self.stop()

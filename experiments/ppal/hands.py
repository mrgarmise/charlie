"""PPAL-1 twin-stick command bridge with acknowledgements and neutral release.

This defines a small transport protocol; it does not assume RetroArch's actual
input format. A receiver or adapter must translate these button names.
"""

from dataclasses import dataclass
import json
import socket

from .models import Action


AXES = {
    "STAY": (), "NONE": (),
    "N": ("up",), "NE": ("up", "right"), "E": ("right",),
    "SE": ("down", "right"), "S": ("down",),
    "SW": ("down", "left"), "W": ("left",), "NW": ("up", "left"),
}


@dataclass(frozen=True)
class ButtonCommand:
    sequence: int
    buttons: tuple[str, ...]
    duration_ms: int

    def as_message(self) -> dict:
        return {"type": "step", "sequence": self.sequence,
                "buttons": list(self.buttons), "duration_ms": self.duration_ms}


def encode(action: Action, sequence: int, duration_ms: int = 100) -> ButtonCommand:
    if sequence < 1 or not 30 <= duration_ms <= 500:
        raise ValueError("sequence must be positive; duration_ms must be 30..500")
    if action.move not in AXES or action.move == "NONE":
        raise ValueError(f"invalid movement: {action.move}")
    if action.fire not in AXES or action.fire == "STAY":
        raise ValueError(f"invalid firing: {action.fire}")
    buttons = tuple("move_" + key for key in AXES[action.move]) + tuple(
        "fire_" + key for key in AXES[action.fire])
    return ButtonCommand(sequence, buttons, duration_ms)


class RecordingSink:
    """Does not transmit; useful for previewing PPAL actions."""

    def __init__(self) -> None:
        self.commands: list[dict] = []
        self.sequence = 0

    def execute(self, action: Action, duration_ms: int = 100) -> dict:
        self.sequence += 1
        message = encode(action, self.sequence, duration_ms).as_message()
        self.commands.append(message)
        return message

    def close(self) -> None:
        self.sequence += 1
        self.commands.append({"type": "release", "sequence": self.sequence, "buttons": []})

    def __enter__(self) -> "RecordingSink":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class TCPCommandSink:
    """Send newline-delimited JSON to a receiver that acknowledges each sequence."""

    def __init__(self, host: str, port: int, timeout: float = 2.0) -> None:
        self.connection = socket.create_connection((host, port), timeout=timeout)
        self.connection.settimeout(timeout)
        self.stream = self.connection.makefile("rwb", buffering=0)
        self.sequence = 0
        self.closed = False

    def _send(self, message: dict) -> dict:
        wire = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        self.stream.write(wire)
        response = self.stream.readline(4097)
        if len(response) > 4096 or not response.endswith(b"\n"):
            raise ConnectionError("controller acknowledgement missing or too long")
        try:
            acknowledgement = json.loads(response)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ConnectionError("invalid controller acknowledgement") from exc
        if acknowledgement.get("ack") != message["sequence"] or acknowledgement.get("ok") is not True:
            raise ConnectionError(f"controller rejected sequence {message['sequence']}")
        return message

    def execute(self, action: Action, duration_ms: int = 100) -> dict:
        if self.closed:
            raise RuntimeError("controller is closed")
        next_sequence = self.sequence + 1
        message = encode(action, next_sequence, duration_ms).as_message()
        self.sequence = next_sequence
        return self._send(message)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.sequence += 1
            self._send({"type": "release", "sequence": self.sequence, "buttons": []})
        finally:
            self.stream.close()
            self.connection.close()

    def __enter__(self) -> "TCPCommandSink":
        return self

    def __exit__(self, exc_type: object, *args: object) -> None:
        if exc_type is None:
            self.close()
        else:
            try:
                self.close()
            except (OSError, ConnectionError):
                pass  # Preserve the original error when the receiver is gone.

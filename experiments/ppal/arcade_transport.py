"""Adapter for charlie-arcade's existing text TCP controller protocol.

The Zero-side launcher accepts one ASCII command per line and replies OK or
ERROR. It neutralizes its virtual controller when the TCP connection closes.
This module runs on Charlie/Mint, never on the arcade Pi Zero.
"""

import socket
import time
from typing import Callable

from .hands import encode
from .models import Action


POSITIONS = {"STAY": "CENTER", "NONE": "CENTER", "N": "UP", "NE": "UP_RIGHT",
             "E": "RIGHT", "SE": "DOWN_RIGHT", "S": "DOWN", "SW": "DOWN_LEFT",
             "W": "LEFT", "NW": "UP_LEFT"}


def positions_for(action: Action) -> tuple[str, str]:
    """Current Zero-side controller's absolute left/right stick commands."""
    if action.move not in POSITIONS or action.move == "NONE":
        raise ValueError(f"invalid movement direction: {action.move}")
    if action.fire not in POSITIONS or action.fire == "STAY":
        raise ValueError(f"invalid firing direction: {action.fire}")
    return "LS_" + POSITIONS[action.move], "RS_" + POSITIONS[action.fire]


def controls_for(action: Action) -> frozenset[str]:
    """Map PPAL's independent move/fire directions to left/right sticks."""
    buttons = encode(action, sequence=1).buttons
    return frozenset(
        ("LS_" if button.startswith("move_") else "RS_") + button.split("_", 1)[1].upper()
        for button in buttons
    )


class ArcadeController:
    def __init__(self, host: str, port: int = 8765, timeout: float = 2.0,
                 sleep: Callable[[float], None] = time.sleep,
                 protocol: str = "positions", pulse: bool = True) -> None:
        if protocol not in ("positions", "legacy"):
            raise ValueError("protocol must be positions or legacy")
        self.protocol = protocol
        self.pulse = pulse
        self.connection = socket.create_connection((host, port), timeout=timeout)
        self.connection.settimeout(timeout)
        self.stream = self.connection.makefile("rwb", buffering=0)
        self.sleep = sleep
        self.held: frozenset[str] = frozenset()
        self.positions = ("LS_CENTER", "RS_CENTER")
        self.closed = False
        try:
            self._command("NEUTRAL")
        except BaseException:
            self.stream.close()
            self.connection.close()
            raise

    def _command(self, command: str) -> None:
        self.stream.write((command + "\n").encode("ascii"))
        response = self.stream.readline(64)
        if response != b"OK\n":
            raise ConnectionError(f"arcade rejected {command}: {response[:32]!r}")

    def execute(self, action: Action, duration_ms: int = 100) -> None:
        if self.closed:
            raise RuntimeError("controller closed")
        # Validate the entire action before modifying any held controls.
        desired_positions = positions_for(action)
        desired = controls_for(action) if self.protocol == "legacy" else frozenset()
        if not 30 <= duration_ms <= 500:
            raise ValueError("duration_ms must be 30..500")
        try:
            if self.protocol == "positions":
                for current, new in zip(self.positions, desired_positions):
                    if current != new:
                        self._command(new)
                self.positions = desired_positions
            else:
                for control in sorted(self.held - desired):
                    self._command(control + "_UP")
                for control in sorted(desired - self.held):
                    self._command(control + "_DOWN")
                self.held = desired
            self.sleep(duration_ms / 1000)
            if self.pulse:
                if self.protocol == "positions":
                    for command in ("LS_CENTER", "RS_CENTER"):
                        self._command(command)
                    self.positions = ("LS_CENTER", "RS_CENTER")
                else:
                    for control in sorted(self.held):
                        self._command(control + "_UP")
                    self.held = frozenset()
        except BaseException:
            # A dropped connection makes the Zero-side launcher neutralize too.
            try:
                self.close()
            except OSError:
                pass
            raise

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self._command("NEUTRAL")
        finally:
            self.held = frozenset()
            self.positions = ("LS_CENTER", "RS_CENTER")
            self.stream.close()
            self.connection.close()

    def __enter__(self) -> "ArcadeController":
        return self

    def __exit__(self, exc_type: object, *args: object) -> None:
        if exc_type is None:
            self.close()
        else:
            try:
                self.close()
            except OSError:
                pass

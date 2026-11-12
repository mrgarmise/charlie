"""Adapter for charlie-arcade's existing text TCP controller protocol.

The Zero-side launcher accepts one ASCII command per line and replies OK or
ERROR. It neutralizes its virtual controller when the TCP connection closes.
This module runs on Charlie/Mint, never on the arcade Pi Zero.
"""

import socket
import os
import time
import threading
from typing import Callable

from .hands import encode
from .models import Action
from .controller_sandbox import ControllerSandbox, validate_controls


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
    buttons = encode(Action(action.move,action.fire), sequence=1).buttons
    return frozenset(
        ("LS_" if button.startswith("move_") else "RS_") + button.split("_", 1)[1].upper()
        for button in buttons
    )


class ArcadeController:
    def __init__(self, host: str, port: int = 8765, timeout: float = 2.0,
                 sleep: Callable[[float], None] = time.sleep,
                 protocol: str = "positions", pulse: bool = True,
                 require_lease: bool | None = None) -> None:
        if protocol not in ("positions", "legacy"):
            raise ValueError("protocol must be positions or legacy")
        self.protocol = protocol
        self.require_lease = (os.environ.get('CHARLIE_CONTROLLER_LEASE') == 'required'
                              if require_lease is None else require_lease)
        self.pulse = pulse
        self.connection = socket.create_connection((host, port), timeout=timeout)
        self.connection.settimeout(timeout)
        self.stream = self.connection.makefile("rwb", buffering=0)
        self.sleep = sleep
        self.held: frozenset[str] = frozenset()
        self.positions = ("LS_CENTER", "RS_CENTER")
        self.closed = False
        self.last_execution = None
        self.last_command = None
        self.sandbox = ControllerSandbox()
        self._wire_lock = threading.RLock()
        self._hold_timer = None
        self._hold_generation = 0
        try:
            self._command("NEUTRAL")
            if self.require_lease:
                self.renew_lease()
        except BaseException:
            self.stream.close()
            self.connection.close()
            raise

    def _command(self, command: str) -> None:
        with self._wire_lock:
            # Validation failures emit nothing and retain only the previously
            # permitted state. Transport failures cannot leave a live stream.
            try:self._authorized_command(command)
            except (OSError, ConnectionError):
                self.closed = True
                if self._hold_timer is not None:self._hold_timer.cancel()
                self.sandbox.commit(set())
                try:
                    self.stream.write(b'NEUTRAL\n')
                    self.stream.readline(64)
                except OSError:pass
                self.stream.close();self.connection.close()
                raise

    def _authorized_command(self, command):
        if self.closed and command != 'NEUTRAL':
            raise RuntimeError('controller closed')
        if command == 'LEASE' and self.require_lease:
            held = set(self.sandbox.held)
        else:
            command, held = self.sandbox.prepare(command)
        self.last_command = {'command':command, 'write_started_at':time.monotonic()}
        self.stream.write((command + "\n").encode("ascii"))
        self.last_command['write_completed_at'] = time.monotonic()
        response = self.stream.readline(64)
        self.last_command['ack_at'] = time.monotonic()
        self.last_command['accepted'] = response == b'OK\n'
        if response != b"OK\n":
            raise ConnectionError(f"arcade rejected {command}: {response[:32]!r}")
        self.sandbox.commit(held)
        self._hold_generation += 1
        if self._hold_timer is not None:
            self._hold_timer.cancel()
        # Bounded safety lease, not an anti-spam limit. Each permitted new
        # pulse/hold renews it; stopped callers cannot hold buttons forever.
        if command != 'NEUTRAL' and (held or command == 'LEASE' or command.startswith(('LS_', 'RS_', 'DPAD_'))):
            self._hold_timer = threading.Timer(.75 if self.require_lease else .5, self._expire_hold,
                                              args=(self._hold_generation,))
            self._hold_timer.daemon = True
            self._hold_timer.start()

    def _expire_hold(self, generation=None):
        try:
            with self._wire_lock:
                if generation is not None and generation != self._hold_generation:
                    return
                self._command('NEUTRAL')
                self.held = frozenset()
                self.positions = ('LS_CENTER', 'RS_CENTER')
        except (OSError, ValueError):self.connection.close()

    def renew_lease(self):
        """Call from progressing gameplay, never an autonomous heartbeat thread.

        Requires the server-side one-second LEASE protocol. A rejected renewal
        closes the transport; reconnect and recompute intent after expiration.
        """
        if not self.require_lease:
            raise RuntimeError('server lease was not required for this connection')
        self._command('LEASE')

    def execute(self, action: Action, duration_ms: int = 100, *, cancel_event=None, deadline=None) -> None:
        if self.closed:
            raise RuntimeError("controller closed")
        # Validate the entire action before modifying any held controls.
        desired_positions = positions_for(action)
        buttons = validate_controls(action.controls, self.sandbox.held)
        desired = controls_for(action) if self.protocol == "legacy" else frozenset()
        if not 30 <= duration_ms <= 500:
            raise ValueError("duration_ms must be 30..500")
        timing = {"started_at":time.monotonic(), "move":action.move,
                  "fire":action.fire, "duration_ms":duration_ms, "commands":[]}
        self.last_execution = timing
        def check_cancel():
            if (cancel_event is not None and cancel_event.is_set()) or (deadline is not None and time.monotonic()>=deadline):
                timing['cancelled_at']=time.monotonic()
                raise InterruptedError('bounded controller operation cancelled')
        def send(command):
            check_cancel()
            began = time.monotonic()
            self._command(command)
            acknowledged=time.monotonic()
            wire=getattr(self,'last_command',None) or {}
            timing["commands"].append({"command":command, "sent_at":began,
                "write_completed_at":wire.get('write_completed_at') if wire.get('command')==command else None,
                "ack_at":acknowledged})
            if command.startswith('RS_'):
                if command=='RS_CENTER' or command.endswith('_UP') and self.protocol=='legacy':
                    timing['fire_off_submitted_at']=began
                    timing['fire_off_ack_at']=acknowledged
                else:
                    timing.setdefault('fire_on_submitted_at',began)
                    timing['fire_on_ack_at']=acknowledged
        try:
            check_cancel()
            if self.require_lease:
                self.renew_lease()
            for button in buttons:
                send(button+'_DOWN')
            if self.protocol == "positions":
                for current, new in zip(self.positions, desired_positions):
                    if current != new:
                        send(new)
                self.positions = desired_positions
            else:
                for control in sorted(self.held - desired):
                    send(control + "_UP")
                for control in sorted(desired - self.held):
                    send(control + "_DOWN")
                self.held = desired
            timing["controls_ready_at"] = time.monotonic()
            if cancel_event is None and deadline is None:self.sleep(duration_ms / 1000)
            else:
                wait=duration_ms/1000
                if deadline is not None:wait=min(wait,max(0.,deadline-time.monotonic()))
                (cancel_event or threading.Event()).wait(wait)
                check_cancel()
            timing["pulse_finished_at"] = time.monotonic()
            if self.pulse:
                timing['release_started_at']=time.monotonic()
                for button in buttons:
                    send(button+'_UP')
                if self.protocol == "positions":
                    for command in ("LS_CENTER", "RS_CENTER"):
                        send(command)
                    self.positions = ("LS_CENTER", "RS_CENTER")
                else:
                    for control in sorted(self.held):
                        send(control + "_UP")
                    self.held = frozenset()
            timing['release_completed_at']=time.monotonic() if self.pulse else None
            timing["returned_at"] = time.monotonic()
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
        if self._hold_timer is not None:self._hold_timer.cancel()
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

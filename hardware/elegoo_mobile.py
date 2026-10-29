import json
import socket
import threading
import time
import itertools
import math
import hashlib
from collections import deque
from copy import deepcopy
from dataclasses import dataclass


@dataclass
class AttentionAlignState:
    active: bool = False
    direction: str | None = None
    start_pan: int = 90
    last_pan: int = 90
    start_yaw: float = 0.0
    target_rotation: float = 0.0
    target_pan: int = 90
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
        turn_speed=55,
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
        self._body_lease = None
        self._rx_buffer = ""
        self._counter = itertools.count(1)

        self._running = False
        self._rx_thread = None

        self._send_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending = {}

        self._wire_history = deque(maxlen=512)
        self._wire_history_lock = threading.Lock()
        self._wire_sequence = 0
        self.align = AttentionAlignState()

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    def connect(self):
        # Normal application consumers cannot create a parallel command owner.
        # Standalone calibration tools retain their explicit native workflow.
        from motion.elegoo_executor import _application_executor
        if _application_executor is not None and _application_executor.base.car is not self:
            raise PermissionError('ELEGOO transport belongs to the application executor')
        if (
            self.sock is not None
            and self._running
        ):
            return

        self.close()

        from hardware.hailo_session import accelerator_lease
        key=hashlib.sha256(f'{self.host}:{self.port}'.encode()).hexdigest()[:16]
        lease=accelerator_lease(f'/tmp/charlie-elegoo-body-{key}.lock')
        lease.__enter__()
        self._body_lease=lease
        try:
            self.sock = socket.create_connection((self.host,self.port),timeout=5)
        except BaseException:
            self.close();raise
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
        lease,self._body_lease=self._body_lease,None
        if lease is not None:lease.__exit__(None,None,None)

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

    def _wire_event(self, kind, **details):
        # In-memory diagnostics only. Never disk I/O on the RX/send-lock path.
        with self._wire_history_lock:
            self._wire_sequence += 1
            self._wire_history.append(dict(sequence=self._wire_sequence,
                at=time.monotonic(), kind=kind, **details))

    def wire_history(self, after=0):
        with self._wire_history_lock:
            rows = [deepcopy(r) for r in self._wire_history if r['sequence'] > after]
            lost = bool(self._wire_history and after < self._wire_history[0]['sequence']-1)
            return dict(events=rows, evicted=lost, latest=self._wire_sequence)

    def _receive_loop(self):
        while (
            self._running
            and self.sock is not None
        ):
            try:
                data = self.sock.recv(4096)

                if not data:
                    self._wire_event('rx_eof')
                    break

                self._rx_buffer += (
                    data.decode(
                        errors="replace"
                    )
                )

                self._process_buffer()

            except socket.timeout:
                continue

            except OSError as exc:
                self._wire_event('rx_error',error=type(exc).__name__,message=str(exc)[:256])
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
        self._wire_event("rx", frame=frame[:512], truncated=len(frame)>512)
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

                    # Qualified motion/STOP require their exact tagged reply.
                    if item.get("expected_response") is not None:
                        return
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
                if item.get("expected_response") not in (None, frame):
                    return
                item["response"] = (
                    frame
                )
                item["value"] = value
                item["event"].set()

    # --------------------------------------------------
    # COMMAND TRANSPORT
    # --------------------------------------------------

    def _send_raw(self, raw, *, preflight=None):
        sock = self.sock

        if (
            sock is None
            or not self._running
        ):
            raise ConnectionError(
                "Elegoo is not connected"
            )

        with self._send_lock:
            if preflight is not None and preflight() is not True:
                raise InterruptedError("command cancelled before wire dispatch")
            self._wire_event('tx_attempt', raw=raw[:512].decode(errors='replace'), bytes=len(raw))
            try:
                sock.sendall(raw)
            except BaseException as exc:
                self._wire_event('tx_error', error=type(exc).__name__, delivery='unknown')
                raise
            self._wire_event('tx_complete', bytes=len(raw))

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
        retry=True,
        preflight=None,
        expected_response=None,
        wait_check=None,
    ):
        if retry:self.connect()
        elif not self.connected:raise ConnectionError("qualified command requires existing live connection")

        pending = None

        if expected_id is not None:
            pending = {
                "event": threading.Event(),
                "response": None,
                "value": None,
                "expected_response": expected_response,
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
                if preflight is None:
                    self._send_raw(raw)
                else:
                    self._send_raw(raw, preflight=preflight)

            except (
                OSError,
                ConnectionError,
            ):
                # One reconnect/retry is useful because the
                # ESP32 may close an idle TCP connection.
                if not retry:raise  # Never replay an ambiguous motor start.
                self.close()
                self.connect()
                if preflight is None:
                    self._send_raw(raw)
                else:
                    self._send_raw(raw, preflight=preflight)

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

            if wait_check is None:
                ready = pending["event"].wait(wait_time)
            else:
                # Only qualified timed commands opt in. Legacy sensor/servo
                # response semantics remain unchanged. Never hold the send lock
                # while checking independent safety or awaiting completion.
                deadline = time.monotonic() + wait_time
                while True:
                    wait_check()
                    if pending["event"].is_set():
                        ready = True
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        ready = False
                        break
                    pending["event"].wait(min(.02, remaining))
                wait_check()  # Cancellation/expiry wins a simultaneous ACK race.
            if not ready:
                self._wire_event('ack_timeout', expected_id=expected_id,
                    expected_response=expected_response, wait_seconds=wait_time)
                raise TimeoutError(f"timeout waiting for {expected_id}")

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
        from motion.elegoo_executor import _application_executor
        if _application_executor is not None:
            raise PermissionError('legacy pan cannot bypass the application executor')
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
        from motion.elegoo_executor import _application_executor
        if _application_executor is not None:
            raise PermissionError('legacy pivot cannot bypass the application executor')
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

    def stop_verified(self):
        """No reconnect/concealed fallback; even an ACK is not measured stopping."""
        ident=self._next_id('safestop')
        started=time.monotonic()
        command={'N':1,'H':ident,'D1':0,'D2':0,'D3':0}
        expected='{'+ident+'_ok}'
        receipt=None;error_message=None
        try:
            result=self._send(command,expected_id=ident,timeout=.150,retry=False,expected_response=expected)
            receipt=dict(sent=True,acknowledged=result['ok'] is True and result.get('response')==expected,
                         response=result.get('response'),physically_stopped=None)
        except Exception as exc:
            receipt=dict(sent=None,acknowledged=False,physically_stopped=None,error=type(exc).__name__)
            error_message=str(exc)[:256]
        finally:
            self.align.active=False
            # Preserve the established receipt API; diagnostics are a separate
            # observation, never an extra physical claim or a repaired outcome.
            self.last_stop_diagnostic=dict(command=command,expected_response=expected,
                ack_timeout_seconds=.150,elapsed_seconds=time.monotonic()-started,
                error_message=error_message,result=deepcopy(receipt))
            self._wire_event('stop_result',**self.last_stop_diagnostic)
        return receipt

    def pulse(self, direction, *, pwm, seconds, lease, boot_id, envelope, safety_check,
              cancel=None, clock=time.monotonic, wait=time.sleep, _executor=None):
        """N2 milliseconds, completion ACK after firmware requests local STOP.

        The callback is protocol evidence, never measured physical stopping.
        No retry/reconnect; safety checks continue while awaiting completion.
        Every attempted pulse exits through an independent explicit STOP.
        """
        self.last_pulse = None
        from motion.elegoo_executor import _application_executor
        if _application_executor is not None and _executor is not _application_executor:
            raise PermissionError('chassis pulse requires application executor')
        if (direction not in ('LEFT','RIGHT','FORWARD','REVERSE') or type(pwm) is not int
                or not 1<=pwm<=min(35,envelope['max_pwm']) or type(seconds) not in (int,float)
                or not math.isfinite(seconds) or not 0<seconds<=min(.2,envelope['max_duration'])
                or not lease.valid(clock(),boot_id) or clock()+seconds>lease.expires_at):
            raise ValueError('finite qualified direction/speed/duration/lease required')
        milliseconds = int(seconds * 1000)  # Round DOWN; never extend the grant.
        if not 1 <= milliseconds <= 200:
            raise ValueError('timed motion requires at least one whole millisecond')
        duration = milliseconds / 1000.
        result=dict(sent=False,acknowledged=False,executed=None,physically_observed=None,
                    timed_completion=False)
        ident=self._next_id('pulse')
        expected='{'+ident+'_ok}'
        def check():
            if (not self.connected or not lease.valid(clock(),boot_id)
                    or (cancel is not None and cancel.is_set()) or safety_check() is not True):
                raise InterruptedError('pulse safety condition changed')
            if result.get('wire_started_at') is not None and clock()>result['wire_started_at']+duration+.05:
                raise TimeoutError('timed completion deadline exceeded')
        def preflight():
            # Cheap cancellation/horizon check under the existing wire lock;
            # independent safety I/O is checked outside that lock.
            now=clock()
            if ((cancel is not None and cancel.is_set()) or not lease.valid(now,boot_id)
                    or now+duration>lease.expires_at):
                return False
            result['wire_started_at']=now
            return True
        def awaiting_completion():
            result['sent']=True  # _send has returned from its single sendall.
            check()
        try:
            check()
            payload={'N':2,'H':ident,'D1':{'LEFT':1,'RIGHT':2,'FORWARD':3,'REVERSE':4}[direction],
                     'D2':pwm,'T':milliseconds}
            result['command']=payload
            result['sent']=None  # Delivery stays ambiguous if the write fails.
            response=self._send(payload,expected_id=ident,timeout=duration+.05,retry=False,
                preflight=preflight,expected_response=expected,wait_check=awaiting_completion)
            result['completion_response']=response.get('response')
            check()
            if (response.get('ok') is not True or response.get('response')!=expected
                    or result.get('wire_started_at') is None
                    or clock()-result['wire_started_at'] < duration-1e-9):
                raise TimeoutError('missing, invalid or premature timed completion ACK')
            result.update(sent=True,acknowledged=True,timed_completion=True)
        except BaseException as exc:
            result.update(error=type(exc).__name__,reason=str(exc))
            raise
        finally:
            # Preserve the attempted wire command even if STOP itself raises.
            result['stop']=dict(sent=None,acknowledged=False,physically_stopped=None)
            self.last_pulse=result
            result['stop']=self.stop_verified()
        return result

    def pan_qualified(self, degrees, *, safety_check, wire_guard=None, _executor=None):
        # Same proven N5 position command, with no reconnect/replay. Independent
        # authority must verify physical servo bounds and cancellation behavior.
        from motion.elegoo_executor import _application_executor
        if _application_executor is not None and _executor is not _application_executor:
            raise PermissionError('pan requires application executor')
        if type(degrees) not in (int, float) or not math.isfinite(degrees) or not 20 <= degrees <= 160:
            raise ValueError('bounded pan position required')
        degrees = int(round(degrees))
        if safety_check() is not True:
            raise InterruptedError('independent pan safety veto')
        ident = self._next_id('qualifiedpan')
        def check():
            if safety_check() is not True or (wire_guard is not None and wire_guard() is not True):
                raise InterruptedError('pan safety or lease changed while awaiting ACK')
        response = self._send({'N':5,'H':ident,'D1':1,'D2':degrees},
            expected_id=ident,timeout=.05,retry=False,preflight=wire_guard,
            expected_response='{'+ident+'_ok}',wait_check=check)
        if response.get('ok') is not True:
            raise TimeoutError('pan acknowledgement unknown')
        return degrees

    def read_ultrasonic(self, *, protocol, clock=time.monotonic):
        """Only an installed-source-verified query; does not prove target range/FOV."""
        if protocol.get('ultrasonic_read_only') is not True or protocol.get('ultrasonic')!={'N':21,'D1':2}:
            raise ValueError('installed query side effects/reply not verified')
        ident=self._next_id('range');started=clock()
        response=self._send(dict(protocol['ultrasonic'],H=ident),expected_id=ident,timeout=.1,retry=False)
        value=float(response['value'])
        if not math.isfinite(value) or not 0<value<=1000:raise ValueError('invalid ultrasonic cm')
        return dict(meters=value/100,at=started,received_at=clock(),valid=True,source='car-qualified',
                    kind='obstacle-only',field_of_view_verified=False,target_association=False)

    # --------------------------------------------------
    # COORDINATED ATTENTION ALIGNMENT
    # --------------------------------------------------

    def begin_attention_align(
        self,
        current_pan,
        max_rotation=None,
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
            full_rotation = 90 - current_pan
            yaw_sign = +1

        else:
            direction = "LEFT"
            full_rotation = current_pan - 90
            yaw_sign = -1

        target_rotation = full_rotation

        if max_rotation is not None:
            target_rotation = min(
                target_rotation,
                float(max_rotation),
            )

        target_pan = int(round(
            current_pan
            + yaw_sign * target_rotation
        ))

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
                target_pan=target_pan,
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

            # Incremental ATTEND: finish at the head angle that
            # corresponds to the requested body assist, rather than
            # always forcing the head all the way to 90 degrees.
            try:
                state.last_pan = self.pan(
                    state.target_pan
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

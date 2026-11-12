"""Opt-in candidate transport admission; never creates a motion qualification.

The existing QualifiedElegooExecutor owns the existing TCP/UART path. No socket,
network configuration, secret persistence or runtime activation is performed here.
"""
import hashlib
import hmac
import json
import re
import threading
import time


class CommandAuthenticator:
    def __init__(self, token, *, clock=time.monotonic):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,64}', token):
            raise ValueError('enrolled device token required')
        self._clock = clock
        self._key = token.encode('ascii')
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self._nonce = None
            self._sequence = 0
            self._invalid = False
            self._ready = threading.Event()

    def challenge(self, frame):
        if not frame.startswith('{Challenge:'):
            return False
        with self._lock:
            match = re.fullmatch(r'\{Challenge:([0-9a-f]{32}):([0-9]{1,10})\}', frame)
            if self._nonce is not None or not match or int(match[2]) > 2**32-1:
                self._invalid = True
            else:
                self._nonce = match[1]
                self._device_at = int(match[2])
                self._received_at = self._clock()
            self._ready.set()
        return True

    def wrap(self, raw, *, qualified):
        if raw == b'{Heartbeat}' or raw == b'{"N":100}':
            return raw
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise PermissionError('candidate requires a qualified command') from None
        # STOP is available before enrollment/qualification, with exact existing ACK.
        if (isinstance(body, dict) and list(body) == ['N', 'H', 'D1', 'D2', 'D3']
                and body['N'] == 1 and all(body[k] == 0 for k in ('D1', 'D2', 'D3'))
                and isinstance(body['H'], str) and re.fullmatch(r'[A-Za-z0-9]{1,32}', body['H'])):
            return raw
        if qualified is not True:
            raise PermissionError('existing qualified executor and wire guard required')
        if not self._ready.wait(.5):
            raise PermissionError('authenticated transport challenge unavailable')
        with self._lock:
            if self._invalid or self._nonce is None or self._sequence >= 2**32-1:
                raise PermissionError('transport session invalid')
            self._sequence += 1
            deadline = (self._device_at + int((self._clock()-self._received_at)*1000) + 100) % 2**32
            message = (f'charlie-elegoo-command-v1\n{self._nonce}\n{self._sequence}\n{deadline}\n'.encode('ascii') + raw)
            tag = hmac.new(self._key, message, hashlib.sha256).hexdigest()
            return f'{{Auth:{self._sequence}:{deadline}:{tag}}}'.encode('ascii') + raw

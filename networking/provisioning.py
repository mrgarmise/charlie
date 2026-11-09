"""Bounded network orchestration. Adapters never receive movement authority.

Discovery is untrusted: only a pinned authenticated device response establishes
identity. No retry or monitor path may call NetworkManager. Explicit operations
use a daemon-owned rollback checkpoint before touching any adapter.
"""
from dataclasses import dataclass, field
import math
import secrets
import threading
import time
from uuid import uuid4

from stimulus.bus import Observation


@dataclass(frozen=True)
class NetworkCredentials:
    ssid: str = field(repr=False)
    password: str = field(repr=False)

    def __post_init__(self):
        if not isinstance(self.ssid, str) or not 1 <= len(self.ssid.encode()) <= 32 or '\0' in self.ssid:
            raise ValueError('invalid network name')
        if not isinstance(self.password, str) or not 8 <= len(self.password.encode()) <= 63 or '\0' in self.password:
            raise ValueError('WPA2 passphrase required')


@dataclass(frozen=True)
class Authorization:
    """Locally issued one-use intent; never construct from a monitoring request."""
    device_id: str
    expires: float
    allow_setup: bool = False
    allow_primary: bool = False
    acknowledged_disconnect: bool = False
    nonce: str = field(default_factory=lambda: secrets.token_hex(16))


class ProvisioningError(RuntimeError):
    pass


class NetworkManager:
    source = 'elegoo-network'

    def __init__(self, bus, discovery, protocol, adapters, *, clock=time.monotonic, sleep=time.sleep):
        self.bus, self.discovery, self.protocol, self.adapters = bus, discovery, protocol, adapters
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.boot = uuid4().hex
        self.sequence = 0
        self.next_retry = 0.
        self.failures = 0
        self.used = set()
        self.state = dict(state='offline', valid=False, device_id=None, transport=None,
                          joined=False, verified=False, restoration='not-needed')
        bus.claim_observations(self.source, self, metadata={
            'body': 'ELEGOO', 'modality': 'network-health', 'clock': 'host-monotonic',
            'acquisition': 'authenticated provisioning; no movement authority'})
        self._publish()

    def status(self):
        return dict(self.state)

    def _publish(self, **changes):
        self.state.update(changes)
        self.sequence += 1
        self.bus.publish_observation(self.source, self, Observation(
            self.source, self.sequence, self.clock(), self.status(),
            {'boot_id': self.boot, 'motion_authority': False}, self.boot))

    def _find(self, device_id, deadline, *, transaction=None):
        # Adapter contracts bound candidate count and each call by deadline.
        try:
            candidates = self.discovery.candidates(device_id, deadline)[:8]
        except (OSError, ValueError, TimeoutError):
            return None
        for candidate in candidates:
            if self.clock() >= deadline: return None
            try:
                reply = self.protocol.status(candidate, device_id, deadline)
                if (reply.get('device_id') == device_id and reply.get('joined') is True
                        and (transaction is None or reply.get('transaction') == transaction)):
                    return candidate
            except (OSError, ValueError, TimeoutError):
                continue
        return None

    def poll(self, device_id):
        """Passive monitor: cannot select adapters, provision or grant authority."""
        if not self.lock.acquire(False):
            return self.status()
        try:
            if self.clock() < self.next_retry:
                return self.status()
            endpoint = self._find(device_id, self.clock()+3)
            self.failures = 0 if endpoint else min(8, self.failures+1)
            self.next_retry = self.clock()+min(60, 2**self.failures)
            self._publish(state='online' if endpoint else 'offline', valid=bool(endpoint),
                          device_id=device_id, verified=bool(endpoint), joined=bool(endpoint),
                          transport='lan' if endpoint else None)
            return self.status()
        finally:
            self.lock.release()

    def provision(self, credentials, authorization):
        if not self.lock.acquire(False):
            raise ProvisioningError('network operation already active')
        checkpoint = None
        try:
            now = self.clock()
            if (not isinstance(authorization, Authorization) or not math.isfinite(authorization.expires) or authorization.expires <= now
                    or authorization.expires > now+120 or authorization.nonce in self.used):
                raise PermissionError('fresh one-use local authorization required')
            if len(self.used) >= 1024:
                raise PermissionError('authorization capacity reached; recreate inactive service')
            self.used.add(authorization.nonce)
            device = authorization.device_id
            deadline = min(authorization.expires, now+90)
            self._publish(state='discovering', device_id=device, valid=False, verified=False,
                          joined=False, restoration='not-needed', transport=None)
            endpoint = self._find(device, deadline)
            if endpoint is None:
                if not authorization.allow_setup:
                    raise PermissionError('setup adapter use requires explicit authorization')
                choices = list(self.adapters.secondary())[:4]
                if authorization.allow_primary:
                    if not authorization.acknowledged_disconnect:
                        raise PermissionError('primary switch deliberately interrupts connectivity; acknowledge separately')
                    choices.append(self.adapters.primary())
                for adapter in choices:
                    if adapter is None:
                        continue
                    try:
                        checkpoint = self.adapters.checkpoint(adapter, 95)
                    except (OSError, ValueError, TimeoutError):
                        continue
                    self._publish(state='connecting-setup', transport=adapter, restoration='pending')
                    try:
                        endpoint = self.adapters.connect_setup(adapter, min(deadline-10, self.clock()+10))
                        if endpoint:
                            # Setup reachability is never identity proof.
                            self.protocol.status(endpoint, device, deadline)
                            break
                    except (OSError, ValueError, TimeoutError):
                        endpoint = None
                    self._restore(checkpoint, deadline)
                    checkpoint = None
                if endpoint is None:
                    raise ProvisioningError('authorized setup routes unavailable')
            transaction = secrets.token_hex(16)
            self._publish(state='provisioning', transport=self.state['transport'] or 'lan')
            reply = self.protocol.prepare(endpoint, device, credentials, transaction, deadline)
            if reply != {'accepted': True, 'transaction': transaction}:
                raise ProvisioningError('device did not acknowledge transaction')
            self._publish(state='accepted')
            if checkpoint is not None:
                self._restore(checkpoint, deadline)
                checkpoint = None
            self._publish(state='rediscovering')
            while self.clock() < deadline:
                endpoint = self._find(device, deadline, transaction=transaction)
                if endpoint:
                    self._publish(state='joined', joined=True)
                    # Fresh TLS pin + identity + transaction + target SSID checked by protocol.
                    self.protocol.confirm(endpoint, device, transaction, credentials.ssid, deadline)
                    if self.clock() >= deadline:
                        raise ProvisioningError('verification expired')
                    self._publish(state='verified', valid=True, verified=True)
                    return self.status()
                self.sleep(min(1, max(0, deadline-self.clock())))
            raise ProvisioningError('target LAN verification timed out; recovery retained')
        except BaseException:
            self._publish(state='failed', valid=False, verified=False)
            raise ProvisioningError('network operation failed; inspect sanitized status') from None
        finally:
            try:
                if checkpoint is not None:
                    self._restore(checkpoint, self.clock()+5)
            finally:
                self.lock.release()

    def _restore(self, checkpoint, deadline):
        self._publish(state='restoring', restoration='pending')
        try:
            if not self.adapters.restore(checkpoint, deadline):
                raise ProvisioningError('restoration unverified')
        except BaseException:
            self._publish(restoration='failed', valid=False, verified=False)
            raise ProvisioningError('primary restoration failed; daemon rollback retained') from None
        self._publish(restoration='verified')

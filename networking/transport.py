"""TLS-pinned provisioning, bounded DNS-SD, private enrollment files.

Enrollment is an out-of-band operator act: verify device ID and certificate
fingerprint physically/USB before saving a freshly generated device token.
Never trust on first network use. No arbitrary URL, redirect or proxy support.
"""
from dataclasses import dataclass, field
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import tempfile
import threading
import time


@dataclass(frozen=True)
class Endpoint:
    address: str
    port: int = 443
    source_ip: str | None = None

    def __post_init__(self):
        ip = ipaddress.ip_address(self.address)
        if not (ip.is_private and not ip.is_loopback and not ip.is_multicast and not ip.is_unspecified):
            raise ValueError('private unicast device address required')
        if not 1 <= self.port <= 65535:
            raise ValueError('invalid port')
        if self.source_ip is not None:
            ipaddress.ip_address(self.source_ip)


@dataclass(frozen=True)
class Enrollment:
    device_id: str
    fingerprint: str
    token: str = field(repr=False)

    def __post_init__(self):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', self.device_id):
            raise ValueError('invalid identity')
        if not re.fullmatch(r'[0-9a-f]{64}', self.fingerprint):
            raise ValueError('SHA256 certificate pin required')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{43,128}', self.token):
            raise ValueError('strong random enrollment token required')


class SecretStore:
    def __init__(self, directory):
        self.path = Path(directory)
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise PermissionError('private owned secret directory required')

    def save(self, enrollment):
        # No credentials returned or printed. Atomic rename and directory fsync.
        raw = json.dumps(dict(device_id=enrollment.device_id, fingerprint=enrollment.fingerprint,
                              token=enrollment.token)).encode()
        fd, temporary = tempfile.mkstemp(dir=self.path)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path / enrollment.device_id)
            directory = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def load(self, device_id):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', device_id):
            raise ValueError('invalid identity')
        fd = os.open(self.path / device_id, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise PermissionError('private owned enrollment required')
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError('enrollment exceeds bound')
        enrollment = Enrollment(**json.loads(raw))
        if enrollment.device_id != device_id:
            raise ValueError('identity mismatch')
        return enrollment


class TLSProtocol:
    def __init__(self, store, *, clock=time.monotonic):
        self.store, self.clock = store, clock

    def _request(self, endpoint, device_id, path, body, deadline):
        enrollment = self.store.load(device_id)
        timeout = min(3, deadline-self.clock())
        if timeout <= 0: raise TimeoutError('operation expired')
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # Exact certificate pin substitutes for public CA/name trust on local devices.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        connection = http.client.HTTPSConnection(endpoint.address, endpoint.port, timeout=timeout,
            context=context, source_address=(endpoint.source_ip, 0) if endpoint.source_ip else None)
        def expire():
            sock = getattr(connection, 'sock', None)
            if sock is not None:
                try: sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            connection.close()
        timer = threading.Timer(timeout, expire)
        timer.daemon = True
        timer.start()
        try:
            connection.connect()
            actual = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
            if not hmac.compare_digest(actual, enrollment.fingerprint):
                raise ValueError('device certificate mismatch')
            # Check the pin BEFORE sending authorization or network credentials.
            connection.request('POST' if body is not None else 'GET', path,
                body=json.dumps(body).encode() if body is not None else None,
                headers={'Authorization': 'Bearer '+enrollment.token, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            raw = response.read(4097)
            if response.status != 200 or len(raw) > 4096:
                raise ValueError('device response rejected')
            result = json.loads(raw)
            if not isinstance(result, dict): raise ValueError('invalid response')
            return result
        except Exception:
            raise OSError('authenticated device request failed') from None
        finally:
            timer.cancel()
            connection.close()

    def status(self, endpoint, device_id, deadline):
        reply = self._request(endpoint, device_id, '/v1/network', None, deadline)
        if reply.get('device_id') != device_id:
            raise ValueError('device identity mismatch')
        # Only protocol fields may escape, never an arbitrary server payload.
        return {key: reply.get(key) for key in ('device_id', 'joined', 'transaction')}

    def prepare(self, endpoint, device_id, credentials, transaction, deadline):
        reply = self._request(endpoint, device_id, '/v1/network/prepare', {
            'ssid': credentials.ssid, 'password': credentials.password, 'transaction': transaction,
            'lease_seconds': max(1, min(90, int(deadline-self.clock())))}, deadline)
        return {key: reply.get(key) for key in ('accepted', 'transaction')}

    def confirm(self, endpoint, device_id, transaction, ssid, deadline):
        # Authenticated target SSID and transaction must match before commit.
        reply = self._request(endpoint, device_id, '/v1/network', None, deadline)
        if (reply.get('device_id') != device_id or reply.get('transaction') != transaction
                or reply.get('ssid') != ssid or reply.get('joined') is not True):
            raise ValueError('target association mismatch')
        result = self._request(endpoint, device_id, '/v1/network/confirm',
                               {'transaction': transaction}, deadline)
        if result != {'verified': True, 'transaction': transaction}:
            raise ValueError('commit not confirmed')


class Discovery:
    """DNS-SD hints are untrusted. Bind every LAN probe to the selected LAN IP.

    Caller supplies Zeroconf bound to that interface; never probes setup AP IPs
    as target LAN. Stable instance name is a hint, TLS is authoritative.
    """
    def __init__(self, zeroconf, lan_ip, *, hints=(), excluded=('192.168.4.0/24',), clock=time.monotonic):
        self.zeroconf, self.lan_ip, self.clock = zeroconf, lan_ip, clock
        self.hints = tuple(hints)[:7]
        self.excluded = tuple(ipaddress.ip_network(n) for n in excluded)

    def candidates(self, device_id, deadline):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', device_id):
            raise ValueError('invalid identity')
        remaining = deadline-self.clock()
        if remaining <= 0: return []
        info = self.zeroconf.get_service_info('_charlie-elegoo._tcp.local.',
            device_id+'._charlie-elegoo._tcp.local.', timeout=int(min(1, remaining)*1000))
        addresses = [(a, info.port) for a in info.parsed_addresses()] if info else []
        addresses += [(h.address, h.port) for h in self.hints]
        result = []
        for address, port in addresses[:16]:
            try:
                ip = ipaddress.ip_address(address)
                if any(ip.version == n.version and ip in n for n in self.excluded): continue
                endpoint = Endpoint(address, port, self.lan_ip)
                if endpoint not in result: result.append(endpoint)
            except ValueError: continue
        return result[:8]

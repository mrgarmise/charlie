"""One-shot acquisition boundary for a separately approved public text snapshot.

This module is deliberately outside the role registry. It ships with no endpoint
configuration and does not perform a request during offline research.
"""

from dataclasses import dataclass
from hashlib import sha256
from http.client import HTTPResponse
from ipaddress import ip_address
import io
import re
import socket
import ssl
from time import monotonic
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SourcePin:
    url: str
    address: str
    sha256: str
    size: int
    license: str

    def destination(self):
        url = urlsplit(self.url)
        address = ip_address(self.address)
        if (url.scheme != "https" or not url.hostname or url.netloc != url.hostname
                or not re.fullmatch(r"[a-z0-9.-]{1,253}", url.hostname)
                or not re.fullmatch(r"/[a-zA-Z0-9_./-]{1,240}", url.path)
                or ".." in url.path.split("/") or url.query or url.fragment
                or not address.is_global or address.is_multicast or address.is_reserved
                or not re.fullmatch(r"[a-f0-9]{64}", self.sha256)
                or not 1 <= self.size <= 65536 or not self.license):
            raise ValueError("unapproved research endpoint or snapshot pin")
        return url.hostname, url.path, address


def remaining(deadline):
    seconds = deadline - monotonic()
    if seconds <= 0:
        raise TimeoutError("external research deadline")
    return seconds


class DeadlineReader(io.RawIOBase):
    def __init__(self, stream, deadline):
        self.stream, self.deadline = stream, deadline

    def readable(self):
        return True

    def readinto(self, buffer):
        self.stream.settimeout(remaining(self.deadline))
        return self.stream.recv_into(buffer)


class ResponseSocket:
    def __init__(self, stream, deadline):
        self.reader = DeadlineReader(stream, deadline)

    def makefile(self, mode):
        return io.BufferedReader(self.reader)


def _https(pin, seconds):
    deadline = monotonic() + seconds
    host, path, address = pin.destination()
    family = socket.AF_INET if address.version == 4 else socket.AF_INET6
    with socket.socket(family) as connection:
        connection.settimeout(remaining(deadline))
        connection.connect((str(address), 443))
        context = ssl.create_default_context()
        connection.settimeout(remaining(deadline))
        with context.wrap_socket(connection, server_hostname=host) as stream:
            stream.settimeout(remaining(deadline))
            stream.sendall(f"GET {path} HTTP/1.0\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode("ascii"))
            with HTTPResponse(ResponseSocket(stream, deadline)) as response:
                response.begin()
                if (response.status != 200 or response.getheader("Content-Encoding") not in (None, "identity")
                        or response.getheader("Transfer-Encoding") is not None
                        or response.getheader("Content-Type", "").split(";", 1)[0] != "text/plain"):
                    raise ValueError("unexpected research response")
                return response.read(pin.size + 1)


class Acquisition:
    """Trusted code supplies a reviewed pin and independent, one-use admission."""

    def __init__(self, pins, admit=None, *, transport=_https, clock=monotonic):
        self.pins = dict(pins)
        self.admit = admit
        self.transport = transport
        self.clock = clock

    def acquire(self, key):
        if self.admit is None or key not in self.pins:
            raise PermissionError("external research is unavailable")
        pin = self.pins[key]
        pin.destination()
        if self.admit(key, pin) is not True:
            raise PermissionError("external research admission denied")
        deadline = self.clock() + 5
        data = self.transport(pin, 5)
        if self.clock() >= deadline:
            raise TimeoutError("external research receipt expired")
        if type(data) is not bytes or len(data) != pin.size or sha256(data).hexdigest() != pin.sha256:
            raise ValueError("external research snapshot does not match its pin")
        excerpt = data.decode("utf-8")[:480]
        return dict(url=pin.url, sha256=pin.sha256, excerpt=excerpt,
                    excerpt_sha256=sha256(excerpt.encode()).hexdigest(), license=pin.license,
                    truncated=excerpt.encode() != data, treatment="untrusted quotation")

"""Process-local transport restrictions for the signed, fixed stationary application."""
import ipaddress
import re
import socket
import sys
from urllib.parse import urlsplit


def display_write(raw):
    from rp2040.object_label import label_request
    if raw in (b'STOP\n', b'PING\n', b'DISPLAY_CAPS\n', b'OBJECT_CLEAR\n'):
        return True
    if re.fullmatch(rb'SESSION [0-9a-f]{32}\n', raw):
        return True
    label = re.fullmatch(rb'OBJECT_LABEL ([0-9]{3,5}) ([0-9]{3}) ([A-Z0-9 ]{1,24})\n', raw)
    if label:
        try:
            ttl, step, text = label.groups()
            return raw == (label_request(text.decode('ascii'), int(ttl), int(step)) + '\n').encode()
        except ValueError:
            pass
    return False


def transport_policy(stream):
    endpoint = urlsplit(stream) if stream else None
    allowed = set()
    if endpoint:
        if (endpoint.scheme != 'http' or endpoint.path != '/stream' or endpoint.username is not None
                or endpoint.query or endpoint.fragment or not endpoint.hostname):
            raise ValueError('reviewed plain MJPEG stream endpoint required')
        port = endpoint.port or 80
        for _, _, _, _, address in socket.getaddrinfo(endpoint.hostname, port, type=socket.SOCK_STREAM):
            allowed.add((str(ipaddress.ip_address(address[0])), port))

    def audit(event, args):
        if event == 'socket.connect':
            sock, address = args
            if (sock.family not in (socket.AF_INET, socket.AF_INET6) or
                    tuple(address[:2]) not in allowed or sock.type != socket.SOCK_STREAM):
                raise PermissionError('stationary network destination denied')
        if event in ('socket.bind', 'socket.sendto', 'socket.sendmsg'):
            raise PermissionError('stationary listener or datagram denied')
        if event == 'urllib.Request':
            url, body, _, method = args
            if url != stream or method != 'GET' or body is not None:
                raise PermissionError('only the selected camera GET is admitted')
    return audit


def install(stream=None):
    import serial
    policy = transport_policy(stream)
    original = serial.Serial

    class StationarySerial(original):
        def open(self):
            if stream is None or self.port != '/dev/ttyACM0':
                raise PermissionError('stationary serial owner denied')
            return super().open()

        def write(self, data):
            if self.port != '/dev/ttyACM0' or stream is None or not display_write(bytes(data)):
                raise PermissionError('stationary serial operation denied')
            return super().write(data)

    serial.Serial = StationarySerial
    sys.addaudithook(policy)

"""Same-owner local IPC for typed recognition and display intents."""
import hmac
import json
import os
from pathlib import Path
from queue import Empty
import secrets
import select
import socket
import struct
from threading import BoundedSemaphore, Lock, Thread
import time


def channel(directory):
    directory = Path(directory)
    if (not directory.is_absolute() or directory.resolve() != directory or not directory.is_dir()
            or directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077):
        raise ValueError('private owner-only recognition directory required')
    endpoint = directory / 'recognition.sock'
    if len(os.fsencode(endpoint)) > 103 or os.path.lexists(endpoint):
        raise ValueError('fresh bounded Unix socket path required')
    credentials = {}
    for role in ('recognize', 'display', 'executive'):
        token = secrets.token_hex(32)
        credentials[role] = token
        if role == 'executive':
            continue
        with open(directory / (role + '.token'), 'x', opener=_private_file) as out:
            out.write(token + '\n')
    return str(endpoint), credentials


def _private_file(path, flags):
    return os.open(path, flags, 0o600)


def _reply(sock, packet):
    data = json.dumps(packet, allow_nan=False, separators=(',', ':')).encode()
    if len(data) > 65535:
        raise ValueError('recognition response exceeds bound')
    sock.sendall(data + b'\n')


class RecognitionServer:
    def __init__(self, endpoint, credentials, inference, display=None):
        self.endpoint, self.credentials = endpoint, credentials
        self.inference, self.display = inference, display
        self.slots = BoundedSemaphore(8)
        self.lock = Lock()
        self.clients = {}
        self.delivered = {'recognize': 0, 'executive': 0, 'display': 0}
        self.peers = set()
        self.stopped = False
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.listener.bind(endpoint)
            os.chmod(endpoint, 0o600)
            self.listener.listen(8)
            self.listener.settimeout(.1)
        except BaseException:
            self.listener.close()
            raise
        self.worker = Thread(target=self._accept, name='recognition-accept', daemon=True)
        self.worker.start()

    def _accept(self):
        while not self.stopped:
            try:
                sock, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            if not self.slots.acquire(blocking=False):
                sock.close()
                continue
            with self.lock:
                if self.stopped:
                    sock.close()
                    self.slots.release()
                    return
                worker = Thread(target=self._serve, args=(sock,), name='recognition-peer', daemon=True)
                self.clients[sock] = worker
                worker.start()

    def _serve(self, sock):
        admitted_peer = None
        try:
            sock.settimeout(.5)
            pid, uid, _ = struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != os.getuid():
                raise PermissionError('unknown peer')
            with sock.makefile('rb') as stream:
                line = stream.readline(1025)
                if len(line) > 1024 or not line.endswith(b'\n'):
                    raise ValueError('bounded JSON request required')
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError('request object required')
                with self.lock:
                    if pid in self.peers:
                        raise RuntimeError('one active request per peer process')
                    self.peers.add(pid)
                    admitted_peer = pid
                self._dispatch(sock, request, pid)
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            try:
                _reply(sock, {'error': type(exc).__name__})
            except OSError:
                pass
        finally:
            self.inference.cancel(sock)
            sock.close()
            with self.lock:
                self.clients.pop(sock, None)
                if admitted_peer is not None:
                    self.peers.discard(admitted_peer)
                self.slots.release()

    def _dispatch(self, sock, request, pid):
        role = request.get('role')
        token = request.get('token')
        if (not isinstance(role, str) or role not in self.credentials or not isinstance(token, str)
                or not hmac.compare_digest(token, self.credentials[role])):
            raise PermissionError('recognition capability denied')
        timeout = request.get('timeout', 2)
        if type(timeout) not in (float, int) or not 0 < timeout <= 10:
            raise ValueError('bounded timeout required')
        deadline = time.monotonic() + timeout
        if role in ('recognize', 'executive'):
            if set(request) - {'role', 'token', 'timeout', 'frames'}:
                raise ValueError('unsupported recognition fields')
            frames = request.get('frames', 1)
            demand = self.inference.request(sock, timeout=timeout, frames=frames)
            for _ in range(frames):
                result = self._consume(sock, demand.pending, deadline)
                if not self.inference.fresh(result):
                    raise TimeoutError('recognition result expired or source changed')
                _reply(sock, {'result': result})
                with self.lock:
                    self.delivered[role] += 1
        elif self.display is not None:
            if set(request) != {'role', 'token', 'timeout', 'text'} or not (request['text'] is None or isinstance(request['text'], str)):
                raise ValueError('display label required')
            # Reconnects from a producer can explicitly clear only its own accepted label.
            receipt = self.display.submit(pid, request['text'], deadline)
            try:
                accepted = self._consume(sock, receipt, deadline)
                _reply(sock, {'acknowledged': accepted})
                if accepted:
                    with self.lock:
                        self.delivered['display'] += 1
            finally:
                self.display.cancel(pid)
        else:
            raise PermissionError('display unavailable')

    def _consume(self, sock, pending, deadline):
        while not self.stopped and time.monotonic() < deadline:
            if select.select([sock], [], [], 0)[0]:
                raise InterruptedError('peer disconnected or sent extra data')
            try:
                return pending.get(timeout=min(.05, max(0, deadline - time.monotonic())))
            except Empty:
                continue
        raise TimeoutError('recognition request expired')

    def close(self):
        with self.lock:
            self.stopped = True
            clients = list(self.clients.items())
        self.listener.close()
        for sock, _ in clients:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.worker.join(1)
        for _, thread in clients:
            thread.join(1)
        Path(self.endpoint).unlink(missing_ok=True)


def recognize(endpoint, token, *, role='recognize', timeout=2, frames=1):
    """Yield bounded observations. Closing this iterator cancels outstanding demand."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout + 1)
        sock.connect(endpoint)
        _reply(sock, dict(role=role, token=token, timeout=timeout, frames=frames))
        with sock.makefile('rb') as stream:
            for _ in range(frames):
                response = json.loads(stream.readline(65536))
                if 'result' not in response:
                    raise OSError(response.get('error', 'recognition result missing'))
                yield response['result']


def display_label(endpoint, token, text, *, timeout=2):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout + 1)
        sock.connect(endpoint)
        _reply(sock, dict(role='display', token=token, timeout=timeout, text=text))
        with sock.makefile('rb') as stream:
            response = json.loads(stream.readline(65536))
        if 'acknowledged' not in response:
            raise OSError(response.get('error', 'display receipt missing'))
        return response['acknowledged']


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--frames', type=int, default=1)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--label')
    mode.add_argument('--ask', choices=['what do you see?'],
                      help='describe one fresh observation on demand')
    args = parser.parse_args()
    if args.ask and args.frames != 1:
        parser.error('--ask describes one observation')
    endpoint = str(args.directory / 'recognition.sock')
    if args.label is None:
        token = (args.directory / 'recognize.token').read_text().strip()
        for result in recognize(endpoint, token, frames=args.frames):
            if args.ask:
                objects = result['observation']['objects']
                labels = ', '.join(f"{row['label']} ({row['confidence']:.0%})" for row in objects)
                print(f"Camera {result['source']}: {labels or 'no objects detected'}.")
            else:
                print(json.dumps(result))
    else:
        token = (args.directory / 'display.token').read_text().strip()
        print(json.dumps({'acknowledged': display_label(endpoint, token, args.label)}))


if __name__ == '__main__':
    main()

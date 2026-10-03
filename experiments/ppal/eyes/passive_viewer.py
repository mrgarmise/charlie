"""Loopback-only viewer. HTTP clients never own/capture the active camera."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import sys
import threading
import time
import uuid

from .passive import runtime_dir, atomic_json, read_json, PassivePublisher
from .camera_lease import camera_owner


class Viewer:
    def __init__(self, directory=None, *, idle=False, camera_factory=None):
        self.directory=directory or runtime_dir()
        self.idle=idle; self.camera_factory=camera_factory
        self.stop=threading.Event(); self.yield_preview=threading.Event()
        self.preview=None; self.error=None
        self.retry_after=0.
        self.token=uuid.uuid4().hex
        self.thread=threading.Thread(target=self._idle,daemon=True)
        self.thread.start()

    def frame(self):
        atomic_json(self.directory/'demand.json',dict(at=time.monotonic(),viewer=self.token))
        packet=read_json(self.directory/'latest.json')
        owner=camera_owner(self.directory)
        viewpoint=read_json(self.directory/'active-vision.json')
        if viewpoint:
            viewpoint=dict(viewpoint, current=bool(owner.get('pid')==viewpoint.get('producer_pid')
                and time.monotonic()-viewpoint.get('at',0)<=2))
        fresh=packet and time.monotonic()-packet['published_at'] <= 2 and time.monotonic()-packet.get('capture_timestamp',0) <= 2
        if fresh and packet['producer_pid']==owner.get('pid'):
            packet=dict(packet, active_vision=viewpoint)
            return dict(status='idle preview' if owner.get('purpose')=='preview' else 'passive', **packet)
        return dict(status='unavailable', active_vision=viewpoint, reason=self.error or (
            'Charlie owns the camera; no fresh passive evidence published' if owner else
            'Waiting for idle preview' if self.idle else 'Charlie is idle; idle preview disabled'),
            evidence={'identity_status':'unknown'}, age_seconds=time.monotonic()-packet['published_at'] if packet else None)

    def _idle(self):
        while not self.stop.wait(1/3):
            demand=read_json(self.directory/'demand.json') or {}
            wanted=self.idle and time.monotonic()-demand.get('at',-100)<=2
            owner=camera_owner(self.directory)
            if self.yield_preview.is_set() or not wanted:
                self._release();self.yield_preview.clear();continue
            if owner.get('purpose')=='active':
                continue
            request=read_json(self.directory/'active-request.json') or {}
            if time.monotonic()-request.get('at',-100) < 2:
                continue
            try:
                if self.preview is None:
                    if time.monotonic()<self.retry_after:continue
                    if self.camera_factory:
                        self.preview=self.camera_factory()
                    else:
                        from vision.camera import Camera
                        self.preview=Camera(purpose='preview')
                        self.preview.autofocus()
                # No tracker, crop, exposure optimizer or identity inference here.
                from PIL import Image
                raw=Image.fromarray(self.preview.read()[...,::-1].copy())
                atomic_json(self.directory/'latest.json',dict(producer_pid=__import__('os').getpid(),
                    published_at=time.monotonic(),capture_timestamp=time.monotonic(),
                    raw=PassivePublisher.jpeg(raw),playfield=None,
                    evidence={'phase':'idle direct preview','identity_status':'unknown','tracks':[]}))
                self.error=None
            except Exception as exc:
                self.error=f'Preview unavailable: {type(exc).__name__}: {exc}'
                self.retry_after=time.monotonic()+5
                self._release()
        self._release()

    def _release(self):
        if self.preview is not None:
            try:self.preview.close()
            finally:self.preview=None

    def close(self):
        self.stop.set();self.thread.join(timeout=2)
        if (read_json(self.directory/'demand.json') or {}).get('viewer')==self.token:
            (self.directory/'demand.json').unlink(missing_ok=True)


def make_server(viewer, port=8767):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/':
                body=Path(__file__).with_name('passive_viewer.html').read_bytes();kind='text/html; charset=utf-8'
            elif self.path=='/frame':
                body=json.dumps(viewer.frame()).encode();kind='application/json'
            else:
                self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port',type=int,default=8767)
    ap.add_argument('--idle-preview',action='store_true')
    ap.add_argument('--exit-on-stdin-close',action='store_true',help='launcher-owned lifetime')
    args=ap.parse_args()
    viewer=Viewer(idle=args.idle_preview)
    try:server=make_server(viewer,args.port)
    except Exception:viewer.close();raise
    def stop(*_):threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGUSR1,lambda *_:viewer.yield_preview.set())
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    if args.exit_on_stdin_close:
        def lifetime():
            while sys.stdin.buffer.read(1):pass
            stop()
        threading.Thread(target=lifetime,daemon=True).start()
    try:server.serve_forever(poll_interval=.1)
    finally:server.server_close();viewer.close()


if __name__=='__main__':main()

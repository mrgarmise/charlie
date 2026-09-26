"""Optional browser MJPEG preview on the local network; read-only images."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import time

from .cli import make_pipeline, make_source


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-2 live browser preview")
    parser.add_argument("--source", choices=("synthetic", "pi"), default="synthetic")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--bind", default="127.0.0.1", help="use 0.0.0.0 to view from another device on your LAN")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    pipeline = make_pipeline(args.source, args.profile, args.calibration)
    source = make_source(args.source, None)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body = b'<!doctype html><title>Charlie PPAL eyes</title><h1>Charlie PPAL eyes</h1><img src="/stream" alt="annotated camera preview">'
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path != "/stream":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            tick = 0
            try:
                while True:
                    result = pipeline.process(source.read(), tick)
                    image = BytesIO()
                    result.annotated.save(image, format="JPEG", quality=75)
                    data = image.getvalue()
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(data)).encode("ascii") + b"\r\n\r\n" + data + b"\r\n")
                    self.wfile.flush()
                    tick += 1
                    time.sleep(0.2)
            except (BrokenPipeError, ConnectionResetError):
                pass

    try:
        with ThreadingHTTPServer((args.bind, args.port), Handler) as server:
            print(f"Preview: http://{args.bind}:{args.port}/ (Ctrl-C to stop)")
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        source.close()


if __name__ == "__main__":
    main()

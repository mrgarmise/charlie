"""A localhost-only stand-in for the eventual RetroPie command accepter."""

import argparse
import json
import socketserver


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        for line in self.rfile:
            try:
                message = json.loads(line)
                if (message.get("type") not in ("step", "release")
                        or type(message.get("sequence")) is not int
                        or not isinstance(message.get("buttons"), list)):
                    raise ValueError("bad command")
                self.server.received.append(message)
                print(f"RECEIVED {message}", flush=True)
                reply = {"ack": message["sequence"], "ok": True}
            except (ValueError, TypeError):
                reply = {"ack": None, "ok": False}
            self.wfile.write((json.dumps(reply) + "\n").encode("utf-8"))


class MockServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, Handler)
        self.received: list[dict] = []


def main() -> None:
    parser = argparse.ArgumentParser(description="PPAL-1 mock controller receiver")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with MockServer(("127.0.0.1", args.port)) as server:
        print(f"Mock accepter listening on 127.0.0.1:{server.server_address[1]}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

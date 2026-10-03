import socketserver
import threading
import unittest

from experiments.ppal.arcade_transport import ArcadeController, controls_for, positions_for
from experiments.ppal.models import Action


class LegacyHandler(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            command = line.decode("ascii").strip()
            self.server.commands.append(command)
            response = "ERROR" if command in self.server.reject else "OK"
            self.wfile.write((response + "\n").encode("ascii"))


class LegacyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, reject=()):
        super().__init__(address, LegacyHandler)
        self.commands = []
        self.reject = set(reject)


class ArcadeTransportTests(unittest.TestCase):
    def test_independent_sticks_and_held_direction_changes(self):
        with LegacyServer(("127.0.0.1", 0)) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with ArcadeController("127.0.0.1", server.server_address[1], sleep=lambda _: None,
                                      protocol="legacy", pulse=False) as ctrl:
                    ctrl.execute(Action("NW", "SE"))
                    ctrl.execute(Action("N", "E"))
                    ctrl.execute(Action("N", "E"))
                self.assertEqual(server.commands, [
                    "NEUTRAL", "LS_LEFT_DOWN", "LS_UP_DOWN", "RS_DOWN_DOWN", "RS_RIGHT_DOWN",
                    "LS_LEFT_UP", "RS_DOWN_UP", "NEUTRAL"])
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_rejected_command_stops_and_releases(self):
        with LegacyServer(("127.0.0.1", 0), reject=("RS_RIGHT_DOWN",)) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with self.assertRaises(ConnectionError):
                    with ArcadeController("127.0.0.1", server.server_address[1], sleep=lambda _: None,
                                          protocol="legacy", pulse=False) as ctrl:
                        ctrl.execute(Action("STAY", "E"))
                self.assertEqual(server.commands, ["NEUTRAL", "RS_RIGHT_DOWN", "NEUTRAL"])
            finally:
                server.shutdown()
                thread.join(timeout=2)

    def test_robotron_directions_map_to_zero_side_controls(self):
        self.assertEqual(controls_for(Action("SW", "NE")),
                         {"LS_DOWN", "LS_LEFT", "RS_UP", "RS_RIGHT"})

    def test_current_absolute_position_protocol_and_neutral(self):
        self.assertEqual(positions_for(Action("SW", "NE")), ("LS_DOWN_LEFT", "RS_UP_RIGHT"))
        with LegacyServer(("127.0.0.1", 0)) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with ArcadeController("127.0.0.1", server.server_address[1], sleep=lambda _: None) as ctrl:
                    ctrl.execute(Action("NW", "SE"))
                    ctrl.execute(Action("N", "E"))
                    ctrl.execute(Action("N", "E"))
                    ctrl.execute(Action("STAY", "NONE"))
                self.assertEqual(server.commands, ["NEUTRAL", "LS_UP_LEFT", "RS_DOWN_RIGHT",
                                                   "LS_CENTER", "RS_CENTER",
                                                   "LS_UP", "RS_RIGHT", "LS_CENTER", "RS_CENTER",
                                                   "LS_UP", "RS_RIGHT", "LS_CENTER", "RS_CENTER",
                                                   "LS_CENTER", "RS_CENTER",
                                                   "NEUTRAL"])
            finally:
                server.shutdown()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

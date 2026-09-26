import threading
import unittest

from experiments.ppal.hands import RecordingSink, TCPCommandSink, encode
from experiments.ppal.mock_accepter import MockServer
from experiments.ppal.models import Action


class HandsTests(unittest.TestCase):
    def test_independent_axes_and_neutral_release(self):
        with RecordingSink() as sink:
            message = sink.execute(Action("NW", "SE"), 120)
        self.assertEqual(message["buttons"], ["move_up", "move_left", "fire_down", "fire_right"])
        self.assertEqual(message["duration_ms"], 120)
        self.assertEqual(sink.commands[-1], {"type": "release", "sequence": 2, "buttons": []})

    def test_invalid_direction_or_duration_rejected(self):
        with self.assertRaises(ValueError):
            encode(Action("LEFT", "NONE"), 1)
        with self.assertRaises(ValueError):
            encode(Action("E", "N"), 1, 800)

    def test_tcp_round_trip_ack_and_release(self):
        with MockServer(("127.0.0.1", 0)) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with TCPCommandSink("127.0.0.1", server.server_address[1]) as sink:
                    sink.execute(Action("SW", "NE"))
                self.assertEqual([item["sequence"] for item in server.received], [1, 2])
                self.assertEqual(server.received[0]["buttons"],
                                 ["move_down", "move_left", "fire_up", "fire_right"])
                self.assertEqual(server.received[1]["type"], "release")
            finally:
                server.shutdown()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

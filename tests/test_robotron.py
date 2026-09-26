import socketserver
import threading
import unittest
from experiments.ppal.models import Action
from experiments.robotron.live import ArcadeController, RobotronSession


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            self.server.commands.append(line.decode().strip())
            self.wfile.write(b'ERROR\n' if self.server.reject else b'OK\n')


class Camera:
    closed = False
    def open(self): pass
    def read(self, **kwargs): return 'pixels'
    def discard_until_new(self, **kwargs): return 'new pixels'
    def close(self): self.closed = True


class RobotronTests(unittest.TestCase):
    def setUp(self):
        self.server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.server.commands = []
        self.server.reject = False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = ArcadeController('127.0.0.1', self.server.server_address[1])
        self.addCleanup(self.cleanup)
    def cleanup(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
    def test_ppal_action_maps_to_confirmed_protocol(self):
        camera = Camera()
        with RobotronSession(self.client, camera) as session:
            result = session.step(Action('NE', 'SW'), .001)
            self.assertEqual(result['frame'], 'new pixels')
        self.assertEqual(self.server.commands, ['NEUTRAL', 'LS_UP_RIGHT', 'RS_DOWN_LEFT', 'NEUTRAL', 'NEUTRAL'])
        self.assertTrue(camera.closed)
    def test_rejection_disconnects_and_cannot_be_reused(self):
        self.client.open()
        self.server.reject = True
        with self.assertRaises(OSError): self.client.execute(Action('E', 'N'))
        self.assertIsNone(self.client.socket)
    def test_camera_failure_releases_controls(self):
        class Failed(Camera):
            def discard_until_new(self, **kwargs): raise TimeoutError('camera offline')
        with RobotronSession(self.client, Failed()) as session:
            with self.assertRaises(TimeoutError): session.step(Action('E', 'N'), .001)
            self.assertIsNone(self.client.socket)
    def test_reset_is_not_fabricated(self):
        session = RobotronSession(self.client, Camera())
        with self.assertRaises(NotImplementedError): session.reset(42)

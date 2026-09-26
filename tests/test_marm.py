import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from memory.former import Experience, MemoryFormer
from memory.marm import MarmClient, MarmOutbox, MarmWriteError


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append((self.path, self.headers.get('Authorization'), payload))
        self.send_response(self.server.code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(self.server.response).encode())


class MarmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.requests = []
        self.server.code = 200
        self.server.response = {'status': 'success', 'entry_id': 'log-1', 'memory_id': 'mem-1'}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.client = MarmClient(f'http://127.0.0.1:{self.server.server_port}', api_key='test-only')
        self.path = Path(self.tmp.name) / 'queue.sqlite3'
        self.memory = MemoryFormer().consider(Experience('decision', 'Use short sweeps', 'head', subject='search'))

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_persist_deliver_scope_and_no_resend(self):
        box = MarmOutbox(self.path)
        box.save(self.memory)
        box.save(self.memory)
        self.assertEqual(box.pending(), 1)
        box = MarmOutbox(self.path)
        self.assertEqual(box.flush(self.client)['delivered'], 1)
        path, auth, payload = self.server.requests[0]
        self.assertEqual(path, '/marm_log_entry')
        self.assertEqual(auth, 'Bearer test-only')
        self.assertEqual(payload['project'], 'charlie')
        self.assertEqual(payload['session_name'], 'charlie-experiences')
        self.assertIn('confidence', payload['entry'])
        self.assertEqual(MarmOutbox(self.path).flush(self.client)['delivered'], 0)
        self.assertEqual(len(self.server.requests), 1)

    def test_failure_survives_restart_then_recovers(self):
        box = MarmOutbox(self.path)
        box.save(self.memory)
        self.server.code = 401
        self.assertEqual(box.flush(self.client)['pending'], 1)
        self.server.code = 200
        self.server.response = {'status': 'error', 'message': 'Database error'}
        self.assertEqual(MarmOutbox(self.path).flush(self.client)['pending'], 1)
        self.server.response = {'status': 'success', 'entry_id': 'log-2', 'memory_id': 'mem-2'}
        self.assertEqual(MarmOutbox(self.path).flush(self.client)['pending'], 0)

    def test_partial_semantic_success_is_not_retried(self):
        self.server.response['memory_id'] = None
        box = MarmOutbox(self.path)
        box.save(self.memory)
        report = box.flush(self.client)
        self.assertEqual(report['log_only'], 1)
        self.assertEqual(box.pending(), 0)
        with self.assertRaises(ValueError):
            MarmClient('http://localhost:8001/mcp')

    def test_connection_failure_leaves_pending(self):
        box = MarmOutbox(self.path)
        box.save(self.memory)
        class Unavailable:
            def write(self, payload):
                raise MarmWriteError('MARM request failed (URLError)')
        self.assertEqual(box.flush(Unavailable())['pending'], 1)


if __name__ == '__main__':
    unittest.main()

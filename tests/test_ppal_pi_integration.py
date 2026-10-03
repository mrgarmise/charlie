from contextlib import closing
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np

from experiments.ppal.closed_loop import EpisodeRunner
from experiments.ppal.eyes.detectors import NoDetector
from experiments.ppal.eyes.pipeline import VisionPipeline
from experiments.ppal.eyes.sources import PiCameraSource, SyntheticSource
from experiments.ppal.hands import RecordingSink
from memory.evaluator import MemoryEvaluator
from memory.gateway import MemoryGateway
from memory.marm import MarmOutbox


class PiIntegrationTests(unittest.TestCase):
    def test_memory_connections_close_on_success_and_error(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            for store in (MarmOutbox(Path(folder) / 'outbox.db'),
                          MemoryEvaluator(Path(folder) / 'evaluation.db')):
                with store._connect() as conn:
                    conn.execute('SELECT 1')
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute('SELECT 1')
                with self.assertRaisesRegex(RuntimeError, 'failure'):
                    with store._connect() as conn:
                        raise RuntimeError('failure')
                with self.assertRaises(sqlite3.ProgrammingError):
                    conn.execute('SELECT 1')

    def test_picamera_bgr_is_converted_for_rgb_detection(self):
        source = PiCameraSource.__new__(PiCameraSource)
        source.camera = SimpleNamespace(read=lambda: np.array([[[10, 20, 200]]], dtype=np.uint8))
        self.assertEqual(source.read().getpixel((0, 0)), (200, 20, 10))

    def test_camera_session_queues_unknown_reward_without_claiming_improvement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            gateway = MemoryGateway(store=MarmOutbox(root / 'outbox.db'),
                                    evaluator=MemoryEvaluator(root / 'evaluation.db'))
            with RecordingSink() as sink:
                outcome = EpisodeRunner(SyntheticSource(), VisionPipeline(NoDetector()), sink,
                                        root / 'session.jsonl', memory_gateway=gateway).run(2)
            rows = [json.loads(line) for line in (root / 'session.jsonl').read_text().splitlines()]
            self.assertIsNone(outcome['reward'])
            self.assertEqual(len({row['run_id'] for row in rows}), 1)
            import sqlite3
            with closing(sqlite3.connect(root / 'outbox.db')) as db:
                payload = db.execute("SELECT payload FROM outbox").fetchone()[0]
                self.assertIn("robotron:camera", payload)
                self.assertIn(rows[0]["run_id"], payload)
            # Read through the evaluator API: evidence and source survive offline.
            records = gateway.evaluator.recent()
            self.assertEqual(len(records), 1)
            self.assertIn('does not establish policy improvement', str(records))
            self.assertEqual(gateway.store.pending(), 1)


if __name__ == '__main__':
    unittest.main()

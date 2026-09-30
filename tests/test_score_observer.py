import json
import threading
from PIL import Image
from experiments.ppal.score_observer import ScoreObserver
from experiments.ppal.eyes.calibration import Calibration


def test_reader_failure_is_unreadable_not_gameplay_failure(tmp_path):
    observer = ScoreObserver(Calibration(((0, .2), (1, .2), (1, 1), (0, 1))), tmp_path/'score.jsonl')
    def fail(frame):
        raise RuntimeError('bad HUD')
    observer.system.tracker.observe = fail
    observer.submit(Image.new('RGB', (100, 100)), timestamp=123., sample=8,
                    preceding_action={'tick':2, 'move':'E'})
    observer.close()
    row = json.loads((tmp_path/'score.jsonl').read_text())
    assert row['timestamp'] == 123.
    assert row['sample'] == 8
    assert row['self_score'] is None
    assert row['p2']['score'] is None
    assert row['self_delta'] == 0
    assert row['error'] == 'RuntimeError: bad HUD'
    assert observer.report()['errors'] == 1


def test_slow_reader_drops_samples_without_waiting(tmp_path):
    observer = ScoreObserver(Calibration(((0, .2), (1, .2), (1, 1), (0, 1))), tmp_path/'score.jsonl')
    entered, release = threading.Event(), threading.Event()
    original = observer.system.tracker.observe
    def wait(frame):
        entered.set()
        release.wait(3)
        return original(frame)
    observer.system.tracker.observe = wait
    image = Image.new('RGB', (100,100))
    observer.submit(image, timestamp=1., sample=1, preceding_action=None)
    assert entered.wait(1)
    for i in range(10):
        observer.submit(image, timestamp=2.+i, sample=2+i, preceding_action=None)
    assert observer.dropped == 8
    release.set()
    observer.close()
    assert observer.report()['samples'] == 3

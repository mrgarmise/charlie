"""Best-effort score instrumentation, isolated from the control thread."""
from __future__ import annotations
import json
import queue
import threading
import time
from .robotron_score_system import RobotronScoreSystem
from .score_events import ScoreEventLog


class ScoreObserver:
    def __init__(self, calibration, path):
        self.system = RobotronScoreSystem(calibration, self_channel=1)
        self.log = ScoreEventLog(path)
        self.queue = queue.Queue(maxsize=2)
        self.dropped = 0
        self.costs = []
        self.errors = 0
        self.frames = []
        self.accepted_confidence = {1:None, 2:None}
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def submit(self, frame, *, timestamp, sample, preceding_action):
        begin = time.monotonic()
        if self.queue.full():
            self.dropped += 1
            return
        # Independent pixels: camera buffers may be reused by the next capture.
        try:
            copied = frame.copy()
            self.queue.put_nowait((copied, timestamp, sample, preceding_action,
                                  time.monotonic()-begin))
        except Exception:
            self.errors += 1

    def _run(self):
        while True:
            item = self.queue.get()
            try:
                if item is None:
                    return
                frame, timestamp, sample, action, copy_seconds = item
                begin = time.monotonic()
                error = None
                try:
                    channels = self.system.observe(frame, t=timestamp)
                except Exception as exc:
                    self.errors += 1
                    error = f'{type(exc).__name__}: {exc}'
                    channels = self.system.tracker.tracker.observe(
                        None, None, player1_confidence=0., player2_confidence=0.)
                    self.system.latest = channels
                elapsed = time.monotonic()-begin
                self.costs.append(elapsed)
                # Build the canonical score evidence without a second disk write.
                row = self._row(channels, timestamp)
                for player, observation in ((1, channels.player1), (2, channels.player2)):
                    if observation.status in ('baseline', 'changed'):
                        self.accepted_confidence[player] = observation.confidence
                    row[f'p{player}']['accepted_confidence'] = self.accepted_confidence[player]
                if len(self.frames) < 16:
                    name = f'score-raw-{sample:04d}.png'
                    self.frames.append((name, frame))
                    row['raw_frame'] = name
                row.update(sample=sample, timestamp=timestamp, preceding_action=action,
                           processing_seconds=elapsed, enqueue_copy_seconds=copy_seconds,
                           error=error, reward_evidence=channels.self_delta if action else 0,
                           attribution='temporal_association_only')
                with self.log.path.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(row)+'\n')
                for player, observation in ((1, channels.player1), (2, channels.player2)):
                    if observation.changed:
                        print(f'SCORE: P{player}={observation.score} Δ=+{observation.delta} confidence={observation.confidence:.2f}')
            except Exception:
                # Instrumentation and its output must never terminate gameplay.
                self.errors += 1
            finally:
                self.queue.task_done()

    @staticmethod
    def _row(channels, timestamp):
        return {'t':timestamp, 'p1':{**vars(channels.player1), 'observed':channels.player1.observed_score},
                'p2':{**vars(channels.player2), 'observed':channels.player2.observed_score},
                'self_channel':channels.self_channel, 'self_score':channels.self_score,
                'self_delta':channels.self_delta}

    def close(self):
        # Called only after camera and controls have closed.
        try:
            self.queue.put(None, timeout=.1)
        except queue.Full:
            return
        self.thread.join(timeout=5.)

    def report(self):
        return {**self.system.report(), 'log':'score.jsonl', 'samples':len(self.costs),
                'dropped_samples':self.dropped, 'errors':self.errors,
                'worker_finished':not self.thread.is_alive(),
                'processing_seconds_total':sum(self.costs),
                'processing_seconds_max':max(self.costs, default=0.),
                'raw_frames':[name for name, _ in self.frames],
                'accepted_confidence':dict(self.accepted_confidence),
                'mode':'observational_background', 'timestamp_clock':'monotonic',
                'metric':'official_game_score', 'policy_feedback':False}


class ObservedCamera:
    """Retain the full camera frame without changing calibration/capture callers."""
    def __init__(self, source):
        self.source = source
        self.raw = None
        self.timestamp = None

    def read(self):
        self.raw = self.source.read()
        self.timestamp = time.monotonic()
        return self.raw

    def __getattr__(self, name):
        return getattr(self.source, name)

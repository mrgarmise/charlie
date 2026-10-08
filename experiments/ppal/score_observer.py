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
        self.system = RobotronScoreSystem(calibration, self_channel=1, confirm_baseline=True)
        self.log = ScoreEventLog(path)
        self.queue = queue.Queue(maxsize=2)
        self.dropped = 0
        self.costs = []
        self.errors = 0
        self.frames = []
        self.latest_frame = None
        self.final_observation = None
        self.late_change_frames = 0
        self.omitted_change_frames = 0
        self.accepted_confidence = {1:None, 2:None}
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def reframe(self,calibration):
        # FIFO changes reader geometry between old/new observations. Preserve
        # game score history; a viewpoint change is not a new game/reset.
        self.queue.put(('geometry',calibration),timeout=1.)

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
                if len(item)==2 and item[0]=='geometry':
                    self.system.reader.calibration=item[1]
                    continue
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
                name = f'score-raw-{sample:04d}.png'
                self.latest_frame = (name, frame)
                changed = channels.player1.changed or channels.player2.changed
                initial = sample <= 16
                if initial or (changed and self.late_change_frames < 16):
                    if not initial:
                        self.late_change_frames += 1
                    self.frames.append((name, frame))
                    row['raw_frame'] = name
                elif changed:
                    self.omitted_change_frames += 1
                row.update(sample=sample, timestamp=timestamp, preceding_action=action,
                           processing_seconds=elapsed, enqueue_copy_seconds=copy_seconds,
                           error=error, reward_evidence=channels.self_delta,
                           attribution='temporal_association_only')
                # The final image is retained at close even when this row did
                # not trigger retention. Bind it explicitly without rewriting
                # the append-only historical score row.
                self.final_observation = dict(sample=sample, timestamp=timestamp,
                    raw_frame=name, observed_score=channels.player1.observed_score,
                    retained_score=channels.player1.score,
                    status=channels.player1.status, error=error)
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
        if not self.thread.is_alive() and self.latest_frame is not None:
            if all(name != self.latest_frame[0] for name, _ in self.frames):
                self.frames.append(self.latest_frame)

    def report(self):
        return {**self.system.report(), 'log':'score.jsonl', 'samples':len(self.costs),
                'dropped_samples':self.dropped, 'errors':self.errors,
                'worker_finished':not self.thread.is_alive(),
                'final_observation':self.final_observation if not self.thread.is_alive() else None,
                'processing_seconds_total':sum(self.costs),
                'processing_seconds_max':max(self.costs, default=0.),
                'raw_frames':[name for name, _ in self.frames],
                'raw_frame_retention':'first 16 samples, up to 16 later accepted changes, final sample',
                'omitted_change_frames':self.omitted_change_frames,
                'accepted_confidence':dict(self.accepted_confidence),
                'mode':'observational_background', 'timestamp_clock':'monotonic',
                'metric':'official_game_score', 'policy_feedback':False}

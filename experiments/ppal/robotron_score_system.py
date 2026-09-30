"""One-call Robotron score perception + temporal validation + evidence logging."""
from __future__ import annotations

from pathlib import Path

from .robotron_hud import RobotronHUDReader
from .score_events import ScoreEventLog
from .score_tracker import VisualScoreTracker


class RobotronScoreSystem:
    def __init__(self, calibration, *, log_path: Path | None = None,
                 self_channel: int | None = 1) -> None:
        self.reader = RobotronHUDReader(calibration)
        self.tracker = VisualScoreTracker(self.reader, self_channel=self_channel)
        self.log = ScoreEventLog(log_path) if log_path is not None else None
        self.latest = None

    def reset(self) -> None:
        self.tracker.reset()
        self.latest = None

    def set_self_channel(self, player: int | None) -> None:
        self.tracker.set_self_channel(player)

    def observe(self, raw_frame, *, t: float):
        self.latest = self.tracker.observe(raw_frame)
        if self.log is not None:
            self.log.append(t=t, channels=self.latest)
        return self.latest

    def report(self) -> dict:
        if self.latest is None:
            return {
                "p1_score": None, "p2_score": None, "self_channel": None,
                "self_score": None, "status": "unmeasured",
            }
        return {
            "p1_score": self.latest.player1.score,
            "p2_score": self.latest.player2.score,
            "self_channel": self.latest.self_channel,
            "self_score": self.latest.self_score,
            "status": "measured" if self.latest.self_score is not None else "unresolved",
        }

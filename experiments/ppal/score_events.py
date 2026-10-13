"""Append-only timestamped score evidence for Robotron runs."""
from __future__ import annotations

import json
from pathlib import Path


class ScoreEventLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, *, t: float, channels) -> dict:
        row = {
            "t": round(float(t), 6),
            "p1": {
                "score": channels.player1.score,
                "observed": channels.player1.observed_score,
                "delta": channels.player1.delta,
                "confidence": channels.player1.confidence,
                "status": channels.player1.status,
            },
            "p2": {
                "score": channels.player2.score,
                "observed": channels.player2.observed_score,
                "delta": channels.player2.delta,
                "confidence": channels.player2.confidence,
                "status": channels.player2.status,
            },
            "self_channel": channels.self_channel,
            "self_score": channels.self_score,
            "self_delta": channels.self_delta,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        return row

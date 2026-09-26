"""Record candidate detections from real or replayed frames without acting."""

from dataclasses import asdict
import json
from pathlib import Path
import time

from .hud import HUDReader
from .pipeline import VisionPipeline


def audit(source, pipeline: VisionPipeline, output: Path, frames: int = 12,
          interval_ms: int = 100, hud_reader: HUDReader | None = None) -> dict:
    if not 1 <= frames <= 200 or not 0 <= interval_ms <= 5000:
        raise ValueError("frames must be 1..200 and interval_ms 0..5000")
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for tick in range(frames):
        try:
            frame = source.read()
        except EOFError:
            break
        result = pipeline.process(frame, tick)
        hud = hud_reader.read(result.playfield) if hud_reader else None
        frame.save(output / f"raw_{tick:03d}.png")
        result.annotated.save(output / f"view_{tick:03d}.jpg", quality=85)
        row = {"tick": tick, "status": result.status,
               "detections": [asdict(item) for item in result.detections],
               "world": asdict(result.world) if result.world else None,
               "hud": asdict(hud) if hud else None}
        rows.append(row)
        (output / f"state_{tick:03d}.json").write_text(
            json.dumps(row, indent=2) + "\n", encoding="utf-8")
        if interval_ms and tick < frames - 1:
            time.sleep(interval_ms / 1000)
    summary = {"frames": len(rows),
               "player_frames": sum(row["world"] is not None for row in rows),
               "human_frames": sum(bool(row["world"] and row["world"]["targets"]) for row in rows),
               "threat_frames": sum(bool(row["world"] and row["world"]["threats"]) for row in rows),
               "hud_frames": sum(row["hud"] is not None for row in rows),
               "status": "REVIEW_CANDIDATES" if rows else "NO_FRAMES",
               "note": "Counts are detector candidates; inspect view images before any live control."}
    (output / "readiness.json").write_text(json.dumps({"summary": summary, "frames": rows}, indent=2)
                                          + "\n", encoding="utf-8")
    return summary

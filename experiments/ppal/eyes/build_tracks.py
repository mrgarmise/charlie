"""Reprocess a recorded Robotron observation into temporal sprite tracks.

Uses the original raw frames plus the recording's saved calibration, so
tracking operates on clean perspective-corrected playfields rather than
annotated diagnostic images.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from .calibration import Calibration
from .sprites import SpriteDetector
from .tracking import SpriteTracker


def padded_crop(image, box, padding=4):
    x1, y1, x2, y2 = box
    return image.crop((
        max(0, x1 - padding),
        max(0, y1 - padding),
        min(image.width, x2 + padding),
        min(image.height, y2 + padding),
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("config/robotron/sprites-draft.json"),
    )
    parser.add_argument("--max-distance", type=float, default=7.0)
    parser.add_argument("--max-missed", type=int, default=3)
    args = parser.parse_args()

    recording = args.recording
    calibration = Calibration.load(recording / "calibration.json")
    detector = SpriteDetector.load(args.profile)
    tracker = SpriteTracker(
        max_distance=args.max_distance,
        max_missed=args.max_missed,
    )

    output = recording / "tracking"
    if output.exists():
        raise SystemExit(
            f"{output} already exists; refusing to overwrite an audit run"
        )

    crops = output / "crops"
    playfields = output / "playfields"
    output.mkdir()
    crops.mkdir()
    playfields.mkdir()

    raw_frames = sorted(recording.glob("raw_*.jpg"))
    if not raw_frames:
        raise SystemExit(f"No raw_*.jpg frames found in {recording}")

    observations = []

    for tick, path in enumerate(raw_frames):
        with Image.open(path) as raw:
            raw = raw.convert("RGB")
            playfield = calibration.apply(raw)

        playfield.save(playfields / f"playfield_{tick:03d}.jpg", quality=95)

        detections = detector.detect(playfield)
        assignments = tracker.update(tick, detections)

        frame_rows = []

        for index, detection in enumerate(detections):
            track_id = assignments[index]

            track_dir = crops / f"track_{track_id:04d}"
            track_dir.mkdir(exist_ok=True)

            crop_path = track_dir / f"{tick:03d}.png"
            padded_crop(playfield, detection.box).save(crop_path)

            frame_rows.append({
                "track_id": track_id,
                "kind": detection.kind,
                "center": list(detection.center),
                "box": list(detection.box),
                "pixels": detection.pixels,
                "crop": str(crop_path.relative_to(recording)),
            })

        observations.append({
            "tick": tick,
            "detections": frame_rows,
        })

    tracks = tracker.finish()
    track_rows = []

    for track in tracks:
        description = tracker.describe(track)

        track_crops = sorted(
            (crops / f"track_{track.track_id:04d}").glob("*.png")
        )

        description["crop_count"] = len(track_crops)
        description["crops"] = [
            str(p.relative_to(recording)) for p in track_crops
        ]

        track_rows.append(description)

    # Put long-lived tracks first because they are generally more useful
    # teaching candidates than one-frame flashes.
    track_rows.sort(
        key=lambda row: (row["observations"], row["displacement"]),
        reverse=True,
    )

    result = {
        "recording": str(recording),
        "frames": len(raw_frames),
        "track_count": len(track_rows),
        "tracks": track_rows,
        "observations": observations,
    }

    (output / "tracks.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )

    # Contact sheet of the most persistent tracks.
    useful = [t for t in track_rows if t["observations"] >= 3][:40]

    thumb_w, thumb_h = 120, 100
    cols = 5
    rows = max(1, (len(useful) + cols - 1) // cols)

    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), "black")
    draw = ImageDraw.Draw(sheet)

    for slot, track in enumerate(useful):
        crop_paths = track["crops"]
        sample = crop_paths[len(crop_paths) // 2]

        with Image.open(recording / sample) as crop:
            crop = crop.convert("RGB")
            crop.thumbnail((90, 65))

            col = slot % cols
            row = slot // cols
            x = col * thumb_w + (thumb_w - crop.width) // 2
            y = row * thumb_h + 18

            sheet.paste(crop, (x, y))

        label = (
            f"T{track['track_id']} "
            f"n={track['observations']} "
            f"d={track['displacement']:.1f}"
        )
        draw.text((col * thumb_w + 3, row * thumb_h + 3), label, fill="white")

    sheet.save(output / "tracks-contact-sheet.jpg", quality=95)

    print(f"Frames: {len(raw_frames)}")
    print(f"Tracks: {len(track_rows)}")
    print(f"Persistent (>=3 observations): {sum(t['observations'] >= 3 for t in track_rows)}")
    print(f"Long-lived (>=10 observations): {sum(t['observations'] >= 10 for t in track_rows)}")
    print()
    print("Top tracks:")

    for track in track_rows[:20]:
        print(
            f"  T{track['track_id']:4d}"
            f"  obs={track['observations']:3d}"
            f"  age={track['age_frames']:3d}"
            f"  move={track['displacement']:6.1f}"
            f"  old={track['candidate_kinds']}"
        )

    print()
    print(f"Contact sheet: {output / 'tracks-contact-sheet.jpg'}")


if __name__ == "__main__":
    main()

"""Build human-grounded Robotron visual knowledge from tracked observations.

Human labels are authoritative.  This tool harvests multiple appearances from
confirmed tracks while rejecting bad segmentation and mixed-object tracks.
It does not control the game and does not promote inferred labels to truth.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


SKIP_IDENTITIES = {"mixed", "unknown"}
SKIP_QUALITIES = {"bad_box", "merged_objects"}


def appearance_feature(image: Image.Image) -> list[float]:
    """Compact appearance descriptor retaining both color and silhouette."""
    rgb = np.asarray(image.convert("RGB"))
    resized = cv2.resize(rgb, (16, 24), interpolation=cv2.INTER_AREA).astype(
        np.float32
    )

    # Keep the existing detector's useful bright-sprite emphasis.
    bright = np.maximum(resized - 75.0, 0.0)
    vector = bright.reshape(-1)
    norm = max(float(np.linalg.norm(vector)), 1e-6)
    return (vector / norm).tolist()


def load_json(path: Path):
    return json.loads(path.read_text())


def choose_samples(paths: list[Path], maximum: int) -> list[Path]:
    """Spread selected samples across the life of a track."""
    if len(paths) <= maximum:
        return paths

    indexes = np.linspace(0, len(paths) - 1, maximum)
    indexes = sorted(set(int(round(i)) for i in indexes))
    return [paths[i] for i in indexes]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument(
        "--labels",
        type=Path,
        help="human-labels.json; defaults to recording/tracking/human-labels.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="output knowledge JSON; defaults to recording/tracking/taught-sprites.json",
    )
    parser.add_argument(
        "--samples-per-track",
        type=int,
        default=12,
        help="maximum representative crops harvested from each confirmed track",
    )
    args = parser.parse_args()

    if not 1 <= args.samples_per_track <= 100:
        parser.error("--samples-per-track must be 1..100")

    recording = args.recording
    tracking = recording / "tracking"

    labels_path = args.labels or tracking / "human-labels.json"
    output_path = args.output or tracking / "taught-sprites.json"
    tracks_path = tracking / "tracks.json"

    if not labels_path.exists():
        raise SystemExit(f"Missing human labels: {labels_path}")
    if not tracks_path.exists():
        raise SystemExit(f"Missing tracks: {tracks_path}")

    labels_doc = load_json(labels_path)
    tracks_doc = load_json(tracks_path)

    if labels_doc.get("schema") != "robotron-human-labels-v1":
        raise SystemExit("Expected robotron-human-labels-v1 human labels")

    tracks = {
        str(track["track_id"]): track
        for track in tracks_doc["tracks"]
    }

    taught = []
    skipped = []
    class_counts = Counter()
    track_counts = Counter()
    pose_counts = defaultdict(Counter)

    for track_id, human in labels_doc["labels"].items():
        if track_id not in tracks:
            skipped.append({
                "track_id": int(track_id),
                "reason": "track_not_found",
            })
            continue

        identity = human.get("identity")
        quality = human.get("quality", "good")

        if identity in SKIP_IDENTITIES:
            skipped.append({
                "track_id": int(track_id),
                "identity": identity,
                "reason": "identity_not_trainable",
            })
            continue

        if quality in SKIP_QUALITIES:
            skipped.append({
                "track_id": int(track_id),
                "identity": identity,
                "reason": quality,
            })
            continue

        track = tracks[track_id]
        crop_paths = [
            recording / relative
            for relative in track.get("crops", [])
        ]
        crop_paths = [p for p in crop_paths if p.exists()]

        if not crop_paths:
            skipped.append({
                "track_id": int(track_id),
                "identity": identity,
                "reason": "no_crops",
            })
            continue

        selected = choose_samples(crop_paths, args.samples_per_track)

        accepted = 0
        for crop_path in selected:
            with Image.open(crop_path) as image:
                image = image.convert("RGB")

                # Reject pathological crops. We retain varied sprite sizes,
                # but do not let huge accidental regions become exemplars.
                w, h = image.size
                if w < 3 or h < 3 or w > 80 or h > 80:
                    continue

                taught.append({
                    "identity": identity,
                    "pose": human.get("pose"),
                    "track_id": int(track_id),
                    "human_confirmed": True,
                    "source": str(crop_path.relative_to(recording)),
                    "size": [w, h],
                    "feature": appearance_feature(image),
                })
                accepted += 1
                class_counts[identity] += 1

        if accepted:
            track_counts[identity] += 1
            if human.get("pose"):
                pose_counts[identity][human["pose"]] += 1
        else:
            skipped.append({
                "track_id": int(track_id),
                "identity": identity,
                "reason": "no_acceptable_crops",
            })

    knowledge = {
        "schema": "robotron-taught-sprites-v1",
        "source_recording": str(recording),
        "authority": "human-confirmed track labels",
        "policy": {
            "human_labels_are_ground_truth": True,
            "inferred_labels_are_not_ground_truth": True,
            "mixed_tracks_trainable": False,
            "bad_boxes_trainable": False,
        },
        "appearance_notes": labels_doc.get("appearance_notes", {}),
        "classes": {
            identity: {
                "confirmed_tracks": track_counts[identity],
                "examples": class_counts[identity],
                "poses": dict(pose_counts[identity]),
            }
            for identity in sorted(class_counts)
        },
        "examples": taught,
        "skipped": skipped,
    }

    output_path.write_text(json.dumps(knowledge, indent=2) + "\n")

    print("ROBOTRON TEACHING PASS")
    print("======================")
    print(f"Human labels:       {len(labels_doc['labels'])}")
    print(f"Accepted examples:  {len(taught)}")
    print(f"Skipped tracks:     {len(skipped)}")
    print()

    for identity in sorted(class_counts):
        poses = dict(pose_counts[identity])
        print(
            f"{identity:18s} "
            f"tracks={track_counts[identity]:2d}  "
            f"examples={class_counts[identity]:3d}  "
            f"poses={poses}"
        )

    if skipped:
        print("\nSkipped:")
        for item in skipped:
            print(
                f"  T{item['track_id']}: "
                f"{item.get('identity', '?')} — {item['reason']}"
            )

    print(f"\nKnowledge written to: {output_path}")


if __name__ == "__main__":
    main()

"""Propose identities for unlabeled Robotron tracks and build a review sheet.

Human labels remain authoritative. Predictions are proposals only and are never
written back into human-labels.json.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def classify(vector, references, threshold=0.82, margin=0.04):
    by_class = {}

    for identity, vectors in references.items():
        if not vectors:
            continue

        matrix = np.asarray(vectors, dtype=np.float32)
        scores = matrix @ vector

        top = np.sort(scores)[-3:]
        by_class[identity] = float(np.median(top))

    if not by_class:
        return "unknown", 0.0, 0.0, {}

    ranked = sorted(
        by_class.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    identity, score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else -1.0

    if score < threshold or score - runner_up < margin:
        identity = "unknown"

    return identity, score, runner_up, by_class


def feature_from_crop(path: Path):
    import cv2

    rgb = np.asarray(Image.open(path).convert("RGB"))
    resized = cv2.resize(
        rgb,
        (16, 24),
        interpolation=cv2.INTER_AREA,
    ).astype(np.float32)

    resized = np.maximum(resized - 75, 0)
    vector = resized.reshape(-1)
    norm = float(np.linalg.norm(vector))

    return vector / max(norm, 1e-6)


def numeric_track_id(track):
    return int(track.get("track_id", track.get("id")))


def crop_paths(recording: Path, track_id: int):
    folder = recording / "tracking" / "crops" / f"track_{track_id:04d}"
    if not folder.exists():
        # tolerate earlier naming conventions
        candidates = [
            recording / "tracking" / "crops" / f"track_{track_id}",
            recording / "tracking" / "crops" / f"T{track_id}",
        ]
        for candidate in candidates:
            if candidate.exists():
                folder = candidate
                break

    return sorted(folder.glob("*.jpg"))


def representative_path(paths):
    if not paths:
        return None
    return paths[len(paths) // 2]


def make_contact_sheet(rows, output: Path, columns=5):
    if not rows:
        return

    tile_w = 190
    tile_h = 150
    thumb_w = 150
    thumb_h = 105

    page_rows = (len(rows) + columns - 1) // columns

    sheet = Image.new(
        "RGB",
        (columns * tile_w, page_rows * tile_h),
        "black",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, row in enumerate(rows):
        col = index % columns
        r = index // columns
        x = col * tile_w
        y = r * tile_h

        path = Path(row["representative"])

        try:
            image = Image.open(path).convert("RGB")
            image.thumbnail((thumb_w, thumb_h))

            px = x + (tile_w - image.width) // 2
            py = y + 4
            sheet.paste(image, (px, py))
        except Exception:
            pass

        label = (
            f"T{row['track_id']} "
            f"{row['proposal'].upper()}\n"
            f"votes {row['winning_votes']}/{row['samples']}"
        )

        draw.multiline_text(
            (x + 4, y + 112),
            label,
            fill="white",
            font=font,
            spacing=2,
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=95)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--margin", type=float, default=0.04)
    parser.add_argument("--max-review", type=int, default=40)
    args = parser.parse_args()

    tracking = args.recording / "tracking"

    knowledge = json.loads(
        (tracking / "taught-sprites.json").read_text()
    )
    tracks_data = json.loads(
        (tracking / "tracks.json").read_text()
    )
    labels = json.loads(
        (tracking / "human-labels.json").read_text()
    )

    examples = knowledge["examples"]

    references = defaultdict(list)
    for example in examples:
        references[example["identity"]].append(
            example["feature"]
        )

    labeled_ids = {int(value) for value in labels["labels"]}

    if isinstance(tracks_data, dict):
        tracks = tracks_data.get("tracks", [])
    else:
        tracks = tracks_data

    proposals = []

    for track in tracks:
        track_id = numeric_track_id(track)

        if track_id in labeled_ids:
            continue

        paths = crop_paths(args.recording, track_id)
        if len(paths) < 3:
            continue

        # Spread at most twelve observations across the track.
        if len(paths) > 12:
            indexes = np.linspace(
                0,
                len(paths) - 1,
                12,
                dtype=int,
            )
            paths = [paths[int(i)] for i in indexes]

        votes = Counter()
        evidence = []

        for path in paths:
            vector = feature_from_crop(path)

            identity, score, runner_up, by_class = classify(
                vector,
                references,
                args.threshold,
                args.margin,
            )

            votes[identity] += 1
            evidence.append({
                "crop": str(path),
                "prediction": identity,
                "score": score,
                "runner_up": runner_up,
                "class_scores": by_class,
            })

        known = {
            identity: count
            for identity, count in votes.items()
            if identity != "unknown"
        }

        if known:
            proposal, winning_votes = max(
                known.items(),
                key=lambda item: item[1],
            )
        else:
            proposal = "unknown"
            winning_votes = 0

        # Require a majority of all sampled observations.
        required = len(paths) // 2 + 1

        if winning_votes < required:
            proposal = "unknown"

        rep = representative_path(paths)
        if rep is None:
            continue

        # Review priority:
        # 1. known proposal
        # 2. more supporting votes
        # 3. longer tracks
        priority = (
            1 if proposal != "unknown" else 0,
            winning_votes,
            len(paths),
        )

        proposals.append({
            "track_id": track_id,
            "proposal": proposal,
            "winning_votes": winning_votes,
            "samples": len(paths),
            "votes": dict(votes),
            "observations": int(
                track.get(
                    "observations",
                    track.get("age", len(paths)),
                )
            ),
            "representative": str(rep),
            "priority": priority,
            "evidence": evidence,
        })

    proposals.sort(
        key=lambda row: tuple(row["priority"]),
        reverse=True,
    )

    review = proposals[:args.max_review]

    output_json = tracking / "review-proposals.json"
    output_sheet = tracking / "review-contact-sheet.jpg"

    output_json.write_text(
        json.dumps(
            {
                "schema": "robotron-review-proposals-v1",
                "warning": (
                    "Machine proposals only. "
                    "Do not promote without human confirmation."
                ),
                "threshold": args.threshold,
                "margin": args.margin,
                "proposals": proposals,
            },
            indent=2,
        )
        + "\n"
    )

    make_contact_sheet(review, output_sheet)

    proposed = Counter(
        row["proposal"]
        for row in proposals
    )

    print("ROBOTRON UNLABELED TRACK REVIEW")
    print("===============================")
    print(f"Unlabeled tracks considered: {len(proposals)}")
    print(f"Review sheet entries:       {len(review)}")
    print()

    for identity, count in sorted(proposed.items()):
        print(f"{identity:20s} {count:4d}")

    print("\nTop review candidates:")
    for row in review:
        print(
            f"  T{row['track_id']:4d}  "
            f"{row['proposal']:18s} "
            f"votes={row['winning_votes']:2d}/{row['samples']:2d} "
            f"{row['votes']}"
        )

    print(f"\nReview data:  {output_json}")
    print(f"Contact sheet: {output_sheet}")


if __name__ == "__main__":
    main()

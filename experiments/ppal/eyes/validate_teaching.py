"""Validate human-taught Robotron appearance recognition.

Uses leave-one-track-out evaluation: examples from the track being tested are
removed from the reference set.  This tests whether Charlie recognizes a
human-confirmed object from OTHER confirmed examples of that identity.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def cosine_scores(query, matrix):
    return matrix @ query


def classify(query, references, threshold, margin):
    """Return identity, best score and runner-up score."""
    by_class = {}

    for identity, vectors in references.items():
        if not vectors:
            continue
        matrix = np.asarray(vectors, dtype=np.float32)
        scores = cosine_scores(query, matrix)

        # Median of the three best exemplars is more robust than trusting one
        # accidentally similar crop.
        best = np.sort(scores)[-3:]
        by_class[identity] = float(np.median(best))

    if not by_class:
        return "uncertain", 0.0, 0.0

    ranked = sorted(
        by_class.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_identity, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else -1.0

    if best_score < threshold or best_score - second_score < margin:
        return "uncertain", best_score, second_score

    return best_identity, best_score, second_score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--threshold", type=float, default=0.82)
    parser.add_argument("--margin", type=float, default=0.04)
    args = parser.parse_args()

    knowledge_path = (
        args.recording / "tracking" / "taught-sprites.json"
    )

    knowledge = json.loads(knowledge_path.read_text())
    examples = knowledge["examples"]

    identities = sorted({e["identity"] for e in examples})

    tracks = defaultdict(list)
    for example in examples:
        tracks[(example["identity"], example["track_id"])].append(example)

    results = []
    confusion = Counter()

    for (truth, track_id), track_examples in sorted(tracks.items()):
        references = defaultdict(list)

        for example in examples:
            # Critical rule: never recognize a track using itself.
            if example["track_id"] == track_id:
                continue
            references[example["identity"]].append(example["feature"])

        # A class represented by only this one track cannot be evaluated
        # honestly with leave-one-track-out.
        if not references.get(truth):
            results.append({
                "truth": truth,
                "track_id": track_id,
                "result": "not_testable",
                "reason": "no other human-confirmed track of this identity",
            })
            continue

        votes = Counter()
        scores = []

        for example in track_examples:
            query = np.asarray(example["feature"], dtype=np.float32)
            prediction, best, second = classify(
                query,
                references,
                args.threshold,
                args.margin,
            )
            votes[prediction] += 1
            scores.append((prediction, best, second))

        # Track identity is based on its crop votes. Unknown votes do not
        # magically become a class identity.
        known_votes = {
            k: v for k, v in votes.items()
            if k != "uncertain"
        }

        if known_votes:
            predicted = max(
                known_votes,
                key=lambda k: known_votes[k],
            )
        else:
            predicted = "uncertain"

        confident_votes = known_votes.get(predicted, 0)
        required_votes = max(2, (len(track_examples) + 2) // 3)

        if confident_votes < required_votes:
            predicted = "uncertain"

        if predicted == truth:
            outcome = "correct"
        elif predicted == "uncertain":
            outcome = "uncertain"
        else:
            outcome = "wrong"
            confusion[(truth, predicted)] += 1

        results.append({
            "truth": truth,
            "track_id": track_id,
            "prediction": predicted,
            "outcome": outcome,
            "votes": dict(votes),
            "examples": len(track_examples),
        })

    testable = [r for r in results if r.get("result") != "not_testable"]
    counts = Counter(r["outcome"] for r in testable)

    print("ROBOTRON LEAVE-ONE-TRACK-OUT TEST")
    print("=================================")
    print(f"Reference examples: {len(examples)}")
    print(f"Human-confirmed tracks: {len(tracks)}")
    print(f"Testable tracks: {len(testable)}")
    print()

    for identity in identities:
        rows = [r for r in testable if r["truth"] == identity]
        if not rows:
            print(f"{identity:18s} not testable (only one confirmed track)")
            continue

        c = Counter(r["outcome"] for r in rows)
        print(
            f"{identity:18s} "
            f"tracks={len(rows):2d}  "
            f"correct={c['correct']:2d}  "
            f"uncertain={c['uncertain']:2d}  "
            f"wrong={c['wrong']:2d}"
        )

    print()
    print(
        f"TOTAL: correct={counts['correct']}  "
        f"uncertain={counts['uncertain']}  "
        f"wrong={counts['wrong']}"
    )

    print("\nPer-track:")
    for row in results:
        if row.get("result") == "not_testable":
            print(
                f"  T{row['track_id']:4d} "
                f"{row['truth']:18s} NOT TESTABLE"
            )
        else:
            print(
                f"  T{row['track_id']:4d} "
                f"{row['truth']:18s} -> "
                f"{row['prediction']:18s} "
                f"{row['outcome']:9s} "
                f"{row['votes']}"
            )

    if confusion:
        print("\nConfusions:")
        for (truth, predicted), count in confusion.most_common():
            print(f"  {truth} -> {predicted}: {count}")

    output = args.recording / "tracking" / "validation.json"
    output.write_text(json.dumps({
        "threshold": args.threshold,
        "margin": args.margin,
        "results": results,
    }, indent=2) + "\n")

    print(f"\nDetails written to: {output}")


if __name__ == "__main__":
    main()

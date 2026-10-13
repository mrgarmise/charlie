"""Learn and evaluate a simple Robotron next-position prediction model.

This is an offline PPAL meditation stage. It consumes reconstructed trajectories,
learns motion from each trajectory's own past, predicts the next observed
position, measures prediction error, and writes durable evidence for later
tracking/reconstruction work.

No controller is opened and no live policy is changed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path


def _xy(point):
    return float(point["center"][0]), float(point["center"][1])


def _velocity(history, window=3):
    """Estimate velocity from up to `window` most recent observations."""
    if len(history) < 2:
        return 0.0, 0.0
    usable = history[-window:]
    first, last = usable[0], usable[-1]
    dt = int(last["tick"]) - int(first["tick"])
    if dt <= 0:
        return 0.0, 0.0
    x0, y0 = _xy(first)
    x1, y1 = _xy(last)
    return (x1 - x0) / dt, (y1 - y0) / dt


def predict_next(history, next_tick, window=3):
    """Constant-velocity prediction using only observations before next_tick."""
    last = history[-1]
    x, y = _xy(last)
    dt = int(next_tick) - int(last["tick"])
    vx, vy = _velocity(history, window=window)
    return x + vx * dt, y + vy * dt


def prediction_rows(track, window=3, max_gap=5):
    """Generate causal predictions for one reconstructed trajectory."""
    path = sorted(track.get("path", []), key=lambda p: int(p["tick"]))
    out = []
    for index in range(1, len(path)):
        # predict_next consults only the last window, never the growing prefix.
        history = path[max(0,index-window):index] if window>0 else path[:index]
        actual = path[index]
        gap = int(actual["tick"]) - int(history[-1]["tick"])
        if gap <= 0 or gap > max_gap:
            continue
        px, py = predict_next(history, int(actual["tick"]), window=window)
        ax, ay = _xy(actual)
        error = math.hypot(ax - px, ay - py)
        out.append({
            "track_id": int(track["track_id"]),
            "source_track_ids": list(track.get("merged_from",
                                               [track["track_id"]])),
            "from_tick": int(history[-1]["tick"]),
            "tick": int(actual["tick"]),
            "gap": gap,
            "predicted": [px, py],
            "actual": [ax, ay],
            "error": error,
        })
    return out


def summarize(predictions):
    errors = sorted(float(p["error"]) for p in predictions)
    if not errors:
        return {
            "predictions": 0,
            "mean_error": None,
            "median_error": None,
            "p90_error": None,
            "within_2": 0.0,
            "within_4": 0.0,
            "within_7": 0.0,
        }

    def percentile(q):
        index = min(len(errors) - 1, max(0, math.ceil(q * len(errors)) - 1))
        return errors[index]

    n = len(errors)
    mid = n // 2
    median = (errors[mid] if n % 2
              else (errors[mid - 1] + errors[mid]) / 2)
    return {
        "predictions": n,
        "mean_error": sum(errors) / n,
        "median_error": median,
        "p90_error": percentile(0.90),
        "within_2": 100.0 * sum(e <= 2.0 for e in errors) / n,
        "within_4": 100.0 * sum(e <= 4.0 for e in errors) / n,
        "within_7": 100.0 * sum(e <= 7.0 for e in errors) / n,
    }


def candidate_matches(prediction, observations, radius=7.0):
    """Rank same/future-tick observations by distance from predicted position.

    This is deliberately generic: reconstruction can later use these rankings
    instead of raw previous-position proximity.
    """
    px, py = prediction
    ranked = []
    for item in observations:
        x, y = _xy(item)
        distance = math.hypot(x - px, y - py)
        if distance <= radius:
            ranked.append((distance, item))
    return sorted(ranked, key=lambda x: x[0])


def evaluate(tracks, window=3, max_gap=5):
    predictions = []
    per_track = defaultdict(list)
    for track in tracks:
        rows = prediction_rows(track, window=window, max_gap=max_gap)
        predictions.extend(rows)
        per_track[int(track["track_id"])].extend(rows)

    track_summaries = []
    by_id = {int(t["track_id"]): t for t in tracks}
    for track_id, rows in per_track.items():
        stats = summarize(rows)
        track = by_id[track_id]
        track_summaries.append({
            "track_id": track_id,
            "source_track_ids": list(track.get("merged_from", [track_id])),
            "first_tick": int(track["first_tick"]),
            "last_tick": int(track["last_tick"]),
            "observations": int(track.get("observations",
                                          len(track.get("path", [])))),
            "candidate_kinds": track.get("candidate_kinds", {}),
            **stats,
        })
    track_summaries.sort(
        key=lambda x: (-x["predictions"],
                       float("inf") if x["mean_error"] is None
                       else x["mean_error"]))
    return predictions, track_summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("--window", type=int, default=3,
                        help="observations used for velocity estimate")
    parser.add_argument("--max-gap", type=int, default=5,
                        help="largest observation gap to predict across")
    args = parser.parse_args()

    source_path = args.replay_dir / "reconstructed-tracks.json"
    if not source_path.exists():
        parser.error(
            f"{source_path} does not exist; run reconstruct_robotron_tracks first")

    doc = json.loads(source_path.read_text())
    tracks = doc.get("tracks", [])
    predictions, track_summaries = evaluate(
        tracks, window=args.window, max_gap=args.max_gap)
    overall = summarize(predictions)

    # Compare ordinary consecutive observations with predictions crossing gaps.
    adjacent = summarize([p for p in predictions if p["gap"] == 1])
    gap = summarize([p for p in predictions if p["gap"] > 1])

    result = {
        "schema": "charlie-robotron-prediction-v1",
        "source": str(source_path),
        "model": {
            "kind": "causal_constant_velocity",
            "window": args.window,
            "max_gap": args.max_gap,
            "units": "normalized_playfield_coordinates",
        },
        "summary": overall,
        "adjacent_summary": adjacent,
        "gap_summary": gap,
        "track_summaries": track_summaries,
        "predictions": predictions,
    }
    output = args.replay_dir / "predictions.json"
    output.write_text(json.dumps(result, indent=2) + "\n")

    def show(label, stats):
        if not stats["predictions"]:
            print(f"{label}: no predictions")
            return
        print(
            f"{label}: n={stats['predictions']} "
            f"mean={stats['mean_error']:.3f} "
            f"median={stats['median_error']:.3f} "
            f"p90={stats['p90_error']:.3f} "
            f"within2={stats['within_2']:.1f}% "
            f"within4={stats['within_4']:.1f}% "
            f"within7={stats['within_7']:.1f}%"
        )

    print(f"PREDICTION MODEL: {len(tracks)} reconstructed tracks")
    print(f"MODEL: constant velocity, history window={args.window}, "
          f"max gap={args.max_gap}")
    show("ALL", overall)
    show("ADJACENT", adjacent)
    show("GAPS", gap)
    print("MOST TESTED TRACKS:")
    for item in track_summaries[:8]:
        print(
            "  track={} predictions={} mean={:.3f} kinds={} sources={}".format(
                item["track_id"], item["predictions"],
                item["mean_error"], item["candidate_kinds"],
                item["source_track_ids"]))
    print(f"Evidence: {output}")


if __name__ == "__main__":
    main()

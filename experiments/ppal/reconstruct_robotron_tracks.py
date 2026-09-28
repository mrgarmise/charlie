"""Offline Robotron track reconstruction.

Second-pass "meditation" over SpriteTracker output.  Live tracking must make
forward-only decisions; this pass may inspect whole trajectories and join
non-overlapping fragments that are spatially/motion compatible.

It never opens a controller, changes live policy, or overwrites tracks.json.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path


def _point(item):
    return float(item["center"][0]), float(item["center"][1])


def _path(track):
    return sorted(track.get("path", []), key=lambda p: int(p["tick"]))


def _velocity(track, samples=3):
    path = _path(track)
    if len(path) < 2:
        return 0.0, 0.0
    usable = path[-samples:]
    first, last = usable[0], usable[-1]
    dt = int(last["tick"]) - int(first["tick"])
    if dt <= 0:
        return 0.0, 0.0
    x0, y0 = _point(first)
    x1, y1 = _point(last)
    return (x1 - x0) / dt, (y1 - y0) / dt


def _kind_counts(track):
    return Counter(track.get("candidate_kinds", {}))


def _kind_penalty(left, right):
    """Soft evidence only: identity classification may change along one object."""
    a, b = _kind_counts(left), _kind_counts(right)
    if not a or not b:
        return 0.0
    ka = {k for k, n in a.items() if n and k != "unknown"}
    kb = {k for k, n in b.items() if n and k != "unknown"}
    if not ka or not kb or ka & kb:
        return 0.0
    return 1.5


def link_score(left, right, max_gap=5, base_distance=4.0,
               distance_per_gap=2.0):
    """Return a lower-is-better fragment link score, or None if implausible."""
    end_tick = int(left["last_tick"])
    start_tick = int(right["first_tick"])
    gap = start_tick - end_tick
    if gap <= 0 or gap > max_gap:
        return None

    lp = _path(left)
    rp = _path(right)
    if not lp or not rp:
        return None

    ex, ey = _point(lp[-1])
    sx, sy = _point(rp[0])
    vx, vy = _velocity(left)
    predicted = (ex + vx * gap, ey + vy * gap)
    distance = math.hypot(sx - predicted[0], sy - predicted[1])
    allowed = base_distance + distance_per_gap * gap
    if distance > allowed:
        return None

    # Prefer short temporal gaps, close predicted positions and compatible
    # appearance evidence.  Penalty is intentionally soft.
    return distance + 0.65 * (gap - 1) + _kind_penalty(left, right)


def merge_tracks(left, right):
    path = _path(left) + _path(right)
    kinds = _kind_counts(left) + _kind_counts(right)
    merged_from = list(left.get("merged_from", [left["track_id"]]))
    merged_from += list(right.get("merged_from", [right["track_id"]]))
    start = path[0]["center"]
    end = path[-1]["center"]
    return {
        "track_id": min(merged_from),
        "first_tick": int(path[0]["tick"]),
        "last_tick": int(path[-1]["tick"]),
        "age_frames": int(path[-1]["tick"]) - int(path[0]["tick"]) + 1,
        "observations": int(left.get("observations", len(_path(left))))
                        + int(right.get("observations", len(_path(right)))),
        "displacement": math.hypot(float(end[0]) - float(start[0]),
                                   float(end[1]) - float(start[1])),
        "start": list(start),
        "end": list(end),
        "candidate_kinds": dict(sorted(kinds.items())),
        "path": path,
        "merged_from": merged_from,
    }


def reconstruct(tracks, max_gap=5, base_distance=4.0,
                distance_per_gap=2.0):
    """Greedily join the strongest non-overlapping fragment pair until stable."""
    working = []
    for track in tracks:
        item = dict(track)
        item["merged_from"] = list(track.get("merged_from", [track["track_id"]]))
        working.append(item)

    merges = []
    while True:
        candidates = []
        for i, left in enumerate(working):
            for j, right in enumerate(working):
                if i == j:
                    continue
                score = link_score(left, right, max_gap, base_distance,
                                   distance_per_gap)
                if score is not None:
                    candidates.append((score, int(left["last_tick"]),
                                       int(right["first_tick"]), i, j))
        if not candidates:
            break

        score, _, _, i, j = min(candidates)
        left, right = working[i], working[j]
        combined = merge_tracks(left, right)
        merges.append({
            "left": list(left["merged_from"]),
            "right": list(right["merged_from"]),
            "result": list(combined["merged_from"]),
            "score": round(score, 4),
        })
        for index in sorted((i, j), reverse=True):
            del working[index]
        working.append(combined)

    working.sort(key=lambda t: (int(t["first_tick"]), int(t["track_id"])))
    return working, merges


def self_lineages(rows, reconstructed):
    """Map replay SELF track IDs onto reconstructed physical-track candidates."""
    used = Counter(
        int(row["self_track_id"])
        for row in rows
        if row.get("self_track_id") is not None and row.get("player") is not None
    )
    lineages = []
    for track in reconstructed:
        source_ids = set(int(x) for x in track.get("merged_from", []))
        hits = sum(count for tid, count in used.items() if tid in source_ids)
        if hits:
            lineages.append({
                "reconstructed_track_id": track["track_id"],
                "source_track_ids": sorted(source_ids),
                "self_frame_votes": hits,
                "first_tick": track["first_tick"],
                "last_tick": track["last_tick"],
                "observations": track["observations"],
                "candidate_kinds": track.get("candidate_kinds", {}),
            })
    return sorted(lineages, key=lambda x: (-x["self_frame_votes"],
                                           x["first_tick"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("--max-gap", type=int, default=5)
    parser.add_argument("--base-distance", type=float, default=4.0)
    parser.add_argument("--distance-per-gap", type=float, default=2.0)
    args = parser.parse_args()

    source = json.loads((args.replay_dir / "tracks.json").read_text())
    rows = json.loads((args.replay_dir / "replay.json").read_text())
    tracks = source.get("tracks", [])
    rebuilt, merges = reconstruct(
        tracks, args.max_gap, args.base_distance, args.distance_per_gap)
    lineages = self_lineages(rows, rebuilt)

    frames = max((int(r.get("tick", -1)) for r in rows), default=-1) + 1
    result = {
        "schema": "charlie-robotron-reconstructed-tracks-v1",
        "source": str(args.replay_dir / "tracks.json"),
        "parameters": {
            "max_gap": args.max_gap,
            "base_distance": args.base_distance,
            "distance_per_gap": args.distance_per_gap,
        },
        "summary": {
            "frames": frames,
            "original_tracks": len(tracks),
            "reconstructed_tracks": len(rebuilt),
            "fragments_merged": len(tracks) - len(rebuilt),
            "merge_operations": len(merges),
            "original_tracks_per_frame":
                round(len(tracks) / frames, 3) if frames else 0.0,
            "reconstructed_tracks_per_frame":
                round(len(rebuilt) / frames, 3) if frames else 0.0,
            "self_lineage_candidates": len(lineages),
        },
        "self_lineages": lineages,
        "merges": merges,
        "tracks": rebuilt,
    }
    output = args.replay_dir / "reconstructed-tracks.json"
    output.write_text(json.dumps(result, indent=2) + "\n")

    s = result["summary"]
    print(f"TRACK RECONSTRUCTION: {s['original_tracks']} -> "
          f"{s['reconstructed_tracks']} tracks")
    print(f"FRAGMENTS MERGED: {s['fragments_merged']} "
          f"({s['merge_operations']} operations)")
    print(f"TRACKS/FRAME: {s['original_tracks_per_frame']:.3f} -> "
          f"{s['reconstructed_tracks_per_frame']:.3f}")
    print(f"SELF LINEAGE CANDIDATES: {s['self_lineage_candidates']}")
    for item in lineages[:5]:
        print("  SELF? track={} votes={} frames={}-{} sources={} kinds={}".format(
            item["reconstructed_track_id"], item["self_frame_votes"],
            item["first_tick"], item["last_tick"],
            item["source_track_ids"], item["candidate_kinds"]))
    print(f"Evidence: {output}")


if __name__ == "__main__":
    main()

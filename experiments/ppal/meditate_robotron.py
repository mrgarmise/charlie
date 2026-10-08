"""Iterative offline Robotron predict -> reconstruct -> evaluate loop.

Uses motion prediction to reconnect raw SpriteTracker fragments, then relearns
motion from the improved trajectories and repeats until stable or max iterations.

This is meditation only: no controller, no live policy changes.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
import json
import math
from pathlib import Path

from experiments.ppal.predict_robotron import evaluate, summarize


def _path(track):
    return sorted(track.get("path", []), key=lambda p: int(p["tick"]))


def _xy(point):
    return float(point["center"][0]), float(point["center"][1])


def _velocity(track, window=3, path=None):
    path = _path(track) if path is None else path
    if len(path) < 2:
        return 0.0, 0.0
    usable = path[-window:]
    a, b = usable[0], usable[-1]
    dt = int(b["tick"]) - int(a["tick"])
    if dt <= 0:
        return 0.0, 0.0
    ax, ay = _xy(a)
    bx, by = _xy(b)
    return (bx - ax) / dt, (by - ay) / dt


def _kind_counts(track):
    return Counter(track.get("candidate_kinds", {}))


def _kind_penalty(a, b):
    ka = {k for k, n in _kind_counts(a).items() if n and k != "unknown"}
    kb = {k for k, n in _kind_counts(b).items() if n and k != "unknown"}
    if not ka or not kb or ka & kb:
        return 0.0
    return 1.5


def _prepare(track, window):
    path=_path(track)
    if not path:return None
    return dict(start=_xy(path[0]),end=_xy(path[-1]),velocity=_velocity(track,window,path),
        kinds={k for k,n in _kind_counts(track).items() if n and k!='unknown'})


def predicted_link(left, right, window=3, max_gap=5,
                   base_radius=2.0, radius_per_gap=1.8, prepared=None):
    """Score A->B using A's predicted future location; None means implausible."""
    gap = int(right["first_tick"]) - int(left["last_tick"])
    if gap <= 0 or gap > max_gap:
        return None

    a,b=prepared if prepared is not None else (_prepare(left,window),_prepare(right,window))
    if a is None or b is None:
        return None

    ex, ey = a['end']
    sx, sy = b['start']
    vx, vy = a['velocity']
    px, py = ex + vx * gap, ey + vy * gap
    error = math.hypot(sx - px, sy - py)
    radius = base_radius + radius_per_gap * gap
    if error > radius:
        return None

    return {
        "score": error + 0.55 * (gap - 1) + (0. if not a['kinds'] or not b['kinds'] or a['kinds'] & b['kinds'] else 1.5),
        "prediction_error": error,
        "gap": gap,
        "predicted": [px, py],
        "actual": [sx, sy],
        "radius": radius,
    }


def _merge(left, right):
    path = _path(left) + _path(right)
    kinds = _kind_counts(left) + _kind_counts(right)
    sources = list(left.get("merged_from", [left["track_id"]]))
    sources += list(right.get("merged_from", [right["track_id"]]))
    x0, y0 = _xy(path[0])
    x1, y1 = _xy(path[-1])
    return {
        "track_id": min(int(x) for x in sources),
        "first_tick": int(path[0]["tick"]),
        "last_tick": int(path[-1]["tick"]),
        "age_frames": int(path[-1]["tick"]) - int(path[0]["tick"]) + 1,
        "observations": int(left.get("observations", len(_path(left))))
                        + int(right.get("observations", len(_path(right)))),
        "displacement": math.hypot(x1 - x0, y1 - y0),
        "start": [x0, y0],
        "end": [x1, y1],
        "candidate_kinds": dict(sorted(kinds.items())),
        "path": path,
        "merged_from": sources,
    }


def _clone_raw(tracks):
    out = []
    for t in tracks:
        item = dict(t)
        item["merged_from"] = list(t.get("merged_from", [t["track_id"]]))
        out.append(item)
    return out


def reconstruct_once(tracks, window=3, max_gap=5,
                     base_radius=2.0, radius_per_gap=1.8, on_progress=None, resume_state=None):
    """Conservative mutual-best predicted matching for one iteration."""
    state = resume_state if resume_state is not None else {}
    if 'rebuilt' in state:
        return state['rebuilt'], state['merge_log']
    candidates = state.setdefault('candidates', [])
    # Only future onsets inside max_gap can link. Preserve original j order,
    # including tie-breaking, while avoiding quadratic impossible pairs.
    onsets = sorted((int(t['first_tick']), j) for j,t in enumerate(tracks))
    times = [at for at,_ in onsets]
    prepared={}
    for i in range(state.get("left", 0), len(tracks)):
        left = tracks[i]
        if on_progress: on_progress()
        end = int(left['last_tick'])
        start, stop = bisect_right(times,end), bisect_right(times,end+max_gap)
        neighbors = sorted(j for _,j in onsets[start:stop])
        for position in range(state.get('neighbor', 0), len(neighbors)):
            if on_progress: on_progress()
            j = neighbors[position]
            right = tracks[j]
            if i == j:
                state["neighbor"] = position + 1
                continue
            if i not in prepared:prepared[i]=_prepare(left,window)
            if j not in prepared:prepared[j]=_prepare(right,window)
            info = predicted_link(left, right, window, max_gap,
                                  base_radius, radius_per_gap,(prepared[i],prepared[j]))
            if info is not None:
                candidates.append((info["score"], i, j, info))
            state['neighbor'] = position + 1
        state['left'] = i + 1
        state['neighbor'] = 0

    if on_progress: on_progress()
    # Mutual-best prevents a busy region from greedily swallowing alternatives.
    best_out, best_in = {}, {}
    for score, i, j, info in sorted(candidates, key=lambda x: x[0]):
        best_out.setdefault(i, (score, j, info))
        best_in.setdefault(j, (score, i, info))

    links = []
    used = set()
    for i, (score, j, info) in best_out.items():
        incoming = best_in.get(j)
        if incoming is None or incoming[1] != i:
            continue
        if i in used or j in used:
            continue
        links.append((i, j, info))
        used.update((i, j))

    result = []
    merge_log = []
    for i, j, info in links:
        merged = _merge(tracks[i], tracks[j])
        result.append(merged)
        merge_log.append({
            "left": list(tracks[i].get("merged_from", [tracks[i]["track_id"]])),
            "right": list(tracks[j].get("merged_from", [tracks[j]["track_id"]])),
            "result": list(merged["merged_from"]),
            "gap": info["gap"],
            "prediction_error": round(info["prediction_error"], 4),
            "score": round(info["score"], 4),
            "predicted": [round(x, 4) for x in info["predicted"]],
            "actual": [round(x, 4) for x in info["actual"]],
        })

    result.extend(t for idx, t in enumerate(tracks) if idx not in used)
    result.sort(key=lambda t: (int(t["first_tick"]), int(t["track_id"])))
    state.update(rebuilt=result, merge_log=merge_log)
    return result, merge_log


def motion_class(track, stationary_threshold=1.0):
    return ("stationary" if float(track.get("displacement", 0.0))
            <= stationary_threshold else "moving")


def quality(tracks, window=3, max_gap=5):
    predictions, _ = evaluate(tracks, window=window, max_gap=max_gap)
    moving_ids = {int(t["track_id"]) for t in tracks
                  if motion_class(t) == "moving"}
    stationary_ids = {int(t["track_id"]) for t in tracks
                      if motion_class(t) == "stationary"}
    return {
        "all": summarize(predictions),
        "adjacent": summarize([p for p in predictions if p["gap"] == 1]),
        "gaps": summarize([p for p in predictions if p["gap"] > 1]),
        "moving": summarize([p for p in predictions
                             if int(p["track_id"]) in moving_ids]),
        "stationary": summarize([p for p in predictions
                                 if int(p["track_id"]) in stationary_ids]),
    }


def meditate(raw_tracks, iterations=6, window=3, max_gap=5,
             base_radius=2.0, radius_per_gap=1.8, on_progress=None, resume_state=None):
    tracks = _clone_raw(raw_tracks)
    history = []
    all_merges = []

    for iteration in range(1, iterations + 1):
        before = len(tracks)
        rebuilt, merges = reconstruct_once(
            tracks, window, max_gap, base_radius, radius_per_gap, on_progress=on_progress, resume_state=resume_state)
        if on_progress: on_progress()
        q = quality(rebuilt, window, max_gap)
        history.append({
            "iteration": iteration,
            "tracks_before": before,
            "tracks_after": len(rebuilt),
            "merges": len(merges),
            "quality": q,
        })
        all_merges.extend({"iteration": iteration, **m} for m in merges)
        tracks = rebuilt
        if resume_state is not None: resume_state.clear()
        if not merges:
            break

    return tracks, history, all_merges


def _fmt(stats):
    if not stats["predictions"]:
        return "n=0"
    return (
        f"n={stats['predictions']} median={stats['median_error']:.3f} "
        f"p90={stats['p90_error']:.3f} "
        f"within4={stats['within_4']:.1f}% "
        f"within7={stats['within_7']:.1f}%"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_dir", type=Path)
    parser.add_argument("--iterations", type=int, default=6)
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--max-gap", type=int, default=5)
    parser.add_argument("--base-radius", type=float, default=2.0)
    parser.add_argument("--radius-per-gap", type=float, default=1.8)
    args = parser.parse_args()

    raw_doc = json.loads((args.replay_dir / "tracks.json").read_text())
    raw_tracks = raw_doc.get("tracks", [])
    final, history, merges = meditate(
        raw_tracks, args.iterations, args.window, args.max_gap,
        args.base_radius, args.radius_per_gap)
    final_quality = quality(final, args.window, args.max_gap)

    result = {
        "schema": "charlie-robotron-predictive-meditation-v1",
        "source": str(args.replay_dir / "tracks.json"),
        "parameters": {
            "iterations": args.iterations,
            "window": args.window,
            "max_gap": args.max_gap,
            "base_radius": args.base_radius,
            "radius_per_gap": args.radius_per_gap,
        },
        "summary": {
            "raw_tracks": len(raw_tracks),
            "final_tracks": len(final),
            "fragments_merged": len(raw_tracks) - len(final),
            "iterations_run": len(history),
            "merge_operations": len(merges),
        },
        "history": history,
        "quality": final_quality,
        "merges": merges,
        "tracks": final,
    }
    output = args.replay_dir / "predictive-reconstruction.json"
    output.write_text(json.dumps(result, indent=2) + "\n")

    print(f"PREDICTIVE MEDITATION: {len(raw_tracks)} raw tracks")
    for h in history:
        print(f"ITERATION {h['iteration']}: {h['tracks_before']} -> "
              f"{h['tracks_after']} tracks; merges={h['merges']}; "
              f"moving {_fmt(h['quality']['moving'])}; "
              f"gaps {_fmt(h['quality']['gaps'])}")
    print(f"FINAL TRACKS: {len(final)}")
    print(f"MOVING: {_fmt(final_quality['moving'])}")
    print(f"STATIONARY: {_fmt(final_quality['stationary'])}")
    print(f"GAPS: {_fmt(final_quality['gaps'])}")
    print(f"Evidence: {output}")


if __name__ == "__main__":
    main()

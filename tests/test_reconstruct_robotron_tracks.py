from experiments.ppal.reconstruct_robotron_tracks import (
    link_score, merge_tracks, reconstruct, self_lineages,
)


def track(tid, first, points, kind="unknown"):
    path = [{"tick": first + i, "center": [x, y]}
            for i, (x, y) in enumerate(points)]
    return {
        "track_id": tid,
        "first_tick": first,
        "last_tick": first + len(points) - 1,
        "age_frames": len(points),
        "observations": len(points),
        "displacement": 0.0,
        "start": path[0]["center"],
        "end": path[-1]["center"],
        "candidate_kinds": {kind: len(points)},
        "path": path,
    }


def test_links_motion_compatible_fragments():
    a = track(1, 0, [(10, 10), (11, 10), (12, 10)], "grunt")
    b = track(9, 4, [(14, 10), (15, 10)], "grunt")
    assert link_score(a, b) is not None


def test_rejects_distant_fragment():
    a = track(1, 0, [(10, 10), (11, 10)])
    b = track(2, 3, [(80, 80)])
    assert link_score(a, b) is None


def test_never_merges_overlapping_tracks():
    a = track(1, 0, [(10, 10), (11, 10), (12, 10)])
    b = track(2, 2, [(12, 10), (13, 10)])
    assert link_score(a, b) is None
    assert link_score(b, a) is None


def test_reconstruct_can_join_chain():
    tracks = [
        track(1, 0, [(10, 10), (11, 10)]),
        track(2, 3, [(13, 10), (14, 10)]),
        track(3, 6, [(16, 10), (17, 10)]),
    ]
    rebuilt, merges = reconstruct(tracks)
    assert len(rebuilt) == 1
    assert rebuilt[0]["merged_from"] == [1, 2, 3]
    assert len(merges) == 2


def test_kind_mismatch_is_soft_not_prohibited():
    a = track(1, 0, [(10, 10), (11, 10)], "unknown")
    b = track(2, 3, [(13, 10)], "player")
    assert link_score(a, b) is not None


def test_self_votes_follow_merged_lineage():
    a = track(1, 0, [(10, 10), (11, 10)])
    b = track(2, 3, [(13, 10)])
    rebuilt, _ = reconstruct([a, b])
    rows = [
        {"self_track_id": 1, "player": [10, 10]},
        {"self_track_id": 1, "player": [11, 10]},
        {"self_track_id": 2, "player": [13, 10]},
    ]
    result = self_lineages(rows, rebuilt)
    assert result[0]["self_frame_votes"] == 3
    assert result[0]["source_track_ids"] == [1, 2]

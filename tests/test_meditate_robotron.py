from experiments.ppal.meditate_robotron import (
    meditate, motion_class, predicted_link, reconstruct_once,
)


def track(tid, first, coords, kind="unknown"):
    path = [{"tick": first + i, "center": [x, y]}
            for i, (x, y) in enumerate(coords)]
    x0, y0 = coords[0]
    x1, y1 = coords[-1]
    return {
        "track_id": tid,
        "first_tick": first,
        "last_tick": first + len(coords) - 1,
        "observations": len(coords),
        "displacement": ((x1-x0)**2 + (y1-y0)**2)**0.5,
        "candidate_kinds": {kind: len(coords)},
        "path": path,
    }


def test_prediction_links_motion_continuation():
    a = track(1, 0, [(10, 10), (11, 10), (12, 10)])
    b = track(2, 4, [(14, 10), (15, 10)])
    info = predicted_link(a, b)
    assert info is not None
    assert info["prediction_error"] == 0.0


def test_prediction_rejects_wrong_direction_candidate():
    a = track(1, 0, [(10, 10), (11, 10), (12, 10)])
    b = track(2, 4, [(5, 10)])
    assert predicted_link(a, b) is None


def test_mutual_best_chooses_best_continuation():
    a = track(1, 0, [(10, 10), (11, 10), (12, 10)])
    good = track(2, 4, [(14, 10), (15, 10)])
    worse = track(3, 4, [(17, 10), (18, 10)])
    rebuilt, merges = reconstruct_once([a, good, worse])
    assert len(merges) == 1
    assert merges[0]["right"] == [2]
    assert len(rebuilt) == 2


def test_meditation_repeats_until_chain_joined():
    tracks = [
        track(1, 0, [(0, 0), (1, 0)]),
        track(2, 3, [(3, 0), (4, 0)]),
        track(3, 6, [(6, 0), (7, 0)]),
    ]
    final, history, merges = meditate(tracks, iterations=6)
    assert len(final) == 1
    assert len(merges) == 2
    assert history[-1]["merges"] == 0


def test_stationary_and_moving_separate():
    still = track(1, 0, [(5, 5), (5, 5), (5, 5)])
    moving = track(2, 0, [(5, 5), (6, 5), (7, 5)])
    assert motion_class(still) == "stationary"
    assert motion_class(moving) == "moving"


def test_overlapping_tracks_never_link():
    a = track(1, 0, [(0, 0), (1, 0), (2, 0)])
    b = track(2, 2, [(2, 0), (3, 0)])
    assert predicted_link(a, b) is None

import math

from experiments.ppal.predict_robotron import (
    candidate_matches, evaluate, predict_next, prediction_rows, summarize,
)


def point(tick, x, y):
    return {"tick": tick, "center": [x, y]}


def track(tid, points):
    return {
        "track_id": tid,
        "first_tick": points[0]["tick"],
        "last_tick": points[-1]["tick"],
        "observations": len(points),
        "candidate_kinds": {"unknown": len(points)},
        "path": points,
        "merged_from": [tid],
    }


def test_constant_velocity_predicts_straight_motion():
    history = [point(0, 10, 20), point(1, 12, 20), point(2, 14, 20)]
    assert predict_next(history, 3) == (16.0, 20.0)


def test_prediction_is_causal():
    t = track(1, [
        point(0, 0, 0), point(1, 1, 0), point(2, 2, 0),
        point(3, 100, 100),
    ])
    rows = prediction_rows(t)
    # Prediction at tick 2 cannot have been influenced by the future jump at 3.
    row = next(r for r in rows if r["tick"] == 2)
    assert row["predicted"] == [2.0, 0.0]
    assert row["error"] == 0.0


def test_predicts_across_short_gap():
    t = track(1, [point(0, 10, 10), point(1, 11, 10),
                  point(4, 14, 10)])
    rows = prediction_rows(t, max_gap=5)
    row = rows[-1]
    assert row["gap"] == 3
    assert row["predicted"] == [14.0, 10.0]
    assert row["error"] == 0.0


def test_skips_gap_larger_than_limit():
    t = track(1, [point(0, 0, 0), point(1, 1, 0), point(20, 20, 0)])
    rows = prediction_rows(t, max_gap=5)
    assert [r["tick"] for r in rows] == [1]


def test_summary_known_errors():
    s = summarize([{"error": 0.0}, {"error": 2.0}, {"error": 4.0}])
    assert s["predictions"] == 3
    assert s["mean_error"] == 2.0
    assert s["median_error"] == 2.0
    assert s["p90_error"] == 4.0


def test_candidate_matching_prefers_predicted_location():
    observations = [point(5, 14, 10), point(5, 20, 10), point(5, 13, 10)]
    ranked = candidate_matches((14, 10), observations, radius=7)
    assert ranked[0][1]["center"] == [14, 10]
    assert len(ranked) == 3


def test_evaluate_keeps_tracks_separate():
    tracks = [
        track(1, [point(0, 0, 0), point(1, 1, 0), point(2, 2, 0)]),
        track(2, [point(0, 10, 10), point(1, 10, 11)]),
    ]
    predictions, summaries = evaluate(tracks)
    assert len(predictions) == 3
    assert {s["track_id"] for s in summaries} == {1, 2}

from experiments.ppal.eyes.tracking import SpriteTracker
from experiments.ppal.eyes.detectors import Detection


def d(x, y, kind='unknown'):
    return Detection(kind, (x, y), (0, 0, 10, 10), 50)


def test_track_persists_across_motion():
    tracker = SpriteTracker(max_distance=5)
    first = tracker.update(0, [d(10, 10)])
    second = tracker.update(1, [d(12, 11)])

    assert first[0] == second[0]
    track = tracker.active[first[0]]
    assert track.observations == 2
    assert track.displacement > 0


def test_far_object_starts_new_track():
    tracker = SpriteTracker(max_distance=5)
    first = tracker.update(0, [d(10, 10)])
    second = tracker.update(1, [d(50, 50)])

    assert first[0] != second[0]


def test_tracks_survive_short_occlusion():
    tracker = SpriteTracker(max_distance=5, max_missed=2)
    first = tracker.update(0, [d(10, 10)])

    tracker.update(1, [])
    tracker.update(2, [])
    third = tracker.update(3, [d(11, 10)])

    assert third[0] == first[0]


def test_track_expires_after_misses():
    tracker = SpriteTracker(max_distance=5, max_missed=1)
    track_id = tracker.update(0, [d(10, 10)])[0]

    tracker.update(1, [])
    tracker.update(2, [])

    assert track_id not in tracker.active
    assert any(t.track_id == track_id for t in tracker.finished)


def test_finish_returns_active_tracks():
    tracker = SpriteTracker()
    tracker.update(0, [d(10, 10)])
    tracks = tracker.finish()

    assert len(tracks) == 1
    assert not tracker.active

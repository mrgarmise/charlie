"""Existing main lifecycle fixtures at the application-owned feeder boundary."""
from contextlib import contextmanager
from stimulus.bus import StimulusBus


def install(monkeypatch, application, camera):
    @contextmanager
    def fake_feeders(*args, **kwargs):
        try:yield StimulusBus()
        finally:camera.close()
    monkeypatch.setattr(application,'application_camera_feeders',fake_feeders)
    monkeypatch.setattr('vision.camera_source.TrackingCamera',lambda subscription:camera)

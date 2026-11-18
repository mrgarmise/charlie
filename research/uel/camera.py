"""Image-plane simulation and immutable, read-only SQLite replay."""

from pathlib import Path
from random import Random
import sqlite3
import time

import numpy as np

from .core import Channel, Observation, Profile


class CameraTwin:
    profile = Profile("projected target", "1",
                      (Channel("amber", "fraction", -1, 1), Channel("jade", "fraction", -1, 1)),
                      (Channel("column", "px", 0, 159), Channel("row", "px", 0, 119)),
                      (0., 0.))

    def __init__(self, *, backlash=0.02, delay=1):
        self.backlash = backlash
        self.delay = delay
        self.occluded = False
        self.stopped = True

    def reset(self, seed):
        self.rng = Random(seed)
        self.target = np.array([105., 40.])
        self.queue = [self.profile.neutral] * self.delay
        self.stopped = False
        return self.observe()

    def observe(self):
        if self.occluded:
            return Observation((), time.monotonic())
        x, y = np.clip(self.target + [self.rng.gauss(0, .18), self.rng.gauss(0, .18)],
                       [1, 1], [158, 118]).round().astype(int)
        image = np.zeros((120, 160), dtype=np.uint8)
        image[y-1:y+2, x-1:x+2] = 255
        rows, columns = np.nonzero(image > 200)
        return Observation((float(columns.mean()), float(rows.mean())), time.monotonic())

    def step(self, action, duration):
        if self.stopped:
            raise RuntimeError("camera twin stopped")
        self.profile.command(action, duration)
        self.queue.append(action)
        incoming = self.queue.pop(0)
        control = np.sign(incoming) * np.maximum(0, np.abs(incoming) - self.backlash)
        self.target = np.clip(self.target + duration / .1 * np.array([[-20., 2.], [3., 18.]]) @ control,
                              [1, 1], [158, 118])
        return self.observe()

    def stop(self, reason):
        self.stopped = True


class CameraTrial:
    """Expose a fixed command and washout window as one experimental trial."""

    profile = CameraTwin.profile

    def __init__(self, camera):
        self.camera = camera

    def reset(self, seed):
        return self.camera.reset(seed)

    def step(self, action, duration):
        reading = self.camera.step(action, duration)
        for _ in range(self.camera.delay):
            reading = self.camera.step(self.profile.neutral, duration)
        return reading

    def stop(self, reason):
        self.camera.stop(reason)


def replay(path, session):
    """Read observations without opening a writable SQLite connection."""
    import hashlib
    import json

    uri = Path(path).resolve().as_uri() + "?mode=ro"
    from contextlib import closing

    with closing(sqlite3.connect(uri, uri=True)) as db:
        for payload, digest in db.execute(
            "SELECT payload,digest FROM events WHERE session=? AND phase='result' ORDER BY trial",
            (session,),
        ):
            if hashlib.sha256(payload.encode()).hexdigest() != digest:
                raise ValueError("corrupt replay")
            yield json.loads(payload)


def physical_connector():
    raise PermissionError("DENIED_PHYSICAL_AUTHORITY")

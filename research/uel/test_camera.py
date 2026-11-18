from itertools import product

import numpy as np
import pytest

from .camera import CameraTrial, CameraTwin, physical_connector, replay
from .core import Journal, Session
from .learner import Model


@pytest.mark.parametrize("seed", [7, 52, 102])
def test_camera_learns_reversal_and_centers(tmp_path, seed):
    camera = CameraTwin()
    adapter = CameraTrial(camera)
    path = tmp_path / "twin.db"
    journal = Journal(path, "camera", adapter.profile, "test")
    session = Session(adapter, journal, trials=9, seconds=10)
    actions = list(product((-.8, 0., .8), repeat=2))
    outputs = []
    for action in actions:
        before, after = session.run(action, .1, seed)
        outputs.append(np.subtract(after.values, before.values))
    session.cancel("completed")
    model = Model.fit(actions, outputs)
    assert np.sign(model.weights).tolist() == [[-1, 1], [1, 1]]
    assert len(list(replay(path, "camera"))) == 9
    target = np.array([80, 60])
    final_errors = []
    for weights in (model.weights, np.eye(2)*20):
        reading = adapter.reset(seed)
        for _ in range(5):
            error = target - reading.values
            command = np.clip(np.linalg.solve(weights.T, error), -.6, .6)
            reading = adapter.step(tuple(map(float, command)), .1)
        final_errors.append(np.linalg.norm(target - reading.values))
        adapter.stop("complete")
    assert final_errors[0] <= 2
    assert final_errors[1] > 20


def test_occlusion_stops(tmp_path):
    camera = CameraTwin()
    adapter = CameraTrial(camera)
    journal = Journal(tmp_path / "twin.db", "camera", adapter.profile, "test")
    session = Session(adapter, journal, trials=1, seconds=10)
    camera.occluded = True
    with pytest.raises(ValueError):
        session.run((1., 0.), .1, 0)
    assert camera.stopped


def test_physical_connector_denied():
    with pytest.raises(PermissionError, match="DENIED_PHYSICAL_AUTHORITY"):
        physical_connector()

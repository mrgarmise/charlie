import numpy as np
import pytest

from .benchmark import sample
from .core import Journal
from .inquiry import Question, investigate
from .learner import Model, select
from .synthetic import LinearTwin


def test_exact_mapping():
    model = Model.fit([(1, 0), (-1, 0), (0, 1), (0, -1)], [(2,), (-2,), (-3,), (3,)])
    prediction, halfwidth = model.predict([(0.5, 0.5)])
    assert np.sign(model.weights).tolist() == [[1], [-1]]
    assert prediction[0, 0] == pytest.approx(-0.5, abs=.01)
    assert halfwidth[0, 0] > 0


def test_selection_masks_bounds_and_increases_rank():
    profile = LinearTwin().profile
    assert select(profile, [(100, 100), (1, 0), (0, 1)], [(1, 0)], .1) == (0, 1)


def test_inquiry_requires_observability(tmp_path):
    journal = Journal(tmp_path / "trials.db", "test", LinearTwin().profile, "test")
    hypotheses = {"increases": (1,), "decreases": (-1,)}
    question = Question("direction", "operator", "experimental", "Which sign?", True)
    assert investigate(journal, 1, question, hypotheses, [-.9], .2, ["held-out"])["surviving"] == ["decreases"]
    hidden = Question("wiring", "operator", "theoretical", "Which pin?", False)
    assert investigate(journal, 2, hidden, hypotheses, [], .2, [])["status"] == "NEEDS_EXTERNAL_EVIDENCE"


@pytest.mark.parametrize("weights", [((1.1, -.4), (-.5, -1.3)), ((-.8,),)])
def test_better_than_no_action(tmp_path, weights):
    result = sample(weights, 1, "active", tmp_path)
    assert result["mae"] < .8 * result["zero_mae"]

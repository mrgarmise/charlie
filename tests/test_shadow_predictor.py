from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.models import Object, Position, WorldState
from experiments.ppal.shadow_predictor import ShadowPredictor


def world(tick, player=(50, 50), targets=(), threats=()):
    return WorldState(
        tick=tick, player=Position(*player),
        targets=tuple(Object(i, Position(x, y)) for i, x, y in targets),
        threats=tuple(Object(i, Position(x, y)) for i, x, y in threats),
        alive=True,
    )


def test_projects_persistent_threat_forward():
    p = ShadowPredictor()
    p.observe(world(0, threats=(("threat_1", 70, 50),)))
    w = world(1, threats=(("threat_1", 68, 50),))
    p.observe(w)
    future = p.project(w)
    assert future.threats[0].position.x == 66
    assert future.threats[0].position.y == 50


def test_first_observation_is_stationary_prediction():
    p = ShadowPredictor()
    w = world(0, targets=(("human_1", 20, 30),))
    p.observe(w)
    future = p.project(w)
    assert future.targets[0].position == Position(20, 30)


def test_velocity_is_smoothed_not_future_aware():
    p = ShadowPredictor(velocity_alpha=0.5)
    p.observe(world(0, threats=(("threat_1", 0, 0),)))
    p.observe(world(1, threats=(("threat_1", 2, 0),)))
    w = world(2, threats=(("threat_1", 6, 0),))
    p.observe(w)
    future = p.project(w)
    assert future.threats[0].position.x == 9  # .5*4 + .5*2 = 3


def test_projection_clamps_playfield():
    p = ShadowPredictor()
    p.observe(world(0, threats=(("threat_1", 98, 50),)))
    w = world(1, threats=(("threat_1", 100, 50),))
    p.observe(w)
    assert p.project(w).threats[0].position.x == 100


def test_shadow_can_disagree_without_changing_live_brain():
    # Current threat is outside panic radius, predicted threat enters it.
    p = ShadowPredictor()
    p.observe(world(0, threats=(("threat_1", 65, 50),)))
    w = world(1, threats=(("threat_1", 60, 50),))
    p.observe(w)
    projected = p.project(w)

    live_goal = Forebrain().update(w)
    _, live_action = Hindbrain().decide(w, live_goal)
    shadow_goal = Forebrain().update(projected)
    _, shadow_action = Hindbrain().decide(projected, shadow_goal)

    assert live_action.reason == "no current rescue target"
    assert shadow_action.reason != live_action.reason

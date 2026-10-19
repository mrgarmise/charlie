"""Exploratory actuation creates evidence, not invented FIRE-caused identity."""
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.models import Goal, Position, WorldState
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.robotron_agency import VisualAgency, VECTORS


def discovery(two_responsive=False):
    points = [(20.,20.),(70.,70.)]
    rows, actions = [], []
    def read():
        return [(Detection('unknown',p,(0,0,10,20),100),{}) for p in points]
    class Controller:
        def execute(self, action, ms):
            actions.append(action)
            vector = VECTORS[action.move]
            for i in range(2 if two_responsive else 1):
                points[i] = tuple(points[i][j]+vector[j] for j in (0,1))
    visual = VisualAgency(bootstrap_body_fire=True)
    visual.discover(read,Controller(),record=rows.append)
    return visual, points, rows, actions


def test_fire_first_continues_past_provisional_until_movement_confirms():
    visual, points, rows, actions = discovery()
    assert [(a.move,a.fire) for a in actions[:2]] == [('STAY','E'),('STAY','N')]
    assert [(a.move,a.fire) for a in actions[2:]] == [('E','N'),('STAY','NONE'),('W','E'),('STAY','NONE'),('S','S'),('STAY','NONE')]
    assert visual.player == points[0] and visual.controlled_track_id == 2
    assert visual.agency.self_id == 2  # Existing movement certificate, not fabricated FIRE evidence.
    assert rows[-1]['identity_status'] == 'confirmed'
    assert any(r['identity_status']=='provisional' for r in rows)
    shots=[r for r in rows if r.get('phase')=='shot_origin_experiment']
    assert len(shots)==6 and all(r['command'] is None for r in shots)
    assert visual.tick == len(rows) == 16
    assert visual.agency.beliefs[2].hits == 3


def test_ambiguity_and_contradiction_do_not_fabricate_provisional_self():
    visual, points, rows, actions = discovery(two_responsive=True)
    assert visual.player is None and rows[-1]['identity_status'] == 'unknown'
    visual, points, rows, actions = discovery()
    points[0]=(points[0][0]-1,points[0][1])
    pairs = [(Detection('unknown',p,(0,0,10,20),100),{}) for p in points]
    result = visual.observe(pairs,'E',observed_at=visual.tracker.last_update['observed_at']+.3)  # contradict commanded direction
    assert result['identity_status'] == 'unknown' and visual.player is None


def test_fire_exploration_requires_no_enemy_label_and_does_not_promote_one():
    hind = Hindbrain(explore_fire=True)
    world = WorldState(0,Position(50,50),(),())
    actions = [hind.decide(world,Goal('survive'))[1] for _ in range(4)]
    assert [a.fire for a in actions] == ['N','E','S','W']
    assert all(a.move != 'STAY' for a in actions)
    assert not world.threats and not world.targets

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


def test_independent_fire_and_simultaneous_body_fire_enter_play_provisionally():
    visual, points, rows, actions = discovery()
    assert actions[0].move == 'STAY' and actions[0].fire == 'E'
    assert [(a.move,a.fire) for a in actions[1:]] == [('E','N'),('STAY','NONE'),('W','E'),('STAY','NONE')]
    assert visual.player == points[0] and visual.controlled_track_id == 1
    assert visual.agency.self_id is None  # No invented combined FIRE certificate.
    assert rows[-1]['identity_status'] == 'provisional'
    assert sum(r.get('phase')=='fire_exploration_unmeasured_body' for r in rows) == 2
    assert all(r['command'] is None for r in rows if r.get('phase')=='fire_exploration_unmeasured_body')
    assert visual.tick == len(rows) == 9  # one association per consumed exposure
    assert visual.agency.beliefs[1].hits == 2
    # Ordinary movement can earn the existing full confirmation without
    # returning to another bootstrap phase or adding a FIRE-origin gate.
    points[0] = (points[0][0],points[0][1]+1)
    pairs = [(Detection('unknown',p,(0,0,10,20),100),{}) for p in points]
    result = visual.observe(pairs,'S',observed_at=visual.tracker.last_update['observed_at']+.3)
    assert result['identity_status'] == 'confirmed' and visual.agency.self_id == 1


def test_ambiguity_and_contradiction_do_not_fabricate_provisional_self():
    visual, points, rows, actions = discovery(two_responsive=True)
    assert visual.player is None and rows[-1]['identity_status'] == 'unknown'
    visual, points, rows, actions = discovery()
    pairs = [(Detection('unknown',p,(0,0,10,20),100),{}) for p in points]
    result = visual.observe(pairs,'E',observed_at=visual.tracker.last_update['observed_at']+.3)  # no commanded response
    assert result['identity_status'] == 'unknown' and visual.player is None


def test_fire_exploration_requires_no_enemy_label_and_does_not_promote_one():
    hind = Hindbrain(explore_fire=True)
    world = WorldState(0,Position(50,50),(),())
    actions = [hind.decide(world,Goal('survive'))[1] for _ in range(4)]
    assert [a.fire for a in actions] == ['N','E','S','W']
    assert all(a.move != 'STAY' for a in actions)
    assert not world.threats and not world.targets

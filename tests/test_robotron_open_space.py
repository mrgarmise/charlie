"""Confirmed agency must remain actionable when semantic roles are unresolved."""
import json
from pathlib import Path
from PIL import Image

from experiments.ppal.forebrain import Forebrain
from experiments.ppal.hindbrain import Hindbrain
from experiments.ppal.models import Goal, Object, Position, WorldState
from experiments.ppal.shadow_predictor import ShadowPredictor
from experiments.ppal.score_observer import ScoreObserver
from experiments.ppal.robotron_hud import RobotronHUDObservation, RobotronHUDReader
from experiments.ppal.eyes.calibration import Calibration

FIXTURE = Path(__file__).parent/'fixtures/robotron-response-012341'


def test_all_40_recorded_idle_worlds_have_an_unlabeled_navigation_fallback():
    rows = json.loads((FIXTURE/'policy-worlds.json').read_text())['worlds']
    fore, hind = Forebrain(), Hindbrain()
    firing = 0
    assert len(rows) == 40
    for r in rows:
        assert r['recorded_action']['move'] == 'STAY' and r['recorded_action']['fire'] == 'NONE'
        groups = {role:tuple(Object(o['id'],Position(*o['position'])) for o in r[role])
                  for role in ('targets','threats','unresolved')}
        assert not groups['targets'] and groups['unresolved']
        assert all(o.id != f"sprite_{r['self_track_id']}" for os in groups.values() for o in os)
        world = WorldState(r['tick'],Position(*r['player']),**groups)
        intent, action = hind.decide(world,fore.update(world))
        assert intent.kind == 'explore' and action.move != 'STAY'
        assert 4 <= intent.destination.x <= 96 and 4 <= intent.destination.y <= 96
        if not world.threats:
            assert action.fire == 'NONE'  # UNKNOWN objects never become shooting targets.
        firing += action.fire != 'NONE'
    assert firing == 14  # Offline decisions, not a counterfactual score/survival claim.


def test_unresolved_occupancy_changes_navigation_without_semantic_promotion():
    hind = Hindbrain()
    world = WorldState(0,Position(50,50),(),(),unresolved=(Object('sprite_4',Position(52,50)),))
    intent, action = hind.decide(world,Goal('survive'))
    assert intent.destination.x < 50 and action.fire == 'NONE'
    assert not world.targets and not world.threats
    edge = WorldState(1,Position(96,96),(),())
    assert hind.decide(edge,Goal('survive'))[1].move in ('N','W','NW')
    dead = WorldState(2,Position(50,50),(),(),alive=False)
    assert hind.decide(dead,Goal('survive'))[1].move == 'STAY'


def test_soft_role_change_preserves_shadow_motion_and_physical_id():
    p = ShadowPredictor()
    first = WorldState(0,Position(50,50),(),(),unresolved=(Object('sprite_4',Position(20,20)),))
    p.observe(first)
    second = WorldState(1,Position(50,50),(),(Object('sprite_4',Position(22,20)),))
    p.observe(second)
    projected = p.project(second)
    assert projected.threats[0].id == 'sprite_4' and projected.threats[0].position.x > 22
    assert not projected.unresolved


def test_final_official_hud_300_matches_live_accepted_score():
    reader = RobotronHUDReader(Calibration.load(FIXTURE/'calibration.json'))
    result = reader.read(Image.open(FIXTURE/'final-300.jpg'))
    assert result.player1_score == 300 and result.player2_score is None


def test_score_retains_late_change_and_final_pixels_after_initial_budget(tmp_path):
    observer = ScoreObserver(Calibration.load(FIXTURE/'calibration.json'),tmp_path/'score.jsonl')
    class Reader:
        n = 0
        def read(self, frame):
            self.n += 1
            return RobotronHUDObservation(0 if self.n <= 17 else 100,None,.9,0.)
    observer.system.tracker.reader = Reader()
    for sample in range(1,22):
        observer.submit(Image.new('RGB',(2,2),(sample,0,0)),timestamp=float(sample),
                        sample=sample,preceding_action=None)
        observer.queue.join()
    observer.close()
    frames = dict(observer.frames)
    assert 'score-raw-0019.png' in frames and 'score-raw-0021.png' in frames
    assert frames['score-raw-0019.png'].getpixel((0,0)) == (19,0,0)
    assert len(frames) == 18 and observer.report()['policy_feedback'] is False
    change = [json.loads(r) for r in (tmp_path/'score.jsonl').read_text().splitlines()
              if json.loads(r)['self_delta']][0]
    assert change['raw_frame'] == 'score-raw-0019.png'

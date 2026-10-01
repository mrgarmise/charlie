"""Distinct tracking, phase and HUD regressions from the latest live Pi archive."""
import json
from pathlib import Path
from PIL import Image
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.eyes.tracking import SpriteTracker
from experiments.ppal.replay_tracking import replay
from experiments.ppal.robotron_hud import RobotronHUDReader
from experiments.ppal.robotron_score_system import RobotronScoreSystem

FIXTURE = Path(__file__).parent/'fixtures/robotron-tracking-score'


def test_original_660_detection_run_remains_exactly_replayable():
    r = replay(FIXTURE/'tracking-inputs.jsonl')
    assert r['assignments_match'] and not r['mismatches']
    assert r['samples'] == 18 and r['detections'] == 660 and r['tracks_created'] == 259


def test_unmatched_dummy_permutations_do_not_quarantine_unseen_tracks():
    t = SpriteTracker()
    def d(x): return Detection('unknown',(x,50),(0,0,10,20),100)
    t.update(0,[d(10),d(10.1),d(30),d(50)],observed_at=0)
    t.update(1,[d(10.05)],observed_at=.5)
    events = t.last_update['events']
    ambiguous = {e['track_id'] for e in events if e['kind']=='ambiguous'}
    assert ambiguous == {1,2}  # actual competing physical identities stay unresolved
    assert not t.active[3].identity_uncertain and not t.active[4].identity_uncertain
    assert t.last_update['configuration']['association_version'] == 2


def diagnostic_calibration():
    labels = json.loads((FIXTURE/'labels.json').read_text())
    return Calibration.from_pixels(labels['diagnostic_corners_pixels'],(1280,720))


def test_real_raw_hud_zero_and_serif_100_with_estimated_current_geometry():
    reader = RobotronHUDReader(diagnostic_calibration())
    for name, expected in json.loads((FIXTURE/'labels.json').read_text())['scores'].items():
        r = reader.read(Image.open(FIXTURE/name))
        assert r.player1_score == expected and r.player2_score is None


def test_live_score_baseline_confirmation_avoids_pre_start_high_score_lock():
    system = RobotronScoreSystem(diagnostic_calibration(), confirm_baseline=True)
    # First sample may still display the preceding game even after START's ACK.
    first = system.tracker.tracker.observe(1900,None,player1_confidence=1.)
    assert first.self_score is None
    zero = Image.open(FIXTURE/'camera-zero.jpg')
    assert system.observe(zero,t=1).self_score is None
    assert system.observe(zero,t=2).self_score == 0
    hundred = Image.open(FIXTURE/'camera-100.jpg')
    assert system.observe(hundred,t=3).self_delta == 0
    changed = system.observe(hundred,t=4)
    assert changed.self_score == 100 and changed.self_delta == 100


def test_score_readability_does_not_certify_full_unobstructed_board():
    import pytest
    from experiments.ppal.eyes.settle import locate
    with pytest.raises(ValueError, match='complete game border'):
        locate(Image.open(FIXTURE/'camera-100.jpg'))


def test_new_assignment_removes_spurious_ambiguity_but_does_not_hide_flash_births():
    t = SpriteTracker()
    ambiguous = 0
    for line in (FIXTURE/'tracking-inputs.jsonl').read_text().splitlines():
        row = json.loads(line)['tracking']
        ds = [Detection(d['kind'],tuple(d['center']),tuple(d['box']),d['pixels'])
              for d in row['detections']]
        t.update(row['tick'],ds,observed_at=row['observed_at'])
        ambiguous += sum(e['kind']=='ambiguous' for e in t.last_update['events'])
    assert ambiguous == 23  # original solver emitted 168 such events
    assert t.next_id-1 == 258  # no claim that transition fragments are physical births


def test_response_window_includes_delayed_motion_before_independent_stop():
    from experiments.ppal.robotron_agency import VisualAgency, VECTORS
    points = [(20.,20.),(70.,70.)]
    pending = [None]
    reads_since_move = [0]
    def read():
        if pending[0] is not None:
            reads_since_move[0] += 1
            if reads_since_move[0] == 2:
                p = points[0]
                points[0] = tuple(p[i]+pending[0][i]*.5 for i in (0,1))
                pending[0] = None
        # A following sprite keeps moving during neutral; it must not acquire SELF.
        points[1] = (points[1][0]-.7,points[1][1])
        return [(Detection('unknown',p,(0,0,10,20),100),{}) for p in points]
    class Controller:
        def execute(self, action, ms):
            if action.move != 'STAY':
                u = VECTORS[action.move]
                p = points[0]
                points[0] = tuple(p[i]+u[i]*.5 for i in (0,1))
                pending[0], reads_since_move[0] = u, 0
    visual = VisualAgency()
    rows = []
    assert visual.discover(read,Controller(),record=rows.append) == points[0]
    assert visual.agency.self_id == 1
    assert visual.agency.beliefs[1].contradictions == 0
    assert visual.agency.beliefs[1].hits == 3 and visual.agency.beliefs[1].stops == 3
    assert visual.agency.beliefs[2].contradictions >= 3
    early = [r for r in rows if r.get('phase')=='response_window_early_unmeasured']
    assert len(early)==3 and all(r['command'] is None for r in early)
    endpoints = [r for r in rows if r.get('phase')=='action_response_window']
    assert len(endpoints)==3 and all(r['response_reference_positions'] for r in endpoints)


def test_score_gain_is_reward_evidence_even_when_no_action_can_be_attributed(tmp_path):
    from experiments.ppal.score_observer import ScoreObserver
    from experiments.ppal.robotron_hud import RobotronHUDObservation
    observer = ScoreObserver(diagnostic_calibration(), tmp_path/'score.jsonl')
    values = iter((0,0,100))
    class Reader:
        def read(self, frame):
            return RobotronHUDObservation(next(values),None,1.,0.)
    observer.system.tracker.reader = Reader()
    frame = Image.new('RGB',(20,20))
    for sample in range(3):
        observer.submit(frame,timestamp=float(sample),sample=sample,preceding_action=None)
        observer.queue.join()
    observer.close()
    row = json.loads((tmp_path/'score.jsonl').read_text().splitlines()[-1])
    assert row['self_delta'] == row['reward_evidence'] == 100
    assert row['preceding_action'] is None
    assert row['attribution'] == 'temporal_association_only'
    assert observer.report()['policy_feedback'] is False

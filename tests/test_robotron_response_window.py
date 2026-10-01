"""Actual delayed-render endpoints must retain action attribution and abstention."""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from experiments.ppal.agency import AgencyTracker
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.eyes.detectors import Detection
from experiments.ppal.replay_tracking import replay
from experiments.ppal.robotron_agency import VisualAgency
from experiments.ppal.robotron_hud import RobotronHUDReader
from experiments.ppal.robotron_score_system import RobotronScoreSystem

FIXTURE = Path(__file__).parent/'fixtures/robotron-exposure-010300'


def test_actual_646_detections_replay_exactly_and_old_agency_stays_unknown():
    result = replay(FIXTURE/'tracking-inputs.jsonl')
    assert result['assignments_match'] and not result['mismatches']
    assert (result['samples'], result['detections'], result['tracks_created']) == (27,646,140)
    agency = AgencyTracker()
    rows = [json.loads(line) for line in (FIXTURE/'tracking-inputs.jsonl').read_text().splitlines()]
    for row in rows:
        agency.observe({d['track_id']:d['center'] for d in row['tracking']['detections']}, row['command'])
    assert agency.self_id is None and agency.beliefs[117].hits == 0


def test_actual_live_pairs_confirm_same_track_via_explicit_response_window():
    rows = [json.loads(line) for line in (FIXTURE/'tracking-inputs.jsonl').read_text().splitlines()]
    visual = VisualAgency()
    def pairs(row):
        return [(Detection(d['kind'],tuple(d['center']),tuple(d['box']),d['pixels']),{})
                for d in row['tracking']['detections']]
    for row in rows[:8]:
        visual.observe(pairs(row), observed_at=row['capture_timestamp'])
    remaining = iter(rows[8:]); current = [None]; recorded = []
    def read():
        current[0] = next(remaining)
        return pairs(current[0])
    class Controller:
        moves = []
        def execute(self, action, ms):
            self.moves.append(action.move)
    controller = Controller()
    player = visual.discover(read, controller, observation_time=lambda:current[0]['capture_timestamp'],
                             record=recorded.append)
    assert player is not None and visual.agency.self_id == 117
    assert controller.moves == ['E','STAY','W','STAY','S','STAY']
    assert visual.agency.beliefs[117].hits == visual.agency.beliefs[117].stops == 3
    assert visual.agency.beliefs[117].contradictions == 0
    assert visual.tick == 18  # exactly one association for every consumed frame
    assert visual.tracker.next_id-1 == 133
    for actual, expected in zip(recorded, rows[8:18]):
        assert [d['track_id'] for d in actual['tracking']['detections']] == [d['track_id'] for d in expected['tracking']['detections']]
    endpoints = [r for r in recorded if r.get('phase')=='action_response_window']
    assert len(endpoints) == 3 and all(r['response_window']['duration_seconds']>0 for r in endpoints)


def test_missing_intermediate_identity_cannot_earn_window_response():
    agency = AgencyTracker()
    origin = {1:(20,20)}
    agency.observe(origin)
    agency.observe({})
    agency.observe({1:(21,20)}, (1,0), reference_positions=origin)
    assert agency.beliefs[1].hits == 0 and agency.self_id is None


def test_luminous_but_dim_real_raw_hud_is_not_erased_by_fixed_cutoff():
    calibration = Calibration.load(FIXTURE/'calibration.json')
    frame = Image.open(FIXTURE/'raw-score-100.png')
    reader = RobotronHUDReader(calibration)
    channel = np.asarray(reader.rectify(frame))[:,64:179]
    assert reader._read_channel_at_threshold(channel)[0] is None
    result = reader.read(frame)
    assert result.player1_score == 100 and result.player2_score is None
    system = RobotronScoreSystem(calibration, confirm_baseline=True)
    assert system.observe(frame,t=1).self_score is None
    assert system.observe(frame,t=2).self_score == 100
    assert system.observe(frame,t=3).self_delta == 0


def test_dim_threshold_disagreement_remains_unknown(monkeypatch):
    def read(cls, channel, threshold=200):
        return (None,0) if threshold == 200 else (100 if threshold < 100 else 300, .9)
    monkeypatch.setattr(RobotronHUDReader,'_read_channel_at_threshold',classmethod(read))
    assert RobotronHUDReader._read_channel(np.full((96,115,3),190,dtype=np.uint8))[0] is None

"""Authentic correlated October 24 regression, not live-game acceptance."""
from pathlib import Path
import hashlib
import json
from PIL import Image
from experiments.ppal.robotron_screen_state import classify_screen_state
from experiments.ppal.episode_end import EpisodeEndObserver
from experiments.ppal.robotron_hud import RobotronHUDReader
from experiments.ppal.eyes.calibration import Calibration

ROOT=Path(__file__).parent/'fixtures/robotron-marathon-20261024'


def test_original_bytes_and_historical_failure_preserved():
    provenance=json.loads((ROOT/'provenance.json').read_text())
    for name,digest in provenance['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    import gzip
    for name,entry in provenance['compressed_originals'].items():
        assert hashlib.sha256(gzip.decompress((ROOT/name).read_bytes())).hexdigest()==entry['original_sha256']
    r=json.loads((ROOT/'report.json').read_text())
    assert r['result']=='OBSERVATION UNCERTAIN' and r['score']==800
    assert r['performance']['meaningful_updates']==2
    assert r['episode_end']['confirmed'] is False


def test_terminal_words_on_temporal_holdouts_not_identity_loss():
    observer=EpisodeEndObserver()
    observer.entry_evidence={'method':'historical acknowledged_START'}
    for n in range(3):observer.observe_phase(dict(phase='gameplay',state='gameplay',capture_timestamp=float(n)))
    for n,name in enumerate(('raw-0086.png','raw-0087.png'),3):
        screen=classify_screen_state(Image.open(ROOT/name))
        assert screen['phase']=='terminal',screen
        observer.observe_phase(dict(screen,capture_timestamp=float(n)))
    assert not observer.confirmed  # only two distinct postgame exposures survived the original stop
    assert classify_screen_state(Image.open(ROOT/'raw-0001.png'))['phase']!='terminal'
    missing=EpisodeEndObserver()
    for n in range(30):
        missing.observe_phase(dict(phase='unknown',state='unknown',capture_timestamp=float(n)))
        missing.observe_agency(False)
    assert not missing.confirmed


def test_confident_false_800_is_withheld_not_replaced_by_operator_500():
    reader=RobotronHUDReader(Calibration.load(ROOT/'calibration.json'))
    assert reader.read(Image.open(ROOT/'score-raw-0047.png')).player1_score is None
    assert reader.read(Image.open(ROOT/'score-raw-0087.png')).player1_score is None


def test_unreadable_current_pixels_cannot_label_a_held_score_measured():
    from experiments.ppal.robotron_score_system import RobotronScoreSystem
    from experiments.ppal.robotron_hud import RobotronHUDObservation
    class Reader:
        value=RobotronHUDObservation(500,None,1.,0.)
        def read(self,frame):return self.value
    reader=Reader();system=RobotronScoreSystem(None,reader=reader)
    system.observe(None,t=1.)
    assert system.report()['status']=='measured'
    reader.value=RobotronHUDObservation(None,None,0.,0.)
    system.observe(None,t=2.)
    report=system.report()
    assert report['self_score']==500 and report['status']=='held_unverified'
    assert report['latest_observed_score'] is None

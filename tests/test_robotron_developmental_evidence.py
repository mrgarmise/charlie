"""Physical held-out page evidence, score failures and conservative transitions."""
import hashlib,json
from pathlib import Path
import pytest
from PIL import Image
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.robotron_screen_state import classify_screen_state
from experiments.ppal.robotron_hud import RobotronHUDReader
from experiments.ppal.episode_end import EpisodeEndObserver
from experiments.ppal.marathon_robotron import safe_to_restart
ROOT=Path(__file__).parent/'fixtures/robotron-developmental'
ROWS=json.loads((ROOT/'provenance.json').read_text())

def image(row):
    path=ROOT/row['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    return Image.open(path),Calibration(tuple(tuple(p) for p in row['calibration']['corners']))

@pytest.mark.parametrize('row',[r for r in ROWS if 'review' in r['path']],ids=lambda r:r['path'])
def test_real_pages_and_temporary_self_loss(row):
    raw,c=image(row);phase=classify_screen_state(c.apply(raw))['phase']
    if row['path'].startswith(('005944-review-005','012801-review-005','015817-review-006')):assert phase=='terminal'
    elif 'final-view' in row['path'] and not row['path'].startswith('003511'):assert phase=='startable'
    elif row['path'].startswith('012801-review-002'):assert phase=='unknown'
    else:assert phase=='gameplay'

@pytest.mark.parametrize('row',[r for r in ROWS if 'score-raw' in r['path']])
def test_demonstrated_false_score_jumps_abstain(row):
    raw,c=image(row);assert RobotronHUDReader(c).read(raw).player1_score is None

def test_boundary_needs_positive_fresh_corroboration():
    observer=EpisodeEndObserver()
    def feed(phase,at):observer.observe_phase(dict(phase=phase,state='gameplay' if phase=='gameplay' else 'not_gameplay' if phase in ('terminal','startable') else 'unknown',capture_timestamp=at))
    feed('gameplay',1)
    for at in range(2,20):feed('startable',at)
    assert not observer.confirmed
    feed('gameplay',20)
    for at in range(21,24):feed('terminal',at)
    for at in range(24,29):feed('startable',at)
    assert observer.confirmed and observer.agency_failures==0
    end=dict(state='game_over',confirmed=True,evidence=observer.evidence(screen=dict(state='not_gameplay',phase='startable'),self_lost_frames=20))
    assert safe_to_restart(dict(result='GAME OVER',episode_end=end))
    assert not safe_to_restart(dict(result='OBSERVATION UNCERTAIN',episode_end=end))
    feed('unknown',29);assert not observer.confirmed
    feed('gameplay',30);assert not observer.terminal_corroborated

def test_stale_exposure_cannot_supply_corroboration():
    observer=EpisodeEndObserver();observer.observe_phase(dict(phase='gameplay',state='gameplay',capture_timestamp=1))
    for _ in range(20):observer.observe_phase(dict(phase='terminal',state='not_gameplay',capture_timestamp=2))
    assert observer.terminal_streak==1 and not observer.confirmed

"""Full-camera regression evidence, including held-out pregame and white borders."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.robotron_screen_state import classify_screen_state
from experiments.ppal import play_robotron as play

ROOT=Path(__file__).parent/'fixtures/robotron-screen-states'
ROWS=json.loads((ROOT/'provenance.json').read_text())


def view(row):
    c=Calibration(tuple(tuple(p) for p in row['calibration']['corners']))
    return c.apply(Image.open(ROOT/row['path']))


@pytest.mark.parametrize('row',ROWS,ids=[r['path'] for r in ROWS])
def test_recorded_state(row):
    assert classify_screen_state(view(row))['phase']==row['expected_phase']


@pytest.mark.parametrize('index,expected',[(0,'start'),(1,'start'),(2,'stop'),(3,'attach'),(4,'attach')])
def test_recorded_initial_start_decision(monkeypatch,index,expected):
    image=view(ROWS[index]);clock=[0.]
    class Source:
        timestamp=0.;capture={}
        def read(self):clock[0]+=.1;self.timestamp=clock[0];return image
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(play.time,'sleep',lambda d:None)
    decision,_=play._initial_start_decision(Source(),SimpleNamespace(apply=lambda f:f),timeout=.5)
    assert decision['action']==expected
    assert len(decision['observations'])>=3


@pytest.mark.parametrize('color',['black','white'])
def test_unknown_and_calibration_like_blank_never_authorize_start(monkeypatch,color):
    clock=[0.]
    class Source:
        timestamp=0.;capture={}
        def read(self):clock[0]+=.1;self.timestamp=clock[0];return Image.new('RGB',(640,480),color)
    monkeypatch.setattr(play.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(play.time,'sleep',lambda d:None)
    decision,_=play._initial_start_decision(Source(),SimpleNamespace(apply=lambda f:f),timeout=.5)
    assert decision['action']=='stop'


def test_ungrounded_striped_page_has_no_start_permission(monkeypatch):
    from PIL import ImageDraw
    im=Image.new('RGB',(640,480));draw=ImageDraw.Draw(im)
    for y in range(0,480,40):draw.rectangle((0,y,12,y+39),fill='red' if y%80 else 'cyan')
    result=classify_screen_state(im)
    assert result['phase']=='unknown'


def test_existing_geometry_locator_keeps_pregame_recognizable():
    from experiments.ppal.eyes.settle import locate
    im=Image.open(ROOT/'pregame-heldout.jpg')
    c=Calibration.from_pixels(locate(im,require_uniform_border=False).tolist(),im.size)
    assert classify_screen_state(c.apply(im))['phase']=='startable'

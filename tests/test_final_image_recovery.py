"""Real archived frames replayed out of order; no live recovery claim."""
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import pytest
from PIL import Image
from experiments.ppal.preflight import verify_final_image
from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.eyes.settle import locate

FIXTURE = Path(__file__).parent/'fixtures/native-border-20261022'


def optics():
    doc=json.loads((FIXTURE/'sensory-preflight.json').read_text())
    corners=doc['geometry']['corners']
    image=Image.open(FIXTURE/'sensory-failed.png')
    return SimpleNamespace(geometry=SimpleNamespace(corners=corners),
        calibration=Calibration.from_pixels(corners,image.size),
        focus=SimpleNamespace(score=doc['focus']['score']))


class Replay:
    def __init__(self,frames):self.frames=iter(frames);self.reads=0
    def read(self):self.reads+=1;return next(self.frames)


def test_authentic_single_frame_miss_then_supported_archived_frame():
    failed=Image.open(FIXTURE/'sensory-failed.png')
    good=Image.open(FIXTURE/'exposure-ev-3.png')
    with pytest.raises(ValueError,match='No complete game border'):locate(failed,require_uniform_border=False)
    report={};source=Replay([failed,good])
    frame,quality=verify_final_image(source,optics(),report=report)
    assert frame is good and quality['detail_pixels']>=50
    assert [r['status'] for r in report['final_image_attempts']]==['border_unavailable','accepted']
    assert report['final_image_attempts'][0]['quality']['sharpness']>0


def test_persistent_authentic_miss_exhausts_bounded_reads():
    source=Replay([Image.open(FIXTURE/'sensory-failed.png')]*4);report={}
    with pytest.raises(ValueError,match='bounded fresh-frame'):verify_final_image(source,optics(),report=report)
    assert source.reads==4 and len(report['final_image_attempts'])==4


def test_moved_supported_rectangle_fails_without_retry(monkeypatch):
    import experiments.ppal.preflight as p
    original=optics();moved=np.asarray(original.geometry.corners)+[30,0]
    monkeypatch.setattr(p,'locate',lambda *a,**kw:moved)
    source=Replay([Image.open(FIXTURE/'exposure-ev-3.png')]);report={}
    with pytest.raises(ValueError,match='differs from stable'):verify_final_image(source,original,report=report)
    assert source.reads==1


def test_blank_incomplete_field_of_view_fails():
    source=Replay([Image.new('RGB',(1280,720))]*4)
    with pytest.raises(ValueError,match='bounded fresh-frame'):verify_final_image(source,optics(),report={})


def test_supported_border_cannot_override_invalid_focus_detail():
    state=optics();state.focus.score=float('nan')
    source=Replay([Image.open(FIXTURE/'exposure-ev-3.png')]);report={}
    with pytest.raises(ValueError,match='insufficient visual detail'):verify_final_image(source,state,report=report)
    assert report['final_image_attempts'][0]['status']=='insufficient_detail'

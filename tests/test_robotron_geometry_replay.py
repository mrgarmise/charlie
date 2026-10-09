"""Original failed-preflight pixels; software replay emits no physical commands."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pytest
from PIL import Image, ImageDraw
from experiments.ppal.eyes.settle import locate
from experiments.ppal.preflight import locate_stable_geometry,PreflightConfig

ROOT=Path(__file__).parent/'fixtures'/'robotron-geometry-004249'


def original(number):
    return Image.open(ROOT/f'camera-{number:06d}.png').copy()


def assert_playfield(points):
    # Broad visually inspected actual border region, not a fabricated exact label.
    assert 580<points[2][1]<620 and 625<points[3][1]<670
    assert 180<points[0][0]<240 and 935<points[1][0]<990


def test_original_fixture_bytes_and_pixels_are_unchanged():
    for row in json.loads((ROOT/'provenance.json').read_text())['rows']:
        p=ROOT/row['frame']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
        assert hashlib.sha256(Image.open(p).convert('RGB').tobytes()).hexdigest()==row['rgb_sha256']


@pytest.mark.parametrize('number',[1,2,3,4,5,6,18])
def test_original_border_not_lower_bezel_or_text(number):
    assert_playfield(locate(original(number),False))


@pytest.mark.parametrize('number',[112,113])
def test_original_dim_border_abstains_not_false_text_rectangle(number):
    # A previous valid observation must not synthesize missing fresh edge evidence.
    previous=locate(original(4),False)
    with pytest.raises(ValueError):locate(original(number),False,previous=previous)


class Replay:
    def __init__(self,frames):self.frames=iter(frames);self.count=0
    def read(self):self.count+=1;return next(self.frames).copy()


def test_six_actual_consecutive_originals_stabilize_without_looser_gate():
    source=Replay([original(n) for n in range(1,7)])
    cfg=PreflightConfig(geometry_interval=0)
    assert cfg.stable_views==6 and cfg.max_jitter_pixels==8
    result=locate_stable_geometry(source,cfg)
    assert source.count==6 and result.observations==6 and result.jitter_pixels<=8
    assert_playfield(np.array(result.corners))


def synthetic(points):
    frame=Image.new('RGB',(1280,720),(40,40,40))
    ImageDraw.Draw(frame).line([tuple(p) for p in points]+[tuple(points[0])],fill='white',width=7)
    return frame


def test_new_viewpoint_discovered_despite_prior_and_requires_six_fresh_views():
    before=np.array([(220,80),(1040,100),(1080,610),(180,590)])
    after=np.array([(300,100),(990,60),(1040,590),(230,620)])
    changed=synthetic(after)
    assert np.max(np.linalg.norm(locate(changed,previous=before)-after,axis=1))<12
    source=Replay([synthetic(before)]*3+[changed]*6)
    result=locate_stable_geometry(source,PreflightConfig(geometry_interval=0))
    assert source.count==9 and result.observations==6 and result.jitter_pixels<=8
    assert np.max(np.linalg.norm(np.array(result.corners)-after,axis=1))<12


def test_continuously_moving_view_never_passes_six_within_eight():
    points=np.array([(220,80),(1040,100),(1080,610),(180,590)])
    source=Replay([synthetic(points+np.array([30*(n%2),0])) for n in range(24)])
    with pytest.raises(ValueError):locate_stable_geometry(source,PreflightConfig(geometry_interval=0))
    assert source.count==24


def test_miss_resets_fresh_confirmation_instead_of_reusing_previous(monkeypatch):
    from experiments.ppal import preflight
    points=np.array([(220,80),(1040,100),(1080,610),(180,590)])
    frames=Replay([synthetic(points)]*12);answers=iter([points]*5+[ValueError('missing border')]+[points]*6)
    def measured(*args,**kwargs):
        value=next(answers)
        if isinstance(value,Exception):raise value
        return value
    monkeypatch.setattr(preflight,'locate',measured)
    assert locate_stable_geometry(frames,PreflightConfig(geometry_interval=0)).observations==6
    assert frames.count==12


def test_full_original_archive_when_supplied():
    root=os.environ.get('CHARLIE_GEOMETRY_ACCEPTANCE_ROOT')
    if not root:pytest.skip('Optional full 119-original archive replay; retained nine originals always run')
    paths=sorted((Path(root)/'observations').glob('camera-*.png'))
    assert len(paths)==119
    rejected=[]
    for path in paths:
        try:points=locate(Image.open(path),False)
        except ValueError:rejected.append(path.name)
        else:assert_playfield(points)
    assert 'camera-000112.png' in rejected and 'camera-000113.png' in rejected

    # Real dim/missing interval then six fresh supported observations in the tail.
    source=Replay([Image.open(p).copy() for p in paths[95:]])
    result=locate_stable_geometry(source,PreflightConfig(geometry_interval=0))
    assert source.count==14 and result.observations==6 and result.jitter_pixels<=8
    assert_playfield(np.array(result.corners))

"""Authentic failed pixels/history; replay is not native hardware acceptance."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageFilter
import pytest

from experiments.ppal.eyes.calibration import Calibration
from experiments.ppal.eyes.visual_readiness import (
    calibration_from_record, confirm_geometry, confirm_view, record_view)
from experiments.ppal.preflight import PreflightConfig, locate_stable_geometry, run_preflight

ROOT = Path(__file__).parent/'fixtures'
OCT22 = ROOT/'native-border-20261022'
OCT24 = ROOT/'native-geometry-20261024'
SELF24 = ROOT/'native-self-20261024'
CFG = replace(PreflightConfig(), geometry_interval=0)


def document(root): return json.loads((root/'sensory-preflight.json').read_text())


def qualified(root=OCT24):
    doc=document(root)
    if 'geometry' in doc:
        corners=np.asarray(doc['geometry']['corners'])
    else:
        # Exactly the six observations that produced the authentic 5.99px lock.
        corners=np.median([row['corners'] for row in doc['geometry_attempts'][1:7]], axis=0)
    image=Image.open(root/('sensory-final.png' if root == SELF24 else 'sensory-failed.png')).copy()
    return Calibration.from_pixels(corners, image.size), image


class Replay:
    """Archived pixels with explicitly synthetic advancing capture metadata."""
    def __init__(self, frames, *, duplicate=False):
        self.frames=iter(frames);self.count=0;self.focus=[];self.duplicate=duplicate
    def read(self):
        self.count+=1
        self.raw=next(self.frames).copy()
        self.capture=dict(sensor_timestamp_ns=1e9 if self.duplicate else self.count*1e8,
                          lens_position=2.,af_state=0)
        return self.raw
    read_fresh=read
    def focus_limits(self): return (0., 32.)
    def set_manual_focus(self, lens): self.focus.append(lens)


@pytest.mark.parametrize('root',[OCT22,OCT24,SELF24])
def test_original_bytes_preserved(root):
    provenance=json.loads((root/'provenance.json').read_text())
    for name, expected in provenance['files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == expected


def history_detector(monkeypatch, history):
    from experiments.ppal import preflight
    from experiments.ppal.eyes import visual_readiness
    answers=iter(history);calls=[]
    def locate(*args, **kwargs):
        row=next(answers);calls.append(row)
        if 'corners' not in row: raise ValueError(row.get('reason','recorded border miss'))
        return np.asarray(row['corners'])
    monkeypatch.setattr(preflight,'locate',locate)
    monkeypatch.setattr(visual_readiness,'locate',locate)
    return calls


def test_oct24_history_reproduces_discarded_six_view_qualification(monkeypatch):
    history=document(OCT24)['geometry_attempts']
    calls=history_detector(monkeypatch,history)
    _,image=qualified()
    source=Replay([image]*50)
    initial=locate_stable_geometry(source,CFG)
    assert len(calls)==7 and initial.observations==6
    assert initial.jitter_pixels == pytest.approx(5.994313991210762)
    with pytest.raises(ValueError, match='could not establish stable'):
        locate_stable_geometry(source,CFG)
    assert len(calls)==31 and calls[-1]['stable_views']==5


def test_oct24_same_history_keeps_qualification_and_confirms_fresh_pixels(monkeypatch):
    history=document(OCT24)['geometry_attempts']
    calls=history_detector(monkeypatch,history)
    _,image=qualified()
    diagnostics=[];source=Replay([image]*50)
    result=run_preflight(source,seed_position=2.,config=CFG,diagnostics=diagnostics)
    assert result.continuity_confirmed and result.geometry.observations==6
    assert len(calls)==10  # Seven acquisition + three current structural checks.
    confirmation=diagnostics[-1]['observations']
    assert len(confirmation)==3 and all(row['status']=='supported' for row in confirmation)
    assert any('discovery_miss' in row for row in confirmation)
    assert source.focus == [2.0]  # No camera position change or focus search.


def test_actual_oct24_failed_frame_confirms_existing_lock_without_gameplay():
    calibration,image=qualified()
    source=Replay([image]*3)
    rows=[]
    accepted,quality=confirm_geometry(source,calibration,config=CFG,diagnostics=rows,require_metadata=True)
    assert source.count==3 and quality['detail_pixels']>=50
    assert min(rows[-1]['endpoint_support'])>=.65
    assert accepted.size==image.size


def test_oct22_miss_is_not_current_evidence_but_fresh_support_recovers():
    calibration,failed=qualified(OCT22)
    good=Image.open(OCT22/'exposure-ev-3.png')
    source=Replay([failed,good,good,good]);rows=[]
    confirm_geometry(source,calibration,config=CFG,diagnostics=rows,require_metadata=True)
    assert rows[0]['status']=='unsupported_or_unreadable'
    assert rows[-1]['consecutive']==3 and source.count==4


@pytest.mark.parametrize('bad',['blank','blur','clipped','moved','duplicate'])
def test_stale_saved_view_never_overrides_current_invalid_evidence(bad):
    calibration,image=qualified()
    if bad=='blank': image=Image.new('RGB',image.size)
    if bad=='blur': image=image.filter(ImageFilter.GaussianBlur(25))
    if bad=='clipped': image=image.crop((100,100,1100,700)).resize(image.size)
    if bad=='moved':
        changed=Image.new('RGB',image.size);changed.paste(image,(45,0));image=changed
    source=Replay([image]*24,duplicate=bad=='duplicate')
    with pytest.raises(ValueError):
        confirm_geometry(source,calibration,config=CFG,require_metadata=True)


@pytest.mark.parametrize('invalid', ['neck','polygon','tampered','simulated','unreleased'])
def test_profile_and_unverified_polygon_cannot_qualify_readability(invalid):
    calibration,image=qualified()
    record=record_view(calibration,dict(lens_position=2.),image,origin=OCT24,observations=[])
    if invalid=='neck':record={'schema':'neck-calibration-v1','qualified':True}
    if invalid=='polygon':record=dict(calibration=record['calibration'])
    if invalid=='tampered':record['calibration']['corners'][0][0]+=.1
    if invalid in ('simulated','unreleased'):
        record.update(schema='charlie-active-vision-v1',state='LOCKED',resources_released=invalid!='unreleased',simulated=invalid=='simulated')
    with pytest.raises(ValueError):calibration_from_record(record)


@pytest.mark.parametrize('kind',['persisted','active_vision'])
def test_shared_handoff_restores_focus_then_requires_fresh_readability(kind):
    calibration,image=qualified()
    record=record_view(calibration,dict(lens_position=2.),image,origin=OCT24,observations=[])
    if kind=='active_vision':
        # Synthetic envelope exercising the real Active Vision result contract;
        # not a claim that a physical LOCKED viewpoint exists.
        record.update(schema='charlie-active-vision-v1',state='LOCKED',resources_released=True,simulated=False)
    source=Replay([image]*12);report={}
    result,_=confirm_view(source,record,report=report)
    assert result==calibration and source.focus==[2.]
    assert report['status']=='confirmed' and source.count==9
    assert report['physical_motion'] is False
    assert 'before START' in report['readiness_scope']


def test_successful_oct24_preflight_was_not_gameplay_or_self_acceptance():
    calibration,image=qualified(SELF24)
    from experiments.ppal.robotron_screen_state import classify_screen_state
    screen=classify_screen_state(calibration.apply(image))
    assert screen['state']=='not_gameplay' and screen['phase']=='startable'
    source=Replay([image]*3)
    confirm_geometry(source,calibration,config=CFG,require_metadata=True)
    original=json.loads((SELF24/'report.json').read_text())
    assert 'cancel_event' in original['result']  # Original failure is preserved.
    assert original['episode_end']['confirmed'] is False


def test_current_camera_session_rechecks_view_before_reusing_it(tmp_path):
    from experiments.ppal.camera_session import CameraSession
    calibration,image=qualified()
    record=record_view(calibration,dict(lens_position=2.),image,origin=OCT24,observations=[])
    source=Replay([image]*12)
    source.close=lambda:None
    session=CameraSession(lambda:source)
    borrower=session.borrow()
    prepare=lambda *a,**kw:(calibration,dict(status='usable',visual_readiness=record))
    session.establish(borrower,tmp_path/'first',prepare)
    _,report=session.establish(borrower,tmp_path/'second',prepare)
    assert report['camera_session']['reused'] and report['viewpoint_handoff']['status']=='confirmed'
    assert source.count==9
    session.close()


def test_changed_view_invalidates_live_session_before_another_start(tmp_path):
    from experiments.ppal.camera_session import CameraSession
    calibration,image=qualified()
    record=record_view(calibration,dict(lens_position=2.),image,origin=OCT24,observations=[])
    source=Replay([Image.new('RGB',image.size)]*40);source.close=lambda:None
    session=CameraSession(lambda:source);borrower=session.borrow()
    session.establish(borrower,tmp_path,lambda *a,**kw:(calibration,dict(status='usable',visual_readiness=record)))
    with pytest.raises(ValueError): session.establish(borrower,tmp_path,lambda *a,**kw:pytest.fail('no unbounded reacquisition'))
    assert session.invalid
    with pytest.raises(RuntimeError):session.borrow()
    session.close()


def test_changed_focus_does_not_carry_provisional_qualification(monkeypatch):
    calls=history_detector(monkeypatch,document(OCT24)['geometry_attempts'])
    _,image=qualified()
    with pytest.raises(ValueError, match='could not establish stable'):
        run_preflight(Replay([image]*50),seed_position=3.,config=CFG)
    assert len(calls)==31


def test_discovered_geometry_change_is_not_hidden_by_supported_reference(monkeypatch):
    from experiments.ppal.eyes import visual_readiness
    calibration,image=qualified()
    changed=np.asarray(calibration.corners)*image.size+[30,0]
    monkeypatch.setattr(visual_readiness,'locate',lambda *a,**kw:changed)
    rows=[]
    with pytest.raises(ValueError,match='differs from qualified'):
        confirm_geometry(Replay([image]),calibration,config=CFG,diagnostics=rows)
    assert rows[0]['status']=='geometry_changed'


def test_real_sensory_path_persists_then_reuses_same_camera_without_reoptimization(tmp_path, monkeypatch):
    from experiments.ppal import preflight
    from experiments.ppal.eyes import visual_readiness
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'state'))
    _,image=qualified()
    source=Replay([image]*60)
    calibration,initial=preflight.sensory_preflight(source,tmp_path/'first',seed_position=2.)
    assert initial['status']=='usable'
    assert initial['geometry']['observations']==6
    saved=visual_readiness.default_view_path()
    original=saved.read_bytes()
    assert calibration_from_record(json.loads(original))[0]==calibration
    monkeypatch.setattr(preflight,'run_preflight',lambda *a,**kw:pytest.fail('qualified view must not rediscover from scratch'))
    monkeypatch.setattr('experiments.ppal.eyes.exposure.optimize_screen_exposure',lambda *a,**kw:pytest.fail('no redundant exposure sweep'))
    before=source.count
    same,reused=preflight.sensory_preflight(source,tmp_path/'second',seed_position=2.)
    assert source.count-before==9 and same==calibration
    assert reused['viewpoint_handoff']['status']=='confirmed'
    assert reused['visual_readiness']['record_id']!=initial['visual_readiness']['record_id']
    assert saved.read_bytes()!=original
    assert (tmp_path/'first/visual-readiness.json').read_bytes()==original  # Original evidence immutable.


def test_explicit_active_vision_lock_is_not_overwritten(tmp_path,monkeypatch):
    from experiments.ppal.preflight import sensory_preflight
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'state'))
    calibration,image=qualified()
    # Synthetic producer envelope, authentic pixels. No physical CAL is asserted.
    record=record_view(calibration,dict(lens_position=2.),image,origin=OCT24,observations=[])
    record.update(schema='charlie-active-vision-v1',state='LOCKED',resources_released=True,simulated=False)
    path=tmp_path/'active-vision/view.json';path.parent.mkdir();path.write_text(json.dumps(record))
    original=path.read_bytes()
    _,report=sensory_preflight(Replay([image]*12),tmp_path/'episode',viewpoint_path=path)
    assert report['viewpoint_handoff']['status']=='confirmed'
    assert path.read_bytes()==original


def test_active_vision_degradation_hysteresis_is_consumed_without_motion(monkeypatch):
    from experiments.ppal.live_view import LiveViewMonitor
    from experiments.ppal.eyes import settle
    calibration,image=qualified()
    monitor=LiveViewMonitor(calibration.apply(image))
    points=np.asarray(calibration.corners)*image.size+[60,0]
    monkeypatch.setattr(settle,'locate',lambda *a,**kw:points)
    shifted=Image.new('RGB',image.size);shifted.paste(image,(60,0));image=shifted
    for at in range(4):
        assert monitor.observe(calibration.apply(image),{'state':'gameplay'},at,raw=image,calibration=calibration) is None
    result=monitor.observe(calibration.apply(image),{'state':'gameplay'},4,raw=image,calibration=calibration)
    assert result['active_vision_decision']=='request_permission' and result['physical_authorization'] is False
    # Expected title/attract transitions do not create motion or fault authority.
    assert monitor.observe(calibration.apply(image),{'state':'not_gameplay'},5,raw=image,calibration=calibration) is None


def test_reused_view_locks_current_exposure_without_sweep(tmp_path,monkeypatch):
    from experiments.ppal.preflight import sensory_preflight
    from experiments.ppal.eyes.visual_readiness import default_view_path
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'state'))
    calibration,image=qualified()
    path=default_view_path();path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record_view(calibration,dict(lens_position=2.),image,origin=OCT24,observations=[])))
    source=Replay([image]*12);locks=[]
    source.lock_exposure=lambda capture:(locks.append(capture.copy()) or True)
    source.lock_white_balance=lambda capture:True
    _,report=sensory_preflight(source,tmp_path/'episode')
    assert report['exposure']['exposure_locked'] and report['white_balance_locked']
    assert len(locks)==1 and locks[0]['sensor_timestamp_ns']==source.capture['sensor_timestamp_ns']


def test_camera_error_during_saved_view_confirmation_is_preserved(tmp_path,monkeypatch):
    from experiments.ppal.preflight import sensory_preflight
    from experiments.ppal.eyes.visual_readiness import default_view_path
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'state'))
    calibration,image=qualified()
    path=default_view_path();path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record_view(calibration,dict(lens_position=2.),image,origin=OCT24,observations=[])))
    source=Replay([])
    def failed(): raise OSError('camera disconnected during confirmation')
    source.read_fresh=failed
    with pytest.raises(OSError, match='camera disconnected'):
        sensory_preflight(source,tmp_path/'episode')
    report=json.loads((tmp_path/'episode/sensory-preflight.json').read_text())
    assert report['status']=='failed' and 'camera disconnected' in report['reason']

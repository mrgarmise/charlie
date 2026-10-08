"""Exact computation/durability equivalence, never independent score evidence."""
import json
from pathlib import Path
import pytest
from experiments.ppal import meditate_robotron as meditation
from experiments.ppal.predict_robotron import prediction_rows,predict_next
from learning.foundry import atomic_json
from learning.lifecycle import DevelopmentLifecycle
from test_meditation_yield import fragments
from test_normal_learning_lifecycle import experience


def test_cached_pair_features_preserve_matching_and_tie_order(monkeypatch):
    tracks=fragments();tracks.append(dict(tracks[-1],track_id=20))
    cached=meditation.reconstruct_once(tracks)
    original=meditation.predicted_link
    calls=[]
    def uncached(left,right,window=3,max_gap=5,base_radius=2.,radius_per_gap=1.8,prepared=None):
        calls.append((left['track_id'],right['track_id']))
        return original(left,right,window,max_gap,base_radius,radius_per_gap)
    monkeypatch.setattr(meditation,'predicted_link',uncached)
    assert meditation.reconstruct_once(tracks)==cached
    assert calls


@pytest.mark.parametrize('window',[0,1,3,10,-1])
def test_prediction_window_preserves_causal_full_prefix_result(window):
    path=[dict(tick=i,center=[i*i,i%3]) for i in (0,1,2,4,5,9)]
    rows=prediction_rows(dict(track_id=1,path=list(reversed(path))),window=window)
    assert [r['predicted'] for r in rows]==[list(predict_next(path[:i],path[i]['tick'],window)) for i in range(1,len(path))]


def test_compact_checkpoint_keeps_content_and_atomic_durability(tmp_path):
    value=dict(history=[dict(iteration=1,merges=0)],tracks=fragments())
    a=tmp_path/'pretty.json';b=tmp_path/'compact.json'
    atomic_json(a,value);atomic_json(b,value,compact=True)
    assert json.loads(a.read_text())==json.loads(b.read_text())==value
    assert b.stat().st_size<a.stat().st_size
    assert not list(tmp_path.glob('*.tmp'))


def test_status_cache_never_sets_progress_from_metadata_or_hides_changed_checkpoint(tmp_path):
    life=DevelopmentLifecycle(tmp_path/'state',[]);path=tmp_path/'checkpoint.json'
    atomic_json(path,dict(history=[],reconstruction={'left':0},tracks=[]))
    first=life.meditation_stages(path)
    path.touch() # bookkeeping alone must not become analytical progress
    assert life.meditation_stages(path)==first
    atomic_json(path,dict(history=[],reconstruction={'left':1},tracks=[]))
    assert life.meditation_stages(path)['completed_left_tracks']==1
    atomic_json(path,dict(state_digest='corrupt',history=[]))
    assert life.meditation_stages(path)['checkpoint_available'] is False
    life.close()


def test_owned_worker_memory_pressure_yields_without_new_commission(tmp_path,monkeypatch):
    from learning.resources import ResourceUnavailable
    from learning.capabilities import default_registry
    import learning.cycle as cycle
    registry=default_registry();original=registry.invoke;calls=[]
    def interrupted(method,**kwargs):
        calls.append(kwargs['plan']['prediction_id'])
        raise ResourceUnavailable('controlled worker-group memory pressure')
    monkeypatch.setattr(registry,'invoke',interrupted);monkeypatch.setattr(cycle,'default_registry',lambda:registry)
    life=DevelopmentLifecycle(tmp_path/'state',[experience(tmp_path)])
    life.turn()
    assert life.phase=='waiting for resources'
    prediction=calls[0]
    before=[r.id for r in life.journal.category_records('event','offline_experiment_plan')]
    monkeypatch.setattr(registry,'invoke',original)
    life.turn()
    plans=life.journal.category_records('event','offline_experiment_plan')
    assert len([r for r in plans if r.data['payload']['plan']['prediction_id']==prediction])==1
    assert all(i in [r.id for r in plans] for i in before)
    life.close()

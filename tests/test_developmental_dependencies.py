"""Explicit software evidence dependencies; no observation/authority fabrication."""
import json
from pathlib import Path
from PIL import Image
from learning.lifecycle import DevelopmentLifecycle
from learning.continuity import compare_restart
from tools.inspect_developmental_progress import inspect
from test_normal_learning_lifecycle import experience
from test_meditation_yield import fragments


def without_torch(monkeypatch):
    import importlib.util
    original=importlib.util.find_spec
    monkeypatch.setattr(importlib.util,'find_spec',lambda name:None if name=='torch' else original(name))


def test_uncommissioned_contexts_are_accounted_before_durable_wait(tmp_path,monkeypatch):
    without_torch(monkeypatch)
    state=tmp_path/'state';life=DevelopmentLifecycle(state,[])
    from learning.datasets import SCOPE
    for i in range(3):
        life.journal.append('observation',dict(category='learning_context_reference',source_episode=f'software-missing-{i}',
            context=dict(questions=[],identity_samples={})),episode=SCOPE,
            producer='existing-evidence-consolidation',version='explicit-software-fixture')
    life.turn()
    assert life.phase=='idle' and life.last_turn['runnable_work_remaining'] is True
    assert life.last_turn['progress_occurred'] is False
    for _ in range(3):life.turn()
    assert life.phase=='waiting for evidence' and life.last_turn['runnable_work_remaining'] is False
    assert all(p['status']=='blocked' for p in life.executive.work_states().values())
    before=inspect(state);count=len(life.journal.records());life.close()
    life=DevelopmentLifecycle(state,[])
    for _ in range(3):life.turn()
    assert len(life.journal.records())==count
    assert compare_restart(before,inspect(state))['restart_exact']
    life.close()


def test_missing_pixels_are_scoped_requests_other_work_runs_and_delivery_wakes(tmp_path,monkeypatch):
    without_torch(monkeypatch)
    root=experience(tmp_path);state=tmp_path/'state';life=DevelopmentLifecycle(state,[root])
    examples=[]
    for i in range(3):
        image=tmp_path/f'explicit-software-{i}.png';Image.new('RGB',(16,16),(40*i,10,20)).save(image)
        examples.append(life.dataset.add(image,episode=f'explicit-software-group-{i}',source={'kind':'simulation'},
            metadata={'identity_status':'unknown','simulation':True}))
    pixel=Path(examples[0].data['payload']['pixel_path']);original=pixel.read_bytes();pixel.unlink()
    for _ in range(10):life.turn()
    requests=life.journal.category_records('event','learning_evidence_request')
    specific=[r for r in requests if r.data['payload']['work_id']=='visual-artifact:'+examples[0].id]
    assert len(specific)==1 and specific[0].data['payload']['required_evidence'][0]['sha256']==pixel.stem
    assert life.phase=='waiting for evidence' and not life.error
    assert life.journal.records('resolution') # unrelated genuine fixture questions ran
    before=inspect(state);count=len(life.journal.records());life.close()
    life=DevelopmentLifecycle(state,[root])
    for _ in range(4):life.turn()
    assert len(life.journal.records())==count
    pixel.write_bytes(b'not the original qualified bytes')
    life.turn();assert len(life.journal.records())==count
    pixel.write_bytes(original)
    life.turn()
    fulfilled=life.journal.category_records('event','acquisition_dependency_satisfied')
    assert len(fulfilled)==1 and fulfilled[0].data['payload']['new_independent_experience'] is False
    assert len(life.journal.category_records('observation','experience_example'))==3
    assert life.journal.category_records('event','experience_dataset_snapshot')
    assert not any(r.get('work_id')=='visual-artifact:'+examples[0].id for r in json.loads((state/'development-status.json').read_text())['evidence_requests'])
    after=inspect(state);report=compare_restart(before,after)
    assert report['continuity_passed'] and report['physical_authorization'] is False
    life.close()


def test_missing_source_preserves_partial_commission_and_other_context_runs(tmp_path,monkeypatch):
    without_torch(monkeypatch)
    root=experience(tmp_path);state=tmp_path/'state'
    (root/'tracks.json').write_text(json.dumps({'tracks':fragments()}))
    life=DevelopmentLifecycle(state,[root],budget_seconds=10)
    original=__import__('experiments.ppal.meditate_robotron',fromlist=['predicted_link'])
    clock=[0.];predict=original.predicted_link
    from types import SimpleNamespace
    import learning.lifecycle as lifecycle
    monkeypatch.setattr(lifecycle,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def compute(*args):
        answer=predict(*args);clock[0]+=11;return answer
    monkeypatch.setattr(original,'predicted_link',compute)
    life.turn();before=inspect(state);checkpoint=next((state/'meditations').glob('*/checkpoint.json'))
    raw=checkpoint.read_bytes();context=checkpoint.parent.name
    episode=life.journal.get(context).data['payload']['source_episode']
    monkeypatch.undo();without_torch(monkeypatch)
    second=tmp_path/'second';second.mkdir()
    (second/'report.json').write_text(json.dumps({'simulation':True,'distinct':2,'steps':[]}))
    (second/'tracks.json').write_text((root/'tracks.json').read_text());life.roots.append(second)
    acquire=life.acquire
    def missing_source():
        changed=acquire();life.available_tracks.pop(episode,None);return changed
    monkeypatch.setattr(life,'acquire',missing_source)
    for _ in range(6):life.turn()
    assert checkpoint.read_bytes()==raw
    assert life.executive.work_states()[context]['status']=='blocked'
    assert life.executive.work_states()[context]['nonprogress_turns']==0 # dependency changed; no failed computation
    assert 'Original input unavailable' in life.executive.work_states()[context]['reason']
    results=life.journal.category_records('observation','normal_meditation_result')
    assert results and not any(r.data['payload']['context_id']==context for r in results)
    assert any(r.data['payload']['work_id']==context for r in life.journal.category_records('event','learning_evidence_request'))
    assert life.phase=='waiting for evidence'
    stopped=inspect(state);compare_restart(before,stopped)
    count=len(life.journal.records());life.close()
    life=DevelopmentLifecycle(state,[root,second],budget_seconds=10)
    acquire=life.acquire
    def missing_after_restart():
        changed=acquire();life.available_tracks.pop(episode,None);return changed
    monkeypatch.setattr(life,'acquire',missing_after_restart)
    for _ in range(4):life.turn()
    assert len(life.journal.records())==count and checkpoint.read_bytes()==raw
    monkeypatch.undo();without_torch(monkeypatch)
    life.turn();after=inspect(state);report=compare_restart(stopped,after)
    assert report['substantive_progress'] and context in report['completed_work']
    assert len(life.journal.category_records('event','reflection_commission'))==2
    life.close()


def test_legacy_unavailable_receipt_resumes_original_partial_checkpoint(tmp_path,monkeypatch):
    root=experience(tmp_path);state=tmp_path/'state'
    (root/'tracks.json').write_text(json.dumps({'tracks':fragments()}))
    life=DevelopmentLifecycle(state,[root]);clock=[0.]
    from types import SimpleNamespace
    import learning.lifecycle as lifecycle
    from experiments.ppal import meditate_robotron as meditation
    original=meditation.predicted_link
    monkeypatch.setattr(lifecycle,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    def compute(*args):
        value=original(*args);clock[0]+=11;return value
    monkeypatch.setattr(meditation,'predicted_link',compute)
    life.turn();monkeypatch.undo()
    cp=next((state/'meditations').glob('*/checkpoint.json'));context=cp.parent.name
    commission=life.journal.category_records('event','reflection_commission')[0].id
    episode=life.journal.get(context).data['payload']['source_episode']
    from learning.foundry import atomic_json
    from learning.datasets import sha
    result=cp.parent/'result.json'
    atomic_json(result,dict(status='unavailable',source_episode=episode,reason='Explicit older software receipt fixture'))
    life.journal.append('observation',dict(category='normal_meditation_result',context_id=context,source_episode=episode,
        result_path=str(result),result_sha256=sha(result),status='unavailable'),
        episode='autonomous-learning-v1',sources=[context,commission],producer='Reflection',version='legacy-software-fixture')
    def no_repeat(left,right,*args):
        assert not (left['track_id']==1 and right['track_id']==2 and len(left['path'])==len(right['path'])==2)
        return original(left,right,*args)
    monkeypatch.setattr(meditation,'predicted_link',no_repeat)
    before=inspect(state);life.turn();after=inspect(state)
    assert compare_restart(before,after)['substantive_progress']
    assert len(list((state/'meditations').glob('**/checkpoint.json')))==1
    assert json.loads(cp.read_text())['history']
    results=life.journal.category_records('observation','normal_meditation_result')
    assert [r.data['payload']['status'] for r in results]==['unavailable','completed']
    assert len(life.journal.category_records('event','reflection_commission'))==1
    life.close()

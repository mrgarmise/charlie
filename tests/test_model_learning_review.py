"""Review integrity and atomic attribution; no synthetic accuracy claims."""
import json
import numpy as np
from PIL import Image
import pytest
from memory.evidence import EvidenceJournal
from learning.model_learning.data import DatasetStore
from learning.model_learning.review import export_gallery, import_reviews, coverage, _binding

@pytest.fixture
def data(tmp_path):
    journal=EvidenceJournal(tmp_path/'journal.sqlite3')
    store=DatasetStore(journal,tmp_path/'frames')
    for i in range(2):
        path=tmp_path/f'{i}.png'
        Image.fromarray(np.random.default_rng(i).integers(0,255,(40,60,3),dtype='uint8')).save(path)
        store.add(path,session=f'session-{i}',provenance={'source':'</script><script>alert(1)</script>'},authentic=False)
    yield store
    journal.close()


def packet(data,tmp_path):
    p=dict(schema='charlie-review-v1',task=data.task,binding=_binding(data),reviewer='actual-reviewer',reason='visible content',rows=[dict(observation_id=r['observation_id'],sha256=r['sha256'],label_id=r['label_id'],label='gameplay') for r in data.rows()])
    path=tmp_path/'reviews.json'
    path.write_text(json.dumps(p))
    return p,path


def test_export_escapes_source_separates_truth_and_does_not_mutate(data,tmp_path):
    before=[r.id for r in data.journal.records()]
    path=tmp_path/'review.html'
    result=export_gallery(data,path)
    assert result['shown']==2
    text=path.read_text()
    assert '</script><script>alert(1)' not in text
    assert '\\u003c/script' in text and 'machine_proposal' in text
    assert '"confirmed": null' in text and 'value="actual-reviewer"' not in text
    assert [r.id for r in data.journal.records()]==before
    with pytest.raises(FileExistsError):export_gallery(data,path)


def test_import_attributed_atomic_idempotent(data,tmp_path):
    p,path=packet(data,tmp_path)
    result=import_reviews(data,path)
    assert result['count']==2
    count=len(data.journal.records())
    assert import_reviews(data,path)['status']=='ALREADY_IMPORTED'
    assert len(data.journal.records())==count
    assert all(r.data['payload']['reviewer']=='actual-reviewer' for r in data.events('model_label'))
    assert not data.events('model_partition') and not data.events('model_dataset')


@pytest.mark.parametrize('failure',['stale','foreign','duplicate','label','binding','hash','blank'])
def test_invalid_batch_cannot_partially_append(data,tmp_path,failure):
    p,path=packet(data,tmp_path)
    if failure=='stale':p['rows'][1]['label_id']='obsolete'
    if failure=='foreign':p['rows'][1]['observation_id']='elsewhere'
    if failure=='duplicate':p['rows'][1]=p['rows'][0]
    if failure=='label':p['rows'][1]['label']='activate'
    if failure=='binding':p['binding']='other-notebook'
    if failure=='hash':p['rows'][1]['sha256']='changed'
    if failure=='blank':p['reviewer']=' '
    path.write_text(json.dumps(p));before=len(data.journal.records())
    with pytest.raises(ValueError):import_reviews(data,path)
    assert len(data.journal.records())==before


def test_superseding_review_preserves_original(data,tmp_path):
    row=data.rows()[0]
    original=data.label(row['observation_id'],'title_menu',reviewer='operator',reason='attract')
    p,path=packet(data,tmp_path)
    import_reviews(data,path)
    assert data.journal.get(original.id)==original
    assert data.events('model_label')[1].data['payload']['supersedes']==original.id


def test_test_holdout_hidden_and_locked(data,tmp_path):
    data.partition('session-1','test',reviewer='curator')
    assert export_gallery(data,tmp_path/'review.html')['shown']==1
    p,path=packet(data,tmp_path)
    with pytest.raises(ValueError):import_reviews(data,path)
    assert not data.events('model_label')
    assert coverage(data)['partitions']=={'unassigned':1,'test':1}


def test_transaction_rolls_back_failure_during_append(data,tmp_path,monkeypatch):
    p,path=packet(data,tmp_path)
    original=data.label;calls=[]
    def fail(*args,**kwargs):
        calls.append(1)
        if len(calls)==2:raise RuntimeError('disk write failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(data,'label',fail)
    before=len(data.journal.records())
    with pytest.raises(RuntimeError):import_reviews(data,path)
    assert len(data.journal.records())==before


def test_cancelled_gallery_leaves_no_partial_output(data,tmp_path):
    def unavailable():raise InterruptedError('resource owner acquired camera/gameplay')
    path=tmp_path/'review.html'
    with pytest.raises(InterruptedError):export_gallery(data,path,on_progress=unavailable)
    assert not path.exists()


def test_changed_pixels_cannot_be_reviewed(data,tmp_path):
    p,path=packet(data,tmp_path)
    row=data.rows()[1]
    target=__import__('pathlib').Path(row['path']);target.chmod(0o644);target.write_bytes(b'changed')
    with pytest.raises(ValueError):import_reviews(data,path)
    assert not data.events('model_label')

import sys
from pathlib import Path
import pytest
from PIL import Image
from memory.evidence import EvidenceJournal
from learning.datasets import ExperienceDataset
from learning.capabilities import default_registry


def dataset(tmp_path):
    journal=EvidenceJournal(tmp_path/'ee.sqlite3')
    return ExperienceDataset(journal,tmp_path/'pixels')


def add(ds,tmp_path,episode,color):
    p=tmp_path/(episode+'.png'); Image.new('RGB',(12,12),color).save(p)
    return ds.add(p,episode=episode,source={'kind':'physical_capture','artifact':str(p)},
                  metadata={'identity_status':'provisional','action':{'fire':'N'}})


def test_versions_annotations_and_prediction_not_truth(tmp_path):
    ds=dataset(tmp_path)
    rows=[add(ds,tmp_path,str(i),(i*40,20,100)) for i in range(3)]
    with pytest.raises(ValueError,match='not ground truth'):
        ds.annotate(rows[0].id,'SELF',status='verified',source='agency_belief',evidence='belief')
    weak=ds.annotate(rows[0].id,'opaque',status='weak',source='model_prediction',evidence='candidate-v1')
    first=ds.snapshot(); before=first.document
    correction=ds.annotate(rows[0].id,'other',status='verified',source='external_annotation',evidence='review',supersedes=weak.id)
    second=ds.snapshot()
    assert first.id!=second.id and ds.journal.get(first.id).document==before
    assert second.data['payload']['examples'][0]['annotation']['id']==correction.id
    assert all(r.data['payload']['identity_status']=='provisional' for r in rows)
    ds.journal.verify()
    with pytest.raises(ValueError): ds.snapshot(objective='classification')


def test_split_isolation_and_artifact_tamper(tmp_path):
    ds=dataset(tmp_path)
    a=add(ds,tmp_path,'a','red'); add(ds,tmp_path,'b','red'); add(ds,tmp_path,'c','blue')
    with pytest.raises(ValueError,match='three independent'): ds.snapshot()
    add(ds,tmp_path,'d','green')
    snap=ds.snapshot().data['payload']
    assert len(snap['examples'])==3 and snap['independent_groups']==3
    path=Path(a.data['payload']['pixel_path']); path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='modified'): ds.snapshot()


def test_partial_crops_of_same_capture_do_not_leak(tmp_path):
    ds=dataset(tmp_path)
    p=tmp_path/'same.png'; Image.new('RGB',(24,24),'red').save(p)
    ds.add(p,episode='a',source={},crop=[0,0,12,12])
    ds.add(p,episode='b',source={},crop=[12,12,24,24])
    add(ds,tmp_path,'c','blue')
    with pytest.raises(ValueError,match='independent'): ds.snapshot()


def test_registry_is_optional_and_inspectable():
    import subprocess
    subprocess.run([sys.executable,'-c',"import learning.datasets, learning.capabilities, learning.cycle; import sys; assert 'torch' not in sys.modules"],check=True)
    registry=default_registry()
    assert registry.get('cnn-reconstruction').execution=='offline'
    assert len(registry.describe())==4

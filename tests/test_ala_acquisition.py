import json
import pytest
from PIL import Image
from memory.evidence import EvidenceJournal
from learning.datasets import ExperienceDataset
from learning.acquisition import collect_crops,apply_annotations


def test_history_transfer_has_verified_manifest_and_no_episode_credit(tmp_path):
    import tarfile, hashlib
    from pathlib import Path
    from learning.acquisition import export_history
    from memory.evidence import EvidenceJournal
    output=tmp_path/'notebook'
    j=EvidenceJournal(output/'learning-evidence.sqlite3')
    row=j.append('observation',dict(example=True),episode='fixture',producer='test',version='1')
    j.close()
    exported=export_history(output)
    assert Path(exported['package']).parent.parent==output/'exports'/'evidence'
    manifest=json.loads(Path(exported['manifest']).read_text())
    assert manifest['original_content_ids']==[row.id] and manifest['export_is_copy']
    with tarfile.open(exported['package']) as archive:
        for name,digest in manifest['files'].items():
            assert hashlib.sha256(archive.extractfile('notebook/'+name).read()).hexdigest()==digest
    assert export_history(output)==exported
    assert exported['new_physical_experience'] is False


def fixture(tmp_path):
    root=tmp_path/'game';root.mkdir();Image.new('RGB',(40,40),'red').save(root/'raw-1.png')
    (root/'report.json').write_text('{"result":"OBSERVATION UNCERTAIN"}')
    (root/'agency.jsonl').write_text(json.dumps({'raw_frame':'raw-1.png','capture_timestamp':2.,'identity_status':'provisional',
        'tracking':{'detections':[{'box':[1,2,20,24],'track_id':42}]}})+'\n')
    return root,ExperienceDataset(EvidenceJournal(tmp_path/'e.sqlite3'),tmp_path/'pixels')


def test_saved_box_acquisition_provenance_abstention_and_retry(tmp_path):
    root,ds=fixture(tmp_path);first=collect_crops(root,ds)
    assert first['status']=='collected' and first['new_physical_experiments']==0
    assert collect_crops(root,ds)==first
    example=ds.examples()[0]
    assert example['label_status']=='unlabeled' and example['identity_status']=='provisional'
    assert example['source']['agency_sha256'] and example['crop']==[1,2,20,24]
    assert example['metadata']['track_id']==42
    labels=tmp_path/'labels.json'
    row=dict(example_id=example['id'],value='human',status='verified',source='external_annotation',evidence='independent explicit observation')
    labels.write_text(json.dumps([row]));ids=apply_annotations(ds,labels)
    assert apply_annotations(ds,labels)==ids
    row.update(value='threat',supersedes=ids[0]);labels.write_text(json.dumps([row]))
    correction=apply_annotations(ds,labels)[0]
    assert ds.examples()[0]['annotation']['supersedes']==ids[0]
    assert ds.journal.get(ids[0]).data['payload']['value']=='human'
    ds.journal.verify()


def test_annotation_batch_failure_is_atomic_and_predictions_are_not_labels(tmp_path):
    root,ds=fixture(tmp_path);example=collect_crops(root,ds)['examples'][0]
    good=dict(example_id=example,value='human',status='verified',source='external_annotation',evidence='independent')
    path=tmp_path/'labels.json';path.write_text(json.dumps([good,dict(good,source='model_prediction')]))
    with pytest.raises(ValueError,match='independent'):apply_annotations(ds,path)
    assert ds.examples()[0]['annotation'] is None
    path.write_text(json.dumps([dict(good,value=None)]))
    with pytest.raises(ValueError,match='abstention'):apply_annotations(ds,path)


def test_acquisition_does_not_open_camera_or_escape_archive(tmp_path,monkeypatch):
    root,ds=fixture(tmp_path)
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:True)
    with pytest.raises(RuntimeError,match='offline'):collect_crops(root,ds)
    monkeypatch.setattr('learning.cycle.gameplay_active',lambda:False)
    (root/'agency.jsonl').write_text('{"raw_frame":"../outside.png"}\n')
    with pytest.raises(ValueError,match='escapes'):collect_crops(root,ds)

"""Controlled source failures; the exact reported native Pi artifact is unavailable."""
import json
from pathlib import Path
import pytest
from learning.datasets import ExperienceDataset, sha
from learning.meditation import consume, InvalidPreservedFinding
from learning.retrospective import ingest, inventory
from memory.evidence import EvidenceJournal
from test_retrospective import episode
from test_normal_learning_lifecycle import experience, startup, rows


def saved(root, raw):
    path=root.parent/(root.name+'-evidence')/'meditation.json'
    path.parent.mkdir(exist_ok=True);path.write_bytes(raw);return path


def payload(value):
    return json.dumps({'quality':{'adjacent':{'mean_error':1},'gaps':{'mean_error':value}}}).encode()


@pytest.mark.parametrize('raw',[payload(None),payload(-1),payload('unknown'),payload(True),
    payload(float('nan')),payload(float('inf')),b'{broken',b'{}',b'null',b'\xff',
    b'{"quality":{"adjacent":{"mean_error":1},"gaps":{"mean_error":2}},"other":NaN}'])
def test_rejected_source_is_preserved_deduplicated_and_strict(tmp_path,raw):
    root=episode(tmp_path);path=saved(root,raw);before=inventory(root)
    out=tmp_path/'state';j=EvidenceJournal(out/'learning-evidence.sqlite3');ds=ExperienceDataset(j,out/'pixels')
    with pytest.raises(InvalidPreservedFinding):consume(ds,path,source_episode='diagnostic',prior_use='diagnostic')
    first=ingest(root,ds);count=len(j.records());ids=[r.id for r in j.records()]
    rejection=j.category_records('event','preserved_meditation_rejection')[0]
    assert Path(rejection.data['payload']['artifact_path']).read_bytes()==raw
    assert rejection.data['payload']['artifact_sha256']==sha(path)
    assert len(j.category_records('event','learning_evidence_request'))==1
    assert not j.category_records('observation','preserved_meditation')
    assert ingest(root,ds)['record_id']==first['record_id'] and len(j.records())==count
    j.verify();j.close()
    j=EvidenceJournal(out/'learning-evidence.sqlite3');ds=ExperienceDataset(j,out/'pixels')
    ingest(root,ds);assert [r.id for r in j.records()]==ids
    assert inventory(root)==before and path.read_bytes()==raw
    j.verify();j.close()


def test_changed_valid_artifact_continues_same_episode_without_erasing_rejection(tmp_path):
    root=episode(tmp_path);path=saved(root,payload(None));original=path.read_bytes()
    j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3');ds=ExperienceDataset(j,tmp_path/'state'/'pixels')
    first=ingest(root,ds);rejected=j.category_records('event','preserved_meditation_rejection')[0]
    # Controlled replacement; not an independent trajectory qualification.
    path.write_bytes(payload(4));ingest(root,ds);count=len(j.records());ingest(root,ds)
    assert len(j.records())==count
    assert len(j.category_records('event','retrospective_ingestion'))==1
    assert len(j.category_records('observation','learning_context_reference'))==1
    assert len(j.category_records('observation','preserved_meditation'))==1
    continuation=j.category_records('event','retrospective_meditation_continuation')[0]
    assert continuation.data['payload']['ingestion_id']==first['record_id']
    assert Path(rejected.data['payload']['artifact_path']).read_bytes()==original
    assert len(j.category_records('event','acquisition_dependency_satisfied'))==1
    path.write_bytes(payload(5))
    with pytest.raises(ValueError,match='artifact changed'):ingest(root,ds)
    j.verify();j.close()


@pytest.mark.parametrize('failure_category',['preserved_meditation_rejection','learning_evidence_request','retrospective_ingestion'])
def test_interrupted_rejection_resumes_exact_records(tmp_path,monkeypatch,failure_category):
    root=episode(tmp_path);saved(root,payload(None))
    j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3');ds=ExperienceDataset(j,tmp_path/'state'/'pixels')
    append=j.append
    def fail(kind,data,**kw):
        if data.get('category')==failure_category:raise InterruptedError('controlled interruption')
        return append(kind,data,**kw)
    monkeypatch.setattr(j,'append',fail)
    with pytest.raises(InterruptedError):ingest(root,ds)
    monkeypatch.setattr(j,'append',append);ingest(root,ds)
    for cat in ('preserved_meditation_rejection','learning_evidence_request','retrospective_ingestion'):
        assert len(j.category_records('event',cat))==1
    j.verify();j.close()


def test_existing_producer_empty_prediction_bin_remains_invalid(tmp_path):
    from experiments.ppal.predict_robotron import summarize
    root=episode(tmp_path)
    path=saved(root,json.dumps({'quality':{'adjacent':summarize([]),'gaps':summarize([])}}).encode())
    j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3');ds=ExperienceDataset(j,tmp_path/'state'/'pixels')
    ingest(root,ds)
    assert 'finite preserved prediction errors' in j.category_records('event','preserved_meditation_rejection')[0].data['payload']['reason']
    assert not j.category_records('observation','preserved_meditation')
    j.close()


def test_normal_executive_continues_unrelated_work_and_restart(tmp_path):
    root=experience(tmp_path);saved(root,payload(None));state=tmp_path/'state'
    process=startup(state,[root],authorize=False,turns=8)
    assert process.returncode==0,process.stderr
    records=rows(state)
    cats={r.data['payload'].get('category') for r in records}
    assert {'preserved_meditation_rejection','normal_meditation_result','perceptual_experiment_proposal'}<=cats
    assert any(r.data['payload'].get('op')=='meditation_dispatch' for r in records)
    ids=[r.id for r in records]
    process=startup(state,[root],authorize=False,turns=8)
    assert process.returncode==0,process.stderr
    assert [r.id for r in rows(state)]==ids
    status=json.loads((state/'development-status.json').read_text())
    assert status['error'] is None and status['physical_authorization'] is False
    assert len(status['rejected_preserved_findings'])==1


def test_snapshot_corruption_and_storage_failure_remain_fatal(tmp_path,monkeypatch):
    root=episode(tmp_path);path=saved(root,payload(4))
    j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3');ds=ExperienceDataset(j,tmp_path/'state'/'pixels')
    append=j.append
    def fail(kind,data,**kw):
        if data.get('category')=='preserved_meditation':raise ValueError('controlled journal integrity failure')
        return append(kind,data,**kw)
    monkeypatch.setattr(j,'append',fail)
    with pytest.raises(ValueError,match='journal integrity'):ingest(root,ds)
    assert not j.category_records('event','preserved_meditation_rejection')
    monkeypatch.setattr(j,'append',append)
    snapshot=ds.artifacts.parent/'preserved-findings'/(sha(path)+'.json')
    snapshot.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='snapshot integrity'):ingest(root,ds)
    assert not j.category_records('event','preserved_meditation_rejection')
    j.close()


def test_authentic_published_empty_meditation_rejected_with_original_binding(tmp_path):
    import gzip
    import hashlib
    from learning.meditation import acquire_preserved
    archive=Path(__file__).resolve().parents[1]/'docs/ppal/native-cycle-20261005'
    manifest=json.loads((archive/'authentic-recovery-manifest.json').read_text())
    entry=next(a for a in manifest['new_artifacts'] if a['name']=='result' and a['context_id'].startswith('9b1e65c9'))
    raw=gzip.decompress((archive/entry['compressed_file']).read_bytes())
    assert hashlib.sha256(raw).hexdigest()==entry['original_sha256']
    finding=json.loads(raw);path=tmp_path/'original-meditation.json';path.write_bytes(raw)
    j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3');ds=ExperienceDataset(j,tmp_path/'state'/'pixels')
    # An inspection reference to original published provenance, not a fabricated
    # original commission, new game, or qualified independent measurement.
    ref=j.append('event',dict(category='published_artifact_inspection',
        context_id=entry['context_id'],commission_id=entry['commission_id'],
        source_sha256=finding['source_sha256'],manifest=str(archive/'authentic-recovery-manifest.json')),
        episode='autonomous-learning-v1',producer='offline-regression',version='1')
    med,rejected=acquire_preserved(ds,path,source_episode=finding['source_episode'],
        prior_use='diagnostic',context_id=ref.id)
    assert med is None and rejected.data['payload']['artifact_sha256']==entry['original_sha256']
    assert Path(rejected.data['payload']['artifact_path']).read_bytes()==raw
    count=len(j.records())
    assert acquire_preserved(ds,path,source_episode=finding['source_episode'],
        prior_use='diagnostic',context_id=ref.id)[1].id==rejected.id
    assert len(j.records())==count
    assert not j.category_records('observation','preserved_meditation')
    j.verify();j.close()


def test_normal_empty_meditation_is_explicitly_rejected_not_silently_skipped(tmp_path):
    root=experience(tmp_path);(root/'tracks.json').write_text('{"tracks":[]}')
    state=tmp_path/'state';p=startup(state,[root],authorize=False,turns=8)
    assert p.returncode==0,p.stderr
    records=rows(state)
    receipt=next(r for r in records if r.data['payload'].get('category')=='normal_meditation_result')
    assert receipt.data['payload']['finding_validation']=='rejected; dependency retained'
    rejection=next(r for r in records if r.data['payload'].get('category')=='preserved_meditation_rejection')
    assert rejection.id in receipt.data['sources']
    assert not any(r.data['payload'].get('category')=='preserved_meditation' for r in records)
    count=len(records);p=startup(state,[root],authorize=False,turns=8)
    assert p.returncode==0,p.stderr
    assert len(rows(state))==count


def test_restart_acceptance_checks_rejection_and_replacement_lineage(tmp_path):
    from copy import deepcopy
    from learning.continuity import compare_restart, ContinuityError
    from memory.evidence import canonical,digest
    from tools.inspect_developmental_progress import inspect
    root=experience(tmp_path);(root/'tracks.json').write_text('{"tracks":[]}')
    path=saved(root,payload(None));state=tmp_path/'state'
    p=startup(state,[root],authorize=False);assert p.returncode==0,p.stderr
    before=inspect(state)
    path.write_bytes(payload(4))  # Clearly controlled replacement, not qualification.
    p=startup(state,[root],authorize=False);assert p.returncode==0,p.stderr
    after=inspect(state)
    report=compare_restart(before,after);assert report['continuity_passed']
    forged=deepcopy(after)
    data=next(json.loads(r['document']) for r in forged['original_records']
        if json.loads(r['document'])['payload'].get('category')=='preserved_meditation_rejection')
    data['version']='adversarial duplicate'
    forged['original_records'].append(dict(id=digest(data),document=canonical(data),committed_at='fixture'))
    forged['records']+=1
    with pytest.raises(ContinuityError,match='duplicate'):compare_restart(before,forged)
    forged=deepcopy(after)
    # Correct content hash cannot excuse an unbound rejection.
    data['payload']['artifact_sha256']='1'*64
    data['payload']['context_id']='missing-context'
    forged['original_records'].append(dict(id=digest(data),document=canonical(data),committed_at='fixture'))
    forged['records']+=1
    with pytest.raises(ContinuityError,match='exact source context'):compare_restart(before,forged)

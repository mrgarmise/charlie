"""Hash-bound software history; fixture imports never establish learning."""
from copy import deepcopy
import json
import time
import pytest

from experiments.ppal.inspect_robotron_score import import_queue
from learning.continuity import compare_restart, ContinuityError
from memory.evidence import EvidenceJournal, digest, canonical
from tools.inspect_developmental_progress import inspect


def histories(tmp_path):
    state=tmp_path/'state';j=EvidenceJournal(state/'learning-evidence.sqlite3')
    (state/'development-status.json').write_text(json.dumps(dict(physical_authorization=False,error=None)))
    before=inspect(state)
    root=tmp_path/'originals';path=root/'game'/'experiment-evidence.sqlite3'
    source=EvidenceJournal(path);at=time.monotonic()
    r=source.append('observation',dict(category='opaque_original_observation'),
        episode='original-live-game',at=at,producer='original-physical-adapter',version='fixture')
    source.predict('fixture original response',episode='original-live-game',at=at,
        deadline=at+10,sources=[r.id],producer='existing-memory-actuator-test',version='fixture',mode='live_prospective')
    source.close();import_queue(j,root);after=inspect(state);j.close()
    return state,path,before,after


def test_preserved_original_prediction_is_history_not_new_work_or_authority(tmp_path):
    state,path,before,after=histories(tmp_path)
    result=compare_restart(before,after)
    assert result['continuity_passed'] and not result['substantive_progress']
    assert result['new_record_categories']['preserved_original_session_record']==2
    assert not result['physical_authorization']
    j=EvidenceJournal(state/'learning-evidence.sqlite3');import_queue(j,path.parent.parent)
    assert inspect(state)['original_records']==after['original_records'];j.close()


def test_unbound_original_producer_name_cannot_bypass_classifier(tmp_path):
    _,_,before,after=histories(tmp_path);after=deepcopy(after)
    after['historical_imports']=[]
    with pytest.raises(ContinuityError,match='unclassified'):compare_restart(before,after)


def test_original_bytes_changed_or_commitment_retimed_cannot_pass(tmp_path):
    _,path,before,after=histories(tmp_path)
    altered=deepcopy(after);altered['historical_imports'][0]['records'][0]['committed_at']='forged-time'
    with pytest.raises(ContinuityError,match='commitment'):compare_restart(before,altered)
    path.write_bytes(b'corrupt replacement')
    with pytest.raises(ContinuityError,match='source journal changed'):compare_restart(before,after)


def test_rehashed_receipt_cannot_infer_authority_or_independent_experience(tmp_path):
    _,_,before,after=histories(tmp_path);after=deepcopy(after)
    receipt=next(r for r in after['original_records'] if json.loads(r['document'])['payload'].get('category')=='preserved_session_history_import')
    data=json.loads(receipt['document']);data['payload']['new_independent_experience']=True
    receipt.update(id=digest(data),document=canonical(data))
    after['historical_imports'][0]['receipt_id']=receipt['id']
    with pytest.raises(ContinuityError,match='receipt'):compare_restart(before,after)

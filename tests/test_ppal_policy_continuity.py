"""Constructed policy contracts: continuity tests, never Robotron learning."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from experiments.ppal.qualified_policy import load_policy, DECISION_ADAPTER, VERSION
from learning.datasets import sha
from memory.evidence import digest
from test_qualified_ppal_policy import parameter_policy, decide, world


def second_version(ds, deployment, root):
    first=deployment.active('ppal-policy')
    p=ds.journal.get(first['proposal_id']).data['payload']
    measured=ds.journal.get(p['evaluation_id']).data['payload']
    spec=dict(adapter=DECISION_ADAPTER,parameters={'goal_preference':{'rescue':1,'survive':-1}})
    path=root/'second-parameters.json';path.write_text(json.dumps(spec))
    candidate=dict(measured['candidate'],spec=spec,identifier=digest(spec),
                   checkpoint=str(path),checkpoint_sha256=sha(path))
    contract=dict(eligible=True,policy_version=VERSION,domains=['goal_preference'],spec_sha256=digest(spec))
    evaluation=ds.journal.append('observation',dict(measured,candidate=candidate,
        metrics=dict(measured['metrics'],decision_contract=contract)),episode='perceptual-learning',
        producer='ModelFoundry',version='explicit-second-interface-fixture')
    proposal=ds.journal.append('event',dict(p,candidate_id=candidate['identifier'],evaluation_id=evaluation.id,
        contract=contract),episode='perceptual-learning',producer='Reflection',version='explicit-second-interface-fixture')
    authority={k:v for k,v in first['authorization'].items() if k!='proposal_id'}
    result=deployment.apply_authority({'operational_proposal':proposal.id},authority,root/'ppal-policy.json')
    assert result['status']=='activated'
    return proposal.id


def test_previous_qualified_version_restores_its_original_grant(tmp_path):
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'rescue':-1,'survive':1}})
    first=d.active('ppal-policy');old_bytes=path.read_bytes()
    expected=decide(world(),load_policy(path))[:3]
    second_version(ds,d,tmp_path)
    assert decide(world(),load_policy(path))[0].kind=='rescue'
    d.rollback('ppal-policy',reason='controlled regression; restore prior offline version',
        authorization=dict(target='ppal-policy',source='explicit offline rollback test',execution='offline'))
    restored=d.active('ppal-policy')
    assert restored['candidate_id']==first['candidate_id']
    d.export_policy('ppal-policy',path)
    assert decide(world(),load_policy(path))[:3]==expected
    assert restored['authorization']==first['authorization']
    assert restored['rollback_authorization']['source']=='explicit offline rollback test'
    count=len(ds.journal.records())
    d.rollback('ppal-policy',reason='controlled regression; restore prior offline version',
        authorization=dict(target='ppal-policy',source='explicit offline rollback test',execution='offline'))
    assert d.active('ppal-policy')==restored and len(ds.journal.records())==count
    path.write_bytes(old_bytes)
    with pytest.raises(ValueError,match='current qualified'):load_policy(path)
    d.export_policy('ppal-policy',path)
    before=[(r.id,r.document,r.committed_at) for r in ds.journal.records()]
    load_policy(path);load_policy(path)
    assert [(r.id,r.document,r.committed_at) for r in ds.journal.records()]==before


def test_changed_narrow_grant_cannot_reuse_old_activation(tmp_path):
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'survive':1}})
    active=d.active('ppal-policy');result={'operational_proposal':active['proposal_id']}
    before=path.read_bytes()
    narrower=dict(active['authorization'],allowed_domains=[])
    blocked=d.apply_authority(result,narrower,path)
    assert blocked['status']=='blocked'
    assert path.read_bytes()==before and d.active('ppal-policy')==active
    count=len(ds.journal.records())
    assert d.apply_authority(result,narrower,path)['status']=='blocked'
    assert len(ds.journal.records())==count
    assert any(r.data['payload'].get('category')=='learning_evidence_request' for r in ds.journal.records())
    from memory.evidence import EvidenceJournal
    from learning.deployment import CapabilityDeployment
    restarted=EvidenceJournal(ds.journal.path)
    try:
        assert CapabilityDeployment(restarted).apply_authority(result,narrower,path)['status']=='blocked'
        assert len(restarted.records())==count
    finally:restarted.close()


def test_changed_physical_request_cannot_reuse_offline_permission(tmp_path):
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'survive':1}})
    active=d.active('ppal-policy');result={'operational_proposal':active['proposal_id']}
    grant=dict(active['authorization'],execution='physical',operating_domain='robotron-camera')
    blocked=d.apply_authority(result,grant,path)
    assert blocked['status']=='blocked' and 'physical policy' in blocked['reason']
    assert d.active('ppal-policy')==active
    assert not any(r.data['payload'].get('category')=='capability_activation' and
                   r.data['payload'].get('authorization',{}).get('execution')=='physical'
                   for r in ds.journal.records())


def test_normal_synthetic_entry_discovers_persisted_policy_and_restarts(tmp_path):
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'rescue':-1,'survive':1}})
    env=dict(os.environ,CHARLIE_LEARNING_STATE=str(tmp_path))
    counts=len(ds.journal.records())
    for i in range(2):
        log=tmp_path/f'entry-{i}.jsonl'
        process=subprocess.run([sys.executable,'-m','experiments.ppal.run_closed_loop','--mode','synthetic',
            '--max-steps','2','--log',str(log)],capture_output=True,text=True,env=env)
        assert process.returncode==0,process.stderr
        records=[json.loads(line) for line in log.read_text().splitlines()]
        assert records and all(r['goal']['kind']=='survive' for r in records)
        assert records[0]['decision_provenance']['forebrain']['policy']['activation_key']==d.active('ppal-policy')['activation_key']
    assert len(ds.journal.records())==counts


def test_startup_rejects_corrupt_notebook_and_explicit_path_wins(tmp_path,monkeypatch):
    from experiments.ppal.policy_loading import load_startup_policy
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'survive':1}})
    monkeypatch.setenv('CHARLIE_LEARNING_STATE',str(tmp_path))
    assert load_startup_policy()[0] is not None
    policy,error=load_startup_policy(tmp_path/'absent.json')
    assert policy is None and 'FileNotFoundError' in error
    payload=json.loads(path.read_text())['payload']
    corrupt=tmp_path/'corrupt.sqlite3';corrupt.write_bytes(b'not a SQLite notebook')
    payload['journal']=str(corrupt)
    path.write_text(json.dumps(dict(payload=payload,sha256=digest(payload))))
    policy,error=load_startup_policy()
    assert policy is None and 'DatabaseError' in error


def test_valid_changed_grant_is_qualified_once(tmp_path):
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'survive':1}})
    active=d.active('ppal-policy')
    grant=dict(active['authorization'],source='another explicit offline fixture grant')
    result={'operational_proposal':active['proposal_id']}
    assert d.apply_authority(result,grant,path)['status']=='activated'
    assert d.active('ppal-policy')['authorization']==grant
    count=len(ds.journal.records())
    assert d.apply_authority(result,grant,path)['status']=='activated'
    assert len(ds.journal.records())==count
    assert load_policy(path).identity['activation_key']==d.active('ppal-policy')['activation_key']
    d.rollback('ppal-policy',reason='restore original grant',
        authorization=dict(target='ppal-policy',source='explicit fixture rollback',execution='offline'))
    d.export_policy('ppal-policy',path)
    assert d.active('ppal-policy')['authorization']==active['authorization']
    assert load_policy(path) is not None
    assert d.apply_authority(result,active['authorization'],path)['status']=='activated'
    assert d.apply_authority(result,grant,path)['status']=='blocked'


def test_reused_runtime_mismatch_blocks_without_replacing_manifest(tmp_path,monkeypatch):
    ds,g,d,path=parameter_policy(tmp_path,{'goal_preference':{'survive':1}})
    active=d.active('ppal-policy');before=path.read_bytes()
    monkeypatch.setattr('learning.policy.runtime_hash',lambda:'changed-runtime')
    result=d.apply_authority({'operational_proposal':active['proposal_id']},active['authorization'],path)
    assert result['status']=='blocked' and 'runtime changed' in result['reason']
    assert path.read_bytes()==before and d.active('ppal-policy')==active

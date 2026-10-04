"""Permanent acquisition and normal-app continuity; no physical capabilities."""
import json
import os
from pathlib import Path
import shutil
import pytest
from memory.evidence import EvidenceJournal
from memory.episode_identity import begin_capture, finalize_capture, inspect_capture, ORIGIN, MANIFEST
from learning.acquisition import maintain_episode_identity as reconcile
from learning.episode_identity import bindings, eligible, verified_tracks
from learning.datasets import sha
from test_normal_learning_lifecycle import experience, startup, rows, delivered_corpus


def package(tmp, name='capture', *, tracks=1, image=b'ancillary'):
    root=tmp/name;root.mkdir()
    (root/'report.json').write_text(json.dumps(dict(result='TIME LIMIT',score=100,provenance={'git_commit':'original'})))
    (root/'tracks.json').write_text(json.dumps(dict(tracks=[],marker=tracks)))
    (root/'diagnostic.bin').write_bytes(image)
    return root


def witness(root, identity, key):
    proof=dict(schema='episode-identity-witness-v1',source='independent_measurement',observer='controlled-test-observer',
        occurrence_key=key,capture_id=identity['capture_id'],manifest_id=identity['manifest_id'],
        boundaries={k:dict(path=k+'.bin',sha256=sha(root/(k+'.bin'))) for k in ('start','terminal')})
    (root/'episode-qualification.json').write_text(json.dumps(proof))


def test_complete_manifest_distinguishes_packages_not_gameplay(tmp_path):
    a=package(tmp_path,'a');b=package(tmp_path,'b',image=b'other')
    j=EvidenceJournal(tmp_path/'state.sqlite3')
    try:
        x,y=reconcile(a,j),reconcile(b,j)
        assert x['status']==y['status']=='verified'
        assert x['manifest_id']!=y['manifest_id'] and x['capture_id']!=y['capture_id']
        assert x['content_id']==y['content_id'] and x['source_episode']==y['source_episode']
        assert not x['independent_gameplay'] and not y['independent_gameplay']
        assert x['provenance']=={'git_commit':'original'}
        before=[r.id for r in j.records()]
        reconcile(a,j);reconcile(b,j)
        assert [r.id for r in j.records()]==before
    finally:j.close()


def test_copies_relocation_and_multiple_restoration_restarts(tmp_path):
    root=package(tmp_path);begin_capture(root);m=finalize_capture(root)
    assert finalize_capture(root)==m
    j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3')
    x=reconcile(root,j);copy=tmp_path/'copy';shutil.copytree(root,copy)
    y=reconcile(copy,j)
    assert x['capture_id']==y['capture_id'] and len(bindings(j))==1
    original=[(r.id,r.document,r.committed_at) for r in j.records()];j.close()
    moved=tmp_path/'relocated';copy.rename(moved)
    restored=tmp_path/'restore';shutil.copytree(tmp_path/'state',restored)
    for _ in range(3):
        j=EvidenceJournal(restored/'learning-evidence.sqlite3');reconcile(moved,j)
        assert [(r.id,r.document,r.committed_at) for r in j.records()][:len(original)]==original
        assert len(bindings(j))==1
        count=len(j.records());reconcile(moved,j);assert len(j.records())==count;j.close()


def test_distinct_capture_attempts_identical_report_do_not_prove_games(tmp_path):
    a=package(tmp_path,'a');b=package(tmp_path,'b')
    begin_capture(a);begin_capture(b);finalize_capture(a);finalize_capture(b)
    j=EvidenceJournal(tmp_path/'j.sqlite3')
    x,y=reconcile(a,j),reconcile(b,j)
    assert x['capture_id']!=y['capture_id']
    assert x['experience_id']==y['experience_id'] and not x['independent_gameplay']
    j.close()


def test_independent_games_identical_reports_require_external_boundaries(tmp_path):
    roots=[package(tmp_path,k) for k in ('a','b')]
    for i,root in enumerate(roots):
        for k in ('start','terminal'):(root/(k+'.bin')).write_bytes(f'{i}-{k}-independent-frame'.encode())
        begin_capture(root);finalize_capture(root)
    j=EvidenceJournal(tmp_path/'j.sqlite3')
    for i,root in enumerate(roots):witness(root,inspect_capture(root),str(i))
    x,y=[reconcile(root,j) for root in roots]
    assert x['legacy_episode_id']==y['legacy_episode_id'] and x['content_id']==y['content_id']
    assert x['experience_id']!=y['experience_id'] and x['observation_id']!=y['observation_id']
    assert x['independent_gameplay'] and y['independent_gameplay']
    assert x['source_episode']!=y['source_episode']
    j.close()


def test_missing_identifier_safe_mapping_malformed_origin_quarantined(tmp_path):
    root=package(tmp_path);j=EvidenceJournal(tmp_path/'j.sqlite3')
    assert reconcile(root,j)['status']=='verified'
    bad=package(tmp_path,'bad');begin_capture(bad)
    origin=json.loads((bad/ORIGIN).read_text());origin['capture_id']='broken'
    (bad/ORIGIN).write_text(json.dumps(origin));before=(bad/ORIGIN).read_bytes()
    rejected=reconcile(bad,j)
    assert rejected['status']=='quarantined' and 'malformed' in rejected['reason']
    assert (bad/ORIGIN).read_bytes()==before
    assert verified_tracks(j) # unrelated evidence continues
    j.close()


def test_modified_verified_artifact_excluded_valid_copy_remains(tmp_path):
    a=package(tmp_path);begin_capture(a);finalize_capture(a)
    b=tmp_path/'copy';shutil.copytree(a,b)
    j=EvidenceJournal(tmp_path/'j.sqlite3');x=reconcile(a,j);reconcile(b,j)
    (a/'diagnostic.bin').write_bytes(b'changed')
    rejected=reconcile(a,j)
    assert rejected['status']=='quarantined' and 'changed' in rejected['reason']
    assert eligible(j,dict(source_episode=x['source_episode'],manifest_id=x['manifest_id']))
    (b/'tracks.json').write_text('{}');reconcile(b,j)
    assert not eligible(j,dict(source_episode=x['source_episode'],manifest_id=x['manifest_id']))
    j.close()


def test_interrupted_finalization_resumes_same_origin(tmp_path,monkeypatch):
    import memory.episode_identity as module
    root=package(tmp_path);origin=begin_capture(root)
    original=module.os.link
    def crash(a,b):
        if Path(b).name==MANIFEST:raise InterruptedError('crash before manifest publication')
        return original(a,b)
    monkeypatch.setattr(module.os,'link',crash)
    with pytest.raises(InterruptedError):finalize_capture(root)
    j=EvidenceJournal(tmp_path/'j.sqlite3');assert reconcile(root,j)['status']=='quarantined'
    monkeypatch.setattr(module.os,'link',original)
    final=finalize_capture(root);assert final['capture_id']==origin['capture_id']
    assert reconcile(root,j)['status']=='verified'
    count=len(j.records());finalize_capture(root);reconcile(root,j);assert len(j.records())==count
    j.close()


def test_ambiguous_legacy_report_reconsidered_when_witness_arrives(tmp_path):
    a=package(tmp_path,'a');b=package(tmp_path,'b',tracks=2)
    for k in ('start','terminal'):(b/(k+'.bin')).write_bytes(k.encode())
    j=EvidenceJournal(tmp_path/'j.sqlite3');reconcile(a,j)
    rejected=reconcile(b,j)
    assert rejected['status']=='quarantined' and rejected['content_id']!=bindings(j)[0]['content_id']
    before=[r.id for r in j.records()]
    witness(b,inspect_capture(b),'new independently observed game')
    accepted=reconcile(b,j);assert accepted['status']=='verified' and accepted['independent_gameplay']
    assert [r.id for r in j.records()][:len(before)]==before
    count=len(j.records());reconcile(b,j);assert len(j.records())==count;j.close()


def test_normal_application_conflict_does_not_block_development_or_restart(tmp_path):
    root=experience(tmp_path);bad=package(tmp_path,'bad');begin_capture(bad)
    origin=json.loads((bad/ORIGIN).read_text());origin['capture_id']='malformed'
    (bad/ORIGIN).write_text(json.dumps(origin))
    state=tmp_path/'state'
    first=startup(state,[root,bad],authorize=False,turns=12)
    assert first.returncode==0,first.stderr
    original=rows(state)
    assert any(r.data['payload'].get('category')=='episode_identity_quarantine' for r in original)
    assert any(r.data['payload'].get('category')=='normal_meditation_result' and r.data['payload']['status']=='completed' for r in original)
    assert any(r.data['kind']=='resolution' for r in original)
    requests=[r for r in original if r.data['payload'].get('op')=='evidence_continuation']
    assert requests and requests[0].data['payload']['required_evidence']
    for _ in range(2):
        restarted=startup(state,[root,bad],authorize=False,turns=12)
        assert restarted.returncode==0,restarted.stderr
        assert [r.id for r in rows(state)]==[r.id for r in original]
    delivered_corpus(tmp_path,state)
    second=startup(state,[root,bad],authorize=False,turns=12)
    assert second.returncode==0,second.stderr
    after=rows(state)
    evaluations=[r for r in after if r.data['payload'].get('category')=='meditation_candidate_evaluation']
    assert len(evaluations)==2 and evaluations[-1].data['payload']['result']['result']=='supported'
    proposed=[r for r in after if r.data['payload'].get('op')=='proposed' and r.data['payload']['project']['method']=='meditation-motion']
    assert len(proposed)==1 # resume original, don't mint another project
    assert not any(r.data['payload'].get('category')=='capability_activation' for r in after)
    assert startup(state,[root,bad],authorize=False,turns=12).returncode==0
    assert [r.id for r in rows(state)]==[r.id for r in after]


def test_actual_october1_collision_normal_discovery(tmp_path):
    value=os.environ.get('CHARLIE_IDENTITY_ACCEPTANCE_ROOT')
    if not value:pytest.skip('original October 1 artifacts required; use documented acceptance environment')
    from learning.retrospective import discover_episodes,inventory
    roots=[r for r in discover_episodes([Path(value)]) if r.name in
        ('tracking-hud-fix-20261001-002127','tracking-hud-fix-goodview-20261001-002659')]
    assert len(roots)==2
    before={str(r):inventory(r) for r in roots}
    assert {v['report.json'] for v in before.values()}=={'ea62567075533157f5f20e0fbe1311c74fd198d5aa54197a3e88cfa6478fa218'}
    assert {v['setup-failed.png'] for v in before.values()}=={
        '491bbdc3e672d6b90c7cf8f2f39a4b91fb2d91fa2bd054109b41dce6cd3bfcf0',
        '573c6f8bce30e23f8c110407d5883b902f2cb099f9e6651dfccb36696da046c6'}
    state=tmp_path/'state';process=startup(state,roots,authorize=False,turns=12)
    assert process.returncode==0,process.stderr
    records=rows(state);j=EvidenceJournal(state/'learning-evidence.sqlite3',read_only=True)
    try:
        source=bindings(j)
        assert len(source)==2 and len({b['content_id'] for b in source})==1
        assert not any(b['independent_gameplay'] for b in source)
        assert {b['artifacts']['setup-failed.png'] for b in source}=={v['setup-failed.png'] for v in before.values()}
        assert all(b['provenance']['git_commit']=='bce4e9595e8d90febe4e72616d46f4957355118a' for b in source)
    finally:j.close()
    assert not any(r.data['payload'].get('category')=='episode_identity_quarantine' for r in records)
    assert sum(r.data['payload'].get('category')=='retrospective_ingestion' for r in records)==1
    assert any(r.data['kind']=='resolution' for r in records)
    assert startup(state,roots,authorize=False,turns=12).returncode==0
    assert [r.id for r in rows(state)]==[r.id for r in records]
    assert {str(r):inventory(r) for r in roots}==before

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


def original_notebook(tmp_path):
    """Restore actual journal documents/IDs/times, never reconstructed summaries."""
    import gzip
    fixture=json.loads(gzip.decompress((Path(__file__).parent/'fixtures/ala2-original-history.json.gz').read_bytes()))
    source=tmp_path/'original-notebook';j=EvidenceJournal(source/'learning-evidence.sqlite3')
    with j.batch():
        for r in fixture['records']:
            j.conn.execute('INSERT INTO records(id,document,committed_at) VALUES (?,?,?)',
                (r['id'],r['document'],r['committed_at']))
    j.verify();j.close()
    return source,fixture['records']


def test_original_distinct_temporal_projects_restore_defer_and_resume(tmp_path):
    from learning.lifecycle import DevelopmentLifecycle
    from learning.retrospective import merge_history
    from memory.learning_projects import LearningExecutive
    source,original=original_notebook(tmp_path)
    state=tmp_path/'state';merge_history(source,state)
    root=experience(tmp_path)
    ids=['aef1dd40685d65655699145b7e6105b2af15b5db18589de7aa58c7c713ac3a9c',
         '63d2f97ab361cf8e17b703c72793ae96c8cca74330b38c9d9a1e4d50bdd79343']
    j=EvidenceJournal(state/'learning-evidence.sqlite3');before=LearningExecutive(j,None).projects()
    assert before[ids[0]]['scope']['meditation_id']!=before[ids[1]]['scope']['meditation_id']
    assert [j.get(before[i]['scope']['meditation_id']).data['payload']['prior_use'] for i in ids]==['consulted-test','train']
    assert all(p['status']=='paused' and len(p['experiment_history'])==1 for p in (before[i] for i in ids))
    j.close()
    process=startup(state,[root],authorize=False,turns=12);assert process.returncode==0,process.stderr
    j=EvidenceJournal(state/'learning-evidence.sqlite3');executive=LearningExecutive(j,None)
    after=executive.projects()
    assert all(after[i]['experiment_history']==before[i]['experiment_history'] for i in ids)
    assert all(after[i]['scope']==before[i]['scope'] and after[i]['origins'][:len(before[i]['origins'])]==before[i]['origins'] for i in ids)
    assert all(after[i]['developmental_bookmark']['required_evidence'] for i in ids)
    assert all(after[i]['agenda_representative']==ids[0] for i in ids)
    assert [(r.id,r.document,r.committed_at) for r in j.records()][:len(original)]==[
        (r['id'],r['document'],r['committed_at']) for r in original]
    count=len(j.records());j.close()
    assert startup(state,[root],authorize=False,turns=12).returncode==0
    assert len(rows(state))==count
    delivered_corpus(tmp_path,state)
    process=startup(state,[root],authorize=False,turns=12);assert process.returncode==0,process.stderr
    j=EvidenceJournal(state/'learning-evidence.sqlite3');projects=LearningExecutive(j,None).projects()
    assert len(projects[ids[0]]['experiment_history'])==2
    assert projects[ids[0]]['experiment_history'][0]==before[ids[0]]['experiment_history'][0]
    assert projects[ids[1]]['experiment_history']==before[ids[1]]['experiment_history']
    assert any(r.data['payload'].get('category')=='meditation_candidate_evaluation'
        and r.data['payload']['result']['result']=='supported' for r in j.records())
    assert len([p for p in projects.values() if p['method']=='meditation-motion'])==2 # both original investigations remain distinct
    count=len(j.records());j.close()
    assert startup(state,[root],authorize=False,turns=12).returncode==0
    assert len(rows(state))==count


def test_standalone_content_adapter_imports_shared_experience_once(tmp_path):
    from experiments.ppal.episode_evidence import import_episode
    a=package(tmp_path,'a');b=package(tmp_path,'b',image=b'new-package')
    j=EvidenceJournal(tmp_path/'j.sqlite3')
    x=import_episode(a,j);y=import_episode(b,j)
    assert x==y and len(j.records('episode'))==1
    assert len(bindings(j))==2
    assert len([r for r in j.records('observation') if r.data['payload'].get('category')=='session_report'])==1
    j.close()


def test_safe_malformed_derived_alias_repair_preserves_original_journal(tmp_path):
    from learning.retrospective import ingest, discover, inventory
    from learning.datasets import ExperienceDataset,SCOPE
    root=package(tmp_path);j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3')
    ds=ExperienceDataset(j,tmp_path/'state'/'pixels')
    original=j.append('observation',dict(category='learning_context_reference',source_episode='broken-legacy-id',
        inventory=inventory(root),context=discover(root)),episode=SCOPE,producer='original-producer',version='legacy')
    marker=j.append('observation',dict(category='retrospective_ingestion',source_episode='broken-legacy-id',context_id=original.id),
        episode=SCOPE,producer='original-producer',version='legacy')
    documents=[(r.id,r.document,r.committed_at) for r in j.records()]
    repaired=ingest(root,ds)
    assert repaired['record_id']==marker.id and repaired['status']=='preserved'
    assert [(r.id,r.document,r.committed_at) for r in j.records()][:2]==documents
    aliases=j.category_records('event','episode_identity_alias')
    assert len(aliases)==1 and aliases[0].data['payload']['original_identifier']=='broken-legacy-id'
    count=len(j.records());ingest(root,ds);assert len(j.records())==count;j.close()


def test_normal_finalized_capture_restart_and_mutation_quarantine(tmp_path):
    root=experience(tmp_path);origin=begin_capture(root);manifest=finalize_capture(root)
    state=tmp_path/'state'
    first=startup(state,[root],authorize=False,turns=12);assert first.returncode==0,first.stderr
    original=rows(state)
    assert startup(state,[root],authorize=False,turns=12).returncode==0
    assert [r.id for r in rows(state)]==[r.id for r in original]
    assert json.loads((root/ORIGIN).read_text())==origin and json.loads((root/MANIFEST).read_text())==manifest
    (root/'unregistered.bin').write_bytes(b'unregistered source change')
    process=startup(state,[root],authorize=False,turns=12);assert process.returncode==0,process.stderr
    status=json.loads((state/'development-status.json').read_text())
    assert status['identity_conflicts'] and status['identity_conflicts'][0]['excluded_from_evaluation']


def test_motion_qualification_uses_capture_occurrence_not_report_alone(tmp_path):
    from learning.datasets import ExperienceDataset
    from learning.meditation import qualify_corpus
    from test_meditation_candidate import corpus
    j=EvidenceJournal(tmp_path/'state'/'learning-evidence.sqlite3');ds=ExperienceDataset(j,tmp_path/'state'/'pixels')
    source=corpus(None,tmp_path);document=json.loads(source.read_text())
    # Four genuinely distinct controlled occurrences with byte-identical reports.
    for n,e in enumerate(document['episodes']):
        root=tmp_path/f'capture-{n}';root.mkdir();(root/'report.json').write_text('{}')
        for k in ('start','terminal'):(root/(k+'.bin')).write_bytes(f'{n}-{k}'.encode())
        begin_capture(root);finalize_capture(root);identity=inspect_capture(root)
        witness(root,identity,str(n));verified=reconcile(root,j)
        e['source_episode']=verified['source_episode'];e['source_capture_root']=str(root)
        e['source_report']=dict(path=str(root/'report.json'),sha256=sha(root/'report.json'))
    source.write_text(json.dumps(document));record=qualify_corpus(ds,source)
    refs=record.data['payload']['identity_references']
    assert len({r['experience_id'] for r in refs})==4 and all(r['observation_id'] for r in refs)
    document['episodes'][1]['source_episode']=document['episodes'][0]['source_episode']
    document['episodes'][1]['source_capture_root']=document['episodes'][0]['source_capture_root']
    document['episodes'][1]['source_report']=document['episodes'][0]['source_report']
    source.write_text(json.dumps(document))
    with pytest.raises(ValueError,match='unique'):qualify_corpus(ds,source)
    j.close()


def test_audit_retrieval_preserves_verified_copy_during_source_quarantine(tmp_path):
    from learning.archive_audit import audit,ingest
    from learning.diagnostics import retrieve_questions
    root=package(tmp_path);j=EvidenceJournal(tmp_path/'j.sqlite3')
    identity=reconcile(root,j);q=ingest(j,audit(root,identity=identity))
    copy=tmp_path/'relocated-copy';shutil.copytree(root,copy);reconcile(copy,j)
    (root/'diagnostic.bin').write_bytes(b'altered');assert reconcile(root,j)['status']=='quarantined'
    actual=retrieve_questions(j,dict(predicate='capture_horizon_supported',source_evidence=[q.id]))
    assert actual['unavailable_references']==[]
    assert actual['capture_horizon_supported'] is False # no compatible frames; evidence still available
    assert actual['distinct_source_episodes']==1
    j.close()

"""Synthetic interface evidence only; never authentic trajectory qualification."""
import json
from pathlib import Path
import pytest
from PIL import Image
from learning.acquisition import investigate_requests, discover_request_sources
from learning.lifecycle import DevelopmentLifecycle
from learning.resources import ResourceUnavailable
from test_acquisition_investigation import request


def episode(root, name='game', *, corrupt=False):
    path=root/name;path.mkdir(parents=True)
    (path/'report.json').write_text('{broken' if corrupt else '{}')
    Image.new('RGB',(12,12),(10,20,30)).save(path/'frame.png')
    (path/'agency.jsonl').write_text(json.dumps(dict(raw_frame='frame.png',capture_timestamp=.15,
        tracking={'track_id':'unverified-model-id'},control_execution={'move':'left'}))+'\n')
    return path


def test_new_files_in_same_existing_root_trigger_request_response(tmp_path):
    root=tmp_path/'source';root.mkdir();life=DevelopmentLifecycle(tmp_path/'state',[root])
    r=request(life,'existing-question',['Independent persistent trajectories'])
    first=investigate_requests(life.dataset,[root],provenance=life.provenance)
    path=episode(root)
    second=investigate_requests(life.dataset,[root],provenance=life.provenance)
    assert first and second and first!=second
    result=life.journal.get(second[0]).data['payload']
    discovery=life.journal.get(result['discovery_ids'][0]).data['payload']
    assert result['request_id']==r.id and result['status']=='unsatisfied'
    frame=discovery['original_observations'][0]
    assert frame['source_kind']=='derived_rectified_playfield'
    assert frame['identity_status']=='unverified' and frame['commanded_action']=={'move':'left'}
    assert not discovery['independent_measurements']
    assert not investigate_requests(life.dataset,[root],provenance=life.provenance)
    before=len(life.journal.records());life.close()
    life=DevelopmentLifecycle(tmp_path/'state',[root])
    assert not investigate_requests(life.dataset,[root],provenance=life.provenance)
    assert len(life.journal.records())==before
    Image.new('RGB',(12,12),(90,80,70)).save(path/'frame.png')
    assert investigate_requests(life.dataset,[root],provenance=life.provenance)
    assert not life.journal.category_records('observation','independent_motion_corpus')
    life.close()


def test_failure_and_escape_do_not_prevent_other_source_search(tmp_path):
    root=tmp_path/'source';episode(root,'bad',corrupt=True);good=episode(root,'good')
    outside=tmp_path/'outside.png';Image.new('RGB',(12,12)).save(outside)
    with (root/'bad'/'agency.jsonl').open('a') as f:
        f.write(json.dumps({'raw_frame':str(outside)})+'\n{broken\n')
    life=DevelopmentLifecycle(tmp_path/'state',[root]);request(life,'retained',['Originals'])
    ids=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    payloads=[life.journal.get(i).data['payload'] for i in ids]
    assert len(payloads)==2 and any(p['episode_path']==str(good) for p in payloads)
    assert any('escapes authorized' in d for p in payloads for d in p['deficiencies'])
    assert any('Expecting' in d for p in payloads for d in p['deficiencies'])
    life.journal.verify();life.close()


def test_no_request_no_inspection(tmp_path):
    root=tmp_path/'source';episode(root)
    life=DevelopmentLifecycle(tmp_path/'state',[root])
    assert discover_request_sources(life.dataset,[root],provenance=life.provenance)==[]
    assert not life.journal.category_records('observation','acquisition_source_discovery')
    life.close()


def test_resource_interruption_retains_completed_source_and_resumes(tmp_path):
    root=tmp_path/'source';episode(root,'a');episode(root,'b')
    life=DevelopmentLifecycle(tmp_path/'state',[root]);request(life,'retained',['Originals'])
    calls=0
    def check():
        nonlocal calls
        calls+=1
        if calls==3:raise ResourceUnavailable('explicit fixture preemption')
    with pytest.raises(ResourceUnavailable):
        discover_request_sources(life.dataset,[root],provenance=life.provenance,check=check)
    original=life.journal.category_records('observation','acquisition_source_discovery')
    assert len(original)==1
    ids=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    assert len(ids)==2 and original[0].id in ids
    life.close()


def test_unchanged_discovery_uses_durable_index_without_rehash(tmp_path,monkeypatch):
    import learning.acquisition as acquisition
    root=tmp_path/'source';path=episode(root)
    state=tmp_path/'state';life=DevelopmentLifecycle(state,[root]);request(life,'retained',['Originals'])
    first=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    life.close();life=DevelopmentLifecycle(state,[root])
    real=acquisition.sha
    def fail(path):raise AssertionError('unchanged archive rehashed')
    monkeypatch.setattr(acquisition,'sha',fail)
    assert discover_request_sources(life.dataset,[root],provenance=life.provenance)==first
    monkeypatch.setattr(acquisition,'sha',real)
    (path/'frame.png').unlink()
    changed=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    assert changed!=first and life.journal.get(changed[0]).data['payload']['status']=='unavailable'
    life.close()


def test_nonframe_history_preserves_provenance_without_qualification(tmp_path):
    root=tmp_path/'source';path=episode(root)
    for name,row in [('score.jsonl',{'timestamp':1,'score':1300}),
                     ('controller.jsonl',{'timestamp':2,'command':'BACK'}),
                     ('events.jsonl',{'at':3,'event':'game_over'}),
                     ('annotations.jsonl',{'timestamp':float('nan'),'reviewed_score':1200})]:
        (path/name).write_text(json.dumps(row)+'\n')
    life=DevelopmentLifecycle(tmp_path/'state',[root]);request(life,'retained',['Score and boundaries'])
    ids=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    p=life.journal.get(ids[0]).data['payload'];rows=p['historical_observations']
    kinds={k for r in rows for k in r['kinds']}
    assert {'score_observation_unqualified','controller_command_report','session_event_unqualified','annotation_unqualified'}<=kinds
    assert all(r['source_stream']['sha256'] and r['row_sha256'] and r['line']==1 for r in rows)
    assert next(r for r in rows if 'annotation_unqualified' in r['kinds'])['timestamp'] is None
    assert not p['independent_measurements']
    assert not life.journal.category_records('observation','independent_motion_corpus')
    life.close()


def test_changed_episode_bound_advances_past_cached_sources(tmp_path):
    root=tmp_path/'source'
    for n in range(130):
        path=root/f'{n:03}';path.mkdir(parents=True);(path/'report.json').write_text('{}')
    life=DevelopmentLifecycle(tmp_path/'state',[root]);request(life,'retained',['Originals'])
    first=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    assert sum('episode_path' in life.journal.get(i).data['payload'] for i in first)==128
    second=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    assert len(second)==130
    assert len(life.journal.category_records('observation','acquisition_source_discovery'))==131
    assert discover_request_sources(life.dataset,[root],provenance=life.provenance)==second
    life.close()


def test_request_driven_search_does_not_assign_agenda_or_qualify_scores(tmp_path):
    root=tmp_path/'source';path=episode(root)
    (path/'score.jsonl').write_text(json.dumps({'timestamp':1,'score':3500})+'\n')
    life=DevelopmentLifecycle(tmp_path/'state',[root])
    scoring=request(life,'own-scoring-question',['Score observations and game boundaries'])
    identity=request(life,'own-identity-question',['Independent player identity'])
    ids=investigate_requests(life.dataset,[root],provenance=life.provenance)
    results={life.journal.get(i).data['payload']['request_id']:life.journal.get(i).data['payload'] for i in ids}
    a,b=results[scoring.id],results[identity.id]
    assert a['search_focus']!=b['search_focus']
    assert a['relevant_sources'][0]['frame_count']==0
    assert b['relevant_sources'][0]['frame_count']==1
    assert all(p['status']=='unsatisfied' and not p['physical_authorization'] for p in results.values())
    assert not life.executive.projects()
    life.close()


def test_frame_alias_retarget_invalidates_discovery_without_independence(tmp_path):
    root=tmp_path/'source';path=episode(root)
    first=path/'original-a.png';second=path/'original-b.png'
    Image.new('RGB',(12,12),'red').save(first);Image.new('RGB',(12,12),'blue').save(second)
    alias=path/'frame.png';alias.unlink();alias.symlink_to(first.name)
    life=DevelopmentLifecycle(tmp_path/'state',[root]);request(life,'retained',['Temporal frames'])
    a=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    alias.unlink();alias.symlink_to(second.name)
    b=discover_request_sources(life.dataset,[root],provenance=life.provenance)
    assert a!=b
    payload=life.journal.get(b[0]).data['payload']
    assert payload['original_observations'][0]['artifact']['path']==str(second)
    assert not payload['independent_measurements']
    assert not life.journal.category_records('observation','independent_motion_corpus')
    life.close()

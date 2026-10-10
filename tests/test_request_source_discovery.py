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

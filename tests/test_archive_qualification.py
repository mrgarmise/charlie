import json
import shutil
from pathlib import Path
from PIL import Image
import pytest
from learning.archive_audit import audit, ingest
from learning.retrospective import inventory
from learning.cycle import investigate
from memory.learning_projects import LearningExecutive
from memory.evidence import EvidenceJournal
from test_ala_cycle import make


def archive(tmp_path, name='archive', spacing=.33, meditation=False):
    root=tmp_path/name;game=root/'game-01';game.mkdir(parents=True)
    agency=[]
    for i in range(4):
        path=f'raw-{i+1:04d}.png';Image.new('RGB',(64,48),(i,0,0)).save(game/path)
        agency.append(dict(sample=i+1,capture_timestamp=1+i*spacing,raw_frame=path,self_track_id=99,
            control_execution={'move':'E','started_at':1+i*spacing-.1}))
    (game/'agency.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in agency))
    score=dict(sample=4,timestamp=2.,p1={'observed_score':None,'score':1300,'status':'absent_or_unreadable'})
    (game/'score.jsonl').write_text(json.dumps(score)+'\n')
    Image.new('RGB',(128,72)).save(game/'score-raw-0004.png')
    (game/'report.json').write_text(json.dumps(dict(score=1300,result='OBSERVATION UNCERTAIN',
        episode_end={'state':'unknown','confirmed':False},score_summary={'worker_finished':True,
        'raw_frames':['score-raw-0004.png']})))
    if meditation:
        evidence=root/'game-01-evidence';evidence.mkdir()
        (evidence/'meditation.json').write_text(json.dumps({'quality':{'adjacent':{'mean_error':1.},'gaps':{'mean_error':4.}}}))
    return root


def test_legacy_final_binding_and_sparse_archive_are_not_certification(tmp_path):
    root=archive(tmp_path);before=inventory(root);result=audit(root)
    assert inventory(root)==before
    assert len(result['capture_bindings'])==5
    assert result['cadence']['compatible_pairs']==[]
    assert result['last_score_observation']['p1']['observed_score'] is None
    assert result['score_retained_without_observation']==1
    assert not result['admissibility']['complete_game_score']
    assert result['meditation_artifact_sha256'] is None
    assert all(x['identity']=='unqualified' for x in result['action_response_review_windows'])
    # A matching filename without the retention declaration supplies no binding.
    r=json.loads((root/'game-01/report.json').read_text());r['score_summary']['raw_frames']=[]
    (root/'game-01/report.json').write_text(json.dumps(r))
    assert len(audit(root)['capture_bindings'])==4


def test_independent_eligibility_loop_and_restart_bookmark(tmp_path):
    ds,g=make(tmp_path);root=archive(tmp_path);q=ingest(ds.journal,audit(root))
    report=investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)
    row=next(x for x in report['results'] if x['plan']['predicate']=='capture_horizon_supported')
    assert row['result']['result']=='contradicted'
    assert row['result']['metrics']['compatible_pairs']==0
    assert row['result']['metrics']['qualified_identities']==0
    assert 'capture timing' in row['result']['reason']
    assert row['result']['reflection']['operational_change'] is None
    assert row['commission']['bookmark_id']
    e=LearningExecutive(ds.journal,g)
    event=e.retain_evidence_request(row['project_id'],ds.journal,[q.id])
    count=len(ds.journal.records())
    assert e.retain_evidence_request(row['project_id'],ds.journal,[q.id]).id==event.id
    assert LearningExecutive(ds.journal,g).projects()[row['project_id']]['developmental_bookmark']['evidence_id']==event.id
    assert len(ds.journal.records())==count
    relocated=tmp_path/'relocated';shutil.copytree(root,relocated)
    assert ingest(ds.journal,audit(relocated)).id==q.id
    assert investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)['results']==[]
    assert len(ds.journal.records())==count
    assert event.data['payload']['status']=='READY_FOR_PLAY'
    assert event.data['payload']['physical_authorization'] is False
    assert event.data['payload']['candidate_admitted'] is False
    ds.journal.verify()
    ds.journal.close()
    copy=tmp_path/'copied-notebook.sqlite3';shutil.copy2(tmp_path/'e.sqlite3',copy)
    moved=EvidenceJournal(copy)
    count=len(moved.records())
    assert LearningExecutive(moved,g).retain_evidence_request(row['project_id'],moved,[q.id]).id==event.id
    assert len(moved.records())==count
    moved.close()


def test_time_availability_does_not_qualify_motion_or_score(tmp_path):
    ds,g=make(tmp_path);root=archive(tmp_path,spacing=.15);q=ingest(ds.journal,audit(root))
    report=investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)
    row=next(x for x in report['results'] if x['plan']['predicate']=='capture_horizon_supported')
    assert row['result']['result']=='supported'
    assert not row['result']['metrics']['fresh_final_evidence']
    assert row['result']['metrics']['qualified_identities']==0
    with pytest.raises(ValueError,match='missing-evidence'):
        LearningExecutive(ds.journal,g).retain_evidence_request(row['project_id'],ds.journal,[q.id])


def test_ready_request_does_not_recommission_for_more_unqualified_captures(tmp_path):
    """Software archives reproduce the native request, not physical evidence."""
    ds,g=make(tmp_path);root=archive(tmp_path);q=ingest(ds.journal,audit(root))
    report=investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)
    row=next(x for x in report['results'] if x['plan']['predicate']=='capture_horizon_supported')
    executive=LearningExecutive(ds.journal,g)
    request=executive.retain_evidence_request(row['project_id'],ds.journal,[q.id])
    other=archive(tmp_path,name='another-sparse-archive')
    report_path=other/'game-01/report.json'
    document=json.loads(report_path.read_text());document['simulation_episode']=2
    report_path.write_text(json.dumps(document))
    ingest(ds.journal,audit(other))
    result=investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)
    assert not any(r['project_id']==row['project_id'] for r in result['results'])
    restored=LearningExecutive(ds.journal,g).projects()[row['project_id']]
    assert restored['developmental_bookmark']['evidence_id']==request.id
    assert len(restored['experiment_history'])==1
    assert restored['hold']
    count=len(ds.journal.records())
    for _ in range(3):
        assert investigate(ds,g,executive=LearningExecutive(ds.journal,g),
            diagnostics_only=True,review_questions=True,max_jobs=8)['results']==[]
    assert len(ds.journal.records())==count
    assert len([r for r in ds.journal.records('event') if r.data['payload'].get('op')=='evidence_continuation'])==1


def test_ready_request_reassesses_first_usable_horizon_without_qualifying_policy(tmp_path):
    ds,g=make(tmp_path);q=ingest(ds.journal,audit(archive(tmp_path)))
    row=next(x for x in investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)['results']
        if x['plan']['predicate']=='capture_horizon_supported')
    request=LearningExecutive(ds.journal,g).retain_evidence_request(row['project_id'],ds.journal,[q.id])
    ingest(ds.journal,audit(archive(tmp_path,name='usable-horizon',spacing=.15)))
    report=investigate(ds,g,executive=LearningExecutive(ds.journal,g),diagnostics_only=True,review_questions=True,max_jobs=8)
    resumed=next(x for x in report['results'] if x['project_id']==row['project_id'])
    assert resumed['plan']['prediction_id']!=row['plan']['prediction_id']
    assert resumed['result']['metrics']['compatible_pairs']>0
    assert resumed['result']['metrics']['qualified_identities']==0
    assert resumed['result']['metrics']['fresh_final_evidence'] is False
    assert resumed['result']['reflection']['operational_change'] is None
    project=LearningExecutive(ds.journal,g).projects()[row['project_id']]
    assert project['developmental_bookmark']['evidence_id']==request.id
    assert len(project['experiment_history'])==2
    assert project['developmental_bookmark']['physical_authorization'] is False
    assert investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)['results']==[]


def test_changed_pixels_refuse_independent_retrieval(tmp_path):
    from learning.diagnostics import retrieve_questions
    ds,g=make(tmp_path);root=archive(tmp_path);q=ingest(ds.journal,audit(root))
    Image.new('RGB',(64,48),'white').save(root/'game-01/raw-0001.png')
    with pytest.raises(ValueError,match='changed'):
        retrieve_questions(ds.journal,dict(predicate='capture_horizon_supported',source_evidence=[q.id]))


def test_first_horizon_without_velocity_history_is_not_eligible(tmp_path):
    root=archive(tmp_path)
    rows=[json.loads(l) for l in (root/'game-01/agency.jsonl').read_text().splitlines()]
    for row,t in zip(rows,(1.,1.15,1.48,1.81)):row['capture_timestamp']=t
    (root/'game-01/agency.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    assert audit(root)['cadence']['compatible_pairs']==[]


def test_unknown_timing_and_unrelated_request_abstain(tmp_path):
    ds,g=make(tmp_path);root=archive(tmp_path)
    rows=(root/'game-01/agency.jsonl').read_text().splitlines();first=json.loads(rows[0]);first['capture_timestamp']=None;rows[0]=json.dumps(first)
    (root/'game-01/agency.jsonl').write_text('\n'.join(rows)+'\n')
    q=ingest(ds.journal,audit(root));report=investigate(ds,g,diagnostics_only=True,review_questions=True,max_jobs=8)
    row=next(x for x in report['results'] if x['plan']['predicate']=='capture_horizon_supported')
    assert row['result']['result']=='unresolved'
    other_root=archive(tmp_path,name='other')
    report_path=other_root/'game-01/report.json'
    different=json.loads(report_path.read_text());different['independent_fixture_episode']='other'
    report_path.write_text(json.dumps(different))
    other=ingest(ds.journal,audit(other_root))
    with pytest.raises(ValueError,match='this investigation'):
        LearningExecutive(ds.journal,g).retain_evidence_request(row['project_id'],ds.journal,[other.id])

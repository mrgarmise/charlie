import json
from pathlib import Path
import pytest
from learning.meditation import consume, qualify_corpus, PlanningCandidate, execute, shadow
from learning.cycle import investigate
from learning.datasets import sha
from learning.deployment import CapabilityDeployment
from test_ala_cycle import make


def finding(ds,tmp_path):
    path=tmp_path/'meditation.json'
    path.write_text(json.dumps(dict(quality={'adjacent':{'mean_error':.5},'gaps':{'mean_error':4.}},
        history=[],merges=[],note='controlled archived fixture')))
    return consume(ds,path,source_episode='meditation-episode',prior_use='diagnostic')


def corpus(ds,tmp_path):
    proof=tmp_path/'external-qualification.txt';proof.write_text('Independent controlled trajectories, not Robotron evidence')
    episodes=[]
    for e in range(4):
        report=tmp_path/f'report-{e}.json';report.write_text(json.dumps({'controlled_episode':e}))
        frames=[]
        for i in range(5):
            capture=tmp_path/f'capture-{e}-{i}.bin';capture.write_bytes(f'external-capture-{e}-{i}'.encode())
            frames.append(dict(timestamp=i*.15,tick=i,player=[20+i,20],
                targets=[dict(id='human',position=[30+i,40])],threats=[],identity_status='independently_verified',
                artifact=dict(path=str(capture),sha256=sha(capture))))
        episodes.append(dict(source_episode='episode:'+sha(report),source_report=dict(path=str(report),sha256=sha(report)),
            partition='validation' if e==0 else 'test',prior_use='unconsulted',frames=frames))
    path=tmp_path/'qualified.json';path.write_text(json.dumps(dict(source_kind='independent_measurement',
        qualification_artifact=dict(path=str(proof),sha256=sha(proof)),episodes=episodes)))
    return path


def test_archived_findings_generate_executable_candidates_but_keep_baseline(tmp_path):
    ds,g=make(tmp_path);source=finding(ds,tmp_path)
    report=investigate(ds,g,diagnostics_only=True,max_jobs=1)
    row=report['results'][0];result=row['result']
    assert row['plan']['method']=='meditation-motion'
    assert row['plan']['source_evidence']==[source.id]
    assert result['baseline_preserved'] and result['operational_proposal'] is None
    assert result['result']=='unresolved' and result['metrics']['qualified_observations']==0
    assert len(result['candidates'])==3
    assert all(PlanningCandidate(c['spec']) for c in result['candidates'])
    assert not any(r.data['payload'].get('category')=='capability_activation' for r in ds.journal.records())
    count=len(ds.journal.records())
    assert execute(row['plan'],ds)['status']=='already_resolved'
    assert len(ds.journal.records())==count
    assert investigate(ds,g,diagnostics_only=True,max_jobs=1)['results']==[]


def test_independent_controlled_loop_guarded_execution_and_rollback(tmp_path):
    ds,g=make(tmp_path);finding(ds,tmp_path);qualify_corpus(ds,corpus(ds,tmp_path),allow_fixture=True)
    row=investigate(ds,g,diagnostics_only=True,max_jobs=1)['results'][0]
    result=row['result'];assert result['result']=='supported'
    assert result['metrics']['fresh_final_evidence']
    assert len(result['metrics']['independence_groups'])==3
    proposal=result['deployment_proposal'];deployment=CapabilityDeployment(ds.journal)
    authorization=dict(target='offline-shadow',proposal_id=proposal,source='explicit controlled offline test')
    with pytest.raises(ValueError,match='authorization'):
        deployment.activate(proposal,target='offline-shadow',authorization=None)
    with pytest.raises(ValueError,match='motion shadow'):
        deployment.activate(proposal,target='offline-shadow',authorization=authorization)
    s=shadow(ds.journal,proposal)
    deployment.activate(proposal,target='offline-shadow',authorization=authorization,shadow_id=s.id)
    assert deployment.planning_adapter() is not None
    # The adapter executes the existing brain and changes a planning position;
    # this is compatibility evidence, never evidence of better physical actions.
    from learning.meditation import world_from_frame
    from experiments.ppal.forebrain import Forebrain
    from experiments.ppal.hindbrain import Hindbrain
    adapter=deployment.planning_adapter();f=Forebrain();h=Hindbrain()
    c=json.loads(corpus(ds,tmp_path).read_text())
    for frame in c['episodes'][0]['frames']:
        intent,action=adapter.decide(world_from_frame(frame),frame['timestamp'],f,h)
        assert action.move and action.fire and intent.kind
    assert s.data['payload']['controller_writes']==0
    deployment.rollback('offline-shadow',reason='controlled rollback',authorization=authorization,to_baseline=True)
    assert deployment.planning_adapter() is None
    with pytest.raises(ValueError,match='revoked'):
        deployment.activate(proposal,target='offline-shadow',authorization=authorization,shadow_id=s.id)
    ds.journal.verify()


@pytest.mark.parametrize('mutation',['model-label','duplicate','changed-frame','prior-use','unverified'])
def test_motion_evidence_gates(tmp_path,mutation):
    ds,g=make(tmp_path);path=corpus(ds,tmp_path);data=json.loads(path.read_text())
    if mutation=='model-label': data['source_kind']='model_prediction'
    if mutation=='duplicate':data['episodes'][1]['frames'][0]['artifact']=data['episodes'][0]['frames'][0]['artifact']
    if mutation=='changed-frame':data['episodes'][1]['frames'][0]['artifact']['sha256']='false'
    if mutation=='prior-use':data['episodes'][1]['prior_use']='train'
    if mutation=='unverified':data['episodes'][1]['frames'][0]['identity_status']='provisional'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):qualify_corpus(ds,path,allow_fixture=True)


def test_motion_crash_consumes_final_once_and_abstains(tmp_path,monkeypatch):
    ds,g=make(tmp_path);finding(ds,tmp_path);qualify_corpus(ds,corpus(ds,tmp_path),allow_fixture=True)
    import learning.meditation as m
    original=m.motion_error
    def fail_final(spec,episodes):
        if episodes[0]['partition']=='test':raise InterruptedError()
        return original(spec,episodes)
    monkeypatch.setattr(m,'motion_error',fail_final)
    with pytest.raises(InterruptedError):investigate(ds,g,diagnostics_only=True,max_jobs=1)
    plan=next(r.data['payload']['plan'] for r in ds.journal.records('event') if r.data['payload'].get('category')=='offline_experiment_plan')
    monkeypatch.setattr(m,'motion_error',lambda *a: (_ for _ in ()).throw(AssertionError('re-evaluated final')))
    result=execute(plan,ds)
    assert result['result']=='unresolved' and 'already consulted' in result['reason']


def test_published_final_episode_cannot_be_renamed_into_new_root(tmp_path):
    ds,g=make(tmp_path);path=corpus(ds,tmp_path);data=json.loads(path.read_text())
    data['episodes'][1]['source_episode']='episode:d3ab93c8fed5349ec783987b1b09890fe3c5378ef28f8d54e3bc2166551812da'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='report bytes'):qualify_corpus(ds,path,allow_fixture=True)


def test_boot_change_abstains_before_any_candidate_evaluation(tmp_path,monkeypatch):
    ds,g=make(tmp_path);finding(ds,tmp_path)
    from learning.meditation import reflect
    from learning.capabilities import default_registry
    from memory.learning_projects import LearningExecutive
    from experiments.ppal.experiment_return import select_offline_experiment
    e=LearningExecutive(ds.journal,g)
    item=reflect(ds,g,default_registry())[0]
    pid=e.propose(item['proposal'],ds.journal,[item['evidence_id']])
    e.select(methods={'meditation-motion'},resources={'offline-slot','meditation-evidence'},
             authorized_methods={'meditation-motion'})
    plan=select_offline_experiment(g,ds.journal,e.chooser_context(pid),budget_seconds=60)
    monkeypatch.setattr('learning.clock.domain',lambda:'other-boot')
    result=execute(plan,ds)
    assert result['result']=='unresolved' and result['metrics']['clock_continuity']=='UNKNOWN'
    assert execute(plan,ds)['result']=='unresolved'
    assert not list((tmp_path/'models').glob('**/*.json'))


@pytest.mark.parametrize('mutation',['boolean-time','negative-time','boolean-position','reused-frame'])
def test_motion_measurement_types_and_within_episode_duplicate_rejected(tmp_path,mutation):
    ds,g=make(tmp_path);path=corpus(ds,tmp_path);data=json.loads(path.read_text())
    frames=data['episodes'][0]['frames']
    if mutation=='boolean-time':frames[0]['timestamp']=False
    if mutation=='negative-time':frames[0]['timestamp']=-1
    if mutation=='boolean-position':frames[0]['player'][0]=True
    if mutation=='reused-frame':frames[1]['artifact']=frames[0]['artifact']
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):qualify_corpus(ds,path,allow_fixture=True)

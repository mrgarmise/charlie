"""Controlled software qualification. Synthetic frames never certify Robotron accuracy."""
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PIL import Image
import pytest
from memory.evidence import EvidenceJournal
from memory.learning_projects import LearningExecutive
from learning.model_learning.service import ModelLearningService
from learning.model_learning.contracts import TrainingProposal
from learning.model_learning.data import LABELS,sha
from learning.model_learning.robotron import import_fixtures,predict,localization_annotation
from learning.model_learning.subscriber import ShadowSubscriber
from learning.model_learning.deployment import approve
from learning.deployment import CapabilityDeployment

REPO=Path(__file__).resolve().parents[1]

@pytest.fixture
def setup(tmp_path):
    journal=EvidenceJournal(tmp_path/'journal.sqlite3')
    memories=[]
    executive=LearningExecutive(journal,SimpleNamespace(remember=memories.append))
    service=ModelLearningService(journal,tmp_path/'learning',allow_synthetic=True)
    yield service,executive,memories
    journal.close()


def corpus(service,root):
    rng=np.random.default_rng(21)
    for split in ('train','validation','test'):
        for label,color in [('title_menu',[160,20,20]),('gameplay',[20,160,20]),('terminal',[20,20,160])]:
            pixels=np.clip(np.array(color)+rng.integers(-35,36,(12,16,3)),0,255).astype('uint8')
            path=root/(split+'-'+label+'.png');Image.fromarray(pixels).resize((640,480)).save(path)
            row=service.data.add(path,session=split,provenance={'fixture':'synthetic-only'},authentic=False,partition=split)
            service.data.label(row.id,label,reviewer='controlled-test',reason='synthetic generator label')
    path=root/'unknown.png';Image.fromarray(rng.integers(0,3,(480,640,3),dtype='uint8')).save(path)
    row=service.data.add(path,session='test',provenance={'fixture':'synthetic-only'},authentic=False,partition='test')
    service.data.label(row.id,'unknown',reviewer='controlled-test',reason='synthetic blank OOD')


def test_authentic_intake_defers_and_restart_is_idempotent(setup):
    service,e,memories=setup
    import_fixtures(service.data,REPO)
    assert service.data.inspect()['counts']==dict(total=6,authentic=6,labeled=5,sessions=3)
    result=e.consider_model_learning(service)
    assert result['status']=='NEEDS_LABELS'
    assert not service.data.events('model_proposal')
    assert service.data.events('model_need') and memories
    count=len(service.journal.records())
    assert LearningExecutive(service.journal,e.gateway).consider_model_learning(service)==result
    assert len(service.journal.records())==count
    assert service.active() is None


def test_no_evidence_no_training(setup):
    service,e,_=setup
    assert e.consider_model_learning(service)['status']=='NO_NEED'
    assert not e.projects()


def test_real_worker_e2e_synthetic_rejected_and_persisted(setup,tmp_path):
    service,e,memories=setup;corpus(service,tmp_path)
    assert service.data.inspect(allow_synthetic=True)['status']=='READY'
    result=e.consider_model_learning(service)
    assert result['status']=='REJECTED',result
    candidate=service.candidate(result['candidate_id'])
    card=json.loads((Path(candidate['artifact']).parent/'model-card.json').read_text())
    assert card['metrics']['candidate']['accuracy']==1
    assert card['metrics']['authentic'] is False
    usage=card['metrics']['resources']['worker']
    assert usage['cpu_limit_seconds']==5 and usage['address_space_limit_bytes']==512*1024**2
    assert usage['cpu_seconds']<5 and usage['peak_rss_kib']>0
    assert 'synthetic plumbing only' in card['decision']['reasons']
    assert card['metrics']['incumbent']['macro_recall']<=1
    assert candidate['mode']=='shadow' and service.active() is None
    assert memories
    count=len(service.data.events('model_proposal'))
    assert e.consider_model_learning(service)==result
    assert len(service.data.events('model_proposal'))==count==1
    service.journal.verify()


def test_missing_review_supersession_and_partition_integrity(setup,tmp_path):
    service,e,_=setup;import_fixtures(service.data,REPO)
    row=service.data.rows()[0];old=row['label_id']
    with pytest.raises(ValueError,match='supersession'):
        service.data.label(row['observation_id'],'unknown',reviewer='a',reason='uncertain')
    service.data.label(row['observation_id'],'unknown',reviewer='a',reason='uncertain',supersedes=old)
    assert service.data.rows()[0]['label']=='unknown'
    assert service.journal.get(old).data['payload']['label']=='title_menu'
    service.data.partition(row['session'],'train',reviewer='a')
    assert {r['effective_partition'] for r in service.data.rows() if r['session']==row['session']}=={'train'}
    with pytest.raises(ValueError,match='NEEDS_LABELS'): service.data.freeze()


def test_pixel_dedup_different_encoding_and_session_rejection(setup,tmp_path):
    service,_,_=setup
    path=REPO/'tests/fixtures/robotron-screen-states/terminal.jpg'
    a=service.data.add(path,session='one',provenance={'source':'fixture'},authentic=True,partition='train')
    recoded=tmp_path/'same.png';Image.open(path).save(recoded)
    assert service.data.add(recoded,session='one',provenance={'source':'recode'},authentic=True,partition='train').id==a.id
    with pytest.raises(ValueError,match='ownership'):
        service.data.add(recoded,session='two',provenance={'source':'recode'},authentic=True,partition='test')


def test_near_duplicate_leakage_fails_closed(setup,tmp_path):
    service,_,_=setup;corpus(service,tmp_path)
    row=service.data.rows()[0]
    image=Image.open(row['path']);pixels=np.array(image);pixels[0,0,0]^=1
    path=tmp_path/'almost.png';Image.fromarray(pixels).save(path)
    duplicate=service.data.add(path,session='new',provenance={'synthetic':'near duplicate'},authentic=False,partition='test')
    service.data.label(duplicate.id,row['label'],reviewer='test',reason='synthetic')
    report=service.data.inspect(allow_synthetic=True)
    assert 'session or near-duplicate leakage across partitions' in report['issues']


def test_tampered_frame_rejected(setup):
    service,_,_=setup;import_fixtures(service.data,REPO)
    path=Path(service.data.rows()[0]['path']);path.chmod(0o644);path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='integrity'):service.data.inspect()


@pytest.mark.parametrize('field,value',[('wall_seconds',float('nan')),('wall_seconds',100),('memory_mb',0),('cpu_seconds',True),('disk_mb',100),('max_frames',2000)])
def test_resource_contract_rejects_unbounded(field,value):
    with pytest.raises(ValueError):TrainingProposal('need','dataset',**{field:value})


def test_frame_budget_and_cancellation(setup,tmp_path):
    service,_,_=setup;corpus(service,tmp_path);snapshot=service.data.freeze(allow_synthetic=True)
    with pytest.raises(ValueError,match='frame budget'):
        service._worker(TrainingProposal('n',snapshot.id,max_frames=3),snapshot,None)
    def cancel():raise InterruptedError('application shutdown')
    with pytest.raises(InterruptedError,match='shutdown'):
        service._worker(TrainingProposal('n',snapshot.id),snapshot,cancel)
    assert not list(service.root.glob('training-*'))


def test_wall_timeout(setup,tmp_path):
    service,_,_=setup;corpus(service,tmp_path);snapshot=service.data.freeze(allow_synthetic=True)
    # A deterministic fake clock forces the real process to be killed before work.
    from unittest.mock import patch
    with patch('learning.model_learning.service.time.monotonic',side_effect=[0.,100.]):
        with pytest.raises(InterruptedError,match='wall budget'):
            service._worker(TrainingProposal('n',snapshot.id),snapshot,None)
    assert not list(service.root.glob('training-*'))


def test_worker_does_not_receive_test_rows(setup,tmp_path,monkeypatch):
    service,_,_=setup;corpus(service,tmp_path);snapshot=service.data.freeze(allow_synthetic=True)
    import learning.model_learning.service as module
    original=module.subprocess.Popen
    def inspected(args,**kwargs):
        config=json.loads(Path(args[-1]).read_text())
        assert all(r['partition']!='test' for r in config['dataset']['rows'])
        assert not any(r['label']=='unknown' for r in config['dataset']['rows'])
        return original(args,**kwargs)
    monkeypatch.setattr(module.subprocess,'Popen',inspected)
    artifact=service._worker(TrainingProposal('n',snapshot.id),snapshot,None)
    assert artifact.exists()


def test_no_training_without_executive_selection(setup,tmp_path):
    service,_,_=setup;corpus(service,tmp_path);snapshot=service.data.freeze(allow_synthetic=True)
    need=service.data.append('model_need',{'need':{'reason':'controlled'}})
    with pytest.raises(ValueError,match='Executive selection'):service.train(need.id,snapshot.id)


def test_unknown_and_no_coordinates():
    model=dict(preprocessing='rgb-spatial-16x12-v1',runtime='numpy-cpu-json-v1',radius=.2,margin=.01,
        centroids={'title_menu':[.2]*576,'gameplay':[.5]*576,'terminal':[.8]*576})
    assert predict(model,Image.new('RGB',(640,480),'black'))['label']=='unknown'
    assert not any(k in predict(model,Image.new('RGB',(640,480),'black')) for k in ('x','y','box'))
    with pytest.raises(ValueError):localization_annotation(frame_sha256='f',session='s',reviewer='r',objects=[dict(**{'class':'player'},box=[0,0,2,1],uncertainty=.5)])


def test_approval_rejects_synthetic_and_subscriber_continuity(setup,tmp_path):
    service,e,_=setup;corpus(service,tmp_path);result=e.consider_model_learning(service)
    with pytest.raises(ValueError,match='qualified'):
        approve(service,result['qualification_id'],operator='human',reason='review')
    subscription=ShadowSubscriber(service,result['candidate_id'])
    row=service.data.rows()[0]
    assert subscription.consume(row['observation_id'])['status']=='shadow'
    artifact=Path(service.candidate(result['candidate_id'])['artifact']);artifact.chmod(0o644);artifact.write_text('{}')
    assert subscription.consume(row['observation_id'])['prediction']['label']=='unknown'
    assert service.active() is None


def controlled_qualification(service,candidate_id):
    """SIMULATED gate records to test transactions, never an accuracy receipt."""
    metrics=dict(authentic=True,fresh_holdout=True,test_observations=[],simulation=True,
        candidate=dict(macro_recall=1.,per_class={k:dict(recall=1.,support=5) for k in LABELS}),
        incumbent=dict(macro_recall=.5),non_ml_majority=dict(macro_recall=.25),latency_ms=dict(maximum=1.))
    evaluation=service.data.append('model_evaluation',dict(candidate_id=candidate_id,
        metrics=metrics),producer='independent-model-evaluator')
    return service.data.append('model_qualification',dict(decision=dict(accepted=True,candidate_id=candidate_id,
        evaluation_id=evaluation.id,reasons=[],approval='required'),gates=service.gates,simulation=True),sources=[evaluation.id])



def test_versioned_activation_rollback_and_revoked_grant(setup,tmp_path):
    service,e,_=setup;corpus(service,tmp_path);result=e.consider_model_learning(service)
    deployment=CapabilityDeployment(service.journal)
    with pytest.raises(ValueError):deployment.activate_perception_shadow(service,result['candidate_id'])
    q=controlled_qualification(service,result['candidate_id'])
    question=service.data.append('human_interaction',dict(op='queued',simulation=True),producer='HumanInteractionGateway')
    service.data.append('model_gateway_link',dict(question_id=question.id,kind='approval',source_id=q.id),sources=[question.id,q.id])
    answer=service.data.append('human_interaction',dict(op='answer',question_id=question.id,value='approve_shadow',operator='controlled-human',simulation=True),sources=[question.id],producer='HumanInteractionGateway')
    grant=approve(service,q.id,operator='controlled-human',reason='SIMULATED approval test',answer_id=answer.id,reviewer='controlled-independent-reviewer')
    first=deployment.activate_perception_shadow(service,grant.id)
    assert deployment.activate_perception_shadow(service,grant.id).id==first.id
    assert service.active()['mode']=='shadow'
    # The subscriber is independent of version-pointer changes.
    subscription=ShadowSubscriber(service,result['candidate_id'])
    deployment.rollback_perception_shadow(service,operator='controlled-human',reason='SIMULATED monitor regression')
    assert service.active()['candidate_id'] is None
    assert subscription.consume(service.data.rows()[0]['observation_id'])['status']=='shadow'
    with pytest.raises(ValueError,match='revoked'):deployment.activate_perception_shadow(service,grant.id)
    service.journal.verify()


def test_normal_application_opt_in_parser():
    import main
    assert main.parser().parse_args([]).model_learning is False
    assert main.parser().parse_args(['--model-learning']).model_learning is True


def test_real_application_executes_need_and_preserves_status(tmp_path):
    from learning.lifecycle import DevelopmentLifecycle
    state=tmp_path/'application'
    lifecycle=DevelopmentLifecycle(state,[],budget_seconds=2.,model_learning=True)
    try:
        import_fixtures(lifecycle.model_learning.data,REPO)
        assert lifecycle.turn() is True
        lifecycle._status()
        status=json.loads((state/'development-status.json').read_text())
        assert status['model_learning_result']['status']=='NEEDS_LABELS'
        assert status['model_learning']['activation'] is None
        assert status['physical_authorization'] is False
    finally:lifecycle.close()


def test_recover_completed_training_without_retraining(setup,tmp_path,monkeypatch):
    service,e,_=setup;corpus(service,tmp_path)
    original=service._worker
    class SimulatedCrash(BaseException):pass
    def crash_after_receipt(*args,**kwargs):
        original(*args,**kwargs)
        raise SimulatedCrash()
    monkeypatch.setattr(service,'_worker',crash_after_receipt)
    with pytest.raises(SimulatedCrash):e.consider_model_learning(service)
    assert len(service.data.events('model_proposal'))==1
    recovered=ModelLearningService(service.journal,service.root,allow_synthetic=True)
    result=e.consider_model_learning(recovered)
    assert result['status']=='REJECTED'
    assert len(service.data.events('model_proposal'))==1
    assert len(service.data.events('model_candidate'))==1
    assert len(service.data.events('model_evaluation'))==1


def test_question_outbox_asks_unresolved_labels_only(setup):
    service,e,_=setup;import_fixtures(service.data,REPO)
    e.consider_model_learning(service)
    from learning.model_learning.questions import review_requests
    requests=review_requests(service)
    assert len(requests)==1
    assert requests[0]['status']=='pending-adapter'
    assert requests[0]['approval_authority'] is False
    assert review_requests(service)==requests


def test_retired_evidence_retains_immutable_lineage(setup):
    service,_,_=setup;import_fixtures(service.data,REPO)
    row=service.data.rows()[0]
    service.data.exclude(row['observation_id'],reviewer='operator',reason='retire biased historical diagnostic frame')
    assert len(service.data.rows())==5
    assert service.journal.get(row['observation_id']).data['payload']['sha256']==row['sha256']


def test_user_gate_configuration_and_model_validation(setup):
    from learning.model_learning.qualification import gates
    assert gates({'min_test_per_class':12})['min_test_per_class']==12
    for value in ({'min_macro_recall':float('nan')},{'unknown_key':1},{'min_test_per_class':True}):
        with pytest.raises(ValueError):gates(value)
    with pytest.raises(ValueError,match='label schema'):
        predict(dict(preprocessing='rgb-spatial-16x12-v1',runtime='numpy-cpu-json-v1',centroids={'x':[]}),Image.new('RGB',(40,40)))


def test_rollback_restores_previous_known_good_version(setup,tmp_path):
    service,e,_=setup;corpus(service,tmp_path);result=e.consider_model_learning(service)
    deployment=CapabilityDeployment(service.journal)
    def simulated_grant(candidate):
        qualification=controlled_qualification(service,candidate)
        question=service.data.append('human_interaction',dict(op='queued',candidate=candidate,simulation=True),producer='HumanInteractionGateway')
        service.data.append('model_gateway_link',dict(question_id=question.id,kind='approval',source_id=qualification.id),sources=[question.id,qualification.id])
        answer=service.data.append('human_interaction',dict(op='answer',question_id=question.id,value='approve_shadow',operator='controlled-human',simulation=True),sources=[question.id],producer='HumanInteractionGateway')
        return approve(service,qualification.id,operator='controlled-human',reason='SIMULATED version test',answer_id=answer.id,reviewer='controlled-reviewer')
    first=deployment.activate_perception_shadow(service,simulated_grant(result['candidate_id']).id)
    old=dict(service.candidate(result['candidate_id']))
    original=json.loads(Path(old['artifact']).read_text());original['radius']*=.99
    alternate=tmp_path/'controlled-alternate-model.json';alternate.write_text(json.dumps(original))
    old.update(artifact=str(alternate),sha256=sha(alternate))
    candidate=service.data.append('model_candidate',dict(candidate=old,simulation=True),sources=[result['candidate_id']])
    second=deployment.activate_perception_shadow(service,simulated_grant(candidate.id).id)
    assert second.data['payload']['previous_activation']==first.data['payload']['activation_key']
    assert service.active()['candidate_id']==candidate.id
    deployment.rollback_perception_shadow(service,operator='controlled-human',reason='SIMULATED candidate drift')
    assert service.active()['candidate_id']==result['candidate_id']
